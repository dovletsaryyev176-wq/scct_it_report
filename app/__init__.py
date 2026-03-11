from flask import Flask
import pymysql
from config import Config
from flask import Flask, redirect, url_for

def create_app():
    app = Flask(__name__)
    
    app.config.from_object(Config)

    from app.admin.routes import admin_bp
    from app.auth import auth_bp
    
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app

def get_db_connection():
    return pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

