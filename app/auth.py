from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Ulgama dolandyryjy hökmünde giriň', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Awtorizasiýany hökman ýerine ýetirmeli', 'danger')
                return redirect(url_for('auth.login'))
            if session.get('role') not in roles:
                flash('Rugsat berilmedik', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from app import get_db_connection
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Salam, {username}!', 'success')
            return redirect(url_for('admin.manage_cities'))
        
        flash('Nädogry ulanyjy ady ýa-da gizlin belgisi', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Siz ulgamdan üstünikli çykdyňyz', 'info')
    return redirect(url_for('auth.login'))

