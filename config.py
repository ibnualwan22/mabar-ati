import os
from dotenv import load_dotenv

# Baris ini akan mencari file .env dan memuat variabelnya
load_dotenv()

class Config:
    """Konfigurasi dasar."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default-secret-key-for-emergency'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'app/static/uploads/barang'
    TRACCAR_URL = "https://traccar.amtsilatipusat.com" # Ganti jika URL Anda berbeda
    TRACCAR_TOKEN = "RzBFAiAQcc1IbBoWuFRQbnM6W21yE_iUEE2tGR7kuSVejbJtuwIhALraY2GnGENCvllH0I5dLQAioz-4ABWjhA2PABaSxM3-eyJ1IjoyLCJlIjoiMjAyNS0xMC0xOVQxNzowMDowMC4wMDArMDA6MDAifQ"
    API_INDUK_URL = "https://sigap.amtsilatipusat.com/api/student"

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