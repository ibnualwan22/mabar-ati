from flask import render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import login_user, logout_user, current_user, login_required
from collections import defaultdict
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

import requests
from . import lapangan_bp
from app import db
from app.models import BarangSantri, Santri, User, Bus, Pendaftaran, Absen, Role, Rombongan
from app.admin.forms import BarangForm, LoginForm, LokasiBusForm, HubungkanPerangkatForm
from app.admin.routes import get_active_edisi, log_activity

import os
import secrets
from werkzeug.utils import secure_filename


@lapangan_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.role.name == 'Korlapda':
        return redirect(url_for('lapangan.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            
            # Arahkan berdasarkan peran
            if user.role.name == 'Korlapda':
                return redirect(url_for('lapangan.dashboard'))
            elif user.role.name == 'Sarpras':
                return redirect(url_for('lapangan.barang_dashboard'))
            else:
                # Jika peran tidak sesuai, logout dan beri pesan
                logout_user()
                flash('Peran Anda tidak diizinkan untuk mengakses halaman ini.', 'danger')
                return redirect(url_for('lapangan.login'))
        else:
            flash('Username atau password salah.', 'danger')
            
    return render_template('login_lapangan.html', form=form)

@lapangan_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('lapangan.login'))

@lapangan_bp.route('/')
@login_required
def dashboard():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)

    bus = Bus.query.get_or_404(current_user.bus_id)
    
    # --- LOGIKA PENGECEKAN BARU ---
    # Jika bus ini belum punya ID Traccar, alihkan ke halaman untuk menghubungkan
    # if not bus.traccar_device_id:
    #     flash("Perangkat Anda belum terhubung. Silakan hubungkan bus Anda dengan perangkat Traccar.", "info")
    #     return redirect(url_for('lapangan.hubungkan_perangkat'))
    
    active_edisi = get_active_edisi()
    
    peserta_pulang = []
    peserta_kembali = []
    grouped_pulang = defaultdict(list)
    grouped_kembali = defaultdict(list)
    absen_map = {}
    checkpoints_pulang = []
    checkpoints_kembali = []

    if active_edisi and bus.rombongan.edisi_id == active_edisi.id:
        peserta_pulang = Pendaftaran.query.options(joinedload(Pendaftaran.santri)).filter_by(bus_pulang_id=bus.id).all()
        peserta_kembali = Pendaftaran.query.options(joinedload(Pendaftaran.santri)).filter_by(bus_kembali_id=bus.id).all()

        for p in peserta_pulang:
            grouped_pulang[p.titik_turun].append(p)
            
        for p in peserta_kembali:
            grouped_kembali[p.santri.kabupaten].append(p)

        pendaftar_ids = [p.id for p in peserta_pulang] + [p.id for p in peserta_kembali]
        absen_tercatat = Absen.query.filter(Absen.pendaftaran_id.in_(pendaftar_ids)).all()
        absen_map = {f"{absen.pendaftaran_id}-{absen.nama_absen}": absen.status for absen in absen_tercatat}
        
        checkpoints_pulang = [c[0] for c in db.session.query(Absen.nama_absen).filter(Absen.pendaftaran_id.in_(pendaftar_ids), Absen.nama_absen.like('%(Pulang)%')).distinct().all()]
        checkpoints_kembali = [c[0] for c in db.session.query(Absen.nama_absen).filter(Absen.pendaftaran_id.in_(pendaftar_ids), Absen.nama_absen.like('%(Kembali)%')).distinct().all()]
    else:
        flash("Saat ini tidak ada edisi perpulangan yang aktif untuk bus Anda.", "info")

    return render_template('dashboard_lapangan.html',
                           bus=bus,
                           grouped_pulang=grouped_pulang,
                           grouped_kembali=grouped_kembali,
                           absen_map=absen_map,
                           checkpoints_pulang=checkpoints_pulang,
                           checkpoints_kembali=checkpoints_kembali)

@lapangan_bp.route('/tambah-checkpoint', methods=['POST'])
@login_required
def tambah_checkpoint_absen():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)
    
    nama_absen_baru = request.form.get('nama_absen_baru')
    arah = request.form.get('arah_perjalanan')
    
    if not nama_absen_baru or not arah:
        flash("Nama checkpoint tidak boleh kosong.", "danger")
        return redirect(url_for('lapangan.dashboard'))

    pendaftar_ids = []
    if arah == 'Pulang':
        pendaftar_ids = [p.id for p in Pendaftaran.query.filter_by(bus_pulang_id=current_user.bus_id).all()]
    else: # Kembali
        pendaftar_ids = [p.id for p in Pendaftaran.query.filter_by(bus_kembali_id=current_user.bus_id).all()]

    nama_absen_final = f"{nama_absen_baru} ({arah})"

    for p_id in pendaftar_ids:
        new_absen = Absen(
            pendaftaran_id=p_id,
            nama_absen=nama_absen_final,
            status="Tidak Hadir",
            dicatat_oleh_id=current_user.id
        )
        db.session.add(new_absen)
    
    db.session.commit()
    flash(f'Checkpoint absen "{nama_absen_baru}" berhasil dibuat.', 'success')
    return redirect(url_for('lapangan.dashboard'))

