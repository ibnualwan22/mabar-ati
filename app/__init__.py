from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name # Import dictionary config
from flask_migrate import Migrate # PASTIKAN BARIS INI ADA
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import locale
from datetime import timezone, timedelta # <-- 1. Tambahkan import ini



# Inisialisasi SQLAlchemy
db = SQLAlchemy()
migrate = Migrate() # <- Tambahkan ini
bcrypt = Bcrypt() # <-- Inisialisasi Bcrypt
login_manager = LoginManager()

# Arahkan user ke halaman login jika mencoba akses halaman terproteksi
login_manager.login_view = 'admin.login' 
# Pesan yang muncul saat redirect
login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'
login_manager.login_message_category = 'info'


def format_datetime_wib(value, format='%d %B %Y %H:%M:%S'):
    """Format a datetime object to WIB with Indonesian month names."""
    if value is None:
        return ""
    
    # Anggap waktu dari DB adalah UTC, lalu beri informasi zona waktu
    utc_time = value.replace(tzinfo=timezone.utc)
    
    # Buat zona waktu WIB (UTC+7)
    wib_tz = timezone(timedelta(hours=7))
    
    # Konversi waktu ke zona WIB
    wib_time = utc_time.astimezone(wib_tz)
    
    try:
        # Atur locale ke Bahasa Indonesia untuk nama bulan
        locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '') # Fallback
    
    return wib_time.strftime(format)

def format_date_wib(value, format='%d %B %Y'):
    """Format a date object with Indonesian month names."""
    if value is None:
        return ""
    try:
        locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    
    return value.strftime(format)

def create_app(config_name):
    app = Flask(__name__)
    app.jinja_env.add_extension('jinja2.ext.do')
    app.config.from_object(config_by_name[config_name])
    app.jinja_env.filters['datetime_wib'] = format_datetime_wib
    app.jinja_env.filters['date_wib'] = format_date_wib


    
    
    db.init_app(app)
    migrate.init_app(app, db) # <- Tambahkan ini, hubungkan app dan db
    bcrypt.init_app(app) # <-- Hubungkan bcrypt dengan app
    login_manager.init_app(app)


    # --- PENAMBAHAN BARU ---
    # Import dan daftarkan Admin Blueprint
    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    # -----------------------
    from .lapangan import lapangan_bp
    app.register_blueprint(lapangan_bp, url_prefix='/lapangan')

    from .main import main_bp
    app.register_blueprint(main_bp)

    # Contoh route sederhana untuk testing
    @app.route('/')
    def index():
        # Menampilkan mode yang sedang berjalan
        mode = app.config['MODE']
        return f'<h1>Selamat Datang di Mabar Ati</h1><p>Mudik Akbar Santri Amtsilati</p>'

    return app