import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from app.auth import client_required

client_bp = Blueprint('client', __name__, url_prefix='/client')

UPLOAD_FOLDER = 'app/static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def calculate_current_period(report_type):
    """Вычисление текущего периода на сервере"""
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



@client_bp.route('/dashboard')
@client_required
def dashboard():
    from app import get_db_connection
    org_id = session.get('org_id')

    today = datetime.today()
    current_day = today.strftime('%Y-%m-%d')
    year, week, _ = today.isocalendar()
    current_week = f"{year}-W{week:02d}"
    current_month = today.strftime('%Y-%m')
    current_year = today.strftime('%Y')
    quarter = (today.month - 1) // 3 + 1
    current_quarter = f"{current_year}-Q{quarter}"

    conn = get_db_connection()
    with conn.cursor() as cursor:

        # 1) Мероприятия без отчёта за текущий период
        cursor.execute("""
            SELECT
                e.id,
                e.item_number,
                e.name as event_name,
                e.deadline,
                p.name as program_name,
                pr.report_type,
                (CASE
                    WHEN pr.report_type = 'gündelik'    THEN %s
                    WHEN pr.report_type = 'hepdeleýin'  THEN %s
                    WHEN pr.report_type = 'aýlyk'       THEN %s
                    WHEN pr.report_type = 'çärýeklik'   THEN %s
                    WHEN pr.report_type = 'ýyllyk'      THEN %s
                END) as current_period
            FROM events e
            JOIN event_organizations eo ON e.id = eo.event_id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON p.id = pr.program_id
            LEFT JOIN reports r ON e.id = r.event_id
                AND r.organization_id = eo.organization_id
                AND r.report_period = (
                    CASE
                        WHEN pr.report_type = 'gündelik'    THEN %s
                        WHEN pr.report_type = 'hepdeleýin'  THEN %s
                        WHEN pr.report_type = 'aýlyk'       THEN %s
                        WHEN pr.report_type = 'çärýeklik'   THEN %s
                        WHEN pr.report_type = 'ýyllyk'      THEN %s
                    END
                )
            WHERE eo.organization_id = %s
              AND e.status = 'active'
              AND pr.status = 'active'
              AND r.id IS NULL
            ORDER BY e.item_number ASC
        """, (
            current_day, current_week, current_month, current_quarter, current_year,
            current_day, current_week, current_month, current_quarter, current_year,
            org_id
        ))
        my_events = cursor.fetchall()

        # 2) Возвращённые отчёты — нужна коррекция клиентом
        cursor.execute("""
            SELECT
                r.id as report_id,
                e.id as event_id,
                e.item_number,
                e.name as event_name,
                e.deadline,
                p.name as program_name,
                pr.report_type,
                r.report_period,
                (SELECT h.reviewer_comment
                 FROM report_review_history h
                 WHERE h.report_id = r.id AND h.review_status = 'returned'
                 ORDER BY h.created_at DESC LIMIT 1) as last_comment,
                (SELECT h.created_at
                 FROM report_review_history h
                 WHERE h.report_id = r.id AND h.review_status = 'returned'
                 ORDER BY h.created_at DESC LIMIT 1) as returned_at
            FROM reports r
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON p.id = pr.program_id AND pr.id = r.program_report_id
            JOIN report_submissions rs ON r.id = rs.report_id
            WHERE r.organization_id = %s AND rs.review_status = 'returned'
            ORDER BY r.updated_at DESC
        """, (org_id,))
        returned_reports = cursor.fetchall()

    conn.close()
    return render_template('client/dashboard.html',
                           events=my_events,
                           returned_reports=returned_reports)