@lapangan_bp.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403

@lapangan_bp.route('/simpan-absen', methods=['POST'])
@login_required
def simpan_absen():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)

    form_data = request.form.to_dict(flat=False)
    
    for key, pendaftar_ids_hadir in form_data.items():
        if key.startswith('hadir-'):
            nama_absen = key.replace('hadir-', '')
            
            manifest_ids = []
            if 'Pulang' in nama_absen:
                 manifest_ids = [p.id for p in Pendaftaran.query.filter_by(bus_pulang_id=current_user.bus_id).all()]
            else: # Kembali
                 manifest_ids = [p.id for p in Pendaftaran.query.filter_by(bus_kembali_id=current_user.bus_id).all()]

            for p_id in manifest_ids:
                Absen.query.filter_by(pendaftaran_id=p_id, nama_absen=nama_absen).delete()
                status = "Hadir" if str(p_id) in pendaftar_ids_hadir else "Tidak Hadir"
                new_absen = Absen(pendaftaran_id=p_id, nama_absen=nama_absen, status=status, dicatat_oleh_id=current_user.id)
                db.session.add(new_absen)
    
    db.session.commit()
    flash('Data absensi berhasil disimpan.', 'success')
    return redirect(url_for('lapangan.dashboard'))

@lapangan_bp.route('/lokasi', methods=['GET', 'POST'])
@login_required
def update_lokasi():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)
    
    bus = Bus.query.get_or_404(current_user.bus_id)
    form = LokasiBusForm(obj=bus)

    if form.validate_on_submit():
        bus.gmaps_share_url = form.gmaps_share_url.data
        db.session.commit()
        flash('Lokasi bus berhasil diperbarui!', 'success')
        # Catat di log aktivitas
        log_activity('Update', 'Lokasi Bus', f"Korlapda '{current_user.username}' memperbarui lokasi untuk bus '{bus.nama_armada} - {bus.nomor_lambung or bus.plat_nomor}'")

    return render_template('update_lokasi.html', form=form, bus=bus)

@lapangan_bp.route('/hubungkan', methods=['GET', 'POST'])
@login_required
def hubungkan_perangkat():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)
        
    bus = Bus.query.get_or_404(current_user.bus_id)
    form = HubungkanPerangkatForm(obj=bus) # Gunakan obj agar field terisi jika sudah ada

    if form.validate_on_submit():
        device_id_input = form.traccar_device_id.data

        # --- LOGIKA VALIDASI BARU KE SERVER TRACCAR ---
        try:
            TRACCAR_URL = current_app.config.get('TRACCAR_URL')
            TRACCAR_TOKEN = current_app.config.get('TRACCAR_TOKEN')

            if not TRACCAR_URL or not TRACCAR_TOKEN:
                flash('Konfigurasi server Traccar belum diatur oleh admin.', 'danger')
                return redirect(url_for('lapangan.hubungkan_perangkat'))

            # 1. Dapatkan session cookie dari Traccar
            session_res = requests.get(f"{TRACCAR_URL}/api/session?token={TRACCAR_TOKEN}", timeout=10)
            session_res.raise_for_status()
            cookies = session_res.cookies

            # 2. Dapatkan daftar semua perangkat dari Traccar
            devices_res = requests.get(f"{TRACCAR_URL}/api/devices", cookies=cookies, timeout=10)
            devices_res.raise_for_status()
            all_devices = devices_res.json()

            # 3. Cek apakah ID yang dimasukkan ada di dalam daftar
            device_found = any(str(d.get('uniqueId')) == str(device_id_input) for d in all_devices)

            if not device_found:
                flash(f"Error: ID Perangkat '{device_id_input}' tidak ditemukan di server Traccar. Pastikan ID sudah benar.", 'danger')
                return redirect(url_for('lapangan.hubungkan_perangkat'))

        except requests.exceptions.RequestException as e:
            flash(f"Gagal terhubung ke server Traccar untuk validasi. Coba lagi nanti.", "danger")
            return redirect(url_for('lapangan.hubungkan_perangkat'))
        # --- AKHIR VALIDASI BARU ---
        
        # Cek apakah ID ini sudah digunakan oleh bus lain di sistem kita
        existing_bus = Bus.query.filter(Bus.id != bus.id, Bus.traccar_device_id == device_id_input).first()
        if existing_bus:
            flash(f"Error: ID Perangkat {device_id_input} sudah digunakan oleh bus lain.", "danger")
            return redirect(url_for('lapangan.hubungkan_perangkat'))

        bus.traccar_device_id = device_id_input
        db.session.commit()
        
        log_activity('Update', 'Traccar', f"Korlapda '{current_user.username}' menghubungkan bus '{bus.nama_armada}' dengan Traccar ID: {device_id_input}")
        
        flash("Perangkat berhasil terhubung! Anda sekarang bisa mulai melacak dan melakukan absensi.", "success")
        return redirect(url_for('lapangan.dashboard'))

    return render_template('hubungkan_perangkat.html', form=form, bus=bus)


