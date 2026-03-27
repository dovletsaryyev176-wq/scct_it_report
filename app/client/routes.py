import os
import uuid
from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from werkzeug.utils import secure_filename
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
        cursor.execute("""
            SELECT 
                e.id, 
                e.item_number, 
                e.name as event_name, 
                e.deadline,
                p.name as program_name,
                pr.report_type,
                (CASE 
                    WHEN pr.report_type = 'gündelik' THEN %s
                    WHEN pr.report_type = 'hepdeleýin' THEN %s
                    WHEN pr.report_type = 'aýlyk' THEN %s
                    WHEN pr.report_type = 'çärýeklik' THEN %s
                    WHEN pr.report_type = 'ýyllyk' THEN %s
                END) as current_period
            FROM events e
            JOIN event_organizations eo ON e.id = eo.event_id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON p.id = pr.program_id
            LEFT JOIN reports r ON e.id = r.event_id 
                AND r.organization_id = eo.organization_id
                AND r.report_period = (
                    CASE 
                        WHEN pr.report_type = 'gündelik' THEN %s
                        WHEN pr.report_type = 'hepdeleýin' THEN %s
                        WHEN pr.report_type = 'aýlyk' THEN %s
                        WHEN pr.report_type = 'çärýeklik' THEN %s
                        WHEN pr.report_type = 'ýyllyk' THEN %s
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
    conn.close()
    
    return render_template('client/dashboard.html', events=my_events)


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
                e.item_number, 
                e.name as event_name,
                p.name as program_name,
                es.name as status_name
            FROM reports r
            JOIN events e ON r.event_id = e.id
            JOIN programs p ON e.program_id = p.id
            JOIN event_statuses es ON r.status_id = es.id
            WHERE r.organization_id = %s
            ORDER BY r.created_at DESC
        """, (org_id,))
        reports = cursor.fetchall()

        files_by_report = {}
        if reports:
            report_ids = [r['id'] for r in reports]
            format_strings = ','.join(['%s'] * len(report_ids))
            
            cursor.execute(f"""
                SELECT id, report_id, file_path, original_name, file_type 
                FROM report_files 
                WHERE report_id IN ({format_strings})
            """, tuple(report_ids))
            files = cursor.fetchall()

            for f in files:
                r_id = f['report_id']
                if r_id not in files_by_report:
                    files_by_report[r_id] = []
                files_by_report[r_id].append(f)

    conn.close()

    return render_template('client/archive.html', reports=reports, files_by_report=files_by_report)


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
                    (organization_id, event_id, program_report_id, report_period, status_id, failure_reason_id, description, created_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (org_id, event_id, event_data['program_report_id'], server_period, status_id, failure_reason_id, description, user_id))
                
                report_id = cursor.lastrowid

                # ДОКУМЕНТЫ (Исправлено сохранение расширения)
                documents = request.files.getlist('documents')
                for doc in documents:
                    if doc and doc.filename != '':
                        orig_name = doc.filename
                        _, ext = os.path.splitext(orig_name) # Забираем расширение до очистки имени!
                        
                        unique_name = f"doc_{report_id}_{uuid.uuid4().hex}{ext.lower()}"
                        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
                        doc.save(file_path)

                        db_path = f"uploads/{unique_name}"
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, %s)
                        """, (report_id, db_path, orig_name, 'document'))

                # ФОТОГРАФИИ (Исправлено сохранение расширения)
                photos = request.files.getlist('photos')
                for photo in photos:
                    if photo and photo.filename != '':
                        orig_name = photo.filename
                        _, ext = os.path.splitext(orig_name)
                        
                        unique_name = f"photo_{report_id}_{uuid.uuid4().hex}{ext.lower()}"
                        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
                        photo.save(file_path)

                        db_path = f"uploads/{unique_name}"
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, %s)
                        """, (report_id, db_path, orig_name, 'photo'))

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

    return render_template('client/report_form.html', event=event_data, statuses=statuses, reasons=reasons, current_period=server_period)