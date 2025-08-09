from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name # Import dictionary config
from flask_migrate import Migrate # PASTIKAN BARIS INI ADA
from flask_login import LoginManager
from flask_bcrypt import Bcrypt


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


def create_app(config_name):
    app = Flask(__name__)
    app.jinja_env.add_extension('jinja2.ext.do')
    app.config.from_object(config_by_name[config_name])
    
    
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

    # Contoh route sederhana untuk testing
    @app.route('/')
    def index():
        # Menampilkan mode yang sedang berjalan
        mode = app.config['MODE']
        return f'<h1>Selamat Datang di Mabar Ati</h1><p>Mudik Akbar Santri Amtsilati</p>'

    return app