@client_bp.route('/archive')
@client_required
def archive():
    from app import get_db_connection
    org_id = session.get('org_id')

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                r.id,
                r.report_period,
                r.description,
                r.created_at,
                r.updated_at,
                e.item_number,
                e.name as event_name,
                p.name as program_name,
                es.name as status_name,
                COALESCE(rs.review_status, 'under_review') as review_status
            FROM reports r
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            JOIN event_statuses es ON r.status_id = es.id
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            WHERE r.organization_id = %s
            ORDER BY r.created_at DESC
        """, (org_id,))
        reports = cursor.fetchall()

        files_by_report = {}
        history_by_report = {}

        if reports:
            report_ids = [r['id'] for r in reports]
            fmt = ','.join(['%s'] * len(report_ids))

            cursor.execute(f"""
                SELECT id, report_id, file_path, original_name, file_type
                FROM report_files
                WHERE report_id IN ({fmt})
            """, tuple(report_ids))
            for f in cursor.fetchall():
                files_by_report.setdefault(f['report_id'], []).append(f)

            cursor.execute(f"""
                SELECT h.*, u.full_name as reviewer_name
                FROM report_review_history h
                LEFT JOIN users u ON h.changed_by = u.id
                WHERE h.report_id IN ({fmt})
                ORDER BY h.created_at DESC
            """, tuple(report_ids))
            for h in cursor.fetchall():
                history_by_report.setdefault(h['report_id'], []).append(h)

    conn.close()
    return render_template('client/archive.html',
                           reports=reports,
                           files_by_report=files_by_report,
                           history_by_report=history_by_report)



@client_bp.route('/report/new/<int:event_id>', methods=['GET', 'POST'])
@client_required
def new_report(event_id):
    from app import get_db_connection
    org_id = session.get('org_id')
    user_id = session.get('user_id')

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT e.*, p.name as program_name, pr.id as program_report_id, pr.report_type
            FROM events e
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON p.id = pr.program_id
            JOIN event_organizations eo ON e.id = eo.event_id
            WHERE e.id = %s AND eo.organization_id = %s AND pr.status = 'active'
        """, (event_id, org_id))
        event_data = cursor.fetchone()

    if not event_data:
        flash('Bu çäre üçin hasabat bermäge rugsadyňyz ýok ýa-da hasabat tertibi kesgitlenmedik.', 'danger')
        conn.close()
        return redirect(url_for('client.dashboard'))

    server_period = calculate_current_period(event_data['report_type'])

    if request.method == 'POST':
        status_id = request.form.get('status_id')
        failure_reason_id = request.form.get('failure_reason_id') or None
        description = request.form.get('description')

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO reports
                    (organization_id, event_id, program_report_id, report_period,
                     status_id, failure_reason_id, description, created_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (org_id, event_id, event_data['program_report_id'],
                      server_period, status_id, failure_reason_id, description, user_id))

                report_id = cursor.lastrowid

                # Текущий статус: под_review
                cursor.execute("""
                    INSERT INTO report_submissions (report_id, review_status)
                    VALUES (%s, 'under_review')
                """, (report_id,))

                # История: первая сдача
                cursor.execute("""
                    INSERT INTO report_review_history (report_id, review_status, changed_by)
                    VALUES (%s, 'under_review', %s)
                """, (report_id, user_id))

                # Файлы — документы
                for doc in request.files.getlist('documents'):
                    if doc and doc.filename:
                        orig = doc.filename
                        _, ext = os.path.splitext(orig)
                        uname = f"doc_{report_id}_{uuid.uuid4().hex}{ext.lower()}"
                        doc.save(os.path.join(UPLOAD_FOLDER, uname))
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, 'document')
                        """, (report_id, f"uploads/{uname}", orig))

                # Файлы — фото
                for photo in request.files.getlist('photos'):
                    if photo and photo.filename:
                        orig = photo.filename
                        _, ext = os.path.splitext(orig)
                        uname = f"photo_{report_id}_{uuid.uuid4().hex}{ext.lower()}"
                        photo.save(os.path.join(UPLOAD_FOLDER, uname))
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, 'photo')
                        """, (report_id, f"uploads/{uname}", orig))

            conn.commit()
            flash('Hasabat we faýllar üstünlikli tabşyryldy!', 'success')
            return redirect(url_for('client.dashboard'))

        except Exception as e:
            conn.rollback()
            flash(f'Ýalňyşlyk ýüze çykdy. Mümkin bu döwür üçin eýýäm hasabat tabşyrylandyr. ({str(e)})', 'danger')

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM event_statuses WHERE status = 'active'")
        statuses = cursor.fetchall()
        cursor.execute("SELECT * FROM failure_reasons WHERE status = 'active'")
        reasons = cursor.fetchall()

    conn.close()
    return render_template('client/report_form.html',
                           event=event_data,
                           statuses=statuses,
                           reasons=reasons,
                           current_period=server_period,
                           is_edit=False,
                           report=None,
                           existing_files=[],
                           last_return=None)