@lapangan_bp.route('/barang')
@login_required
def barang_dashboard():
    if current_user.role.name != 'Sarpras':
        abort(403)
    
    # Ambil filter dari URL
    nama_filter = request.args.get('nama', '')
    perjalanan_filter = request.args.get('perjalanan', '') # 'pulang' atau 'kembali'

    # Ambil rombongan yang dikelola oleh user Sarpras
    managed_rombongan_ids = [r.id for r in current_user.active_managed_rombongan]
    if not managed_rombongan_ids:
        return render_template('barang_dashboard.html', pendaftar_list=[], perjalanan_filter=perjalanan_filter)

    # Query dasar untuk pendaftar di rombongan yang dikelola
    query = Pendaftaran.query.join(Santri).filter(
        or_(
            Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
            Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
        )
    )

    # Terapkan filter perjalanan
    if perjalanan_filter == 'pulang':
        query = query.filter(Pendaftaran.status_pulang != 'Tidak Ikut')
    elif perjalanan_filter == 'kembali':
        query = query.filter(Pendaftaran.status_kembali != 'Tidak Ikut')

    # Terapkan filter nama
    if nama_filter:
        query = query.filter(Santri.nama.ilike(f'%{nama_filter}%'))
        
    pendaftar_list = query.order_by(Santri.nama).all()

    return render_template('barang_dashboard.html', 
                           pendaftar_list=pendaftar_list, 
                           perjalanan_filter=perjalanan_filter)


# --- HALAMAN UNTUK MENGELOLA (INPUT/EDIT) BARANG ---
@lapangan_bp.route('/barang/kelola/<int:pendaftaran_id>', methods=['GET', 'POST'])
@login_required
def kelola_barang(pendaftaran_id):
    if current_user.role.name != 'Sarpras':
        abort(403)
    
    pendaftaran = Pendaftaran.query.get_or_404(pendaftaran_id)
    # Ambil data barang jika sudah ada, jika tidak, buat objek baru
    barang = pendaftaran.barang[0] if pendaftaran.barang else BarangSantri(pendaftaran_id=pendaftaran_id)
    
    form = BarangForm(obj=barang)

    if form.validate_on_submit():
        barang.jumlah_koli = form.jumlah_koli.data
        barang.dicatat_oleh_id = current_user.id
        
        # Logika untuk menyimpan file foto
        if form.foto_barang.data:
            # Hapus foto lama jika ada
            if barang.foto_barang:
                try:
                    os.remove(os.path.join(current_app.root_path, '..', current_app.config['UPLOAD_FOLDER'], barang.foto_barang))
                except FileNotFoundError:
                    pass # Abaikan jika file tidak ditemukan

            # Simpan foto baru dan update nama filenya
            filename = save_picture(form.foto_barang.data)
            barang.foto_barang = filename

        if not barang.id: # Jika ini data baru
            db.session.add(barang)
            
        db.session.commit()
        flash(f"Data barang untuk {pendaftaran.santri.nama} berhasil disimpan.", "success")
        return redirect(url_for('lapangan.barang_dashboard'))

    return render_template('kelola_barang.html', form=form, pendaftaran=pendaftaran, barang=barang)


# --- AKSI UNTUK ABSENSI BARANG ---
@lapangan_bp.route('/barang/absen/<int:barang_id>', methods=['POST'])
@login_required
def absen_barang(barang_id):
    if current_user.role.name != 'Sarpras':
        abort(403)
        
    barang = BarangSantri.query.get_or_404(barang_id)
    
    # Toggle status absensi
    if barang.status_absensi == 'Belum Diabsen':
        barang.status_absensi = 'Sudah Diabsen'
    else:
        barang.status_absensi = 'Belum Diabsen'
        
    db.session.commit()
    flash(f"Status absensi barang untuk {barang.pendaftaran.santri.nama} diubah.", "info")
    return redirect(url_for('lapangan.barang_dashboard'))

def save_picture(form_picture):
    """Menyimpan file gambar yang diunggah dengan nama acak."""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, '..', current_app.config['UPLOAD_FOLDER'], picture_fn)

    # Pastikan direktori ada
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)

    form_picture.save(picture_path)
    return picture_fn