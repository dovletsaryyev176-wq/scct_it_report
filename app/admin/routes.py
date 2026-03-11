from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.auth import roles_required
from app import get_db_connection 


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

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
            flash('Täze şäher hasaba alyndy', 'success')
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
            flash(f'Ýagdaýy üýtgedildi - {new_status}', 'info')
    conn.close()
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
            flash(f'Район "{name}" добавлен', 'success')
        return redirect(url_for('admin.manage_districts'))

    cursor.execute("""
        SELECT d.*, c.name as city_name 
        FROM districts d 
        JOIN cities c ON d.city_id = c.id 
        ORDER BY d.created_at DESC
    """)
    districts = cursor.fetchall()

    cursor.execute("SELECT id, name FROM cities WHERE status = 'active'")
    cities = cursor.fetchall()
    
    conn.close()
    return render_template('admin/districts.html', districts=districts, cities=cities)

