from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from app.auth import company_user_required
from datetime import datetime

company_user_bp = Blueprint('company_user', __name__, url_prefix='/company')


def calculate_current_period(report_type):
    """Вычисление текущего периода (та же логика что у клиента)"""
    today = datetime.today()
    if report_type == 'gündelik':
        return today.strftime('%Y-%m-%d')
    elif report_type == 'hepdeleýin':
        year, week, _ = today.isocalendar()
        return f"{year}-W{week:02d}"
    elif report_type == 'aýlyk':
        return today.strftime('%Y-%m')
    elif report_type == 'çärýeklik':
        quarter = (today.month - 1) // 3 + 1
        return f"{today.year}-Q{quarter}"
    elif report_type == 'ýyllyk':
        return str(today.year)
    return today.strftime('%Y-%m-%d')



@company_user_bp.route('/programs')
@company_user_required
def programs():
    from app import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.order_number,
                p.order_date,
                p.start_date,
                p.end_date,
                p.status,
                -- Всего организаций × мероприятий за текущий период
                (
                    SELECT COUNT(DISTINCT eo.organization_id)
                    FROM events e2
                    JOIN event_organizations eo ON e2.id = eo.event_id
                    WHERE e2.program_id = p.id AND e2.status = 'active'
                ) as total_orgs_events,
                -- under_review
                (
                    SELECT COUNT(*)
                    FROM reports r
                    JOIN events e2 ON r.event_id = e2.id
                    JOIN report_submissions rs ON r.id = rs.report_id
                    WHERE e2.program_id = p.id AND rs.review_status = 'under_review'
                ) as cnt_under_review,
                -- returned
                (
                    SELECT COUNT(*)
                    FROM reports r
                    JOIN events e2 ON r.event_id = e2.id
                    JOIN report_submissions rs ON r.id = rs.report_id
                    WHERE e2.program_id = p.id AND rs.review_status = 'returned'
                ) as cnt_returned,
                -- accepted
                (
                    SELECT COUNT(*)
                    FROM reports r
                    JOIN events e2 ON r.event_id = e2.id
                    JOIN report_submissions rs ON r.id = rs.report_id
                    WHERE e2.program_id = p.id AND rs.review_status = 'accepted'
                ) as cnt_accepted
            FROM programs p
            WHERE p.status = 'active'
            ORDER BY p.name ASC
        """)
        programs_list = cursor.fetchall()
    conn.close()
    return render_template('company_user/programs.html', programs=programs_list)



@company_user_bp.route('/programs/<int:program_id>/events')
@company_user_required
def program_events(program_id):
    from app import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Загружаем программу
        cursor.execute("SELECT * FROM programs WHERE id = %s", (program_id,))
        program = cursor.fetchone()

    if not program:
        flash('Maksatnama tapylmady.', 'danger')
        conn.close()
        return redirect(url_for('company_user.programs'))

    with conn.cursor() as cursor:
        # Тип отчёта у программы
        cursor.execute("""
            SELECT id, report_type FROM program_reports
            WHERE program_id = %s AND status = 'active'
            LIMIT 1
        """, (program_id,))
        pr = cursor.fetchone()

    report_type = pr['report_type'] if pr else None
    current_period = calculate_current_period(report_type) if report_type else None

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                e.id,
                e.item_number,
                e.name as event_name,
                e.deadline,
                e.status,
                -- Всего организаций
                (
                    SELECT COUNT(*)
                    FROM event_organizations eo2
                    WHERE eo2.event_id = e.id
                ) as total_orgs,
                -- Сдавших отчёт за текущий период
                (
                    SELECT COUNT(*)
                    FROM reports r2
                    WHERE r2.event_id = e.id AND r2.report_period = %s
                ) as submitted,
                -- under_review (все периоды — pending нельзя пропускать)
                (
                    SELECT COUNT(*)
                    FROM reports r2
                    JOIN report_submissions rs2 ON r2.id = rs2.report_id
                    WHERE r2.event_id = e.id
                      AND rs2.review_status = 'under_review'
                ) as cnt_under_review,
                -- returned (все периоды)
                (
                    SELECT COUNT(*)
                    FROM reports r2
                    JOIN report_submissions rs2 ON r2.id = rs2.report_id
                    WHERE r2.event_id = e.id
                      AND rs2.review_status = 'returned'
                ) as cnt_returned,
                -- accepted (все периоды)
                (
                    SELECT COUNT(*)
                    FROM reports r2
                    JOIN report_submissions rs2 ON r2.id = rs2.report_id
                    WHERE r2.event_id = e.id
                      AND rs2.review_status = 'accepted'
                ) as cnt_accepted
            FROM events e
            WHERE e.program_id = %s AND e.status = 'active'
            ORDER BY e.item_number ASC
        """, (current_period, program_id))
        events = cursor.fetchall()

    conn.close()
    return render_template('company_user/events.html',
                           program=program,
                           events=events,
                           current_period=current_period,
                           report_type=report_type)



