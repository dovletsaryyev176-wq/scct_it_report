from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.auth import roles_required
from app import get_db_connection 


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


#Welaýatlar barada maglumatlar we täze welaýaty goşmak
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

    # JOIN для получения названия велаята
    cursor.execute("""
        SELECT d.*, c.name as city_name 
        FROM districts d 
        JOIN cities c ON d.city_id = c.id 
        ORDER BY d.created_at DESC
    """)
    districts = cursor.fetchall()

    # Список активных велаятов для выбора в модалке
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
            # updated_at обновится сам на стороне MySQL
            cursor.execute("UPDATE districts SET name = %s, city_id = %s WHERE id = %s", 
                           (name, city_id, dist_id))
            conn.commit()
        conn.close()
        flash('Etrap maglumatlary täzelendi', 'success')
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
            flash(f'Etrabyň statusy "{new_status}" edildi', 'info')
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

    # Получаем список организаций со всеми связями
    cursor.execute("""
        SELECT o.*, c.name as city_name, d.name as district_name, p.name as parent_name
        FROM organizations o
        JOIN cities c ON o.city_id = c.id
        JOIN districts d ON o.district_id = d.id
        LEFT JOIN organizations p ON o.parent_id = p.id
        ORDER BY o.created_at DESC
    """)
    orgs = cursor.fetchall()

    # Списки для выпадающих меню в модалке
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
            flash(f'Edaranyň statusy "{new_status}" edildi', 'info')
    conn.close()
    return redirect(url_for('admin.manage_organizations'))