from flask import Blueprint

admin_bp = Blueprint('admin', __name__, template_folder='templates')

# Kita import routes di sini agar terdeteksi oleh aplikasi
from . import routes