@company_user_bp.route('/events/<int:event_id>/reports')
@company_user_required
def event_reports(event_id):
    from app import get_db_connection
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT e.*, p.name as program_name,
                   pr.report_type, pr.id as program_report_id
            FROM events e
            JOIN programs p ON e.program_id = p.id
            LEFT JOIN program_reports pr ON p.id = pr.program_id AND pr.status = 'active'
            WHERE e.id = %s
        """, (event_id,))
        event = cursor.fetchone()

    if not event:
        flash('Çäre tapylmady.', 'danger')
        conn.close()
        return redirect(url_for('company_user.programs'))

    current_period = calculate_current_period(event['report_type']) if event['report_type'] else None

    with conn.cursor() as cursor:
        # Для каждой организации берём наиболее актуальный отчёт:
        # 1) pending (under_review / returned) с любого периода
        # 2) если pending нет — отчёт текущего периода (accepted)
        # 3) если ничего нет — NULL (не сдан)
        cursor.execute("""
            SELECT
                o.id as org_id,
                o.name as org_name,
                o.address,
                ci.name as city_name,
                di.name as district_name,
                r.id as report_id,
                r.report_period,
                r.description,
                r.created_at as submitted_at,
                es.name as status_name,
                rs.review_status
            FROM event_organizations eo
            JOIN organizations o ON eo.organization_id = o.id
            LEFT JOIN cities ci ON o.city_id = ci.id
            LEFT JOIN districts di ON o.district_id = di.id
            LEFT JOIN reports r ON r.id = (
                SELECT r2.id
                FROM reports r2
                LEFT JOIN report_submissions rs2 ON r2.id = rs2.report_id
                WHERE r2.event_id = eo.event_id
                  AND r2.organization_id = eo.organization_id
                ORDER BY
                    -- pending-отчёты всплывают первыми (0 = pending, 1 = остальное)
                    CASE
                        WHEN COALESCE(rs2.review_status, 'under_review')
                             IN ('under_review', 'returned') THEN 0
                        ELSE 1
                    END ASC,
                    r2.created_at DESC
                LIMIT 1
            )
            LEFT JOIN event_statuses es ON r.status_id = es.id
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            WHERE eo.event_id = %s
            ORDER BY
                -- pending сверху, потом принятые, потом не сдавшие
                CASE
                    WHEN rs.review_status = 'under_review' THEN 0
                    WHEN rs.review_status = 'returned'     THEN 1
                    WHEN rs.review_status = 'accepted'     THEN 2
                    ELSE 3
                END ASC,
                o.name ASC
        """, (event_id,))
        orgs = cursor.fetchall()

    conn.close()
    return render_template('company_user/event_reports.html',
                           event=event,
                           orgs=orgs,
                           current_period=current_period)



@company_user_bp.route('/reports/<int:report_id>')
@company_user_required
def report_detail(report_id):
    from app import get_db_connection
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                r.*,
                o.name as org_name,
                o.address as org_address,
                ci.name as city_name,
                di.name as district_name,
                e.name as event_name,
                e.item_number,
                e.deadline,
                p.name as program_name,
                pr.report_type,
                es.name as status_name,
                fr.name as failure_reason_name,
                COALESCE(rs.review_status, 'under_review') as review_status,
                u.full_name as created_by_name
            FROM reports r
            JOIN organizations o ON r.organization_id = o.id
            LEFT JOIN cities ci ON o.city_id = ci.id
            LEFT JOIN districts di ON o.district_id = di.id
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON r.program_report_id = pr.id
            LEFT JOIN event_statuses es ON r.status_id = es.id
            LEFT JOIN failure_reasons fr ON r.failure_reason_id = fr.id
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            LEFT JOIN users u ON r.created_user_id = u.id
            WHERE r.id = %s
        """, (report_id,))
        report = cursor.fetchone()

    if not report:
        flash('Hasabat tapylmady.', 'danger')
        conn.close()
        return redirect(url_for('company_user.programs'))

    with conn.cursor() as cursor:
        # История проверок
        cursor.execute("""
            SELECT h.*, u.full_name as reviewer_name
            FROM report_review_history h
            LEFT JOIN users u ON h.changed_by = u.id
            WHERE h.report_id = %s
            ORDER BY h.created_at ASC
        """, (report_id,))
        history = cursor.fetchall()

        # Файлы
        cursor.execute("""
            SELECT * FROM report_files
            WHERE report_id = %s
            ORDER BY file_type, created_at ASC
        """, (report_id,))
        files = cursor.fetchall()

    conn.close()
    return render_template('company_user/report_detail.html',
                           report=report,
                           history=history,
                           files=files)




