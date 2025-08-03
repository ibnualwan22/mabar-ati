from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name # Import dictionary config
from flask_migrate import Migrate # PASTIKAN BARIS INI ADA


# Inisialisasi SQLAlchemy
db = SQLAlchemy()
migrate = Migrate() # <- Tambahkan ini


def create_app(config_name):
    """
    Function factory untuk membuat aplikasi Flask.
    """
    app = Flask(__name__)

    # Memuat konfigurasi dari objek config
    app.config.from_object(config_by_name[config_name])

    # Menginisialisasi database dengan aplikasi
    db.init_app(app)
    migrate.init_app(app, db) # <- Tambahkan ini, hubungkan app dan db


    # --- PENAMBAHAN BARU ---
    # Import dan daftarkan Admin Blueprint
    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    # -----------------------

    # Contoh route sederhana untuk testing
    @app.route('/')
    def index():
        # Menampilkan mode yang sedang berjalan
        mode = app.config['MODE']
        return f'<h1>Selamat Datang di Mabar-Ati!</h1><p>Mode saat ini: <strong>{mode}</strong></p>'

    return app