@client_bp.route('/report/edit/<int:report_id>', methods=['GET', 'POST'])
@client_required
def edit_report(report_id):
    from app import get_db_connection
    org_id = session.get('org_id')
    user_id = session.get('user_id')

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.*, e.name as event_name, e.item_number, e.deadline,
                   p.name as program_name, pr.report_type, pr.id as program_report_id,
                   COALESCE(rs.review_status, 'under_review') as review_status
            FROM reports r
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON r.program_report_id = pr.id
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            WHERE r.id = %s AND r.organization_id = %s
        """, (report_id, org_id))
        report = cursor.fetchone()

    if not report:
        flash('Hasabat tapylmady.', 'danger')
        conn.close()
        return redirect(url_for('client.archive'))

    # Блокировка: редактировать можно только returned
    if report['review_status'] != 'returned':
        flash('Bu hasabaty üýtgetmek bolmaýar. Diňe gaýtarylan hasabatlar düzedilip bilner.', 'warning')
        conn.close()
        return redirect(url_for('client.archive'))

    if request.method == 'POST':
        status_id = request.form.get('status_id')
        failure_reason_id = request.form.get('failure_reason_id') or None
        description = request.form.get('description')

        try:
            with conn.cursor() as cursor:
                # Обновляем отчёт
                cursor.execute("""
                    UPDATE reports
                    SET status_id=%s, failure_reason_id=%s, description=%s
                    WHERE id=%s AND organization_id=%s
                """, (status_id, failure_reason_id, description, report_id, org_id))

                # Добавляем новые документы
                for doc in request.files.getlist('documents'):
                    if doc and doc.filename:
                        orig = doc.filename
                        _, ext = os.path.splitext(orig)
                        uname = f"doc_{report_id}_{uuid.uuid4().hex}{ext.lower()}"
                        doc.save(os.path.join(UPLOAD_FOLDER, uname))
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, 'document')
                        """, (report_id, f"uploads/{uname}", orig))

                # Добавляем новые фото
                for photo in request.files.getlist('photos'):
                    if photo and photo.filename:
                        orig = photo.filename
                        _, ext = os.path.splitext(orig)
                        uname = f"photo_{report_id}_{uuid.uuid4().hex}{ext.lower()}"
                        photo.save(os.path.join(UPLOAD_FOLDER, uname))
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, 'photo')
                        """, (report_id, f"uploads/{uname}", orig))

                # Обновляем текущий статус → under_review
                cursor.execute("""
                    UPDATE report_submissions
                    SET review_status='under_review'
                    WHERE report_id=%s
                """, (report_id,))

                # Добавляем запись в историю
                cursor.execute("""
                    INSERT INTO report_review_history (report_id, review_status, changed_by)
                    VALUES (%s, 'under_review', %s)
                """, (report_id, user_id))

            conn.commit()
            flash('Hasabat üstünlikli täzeden tabşyryldy!', 'success')
            return redirect(url_for('client.archive'))

        except Exception as e:
            conn.rollback()
            flash(f'Ýalňyşlyk ýüze çykdy: {str(e)}', 'danger')

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM event_statuses WHERE status = 'active'")
        statuses = cursor.fetchall()

        cursor.execute("SELECT * FROM failure_reasons WHERE status = 'active'")
        reasons = cursor.fetchall()

        cursor.execute("""
            SELECT * FROM report_files WHERE report_id = %s ORDER BY created_at ASC
        """, (report_id,))
        existing_files = cursor.fetchall()

        # Последний комментарий проверяющего (при возврате)
        cursor.execute("""
            SELECT reviewer_comment, created_at
            FROM report_review_history
            WHERE report_id = %s AND review_status = 'returned'
            ORDER BY created_at DESC LIMIT 1
        """, (report_id,))
        last_return = cursor.fetchone()

    conn.close()
    return render_template('client/report_form.html',
                           event=report,
                           statuses=statuses,
                           reasons=reasons,
                           current_period=report['report_period'],
                           is_edit=True,
                           report=report,
                           existing_files=existing_files,
                           last_return=last_return)



@client_bp.route('/report/<int:report_id>')
@client_required
def report_detail(report_id):
    from app import get_db_connection
    org_id = session.get('org_id')

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.*, e.name as event_name, e.item_number, e.deadline,
                   p.name as program_name, pr.report_type,
                   es.name as status_name,
                   COALESCE(rs.review_status, 'under_review') as review_status
            FROM reports r
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON r.program_report_id = pr.id
            LEFT JOIN report_submissions rs ON r.id = rs.report_id
            LEFT JOIN event_statuses es ON r.status_id = es.id
            WHERE r.id = %s AND r.organization_id = %s
        """, (report_id, org_id))
        report = cursor.fetchone()

    if not report:
        flash('Hasabat tapylmady.', 'danger')
        conn.close()
        return redirect(url_for('client.archive'))

    with conn.cursor() as cursor:
        # История в хронологическом порядке (от старого к новому)
        cursor.execute("""
            SELECT h.*, u.full_name as reviewer_name
            FROM report_review_history h
            LEFT JOIN users u ON h.changed_by = u.id
            WHERE h.report_id = %s
            ORDER BY h.created_at ASC
        """, (report_id,))
        history = cursor.fetchall()

        cursor.execute("""
            SELECT * FROM report_files WHERE report_id = %s ORDER BY file_type, created_at ASC
        """, (report_id,))
        files = cursor.fetchall()

    conn.close()
    return render_template('client/report_detail.html',
                           report=report,
                           history=history,
                           files=files)