@company_user_bp.route('/reports/<int:report_id>/accept', methods=['POST'])
@company_user_required
def accept_report(report_id):
    from app import get_db_connection
    user_id = session.get('user_id')
    comment = request.form.get('comment', '').strip() or None

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Проверяем что отчёт существует и статус = under_review
            cursor.execute("""
                SELECT rs.review_status FROM report_submissions rs
                WHERE rs.report_id = %s
            """, (report_id,))
            sub = cursor.fetchone()

        if not sub:
            flash('Hasabat tapylmady ýa-da entek tabşyrylmadyk.', 'danger')
            conn.close()
            return redirect(url_for('company_user.programs'))

        if sub['review_status'] not in ('under_review',):
            flash('Bu hasabat eýýäm kabul edildi ýa-da gözden geçirilýär.', 'warning')
            conn.close()
            return redirect(url_for('company_user.report_detail', report_id=report_id))

        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE report_submissions
                SET review_status = 'accepted'
                WHERE report_id = %s
            """, (report_id,))

            cursor.execute("""
                INSERT INTO report_review_history
                    (report_id, review_status, reviewer_comment, changed_by)
                VALUES (%s, 'accepted', %s, %s)
            """, (report_id, comment, user_id))

        conn.commit()
        flash('Hasabat kabul edildi!', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Ýalňyşlyk ýüze çykdy: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('company_user.report_detail', report_id=report_id))



@company_user_bp.route('/reports/<int:report_id>/return', methods=['POST'])
@company_user_required
def return_report(report_id):
    from app import get_db_connection
    user_id = session.get('user_id')
    comment = request.form.get('comment', '').strip()

    if not comment:
        flash('Hasabaty yzyna gaýtarmak üçin düşündiriş hökman gerek.', 'danger')
        return redirect(url_for('company_user.report_detail', report_id=report_id))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT rs.review_status FROM report_submissions rs
                WHERE rs.report_id = %s
            """, (report_id,))
            sub = cursor.fetchone()

        if not sub:
            flash('Hasabat tapylmady ýa-da entek tabşyrylmadyk.', 'danger')
            conn.close()
            return redirect(url_for('company_user.programs'))

        if sub['review_status'] != 'under_review':
            flash('Bu hasabaty yzyna gaýtarmak bolmaýar.', 'warning')
            conn.close()
            return redirect(url_for('company_user.report_detail', report_id=report_id))

        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE report_submissions
                SET review_status = 'returned'
                WHERE report_id = %s
            """, (report_id,))

            cursor.execute("""
                INSERT INTO report_review_history
                    (report_id, review_status, reviewer_comment, changed_by)
                VALUES (%s, 'returned', %s, %s)
            """, (report_id, comment, user_id))

        conn.commit()
        flash('Hasabat düzetmek üçin yzyna gaýtaryldy.', 'warning')

    except Exception as e:
        conn.rollback()
        flash(f'Ýalňyşlyk ýüze çykdy: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('company_user.report_detail', report_id=report_id))



@company_user_bp.route('/all-reports')
@company_user_required
def all_reports():
    from app import get_db_connection
    conn = get_db_connection()

    # Filters
    program_id = request.args.get('program_id', '')
    organization_id = request.args.get('organization_id', '')
    period = request.args.get('period', '').strip()
    review_status = request.args.get('review_status', '')

    with conn.cursor() as cursor:
        # Get active programs for dropdown
        cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
        programs_list = cursor.fetchall()

        # Get active organizations for dropdown
        cursor.execute("SELECT id, name FROM organizations WHERE status = 'active' ORDER BY name ASC")
        orgs_list = cursor.fetchall()

        # Build dynamic query for reports
        query = """
            SELECT
                r.id as report_id,
                r.report_period,
                r.created_at as submitted_at,
                o.name as org_name,
                p.name as program_name,
                e.item_number,
                e.name as event_name,
                es.name as status_name,
                COALESCE(rs.review_status, 'under_review') as review_status
            FROM reports r
            JOIN organizations o ON r.organization_id = o.id
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            LEFT JOIN event_statuses es ON r.status_id = es.id
            WHERE 1=1
        """
        params = []

        if program_id and program_id.isdigit():
            query += " AND p.id = %s"
            params.append(int(program_id))

        if organization_id and organization_id.isdigit():
            query += " AND o.id = %s"
            params.append(int(organization_id))

        if period:
            query += " AND r.report_period LIKE %s"
            params.append(f"%{period}%")

        if review_status in ('under_review', 'returned', 'accepted'):
            if review_status == 'under_review':
                query += " AND COALESCE(rs.review_status, 'under_review') = 'under_review'"
            else:
                query += " AND rs.review_status = %s"
                params.append(review_status)

        query += """
            ORDER BY
                CASE
                    WHEN COALESCE(rs.review_status, 'under_review') = 'under_review' THEN 0
                    WHEN rs.review_status = 'returned' THEN 1
                    WHEN rs.review_status = 'accepted' THEN 2
                    ELSE 3
                END ASC,
                r.created_at DESC
            LIMIT 1000
        """

        cursor.execute(query, tuple(params))
        reports_list = cursor.fetchall()

    conn.close()

    return render_template('company_user/all_reports.html',
                           reports=reports_list,
                           programs=programs_list,
                           organizations=orgs_list,
                           selected_program=program_id,
                           selected_org=organization_id,
                           selected_period=period,
                           selected_status=review_status)


# ----------------------------------------------------------------------------
# HASABATLAR (графические отчёты)
# ----------------------------------------------------------------------------

# Подсчёт отчётов по статусам проверки. Отсутствие строки в
# report_submissions трактуем как 'under_review' (отчёт подан, но не проверен).
# Guard `r.id IS NOT NULL` нужен из-за LEFT JOIN: строки без отчёта не должны
# попадать в under_review (иначе COALESCE на NULL даст ложный +1).
_STATUS_COUNTS_SQL = """
    SUM(CASE WHEN r.id IS NOT NULL
             AND COALESCE(rs.review_status, 'under_review') = 'under_review'
             THEN 1 ELSE 0 END) AS cnt_under_review,
    SUM(CASE WHEN rs.review_status = 'returned' THEN 1 ELSE 0 END) AS cnt_returned,
    SUM(CASE WHEN rs.review_status = 'accepted' THEN 1 ELSE 0 END) AS cnt_accepted,
    COUNT(r.id) AS total
