from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.auth import roles_required
from app import get_db_connection 

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

#------------------------- Welaýatlar--------------------------------------------------------

#Welaýatlar barada maglumat almak we täze welaýaty goşmak
@admin_bp.route('/cities', methods=['GET', 'POST'])
@roles_required('admin')
def manage_cities():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name').strip()
        if name:
            cursor.execute("INSERT INTO cities (name) VALUES (%s)", (name,))
            conn.commit()
            flash('Täze welaýat hasaba alyndy', 'success')
        return redirect(url_for('admin.manage_cities'))

    cursor.execute("SELECT * FROM cities ORDER BY created_at DESC")
    cities = cursor.fetchall()
    conn.close()
    return render_template('admin/cities.html', cities=cities)


#Welaýaty bloklamak we blokdan açmak
@admin_bp.route('/cities/toggle/<int:city_id>', methods=['POST'])
@roles_required('admin')
def toggle_city_status(city_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM cities WHERE id = %s", (city_id,))
        city = cursor.fetchone()
        if city:
            new_status = 'blocked' if city['status'] == 'active' else 'active'
            cursor.execute("UPDATE cities SET status = %s WHERE id = %s", (new_status, city_id))
            conn.commit()
            flash(f'Ýagdaýy üýtgedildi - {new_status}', 'info')
    conn.close()
    return redirect(url_for('admin.manage_cities'))


#Welaýatyň adyny üýtgetmek
@admin_bp.route('/cities/update', methods=['POST'])
@roles_required('admin')
def update_city():
    city_id = request.form.get('id')
    new_name = request.form.get('name').strip()
    
    if city_id and new_name:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE cities SET name = %s WHERE id = %s", (new_name, city_id))
            conn.commit()
        conn.close()
        flash(f'Welaýatyň ady üýtgedildi -  "{new_name}"', 'success')
    else:
        flash('Ýalňyş, ady boş bolup bilmeýär', 'danger')
        
    return redirect(url_for('admin.manage_cities'))

#------------------------- Etraplar--------------------------------------------------------

#Etraby ýa-da şäheri hasaba almak we maglumatlaryny gaýtarmak
@admin_bp.route('/districts', methods=['GET', 'POST'])
@roles_required('admin')
def manage_districts():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        city_id = request.form.get('city_id')
        name = request.form.get('name').strip()
        if name and city_id:
            cursor.execute("INSERT INTO districts (city_id, name) VALUES (%s, %s)", (city_id, name))
            conn.commit()
            flash(f'"{name}" etraby üstünlikli goşuldy', 'success')
        return redirect(url_for('admin.manage_districts'))

    
    cursor.execute("""
        SELECT d.*, c.name as city_name 
        FROM districts d 
        JOIN cities c ON d.city_id = c.id 
        ORDER BY d.created_at DESC
    """)
    districts = cursor.fetchall()

    
    cursor.execute("SELECT id, name FROM cities WHERE status = 'active' ORDER BY name")
    cities = cursor.fetchall()
    
    conn.close()
    return render_template('admin/districts.html', districts=districts, cities=cities)


#Etrap ýa-da şäher boýunça maglumatlary täzelemek
@admin_bp.route('/districts/update', methods=['POST'])
@roles_required('admin')
def update_district():
    dist_id = request.form.get('id')
    city_id = request.form.get('city_id')
    name = request.form.get('name').strip()
    
    if dist_id and city_id and name:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            
            cursor.execute("UPDATE districts SET name = %s, city_id = %s WHERE id = %s", 
                           (name, city_id, dist_id))
            conn.commit()
        conn.close()
        flash('Etrap maglumatlary täzelendi', 'success')
    return redirect(url_for('admin.manage_districts'))


#Etraby ýa-da şäheri bloklamak
@admin_bp.route('/districts/toggle/<int:dist_id>', methods=['POST'])
@roles_required('admin')
def toggle_district_status(dist_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM districts WHERE id = %s", (dist_id,))
        dist = cursor.fetchone()
        if dist:
            new_status = 'blocked' if dist['status'] == 'active' else 'active'
            cursor.execute("UPDATE districts SET status = %s WHERE id = %s", (new_status, dist_id))
            conn.commit()
            flash(f'Etrabyň statusy "{new_status}" edildi', 'info')
    conn.close()
    return redirect(url_for('admin.manage_districts'))

#------------------------- Edaralar--------------------------------------------------------

#Täze edara döretmek we maglumatlaryny almak
@admin_bp.route('/organizations', methods=['GET', 'POST'])
@roles_required('admin')
def manage_organizations():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name').strip()
        parent_id = request.form.get('parent_id') or None
        city_id = request.form.get('city_id')
        district_id = request.form.get('district_id')
        address = request.form.get('address')
        phone = request.form.get('phone')
        
        if name and city_id and district_id:
            cursor.execute("""
                INSERT INTO organizations (name, parent_id, city_id, district_id, address, phone) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, parent_id, city_id, district_id, address, phone))
            conn.commit()
            flash(f'"{name}" edarasy goşuldy', 'success')
        return redirect(url_for('admin.manage_organizations'))

    
    cursor.execute("""
        SELECT o.*, c.name as city_name, d.name as district_name, p.name as parent_name
        FROM organizations o
        JOIN cities c ON o.city_id = c.id
        JOIN districts d ON o.district_id = d.id
        LEFT JOIN organizations p ON o.parent_id = p.id
        ORDER BY o.created_at DESC
    """)
    orgs = cursor.fetchall()

    
    cursor.execute("SELECT id, name FROM cities WHERE status = 'active' ORDER BY name")
    cities = cursor.fetchall()
    
    cursor.execute("SELECT id, name, city_id FROM districts WHERE status = 'active' ORDER BY name")
    districts = cursor.fetchall()

    cursor.execute("SELECT id, name FROM organizations WHERE status = 'active' ORDER BY name")
    parent_orgs = cursor.fetchall()
    
    conn.close()
    return render_template('admin/organizations.html', 
                           orgs=orgs, cities=cities, 
                           districts=districts, parent_orgs=parent_orgs)


#Edara boýunça maglumatlary täzelemek
@admin_bp.route('/organizations/update', methods=['POST'])
@roles_required('admin')
def update_organization():
    org_id = request.form.get('id')
    name = request.form.get('name').strip()
    parent_id = request.form.get('parent_id') or None
    city_id = request.form.get('city_id')
    district_id = request.form.get('district_id')
    address = request.form.get('address')
    phone = request.form.get('phone')
    
    if org_id and name:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE organizations 
                SET name=%s, parent_id=%s, city_id=%s, district_id=%s, address=%s, phone=%s 
                WHERE id=%s
            """, (name, parent_id, city_id, district_id, address, phone, org_id))
            conn.commit()
        conn.close()
        flash('Edaranyň maglumatlary täzelendi', 'success')
    return redirect(url_for('admin.manage_organizations'))


#Edarany bloklamak we blokdan açmak
@admin_bp.route('/organizations/toggle/<int:org_id>', methods=['POST'])
@roles_required('admin')
def toggle_org_status(org_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM organizations WHERE id = %s", (org_id,))
        org = cursor.fetchone()
        if org:
            new_status = 'blocked' if org['status'] == 'active' else 'active'
            cursor.execute("UPDATE organizations SET status = %s WHERE id = %s", (new_status, org_id))
            conn.commit()
            flash(f'Edaranyň statusy "{new_status}" edildi', 'info')
    conn.close()
    return redirect(url_for('admin.manage_organizations'))

#------------------------- Maksatnamalar--------------------------------------------------------

#Döwlet maksatnamalary goşmak we maglumatlaryny almak
@admin_bp.route('/programs', methods=['GET', 'POST'])
@roles_required('admin')
def manage_programs():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO programs (name, order_date, order_number, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (request.form['name'], request.form['order_date'], request.form['order_number'], 
              request.form['start_date'], request.form['end_date']))
        conn.commit()
        flash('Maksatnama goşuldy', 'success')
        return redirect(url_for('admin.manage_programs'))
    
    cursor.execute("SELECT * FROM programs ORDER BY created_at DESC")
    programs = cursor.fetchall()
    conn.close()
    return render_template('admin/programs.html', programs=programs)


#Döwlet maksatnamalary barada maglumatlary üýtgetmek
@admin_bp.route('/programs/update', methods=['POST'])
@roles_required('admin')
def update_program():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE programs SET name=%s, order_date=%s, order_number=%s, start_date=%s, end_date=%s
            WHERE id=%s
        """, (request.form['name'], request.form['order_date'], request.form['order_number'],
              request.form['start_date'], request.form['end_date'], request.form['id']))
        conn.commit()
    conn.close()
    flash('Maksatnama täzelendi', 'success')
    return redirect(url_for('admin.manage_programs'))


#Döwlet maksatnamalary bloklamak we blokdan açmak
@admin_bp.route('/programs/toggle/<int:id>', methods=['POST'])
@roles_required('admin')
def toggle_program_status(id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM programs WHERE id=%s", (id,))
        p = cursor.fetchone()
        new_status = 'blocked' if p['status'] == 'active' else 'active'
        cursor.execute("UPDATE programs SET status=%s WHERE id=%s", (new_status, id))
        conn.commit()
    conn.close()
    return redirect(url_for('admin.manage_programs'))

#------------------------- Çäreler--------------------------------------------------------

#Çäreleri döretmek we maglumatlaryny almak
@admin_bp.route('/events', methods=['GET', 'POST'])
@roles_required('admin')
def manage_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        program_id = request.form.get('program_id')
        item_number = request.form.get('item_number')
        name = request.form.get('name')
        deadline = request.form.get('deadline')
        org_ids = request.form.getlist('org_ids') # Получаем список выбранных организаций

        # 1. Вставляем само мероприятие
        cursor.execute("""
            INSERT INTO events (program_id, item_number, name, deadline)
            VALUES (%s, %s, %s, %s)
        """, (program_id, item_number, name, deadline))
        
        event_id = cursor.lastrowid # Получаем ID только что созданной записи

        # 2. Связываем мероприятие с выбранными организациями в таблице event_organizations
        if org_ids:
            for o_id in org_ids:
                cursor.execute("""
                    INSERT INTO event_organizations (event_id, organization_id) 
                    VALUES (%s, %s)
                """, (event_id, o_id))
        
        conn.commit()
        flash('Täze çäre üstünlikli goşuldy', 'success')
        return redirect(url_for('admin.manage_events'))

    # ОБНОВЛЕННЫЙ ЗАПРОС: добавили GROUP_CONCAT(o.id) as org_ids_list
    cursor.execute("""
        SELECT 
            e.*, 
            p.name as program_name, 
            GROUP_CONCAT(o.name SEPARATOR ', ') as org_names,
            GROUP_CONCAT(o.id) as org_ids_list
        FROM events e
        JOIN programs p ON e.program_id = p.id
        LEFT JOIN event_organizations eo ON e.id = eo.event_id
        LEFT JOIN organizations o ON eo.organization_id = o.id
        GROUP BY e.id 
        ORDER BY e.item_number ASC
    """)
    events = cursor.fetchall()
    
    # Загружаем списки для выпадающих меню в модальном окне
    cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
    programs = cursor.fetchall()
    
    cursor.execute("SELECT id, name FROM organizations WHERE status = 'active' ORDER BY name ASC")
    organizations = cursor.fetchall()
    
    conn.close()
    return render_template('admin/events.html', 
                           events=events, 
                           programs=programs, 
                           organizations=organizations)

@admin_bp.route('/events/update', methods=['POST'])
@roles_required('admin')
def update_event():
    event_id = request.form.get('id')
    program_id = request.form.get('program_id')
    item_number = request.form.get('item_number')
    name = request.form.get('name')
    deadline = request.form.get('deadline')
    org_ids = request.form.getlist('org_ids') # Список выбранных ID

    if event_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 1. Обновляем основные данные мероприятия
        cursor.execute("""
            UPDATE events SET program_id=%s, item_number=%s, name=%s, deadline=%s
            WHERE id=%s
        """, (program_id, item_number, name, deadline, event_id))
        
        # 2. Обновляем связи с организациями (удаляем старые и пишем новые)
        cursor.execute("DELETE FROM event_organizations WHERE event_id=%s", (event_id,))
        for o_id in org_ids:
            cursor.execute("INSERT INTO event_organizations (event_id, organization_id) VALUES (%s, %s)", (event_id, o_id))
        
        conn.commit()
        conn.close()
        flash('Çäre maglumatlary täzelendi', 'success')
    return redirect(url_for('admin.manage_events'))


@admin_bp.route('/events/toggle/<int:id>', methods=['POST'])
@roles_required('admin')
def toggle_event_status(id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM events WHERE id=%s", (id,))
        ev = cursor.fetchone()
        if ev:
            new_status = 'blocked' if ev['status'] == 'active' else 'active'
            cursor.execute("UPDATE events SET status=%s WHERE id=%s", (new_status, id))
            conn.commit()
    conn.close()
    return redirect(url_for('admin.manage_events'))

#------------------------- Çäräniň ýagdaýlary--------------------------------------------------------

@admin_bp.route('/event-statuses', methods=['GET', 'POST'])
@roles_required('admin')
def manage_event_statuses():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name').strip()
        if name:
            cursor.execute("INSERT INTO event_statuses (name) VALUES (%s)", (name,))
            conn.commit()
            flash('Täze ýagdaýyň görnüşi goşuldy', 'success')
        return redirect(url_for('admin.manage_event_statuses'))
    
    cursor.execute("SELECT * FROM event_statuses ORDER BY name ASC")
    statuses = cursor.fetchall()
    conn.close()
    return render_template('admin/event_statuses.html', statuses=statuses)


@admin_bp.route('/event-statuses/update', methods=['POST'])
@roles_required('admin')
def update_event_status():
    status_id = request.form.get('id')
    name = request.form.get('name').strip()
    if status_id and name:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE event_statuses SET name = %s WHERE id = %s", (name, status_id))
            conn.commit()
        conn.close()
        flash('Ýagdaýýyň görnüşi täzelendi', 'success')
    return redirect(url_for('admin.manage_event_statuses'))


@admin_bp.route('/event-statuses/toggle/<int:id>', methods=['POST'])
@roles_required('admin')
def toggle_event_type_status(id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM event_statuses WHERE id = %s", (id,))
        s = cursor.fetchone()
        new_status = 'blocked' if s['status'] == 'active' else 'active'
        cursor.execute("UPDATE event_statuses SET status = %s WHERE id = %s", (new_status, id))
        conn.commit()
    conn.close()
    return redirect(url_for('admin.manage_event_statuses'))

#------------------------- Sebäpler--------------------------------------------------------

@admin_bp.route('/failure-reasons', methods=['GET', 'POST'])
@roles_required('admin')
def manage_failure_reasons():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name').strip()
        if name:
            cursor.execute("INSERT INTO failure_reasons (name) VALUES (%s)", (name,))
            conn.commit()
            flash('Täze sebäbiň görnüşi goşuldy', 'success')
        return redirect(url_for('admin.manage_failure_reasons'))
    
    cursor.execute("SELECT * FROM failure_reasons ORDER BY name ASC")
    reasons = cursor.fetchall()
    conn.close()
    return render_template('admin/failure_reasons.html', reasons=reasons)


@admin_bp.route('/failure-reasons/update', methods=['POST'])
@roles_required('admin')
def update_failure_reason():
    reason_id = request.form.get('id')
    name = request.form.get('name').strip()
    if reason_id and name:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE failure_reasons SET name = %s WHERE id = %s", (name, reason_id))
            conn.commit()
        conn.close()
        flash('Sebäbiň görnüşi täzelendi', 'success')
    return redirect(url_for('admin.manage_failure_reasons'))


@admin_bp.route('/failure-reasons/toggle/<int:id>', methods=['POST'])
@roles_required('admin')
def toggle_failure_reason(id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM failure_reasons WHERE id = %s", (id,))
        r = cursor.fetchone()
        new_status = 'blocked' if r['status'] == 'active' else 'active'
        cursor.execute("UPDATE failure_reasons SET status = %s WHERE id = %s", (new_status, id))
        conn.commit()
    conn.close()
    return redirect(url_for('admin.manage_failure_reasons'))

