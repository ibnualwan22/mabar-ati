from flask import render_template, flash, redirect, url_for, jsonify, current_app
from sqlalchemy.orm import joinedload
import requests

from . import main_bp
from app.models import Rombongan, Edisi, Bus, Pendaftaran, Tarif
from app.admin.routes import get_active_edisi

@main_bp.route('/')
def index():
    active_edisi = get_active_edisi()
    semua_rombongan = []
    if active_edisi:
        semua_rombongan = Rombongan.query.options(
            joinedload(Rombongan.tarifs),
            joinedload(Rombongan.buses)
        ).filter_by(edisi_id=active_edisi.id).order_by(Rombongan.nama_rombongan).all()
        
    return render_template('index.html', 
                           active_edisi=active_edisi,
                           semua_rombongan=semua_rombongan)

@main_bp.route('/informasi')
def informasi_perpulangan():
    active_edisi = get_active_edisi()
    return render_template('informasi.html', active_edisi=active_edisi)

# Pastikan decorator ini ada di atas fungsi lacak_bus
@main_bp.route('/lacak-bus/<int:bus_id>')
def lacak_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    if not bus.traccar_device_id:
        flash("Pelacakan tidak tersedia untuk bus ini.", "warning")
        return redirect(url_for('main.index'))
        
    return render_template('peta_pelacakan.html', bus=bus)

# Pastikan decorator ini ada di atas fungsi traccar_proxy
@main_bp.route('/api/traccar/positions/<string:device_id>')
def traccar_proxy(device_id):
    TRACCAR_URL = current_app.config.get('TRACCAR_URL')
    TOKEN = current_app.config.get('TRACCAR_TOKEN')
    
    if not TRACCAR_URL or not TOKEN:
        return jsonify({"error": "Konfigurasi Traccar tidak ditemukan"}), 500
    
    try:
        session_res = requests.get(f"{TRACCAR_URL}/api/session?token={TOKEN}", timeout=10)
        session_res.raise_for_status()
        cookies = session_res.cookies

        # Cari berdasarkan uniqueId, bukan id internal Traccar
        pos_res = requests.get(f"{TRACCAR_URL}/api/positions?uniqueId={device_id}", cookies=cookies, timeout=10)
        pos_res.raise_for_status()
        
        return jsonify(pos_res.json())
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 404:
            return jsonify({"error": "Device not found on Traccar server"}), 404
        return jsonify({"error": str(e)}), 500