"""


def _pivot_execution(flat, statuses, label_attr):
    """Сворачивает плоские строки (group_id, ..., status_id, cnt) в строки по
    группам со словарём counts[status_id] и строит структуру для графика.

    Статусы (event_statuses) динамические, поэтому колонки/серии строятся по
    переданному списку `statuses`. Возвращает (rows, chart, totals).
    """
    grouped = {}
    order = []
    for f in flat:
        gid = f['group_id']
        if gid not in grouped:
            grouped[gid] = {**f, 'counts': {}, 'total': 0}
            order.append(gid)
        grouped[gid]['counts'][f['status_id']] = f['cnt']
        grouped[gid]['total'] += f['cnt']

    rows = [grouped[gid] for gid in order]

    chart = {
        'labels': [str(r[label_attr]) for r in rows],
        'series': [
            {'name': s['name'],
             'data': [r['counts'].get(s['id'], 0) for r in rows]}
            for s in statuses
        ],
    }

    totals = {s['id']: sum(r['counts'].get(s['id'], 0) for r in rows) for s in statuses}
    totals['total'] = sum(r['total'] for r in rows)
    totals['groups'] = len(rows)

    return rows, chart, totals


@company_user_bp.route('/reports/by-program')
@company_user_required
def report_by_program():
    """Общий отчёт по программам (графики)."""
    from app import get_db_connection
    conn = get_db_connection()

    period = request.args.get('period', '').strip()
    # Период фильтруется в ON-условии reports, чтобы программы без отчётов
    # в этом периоде всё равно отображались (с нулями).
    join_period = ""
    params = []
    if period:
        join_period = " AND r.report_period LIKE %s"
        params.append(f"%{period}%")

    with conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT
                p.id,
                p.name,
                {_STATUS_COUNTS_SQL}
            FROM programs p
            LEFT JOIN events e ON e.program_id = p.id
            LEFT JOIN reports r ON r.event_id = e.id{join_period}
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            WHERE p.status = 'active'
            GROUP BY p.id, p.name
            ORDER BY p.name ASC
        """, tuple(params))
        rows = cursor.fetchall()
    conn.close()

    totals = {
        'under_review': sum(r['cnt_under_review'] for r in rows),
        'returned': sum(r['cnt_returned'] for r in rows),
        'accepted': sum(r['cnt_accepted'] for r in rows),
        'total': sum(r['total'] for r in rows),
        'programs': len(rows),
    }

    return render_template('company_user/report_by_program.html',
                           rows=rows,
                           totals=totals,
                           selected_period=period)


