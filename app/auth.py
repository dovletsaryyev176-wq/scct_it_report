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



def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') not in ['user']:
            flash('Bu bölüme girmek üçin öz hasabyňyza giriň', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def company_user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'company_user':
            flash('Bu bölüme girmek üçin company_user hökmünde giriň', 'danger')
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
           
            cursor.execute("""
                SELECT u.*, uo.organization_id 
                FROM users u
                LEFT JOIN user_organizations uo ON u.id = uo.user_id AND uo.is_main = 1
                WHERE u.username = %s
            """, (username,))
            user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            
            if user['status'] == 'blocked':
                flash('Siziň hasabyňyz bloklanan. Adminstrator bilen habarlaşyň.', 'danger')
                return redirect(url_for('auth.login'))

            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name'] 
            session['role'] = user['role']
            session['org_id'] = user['organization_id']

            flash(f'Salam, {user["full_name"]}!', 'success')

            
            if user['role'] == 'admin':
                return redirect(url_for('admin.manage_cities'))
            elif user['role'] == 'company_user':
                return redirect(url_for('company_user.programs'))
            else:
                return redirect(url_for('client.dashboard'))
        
        flash('Nädogry ulanyjy ady ýa-da gizlin belgisi', 'danger')
        
    return render_template('login.html')



@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Siz ulgamdan üstünlikli çykdyňyz', 'info')
    return redirect(url_for('auth.login'))