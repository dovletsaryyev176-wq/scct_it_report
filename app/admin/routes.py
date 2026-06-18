from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.auth import roles_required
from app import get_db_connection 
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

#Bellik: cities-welaýatlar, districts-etraplar we şäherçeler

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
            flash(f'Welaýatyň ýagdaýy üýtgedildi - {new_status}', 'info')
    conn.close()
    return redirect(url_for('admin.manage_cities'))



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



#Bellik: districts-etraplar


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
            flash(f'"{name}" etraby/şäherçesi üstünlikli goşuldy', 'success')
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
        flash('Etrap ýa-da şäherçäniň maglumatlary täzelendi', 'success')
    return redirect(url_for('admin.manage_districts'))



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
            flash(f'Etrabyň ýa-da şäherçäniň ýagdaýy  "{new_status}" edildi', 'info')
    conn.close()
    return redirect(url_for('admin.manage_districts'))



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
            flash(f'Edaranyň ýagdaýy "{new_status}" edildi', 'info')
    conn.close()
    return redirect(url_for('admin.manage_organizations'))



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
    flash('Döwlet maksatnamasy boýunça maglumatlar täzelendi', 'success')
    return redirect(url_for('admin.manage_programs'))



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
        org_ids = request.form.getlist('org_ids')

        
        cursor.execute("""
            INSERT INTO events (program_id, item_number, name, deadline)
            VALUES (%s, %s, %s, %s)
        """, (program_id, item_number, name, deadline))
        
        event_id = cursor.lastrowid 

        
        if org_ids:
            for o_id in org_ids:
                cursor.execute("""
                    INSERT INTO event_organizations (event_id, organization_id) 
                    VALUES (%s, %s)
                """, (event_id, o_id))
        
        conn.commit()
        flash('Täze çäre üstünlikli goşuldy', 'success')
        return redirect(url_for('admin.manage_events'))


    filter_program_id = request.args.get('program_id') or None

    query = """
        SELECT
            e.*,
            p.name as program_name,
            GROUP_CONCAT(o.name SEPARATOR ', ') as org_names,
            GROUP_CONCAT(o.id) as org_ids_list
        FROM events e
        JOIN programs p ON e.program_id = p.id
        LEFT JOIN event_organizations eo ON e.id = eo.event_id
        LEFT JOIN organizations o ON eo.organization_id = o.id
    """
    params = []
    if filter_program_id:
        query += " WHERE e.program_id = %s"
        params.append(filter_program_id)
    query += " GROUP BY e.id ORDER BY e.item_number ASC"

    cursor.execute(query, params)
    events = cursor.fetchall()


    cursor.execute("SELECT id, name FROM programs WHERE status = 'active' ORDER BY name ASC")
    programs = cursor.fetchall()

    cursor.execute("SELECT id, name FROM organizations WHERE status = 'active' ORDER BY name ASC")
    organizations = cursor.fetchall()

    conn.close()
    return render_template('admin/events.html',
                           events=events,
                           programs=programs,
                           organizations=organizations,
                           filter_program_id=filter_program_id)