@company_user_bp.route('/reports/by-organization')
@company_user_required
def report_by_organization():
    """Отчёт по организациям (с фильтром по программе)."""
    from app import get_db_connection
    conn = get_db_connection()

    program_id = request.args.get('program_id', '')
    period = request.args.get('period', '').strip()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
        programs_list = cursor.fetchall()

        # Отталкиваемся от event_organizations — это организации, которые ОБЯЗАНЫ
        # отчитываться. expected = сколько чаре закреплено за организацией,
        # submitted_events = по скольким из них есть отчёт. Период фильтруется в
        # ON-условии reports, чтобы не сданные за период тоже учитывались.
        join_period = ""
        params = []
        if period:
            join_period = " AND r.report_period LIKE %s"
            params.append(f"%{period}%")

        where_prog = ""
        if program_id and program_id.isdigit():
            where_prog = " AND e.program_id = %s"
            params.append(int(program_id))

        cursor.execute(f"""
            SELECT
                o.id,
                o.name,
                COUNT(DISTINCT e.id) AS expected,
                COUNT(DISTINCT CASE WHEN r.id IS NOT NULL THEN e.id END) AS submitted_events,
                {_STATUS_COUNTS_SQL}
            FROM organizations o
            JOIN event_organizations eo ON eo.organization_id = o.id
            JOIN events e ON eo.event_id = e.id AND e.status = 'active'
            LEFT JOIN reports r ON r.event_id = e.id
                               AND r.organization_id = o.id{join_period}
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            WHERE o.status = 'active'{where_prog}
            GROUP BY o.id, o.name
            ORDER BY o.name ASC
        """, tuple(params))
        rows = cursor.fetchall()
    conn.close()

    # Не сданные = закреплённые чаре без отчёта (за выбранный период).
    for r in rows:
        r['not_submitted'] = r['expected'] - r['submitted_events']

    totals = {
        'under_review': sum(r['cnt_under_review'] for r in rows),
        'returned': sum(r['cnt_returned'] for r in rows),
        'accepted': sum(r['cnt_accepted'] for r in rows),
        'not_submitted': sum(r['not_submitted'] for r in rows),
        'expected': sum(r['expected'] for r in rows),
        'total': sum(r['total'] for r in rows),
        'organizations': len(rows),
    }

    return render_template('company_user/report_by_organization.html',
                           rows=rows,
                           totals=totals,
                           programs=programs_list,
                           selected_program=program_id,
                           selected_period=period)


