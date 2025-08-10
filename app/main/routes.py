from flask import render_template
from . import main_bp
from app.models import Rombongan, Edisi
from app.admin.routes import get_active_edisi

from sqlalchemy.orm import joinedload

@main_bp.route('/')
def index():
    active_edisi = get_active_edisi()
    semua_rombongan = []
    if active_edisi:
        # Gunakan joinedload untuk mengambil data terkait (tarifs, buses) dalam satu query
        semua_rombongan = Rombongan.query.options(
            joinedload(Rombongan.tarifs),
            joinedload(Rombongan.buses)
        ).filter_by(edisi=active_edisi).order_by(Rombongan.nama_rombongan).all()
        
    return render_template('index.html', 
                           active_edisi=active_edisi,
                           semua_rombongan=semua_rombongan)

@main_bp.route('/informasi')
def informasi_perpulangan():
    active_edisi = get_active_edisi()
    # Anda bisa mengambil data lain yang relevan di sini jika perlu
    return render_template('informasi.html', active_edisi=active_edisi)