@admin_bp.route('/events/update', methods=['POST'])
@roles_required('admin')
def update_event():
    event_id = request.form.get('id')
    program_id = request.form.get('program_id')
    item_number = request.form.get('item_number')
    name = request.form.get('name')
    deadline = request.form.get('deadline')
    org_ids = request.form.getlist('org_ids') 

    if event_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE events SET program_id=%s, item_number=%s, name=%s, deadline=%s
            WHERE id=%s
        """, (program_id, item_number, name, deadline, event_id))
        
        
        cursor.execute("DELETE FROM event_organizations WHERE event_id=%s", (event_id,))
        for o_id in org_ids:
            cursor.execute("INSERT INTO event_organizations (event_id, organization_id) VALUES (%s, %s)", (event_id, o_id))
        
        conn.commit()
        conn.close()
        flash('Çärä degişli maglumatlar täzelendi', 'success')
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



@admin_bp.route('/users', methods=['GET', 'POST'])
@roles_required('admin')
def manage_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        full_name = request.form.get('full_name').strip()
        username = request.form.get('username').strip()
        password = request.form.get('password')
        phone = request.form.get('phone').strip()
        role = request.form.get('role')
        order_number = request.form.get('order_number')
        order_date = request.form.get('order_date') or None
        org_id = request.form.get('organization_id')

        hashed_pw = generate_password_hash(password)

        try:
            cursor.execute("""
                INSERT INTO users (full_name, username, password_hash, phone, order_number, order_date, role, is_verified) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
            """, (full_name, username, hashed_pw, phone, order_number, order_date, role))
            
            user_id = cursor.lastrowid
            if org_id:
                cursor.execute("INSERT INTO user_organizations (user_id, organization_id) VALUES (%s, %s)", (user_id, org_id))
            
            conn.commit()
            flash('Ulanyjy üstünlikli hasaba alyndy', 'success')
        except Exception as e:
            flash(f'Ýalňyşlyk: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_users'))

    cursor.execute("""
        SELECT u.*, o.name as org_name, o.id as org_id
        FROM users u
        LEFT JOIN user_organizations uo ON u.id = uo.user_id AND uo.is_main = 1
        LEFT JOIN organizations o ON uo.organization_id = o.id
        ORDER BY u.created_at DESC
    """)
    users = cursor.fetchall()

    cursor.execute("SELECT id, name FROM organizations WHERE status = 'active' ORDER BY name")
    organizations = cursor.fetchall()
    
    conn.close()
    return render_template('admin/users.html', users=users, organizations=organizations)



@admin_bp.route('/users/update', methods=['POST'])
@roles_required('admin')
def update_user():
    user_id = request.form.get('id')
    full_name = request.form.get('full_name').strip()
    username = request.form.get('username').strip()
    phone = request.form.get('phone').strip()
    role = request.form.get('role')
    order_number = request.form.get('order_number')
    order_date = request.form.get('order_date') or None
    org_id = request.form.get('organization_id')
    new_password = request.form.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    if new_password:
        hashed_pw = generate_password_hash(new_password)
        cursor.execute("""
            UPDATE users SET full_name=%s, username=%s, phone=%s, role=%s, 
            order_number=%s, order_date=%s, password_hash=%s WHERE id=%s
        """, (full_name, username, phone, role, order_number, order_date, hashed_pw, user_id))
    else:
        cursor.execute("""
            UPDATE users SET full_name=%s, username=%s, phone=%s, role=%s, 
            order_number=%s, order_date=%s WHERE id=%s
        """, (full_name, username, phone, role, order_number, order_date, user_id))

    cursor.execute("DELETE FROM user_organizations WHERE user_id=%s", (user_id,))
    if org_id:
        cursor.execute("INSERT INTO user_organizations (user_id, organization_id) VALUES (%s, %s)", (user_id, org_id))
    
    conn.commit()
    conn.close()
    flash('Ulanyjy maglumatlary täzelendi', 'success')
    return redirect(url_for('admin.manage_users'))



@admin_bp.route('/users/toggle/<int:id>', methods=['POST'])
@roles_required('admin')
def toggle_user_status(id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT status FROM users WHERE id=%s", (id,))
        u = cursor.fetchone()
        if u:
            
            new_status = 'blocked' if u['status'] == 'active' else 'active'
            cursor.execute("UPDATE users SET status=%s WHERE id=%s", (new_status, id))
            conn.commit()
            flash(f'Ulanyjynyň ýagdaýy üýtgedildi: {new_status}', 'info')
    conn.close()
    return redirect(url_for('admin.manage_users'))



@admin_bp.route('/program-reports', methods=['GET', 'POST'])
@roles_required('admin')
def manage_program_reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        program_id = request.form.get('program_id')
        report_type = request.form.get('report_type')

        try:
            cursor.execute("""
                INSERT INTO program_reports (program_id, report_type) 
                VALUES (%s, %s)
            """, (program_id, report_type))
            conn.commit()
            flash('Hasabatlylyk düzümi goşuldy', 'success')
        except Exception as e:
            flash(f'Ýalňyşlyk: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_program_reports'))

    
    cursor.execute("""
        SELECT pr.*, p.name as program_name 
        FROM program_reports pr
        JOIN programs p ON pr.program_id = p.id
        ORDER BY p.name ASC
    """)
    reports = cursor.fetchall()

    
    cursor.execute("SELECT id, name FROM programs WHERE status = 'active'")
    programs = cursor.fetchall()

    conn.close()
    return render_template('admin/program_reports.html', reports=reports, programs=programs)




@admin_bp.route('/program-reports/update', methods=['POST'])
@roles_required('admin')
def update_program_report():
    report_id = request.form.get('id')
    program_id = request.form.get('program_id')
    report_type = request.form.get('report_type')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE program_reports SET program_id=%s, report_type=%s WHERE id=%s
    """, (program_id, report_type, report_id))
    conn.commit()
    conn.close()
    flash('Maglumat täzelendi', 'success')
    return redirect(url_for('admin.manage_program_reports'))




@admin_bp.route('/program-reports/toggle/<int:id>', methods=['POST'])
@roles_required('admin')
def toggle_report_status(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM program_reports WHERE id=%s", (id,))
    r = cursor.fetchone()
    if r:
        new_status = 'blocked' if r['status'] == 'active' else 'active'
        cursor.execute("UPDATE program_reports SET status=%s WHERE id=%s", (new_status, id))
        conn.commit()
    conn.close()
    return redirect(url_for('admin.manage_program_reports'))