@company_user_bp.route('/reports/by-event')
@company_user_required
def report_by_event():
    """Общий отчёт по мероприятиям (с фильтром по программе)."""
    from app import get_db_connection
    conn = get_db_connection()

    program_id = request.args.get('program_id', '')
    period = request.args.get('period', '').strip()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
        programs_list = cursor.fetchall()

        # Период фильтруется в ON-условии reports, чтобы чаре без отчётов в этом
        # периоде всё равно отображались (с нулями). Порядок params: сначала
        # период (раньше в SQL), потом программа (в WHERE).
        join_period = ""
        params = []
        if period:
            join_period = " AND r.report_period LIKE %s"
            params.append(f"%{period}%")

        where_prog = ""
        if program_id and program_id.isdigit():
            where_prog = " AND e.program_id = %s"
            params.append(int(program_id))

        cursor.execute(f"""
            SELECT
                e.id,
                e.item_number,
                e.name AS event_name,
                p.name AS program_name,
                {_STATUS_COUNTS_SQL}
            FROM events e
            JOIN programs p ON e.program_id = p.id
            LEFT JOIN reports r ON r.event_id = e.id{join_period}
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            WHERE e.status = 'active'{where_prog}
            GROUP BY e.id, e.item_number, e.name, p.name
            ORDER BY p.name ASC, e.item_number ASC
        """, tuple(params))
        rows = cursor.fetchall()
    conn.close()

    totals = {
        'under_review': sum(r['cnt_under_review'] for r in rows),
        'returned': sum(r['cnt_returned'] for r in rows),
        'accepted': sum(r['cnt_accepted'] for r in rows),
        'total': sum(r['total'] for r in rows),
        'events': len(rows),
    }

    return render_template('company_user/report_by_event.html',
                           rows=rows,
                           totals=totals,
                           programs=programs_list,
                           selected_program=program_id,
                           selected_period=period)


# ----------------------------------------------------------------------------
# ÝERINE ÝETIRILIŞ (выполнение по статусам event_statuses)
# ----------------------------------------------------------------------------

@company_user_bp.route('/reports/execution/by-program')
@company_user_required
def exec_by_program():
    """Выполнение программ — разбивка отчётов по статусам (event_statuses)."""
    from app import get_db_connection
    conn = get_db_connection()

    period = request.args.get('period', '').strip()
    params = []
    where_period = ""
    if period:
        where_period = " AND r.report_period LIKE %s"
        params.append(f"%{period}%")

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM event_statuses WHERE status = 'active' ORDER BY id ASC")
        statuses = cursor.fetchall()

        cursor.execute(f"""
            SELECT
                p.id   AS group_id,
                p.name AS group_name,
                r.status_id,
                COUNT(r.id) AS cnt
            FROM programs p
            JOIN events e ON e.program_id = p.id
            JOIN reports r ON r.event_id = e.id
            JOIN event_statuses es ON r.status_id = es.id
            WHERE p.status = 'active'{where_period}
            GROUP BY p.id, p.name, r.status_id
            ORDER BY p.name ASC
        """, tuple(params))
        flat = cursor.fetchall()
    conn.close()

    rows, chart, totals = _pivot_execution(flat, statuses, 'group_name')

    return render_template('company_user/exec_by_program.html',
                           rows=rows, chart=chart, totals=totals,
                           statuses=statuses, selected_period=period)


