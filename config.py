import os
from dotenv import load_dotenv

# Baris ini akan mencari file .env dan memuat variabelnya
load_dotenv()

class Config:
    """Konfigurasi dasar."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default-secret-key-for-emergency'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Konfigurasi untuk Development (MySQL Lokal)."""
    DEBUG = True
    
    # Membaca variabel database development dari environment (.env)
    USER = os.environ.get('DEV_DB_USER')
    PASS = os.environ.get('DEV_DB_PASS')
    HOST = os.environ.get('DEV_DB_HOST')
    PORT = os.environ.get('DEV_DB_PORT')
    NAME = os.environ.get('DEV_DB_NAME')

    SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{USER}:{PASS}@{HOST}:{PORT}/{NAME}"
    MODE = 'Development'

class ProductionConfig(Config):
    """Konfigurasi untuk Produksi."""
    DEBUG = False

    # Membaca variabel database produksi dari environment (.env)
    USER = os.environ.get('PROD_DB_USER')
    PASS = os.environ.get('PROD_DB_PASS')
    HOST = os.environ.get('PROD_DB_HOST')
    PORT = os.environ.get('PROD_DB_PORT')
    NAME = os.environ.get('PROD_DB_NAME')

    SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{USER}:{PASS}@{HOST}:{PORT}/{NAME}"
    MODE = 'Produksi'

# Dictionary untuk mempermudah pemilihan konfigurasi
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}