import os
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from app.auth import client_required
from werkzeug.utils import secure_filename
from datetime import datetime

client_bp = Blueprint('client', __name__, url_prefix='/client')

# Папка для сохранения файлов на сервере
UPLOAD_FOLDER = 'app/static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@client_bp.route('/dashboard')
@client_required
def dashboard():
    from app import get_db_connection
    org_id = session.get('org_id')

    today = datetime.today()
    
    current_day = today.strftime('%Y-%m-%d') # Например: "2026-03-26"
    
    # Для недели используем ISO-календарь (соответствует стандарту <input type="week">)
    year, week, weekday = today.isocalendar()
    current_week = f"{year}-W{week:02d}"     # Например: "2026-W13"
    
    current_month = today.strftime('%Y-%m')    # Например: "2026-03"
    current_year = today.strftime('%Y')       # Например: "2026"
    
    quarter = (today.month - 1) // 3 + 1
    current_quarter = f"{current_year}-Q{quarter}" # Например: "2026-Q1"

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 2. Выбираем мероприятия, у которых НЕТ отчета за текущий период
        cursor.execute("""
            SELECT 
                e.id, 
                e.item_number, 
                e.name as event_name, 
                e.deadline,
                p.name as program_name,
                pr.report_type
            FROM events e
            JOIN event_organizations eo ON e.id = eo.event_id
            JOIN programs p ON e.program_id = p.id
            JOIN program_reports pr ON p.id = pr.program_id
            
            -- Присоединяем таблицу отчетов за ТЕКУЩИЙ период
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
              AND r.id IS NULL -- Ключевое условие: отчета за этот период еще нет
            ORDER BY e.item_number ASC
        """, (current_day, current_week, current_month, current_quarter, current_year, org_id))
        my_events = cursor.fetchall()
    conn.close()
    
    return render_template('client/dashboard.html', events=my_events)

@client_bp.route('/report/new/<int:event_id>', methods=['GET', 'POST'])
@client_required
def new_report(event_id):
    from app import get_db_connection
    org_id = session.get('org_id')
    user_id = session.get('user_id')

    conn = get_db_connection()

    # 1. Получаем данные о мероприятии и правиле отчетности
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

    # 2. Обработка POST-запроса (Сохранение данных)
    if request.method == 'POST':
        report_period = request.form.get('report_period')
        status_id = request.form.get('status_id')
        failure_reason_id = request.form.get('failure_reason_id') or None
        description = request.form.get('description')

        try:
            with conn.cursor() as cursor:
                # А. Записываем сам отчет
                cursor.execute("""
                    INSERT INTO reports 
                    (organization_id, event_id, program_report_id, report_period, status_id, failure_reason_id, description, created_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (org_id, event_id, event_data['program_report_id'], report_period, status_id, failure_reason_id, description, user_id))
                
                report_id = cursor.lastrowid # Получаем ID созданного отчета

                # Б. Сохраняем Документы
                documents = request.files.getlist('documents')
                for doc in documents:
                    if doc and doc.filename != '':
                        filename = secure_filename(doc.filename)
                        unique_name = f"doc_{report_id}_{filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
                        doc.save(file_path)

                        # Сохраняем в БД относительный путь для статики
                        db_path = f"uploads/{unique_name}"
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, %s)
                        """, (report_id, db_path, filename, 'document'))

                # В. Сохраняем Фотографии
                photos = request.files.getlist('photos')
                for photo in photos:
                    if photo and photo.filename != '':
                        filename = secure_filename(photo.filename)
                        unique_name = f"photo_{report_id}_{filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
                        photo.save(file_path)

                        db_path = f"uploads/{unique_name}"
                        cursor.execute("""
                            INSERT INTO report_files (report_id, file_path, original_name, file_type)
                            VALUES (%s, %s, %s, %s)
                        """, (report_id, db_path, filename, 'photo'))

            conn.commit()
            flash('Hasabat we faýllar üstünlikli tabşyryldy!', 'success')
            return redirect(url_for('client.dashboard'))

        except Exception as e:
            conn.rollback()
            flash(f'Ýalňyşlyk ýüze çykdy: Bu döwür üçin hasabat eýýäm tabşyrylan bolmagy mümkin. ({str(e)})', 'danger')

    # 3. Получение списков для селектов (GET-запрос)
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM event_statuses WHERE status = 'active'")
        statuses = cursor.fetchall()

        cursor.execute("SELECT * FROM failure_reasons WHERE status = 'active'")
        reasons = cursor.fetchall()

    conn.close()

    return render_template('client/report_form.html', event=event_data, statuses=statuses, reasons=reasons)