@company_user_bp.route('/reports/execution/by-organization')
@company_user_required
def exec_by_organization():
    """Выполнение организациями — разбивка отчётов по статусам (event_statuses)."""
    from app import get_db_connection
    conn = get_db_connection()

    program_id = request.args.get('program_id', '')
    period = request.args.get('period', '').strip()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
        programs_list = cursor.fetchall()

        cursor.execute("SELECT id, name FROM event_statuses WHERE status = 'active' ORDER BY id ASC")
        statuses = cursor.fetchall()

        params = []
        where_prog = ""
        if program_id and program_id.isdigit():
            where_prog = " AND e.program_id = %s"
            params.append(int(program_id))
        where_period = ""
        if period:
            where_period = " AND r.report_period LIKE %s"
            params.append(f"%{period}%")

        cursor.execute(f"""
            SELECT
                o.id   AS group_id,
                o.name AS group_name,
                r.status_id,
                COUNT(r.id) AS cnt
            FROM organizations o
            JOIN reports r ON r.organization_id = o.id
            JOIN events e ON r.event_id = e.id
            JOIN event_statuses es ON r.status_id = es.id
            WHERE o.status = 'active'{where_prog}{where_period}
            GROUP BY o.id, o.name, r.status_id
            ORDER BY o.name ASC
        """, tuple(params))
        flat = cursor.fetchall()
    conn.close()

    rows, chart, totals = _pivot_execution(flat, statuses, 'group_name')

    return render_template('company_user/exec_by_organization.html',
                           rows=rows, chart=chart, totals=totals,
                           statuses=statuses, programs=programs_list,
                           selected_program=program_id, selected_period=period)


@company_user_bp.route('/reports/execution/by-event')
@company_user_required
def exec_by_event():
    """Выполнение мероприятий — разбивка отчётов по статусам (event_statuses)."""
    from app import get_db_connection
    conn = get_db_connection()

    program_id = request.args.get('program_id', '')
    period = request.args.get('period', '').strip()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
        programs_list = cursor.fetchall()

        cursor.execute("SELECT id, name FROM event_statuses WHERE status = 'active' ORDER BY id ASC")
        statuses = cursor.fetchall()

        params = []
        where_prog = ""
        if program_id and program_id.isdigit():
            where_prog = " AND e.program_id = %s"
            params.append(int(program_id))
        where_period = ""
        if period:
            where_period = " AND r.report_period LIKE %s"
            params.append(f"%{period}%")

        cursor.execute(f"""
            SELECT
                e.id          AS group_id,
                e.item_number AS item_number,
                e.name        AS event_name,
                p.name        AS program_name,
                r.status_id,
                COUNT(r.id)   AS cnt
            FROM events e
            JOIN programs p ON e.program_id = p.id
            JOIN reports r ON r.event_id = e.id
            JOIN event_statuses es ON r.status_id = es.id
            WHERE e.status = 'active'{where_prog}{where_period}
            GROUP BY e.id, e.item_number, e.name, p.name, r.status_id
            ORDER BY p.name ASC, e.item_number ASC
        """, tuple(params))
        flat = cursor.fetchall()
    conn.close()

    rows, chart, totals = _pivot_execution(flat, statuses, 'item_number')

    return render_template('company_user/exec_by_event.html',
                           rows=rows, chart=chart, totals=totals,
                           statuses=statuses, programs=programs_list,
                           selected_program=program_id, selected_period=period)
