import os

# === KONFIGURASI DATABASE PRODUKSI ===
PROD_DB_IP = '165.22.106.176'
PROD_DB_USER = 'alan'
PROD_DB_PASS = 'alan'
PROD_DB_PORT = '3306'
PROD_DB_NAME = 'mabar_ati_prod'

# === KONFIGURASI DATABASE DEVELOPMENT (LOKAL) ===
DEV_DB_HOST = '165.22.106.176'
DEV_DB_USER = 'alan'
DEV_DB_PASS = 'alan'
DEV_DB_PORT = '3306'
DEV_DB_NAME = 'mabar_ati_dev'


class Config:
    """Konfigurasi dasar."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-yang-sulit-ditebak'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Konfigurasi untuk Development (MySQL Lokal)."""
    DEBUG = True
    # Menggunakan database MySQL di komputer lokal Anda
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DEV_DB_USER}:{DEV_DB_PASS}@{DEV_DB_HOST}:{DEV_DB_PORT}/{DEV_DB_NAME}"
    MODE = 'Development'

class ProductionConfig(Config):
    """Konfigurasi untuk Produksi."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{PROD_DB_USER}:{PROD_DB_PASS}@{PROD_DB_IP}:{PROD_DB_PORT}/{PROD_DB_NAME}"
    MODE = 'Produksi'

# Dictionary untuk mempermudah pemilihan konfigurasi
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}