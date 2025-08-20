from . import admin_bp
from flask import render_template, redirect, url_for, flash, request, jsonify, abort, Response, send_file, current_app
from app.models import ActivityLog, Rombongan, Tarif, Santri, Pendaftaran, Izin, Partisipan, Transaksi, User, Edisi, Bus, Role, Wisuda
from app.admin.forms import ChangePasswordForm, ImportWisudaForm, KonfirmasiSetoranForm, PengeluaranBusForm, RombonganForm, SantriEditForm, PendaftaranForm, PendaftaranEditForm, IzinForm, PartisipanForm, PartisipanEditForm, LoginForm, TransaksiForm, UserForm, UserEditForm, EdisiForm, BusForm, KorlapdaForm, WisudaForm
from app import db, login_manager
import json, requests
from collections import defaultdict
from sqlalchemy import update, text, or_, and_, func
from datetime import date, datetime
from flask_login import login_user, logout_user, current_user, login_required
from functools import wraps
from sqlalchemy.orm import joinedload, selectinload # <-- Tambahkan import ini di atas
from datetime import date, datetime # Pastikan datetime diimpor
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
import locale
import pandas as pd




def check_and_update_expired_izin():
    """Mencari izin yang kadaluwarsa, mengubah statusnya, dan mengembalikan status santri."""
    today = date.today()
    # Cari izin yang statusnya 'Aktif' dan sudah lewat tanggal
    expired_izins = Izin.query.filter(Izin.status == 'Aktif', Izin.tanggal_berakhir < today).all()
    
    if not expired_izins:
        return

    for izin in expired_izins:
        santri = izin.santri
        if santri and santri.status_santri == 'Izin':
            santri.status_santri = 'Aktif'
            izin.status = 'Selesai' # <-- Ubah status, bukan hapus
            log_activity('Update Otomatis', 'Perizinan', f"Izin untuk '{santri.nama}' telah berakhir.")

    db.session.commit()
    print(f"Update otomatis: {len(expired_izins)} status izin telah diperbarui.")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Di app/admin/routes.py
@admin_bp.before_request
def require_login():
    # Cek jika endpoint yang diminta BUKAN halaman login dan user BELUM login
    if request.endpoint and 'admin.' in request.endpoint and request.endpoint != 'admin.login':
        if not current_user.is_authenticated:
            return redirect(url_for('admin.login', next=request.url))

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Jika user sudah login, arahkan ke dashboard
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Cari user di database berdasarkan username
        user = User.query.filter_by(username=form.username.data).first()
        
        # Cek apakah user ada dan passwordnya cocok
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            # Arahkan ke halaman yang tadinya ingin diakses, atau ke dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin.dashboard'))
        else:
            flash('Username atau password salah.', 'danger')
            
    return render_template('login.html', form=form)

# Di app/admin/routes.py
@admin_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('admin.login'))

def role_required(*roles): # Terima beberapa nama peran
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('admin.login', next=request.url))
            if current_user.role.name not in roles:
                abort(403) # Forbidden - Akses Ditolak
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@admin_bp.route('/users')
@login_required
@role_required('Korpus')
def manajemen_user():
    users = User.query.all()
    return render_template('manajemen_user.html', users=users)
@admin_bp.route('/users/tambah', methods=['GET', 'POST'])
@login_required
@role_required('Korpus')
def tambah_user():
    form = UserForm()
    if form.validate_on_submit():
        # Buat objek user terlebih dahulu
        new_user = User(
            username=form.username.data,
            role=form.role.data
        )
        # Set password-nya
        new_user.set_password(form.password.data)
        
        # Tentukan rombongan yang dikelola berdasarkan peran
        if form.role.data.name == 'Korwil':
            new_user.managed_rombongan = form.managed_rombongan_multi.data
        elif form.role.data.name == 'Korda':
            # Pastikan ada data sebelum dimasukkan ke list
            if form.managed_rombongan_single.data:
                new_user.managed_rombongan = [form.managed_rombongan_single.data]
            else:
                new_user.managed_rombongan = []
        else: # Untuk peran lain, kosongkan
            new_user.managed_rombongan = []
            
        # Simpan user baru ke database
        db.session.add(new_user)
        log_activity('Tambah', 'User', f"Menambahkan user baru: '{form.username.data}' dengan peran '{form.role.data.name}'")
        db.session.commit()
        
        flash('User baru berhasil ditambahkan.', 'success')
        return redirect(url_for('admin.manajemen_user'))
        
    return render_template('form_user.html', form=form, title="Tambah User Baru")


@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    # Saat GET, form diisi dengan data awal dari 'user'
    form = UserEditForm(obj=user)
    
    # Saat POST, kita proses datanya
    if form.validate_on_submit():
        user.username = form.username.data
        user.role = form.role.data
        
        # Tentukan rombongan yang dikelola berdasarkan peran
        if form.role.data.name == 'Korwil':
            user.managed_rombongan = form.managed_rombongan_multi.data
        elif form.role.data.name == 'Korda':
            if form.managed_rombongan_single.data:
                user.managed_rombongan = [form.managed_rombongan_single.data]
            else:
                user.managed_rombongan = []
        else:
            user.managed_rombongan = []

        # Jika ada password baru yang diisi, update passwordnya
        if form.password.data:
            user.set_password(form.password.data)
            
        log_activity('Edit', 'User', f"Mengubah data user: '{user.username}'")
        db.session.commit()
        
        flash('Data user berhasil diperbarui.', 'success')
        return redirect(url_for('admin.manajemen_user'))

    # Saat GET, isi field rombongan secara manual karena 'obj' tidak menanganinya dengan baik untuk field ini
    if user.role.name == 'Korwil':
        form.managed_rombongan_multi.data = user.managed_rombongan
    elif user.role.name == 'Korda' and user.managed_rombongan:
        form.managed_rombongan_single.data = user.managed_rombongan[0]

    return render_template('form_user.html', form=form, title="Edit User")

@admin_bp.route('/users/hapus/<int:user_id>', methods=['POST'])
@login_required
@role_required('Korpus')
def hapus_user(user_id):
    user = User.query.get_or_404(user_id)
    # Jangan biarkan korpus menghapus dirinya sendiri
    if user == current_user:
        flash('Anda tidak bisa menghapus akun Anda sendiri.', 'danger')
        return redirect(url_for('admin.manajemen_user'))
    username_dihapus = user.username
    log_activity('Hapus', 'User', f"Menghapus user: '{username_dihapus}'")
    db.session.delete(user)
    db.session.commit()
    flash('User berhasil dihapus.', 'info')
    return redirect(url_for('admin.manajemen_user'))


@admin_bp.route('/')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara', 'Bendahara Pusat')
def dashboard():
    check_and_update_expired_izin()
    active_edisi = get_active_edisi()
    stats = { 'total_peserta': 0, 'total_izin': 0, 'santri_belum_terdaftar': 0, 
              'total_pemasukan': 0, 'total_lunas': 0, 'total_belum_lunas': 0, 
              'pendaftar_terlambat': [], 'total_partisipan': 0 }
    semua_rombongan = []

    if not active_edisi:
        flash("Tidak ada edisi yang aktif. Silakan aktifkan satu edisi di Manajemen Edisi.", "warning")
        stats['santri_belum_terdaftar'] = Santri.query.filter(Santri.status_santri == 'Aktif', Santri.pendaftarans == None).count()
        return render_template('dashboard.html', stats=stats, semua_rombongan=semua_rombongan)

    # --- MULAI KALKULASI JIKA EDISI AKTIF ---
    
    # 1. Query dasar untuk mengambil semua pendaftaran di edisi aktif
    pendaftaran_query = Pendaftaran.query.join(
        Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id
    ).filter(Rombongan.edisi_id == active_edisi.id)

    # 2. Ambil ID rombongan yang dikelola user
    managed_rombongan_ids = []
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = {r.id for r in current_user.managed_rombongan} # Gunakan set untuk pencarian cepat

    # 3. Terapkan filter hak akses jika bukan Korpus
    if current_user.role.name != 'Korpus':
        if not managed_rombongan_ids:
            pendaftaran_query = pendaftaran_query.filter(db.false())
        else:
            pendaftaran_query = pendaftaran_query.filter(
                or_(
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                    Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                )
            )
    
    # 4. Eksekusi query pendaftaran sekali untuk efisiensi
    pendaftar_list = pendaftaran_query.options(
        joinedload(Pendaftaran.santri), 
        joinedload(Pendaftaran.rombongan_pulang), 
        joinedload(Pendaftaran.rombongan_kembali)
    ).all()
    
    # 5. Kalkulasi Statistik Peserta & Keuangan (Akurat untuk Lintas Rombongan)
    stats['total_peserta'] = len({p.santri_id for p in pendaftar_list})
    stats['total_izin'] = Izin.query.filter_by(edisi=active_edisi, status='Aktif').count()
    stats['total_partisipan'] = Partisipan.query.filter_by(edisi_id=active_edisi.id).count()

    total_pemasukan = 0
    total_lunas = 0
    for p in pendaftar_list:
        # Kalkulasi biaya pulang
        if p.status_pulang != 'Tidak Ikut' and p.rombongan_pulang_id:
            if current_user.role.name == 'Korpus' or p.rombongan_pulang_id in managed_rombongan_ids:
                tarif_pulang = Tarif.query.filter_by(rombongan_id=p.rombongan_pulang_id, titik_turun=p.titik_turun).first()
                if tarif_pulang:
                    biaya_pulang = tarif_pulang.harga_bus + tarif_pulang.fee_korda + 10000
                    total_pemasukan += biaya_pulang
                    if p.status_pulang == 'Lunas':
                        total_lunas += biaya_pulang
        
        # Kalkulasi biaya kembali
        if p.status_kembali != 'Tidak Ikut' and p.rombongan_kembali_id:
            if current_user.role.name == 'Korpus' or p.rombongan_kembali_id in managed_rombongan_ids:
                tarif_kembali = Tarif.query.filter_by(rombongan_id=p.rombongan_kembali_id, titik_turun=p.titik_jemput_kembali).first()
                if tarif_kembali:
                    biaya_kembali = tarif_kembali.harga_bus + tarif_kembali.fee_korda + 10000
                    total_pemasukan += biaya_kembali
                    if p.status_kembali == 'Lunas':
                        total_lunas += biaya_kembali

    stats['total_pemasukan'] = total_pemasukan
    stats['total_lunas'] = total_lunas
    stats['total_belum_lunas'] = total_pemasukan - total_lunas
    
    # 6. Kalkulasi Santri Belum Terdaftar (berdasarkan hak akses)
    all_registered_santri_ids = {p.santri_id for p in Pendaftaran.query.join(Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id).filter(Rombongan.edisi_id == active_edisi.id)}
    query_belum_terdaftar = Santri.query.filter(Santri.status_santri == 'Aktif', ~Santri.id.in_(all_registered_santri_ids))

    if current_user.role.name in ['Korwil', 'Korda']:
        managed_regions = {w.get('label') for r in current_user.managed_rombongan if r.cakupan_wilayah for w in r.cakupan_wilayah}
        if managed_regions:
            query_belum_terdaftar = query_belum_terdaftar.filter(Santri.kabupaten.in_(list(managed_regions)))
        else:
            query_belum_terdaftar = query_belum_terdaftar.filter(db.false())
    
    stats['santri_belum_terdaftar'] = query_belum_terdaftar.count()

    # 7. Ambil data rombongan sesuai hak akses (untuk tabel ringkasan)
    rombongan_query = Rombongan.query.filter_by(edisi=active_edisi)
    if current_user.role.name in ['Korwil', 'Korda']:
        if not managed_rombongan_ids:
            rombongan_query = rombongan_query.filter(db.false())
        else:
            rombongan_query = rombongan_query.filter(Rombongan.id.in_(managed_rombongan_ids))
    semua_rombongan = rombongan_query.order_by(Rombongan.nama_rombongan).all()

    return render_template('dashboard.html', stats=stats, semua_rombongan=semua_rombongan)

@admin_bp.route('/rombongan')
@login_required
@role_required('Korpus', 'Korwil', 'Korda', 'Bendahara Pusat')
def manajemen_rombongan():
    active_edisi = get_active_edisi()
    semua_rombongan = []  # Inisialisasi daftar kosong di awal
    search_query = None   # <--- Tambahkan inisialisasi awal di sini

    if active_edisi:
        # Query hanya dijalankan jika ada edisi yang aktif
        query = Rombongan.query.filter_by(edisi=active_edisi)
        
        if current_user.role.name in ['Korwil', 'Korda']:
            managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
            if not managed_rombongan_ids:
                query = query.filter(db.false())
            else:
                query = query.filter(Rombongan.id.in_(managed_rombongan_ids))
        
        search_query = request.args.get('q')
        
        if search_query:
            query = query.filter(Rombongan.nama_rombongan.ilike(f'%{search_query}%'))

        semua_rombongan = query.order_by(Rombongan.nama_rombongan).all()

    return render_template('manajemen_rombongan.html', semua_rombongan=semua_rombongan)



# --- KODE BARU DIMULAI DI SINI ---

@admin_bp.route('/rombongan/tambah', methods=['GET', 'POST'])
@login_required
@role_required('Korpus')
def tambah_rombongan():
    active_edisi = get_active_edisi()
    if not active_edisi:
        flash("Tidak bisa menambah rombongan karena tidak ada edisi yang aktif.", "danger")
        return redirect(url_for('admin.manajemen_rombongan'))
    
    form = RombonganForm()
    if form.validate_on_submit():
        new_rombongan = Rombongan(
            edisi=active_edisi,
            nama_rombongan=form.nama_rombongan.data,
            penanggung_jawab_putra=form.penanggung_jawab_putra.data,
            kontak_person_putra=form.kontak_person_putra.data,
            penanggung_jawab_putri=form.penanggung_jawab_putri.data,
            kontak_person_putri=form.kontak_person_putri.data,
            nomor_rekening=form.nomor_rekening.data,
            cakupan_wilayah=json.loads(form.cakupan_wilayah.data or '[]'),
            jadwal_pulang=form.jadwal_pulang.data,
            batas_pembayaran_pulang=form.batas_pembayaran_pulang.data,
            jadwal_berangkat=form.jadwal_berangkat.data,
            batas_pembayaran_berangkat=form.batas_pembayaran_berangkat.data,
            titik_jemput_berangkat=form.titik_jemput_berangkat.data
        )
        # Hapus tarif lama (jika ada, seharusnya tidak ada untuk form tambah) dan isi dengan yang baru
        new_rombongan.tarifs = []
        for tarif_data in form.tarifs.data:
            if tarif_data['titik_turun'] and tarif_data['harga_bus'] is not None:
                new_rombongan.tarifs.append(Tarif(**tarif_data))
        
        db.session.add(new_rombongan)
        log_activity('Tambah', 'Rombongan', f"Menambahkan rombongan baru: '{new_rombongan.nama_rombongan}'")
        db.session.commit()
        flash('Rombongan baru berhasil ditambahkan.', 'success')
        # Arahkan ke halaman edit agar bisa langsung tambah bus
        return redirect(url_for('admin.edit_rombongan', id=new_rombongan.id))

    return render_template('form_rombongan.html', form=form, title="Tambah Rombongan Baru")


@admin_bp.route('/rombongan/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda')
def edit_rombongan(id):
    """Route untuk edit rombongan dengan manajemen bus"""
    active_edisi = get_active_edisi()
    rombongan = Rombongan.query.get_or_404(id)

    # Validasi akses rombongan
    if active_edisi and rombongan.edisi_id != active_edisi.id:
        flash("Anda tidak bisa mengedit rombongan dari edisi yang sudah selesai.", "danger")
        return redirect(url_for('admin.manajemen_rombongan'))
    
    if current_user.role.name == 'Korda' and rombongan not in current_user.managed_rombongan:
        abort(403)

    # Buat form untuk rombongan dan bus
    form = RombonganForm(obj=rombongan)
    bus_form = BusForm()

    if form.validate_on_submit():
        try:
            # Update semua field dari form ke objek rombongan
            rombongan.nama_rombongan = form.nama_rombongan.data
            rombongan.penanggung_jawab_putra = form.penanggung_jawab_putra.data
            rombongan.kontak_person_putra = form.kontak_person_putra.data
            rombongan.penanggung_jawab_putri = form.penanggung_jawab_putri.data
            rombongan.kontak_person_putri = form.kontak_person_putri.data
            rombongan.nomor_rekening = form.nomor_rekening.data

            
            # Handle cakupan_wilayah - parse JSON string
            try:
                cakupan_wilayah_data = form.cakupan_wilayah.data
                if cakupan_wilayah_data:
                    rombongan.cakupan_wilayah = json.loads(form.cakupan_wilayah.data)
                else:
                    rombongan.cakupan_wilayah = []
            except json.JSONDecodeError:
                flash("Format cakupan wilayah tidak valid. Gunakan format JSON yang benar.", "danger")
                return render_template('edit_rombongan.html', 
                                     form=form, 
                                     bus_form=bus_form,
                                     title="Edit Rombongan", 
                                     rombongan=rombongan)
            
            rombongan.jadwal_pulang = form.jadwal_pulang.data
            rombongan.batas_pembayaran_pulang = form.batas_pembayaran_pulang.data
            rombongan.jadwal_berangkat = form.jadwal_berangkat.data
            rombongan.batas_pembayaran_berangkat = form.batas_pembayaran_berangkat.data
            rombongan.titik_jemput_berangkat = form.titik_jemput_berangkat.data
            
            # Update tarif - hapus tarif lama dan ganti dengan yang baru
            for tarif in rombongan.tarifs:
                db.session.delete(tarif)

            for tarif_data in form.tarifs.data:
                if tarif_data['titik_turun'] and tarif_data['harga_bus'] is not None:
                    new_tarif = Tarif(
                        titik_turun=tarif_data['titik_turun'],
                        harga_bus=tarif_data['harga_bus'],
                        fee_korda=tarif_data.get('fee_korda', 0),
                        rombongan=rombongan
                    )
                    rombongan.tarifs.append(new_tarif)
            
            # Log aktivitas
            log_activity('Edit', 'Rombongan', f"Mengubah detail rombongan: '{rombongan.nama_rombongan}'")
            
            db.session.commit()
            flash('Data rombongan berhasil diperbarui!', 'success')
            return redirect(url_for('admin.edit_rombongan', id=rombongan.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Terjadi kesalahan saat menyimpan data: {str(e)}', 'danger')

    # Isi data untuk request GET (pertama kali halaman dibuka)
    if request.method == 'GET':
        # Set cakupan_wilayah sebagai JSON string untuk tampilan di form
        form.cakupan_wilayah.data = json.dumps(rombongan.cakupan_wilayah or [], ensure_ascii=False, indent=2)
        
        # Clear existing tarif entries and add current ones
        while len(form.tarifs) > 0:
            form.tarifs.pop_entry()
        
        for tarif in rombongan.tarifs:
            tarif_form = form.tarifs.append_entry()
            tarif_form.titik_turun.data = tarif.titik_turun
            tarif_form.harga_bus.data = tarif.harga_bus
            tarif_form.fee_korda.data = tarif.fee_korda

        # Jika tidak ada tarif, tambahkan satu baris kosong
        if not rombongan.tarifs:
            form.tarifs.append_entry()

    return render_template('edit_rombongan.html', 
                         form=form, 
                         bus_form=bus_form,
                         title="Edit Rombongan", 
                         rombongan=rombongan)

@admin_bp.route('/rombongan/hapus/<int:id>', methods=['POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def hapus_rombongan(id):
    rombongan = Rombongan.query.get_or_404(id)
    nama_rombongan = rombongan.nama_rombongan
    log_activity('Hapus', 'Rombongan', f"Menghapus rombongan: '{nama_rombongan}'")
    db.session.delete(rombongan)
    db.session.commit()
    flash('Rombongan berhasil dihapus.', 'info')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/api/search-wilayah')
def search_wilayah_proxy():
    # Ambil query pencarian dari parameter URL (contoh: /api/search-wilayah?q=tegal)
    query = request.args.get('q', '')
    if not query:
        return jsonify({"results": []})

    try:
        # Panggil API sebenarnya dari backend
        api_url = f"https://backapp.amtsilatipusat.com/api/regencies?name={query}"
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()  # Cek jika ada error HTTP
        
        # Kembalikan hasil JSON ke frontend kita
        return jsonify(response.json())
        
    except requests.exceptions.RequestException as e:
        # Tangani jika ada error koneksi ke API
        print(f"Error fetching API: {e}")
        return jsonify({"error": "Gagal mengambil data dari API"}), 500
    
    
@admin_bp.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403

@admin_bp.route('/santri')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
def manajemen_santri():
    page = request.args.get('page', 1, type=int)
    active_edisi = get_active_edisi()
    query = Santri.query

    # Ambil parameter filter
    search_nama = request.args.get('nama')
    search_alamat_list = request.args.getlist('alamat')
    search_asrama = request.args.get('asrama')
    search_status = request.args.get('status')
    f_rombongan_id = request.args.get('rombongan_id')
    f_keterangan = request.args.get('keterangan') # <-- Filter baru


    # Terapkan filter
    if search_nama:
        query = query.filter(Santri.nama.ilike(f'%{search_nama}%'))
    if search_alamat_list:
        query = query.filter(Santri.kabupaten.in_(search_alamat_list))
    if search_asrama:
        query = query.filter(Santri.asrama.ilike(f'%{search_asrama}%'))
    if search_status:
        query = query.filter(Santri.status_santri == search_status)

    if f_rombongan_id:
        if f_rombongan_id == 'belum_terdaftar':
            if active_edisi:
                subquery = db.session.query(Pendaftaran.santri_id).join(Rombongan, or_(
                    Pendaftaran.rombongan_pulang_id == Rombongan.id,
                    Pendaftaran.rombongan_kembali_id == Rombongan.id
                )).filter(Rombongan.edisi_id == active_edisi.id)
                query = query.filter(~Santri.id.in_(subquery))
        else:
            # Cari santri yang terdaftar di rombongan spesifik (baik pulang maupun kembali)
            query = query.join(Pendaftaran).filter(
                or_(
                    Pendaftaran.rombongan_pulang_id == f_rombongan_id,
                    Pendaftaran.rombongan_kembali_id == f_rombongan_id
                )
            )
    if f_keterangan:
        if f_keterangan == 'Pengurus':
            # Tampilkan semua yang memiliki jabatan
            query = query.filter(Santri.nama_jabatan != None, Santri.nama_jabatan != '')
        elif f_keterangan == 'Santri':
            # Tampilkan semua yang tidak memiliki jabatan
            query = query.filter((Santri.nama_jabatan == None) | (Santri.nama_jabatan == ''))

    pagination = query.order_by(Santri.nama).paginate(page=page, per_page=50, error_out=False)
    santri_ids_on_page = [s.id for s in pagination.items]
    pendaftaran_terkait = {}
    if active_edisi and santri_ids_on_page:
        pendaftaran_objects = Pendaftaran.query.filter(
            Pendaftaran.santri_id.in_(santri_ids_on_page),
            or_(
                Pendaftaran.rombongan_pulang.has(edisi_id=active_edisi.id),
                Pendaftaran.rombongan_kembali.has(edisi_id=active_edisi.id)
            )
        ).all()
        pendaftaran_terkait = {p.santri_id: p for p in pendaftaran_objects}

    
    all_rombongan = Rombongan.query.filter_by(edisi=active_edisi).order_by(Rombongan.nama_rombongan).all() if active_edisi else []
    all_kabupaten = [k[0] for k in db.session.query(Santri.kabupaten).distinct().order_by(Santri.kabupaten).all() if k[0] is not None]
    
    return render_template('manajemen_santri.html', 
                           pagination=pagination, 
                           all_rombongan=all_rombongan,
                           all_kabupaten=all_kabupaten,
                           pendaftaran_terkait=pendaftaran_terkait)

@admin_bp.route('/api/search-student')
def search_student_proxy():
    query = request.args.get('q', '')
    if not query:
        return jsonify({"data": [], "success": False})

    try:
        # Panggil API sebenarnya dari backend. Tambahkan limit untuk mendapatkan lebih banyak hasil.
        api_url = f"https://dev.amtsilatipusat.com/api/student?search={query}&limit=20"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching student API: {e}")
        return jsonify({"error": "Gagal mengambil data dari API"}), 500


# Route ini untuk memproses aksi "Impor"
@admin_bp.route('/santri/impor', methods=['POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def impor_santri():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Data tidak valid"}), 400

    # Cek apakah santri dengan api_student_id ini sudah ada di database lokal
    existing_santri = Santri.query.filter_by(api_student_id=data['id']).first()
    if existing_santri:
        return jsonify({"success": False, "message": "Santri ini sudah pernah diimpor"}), 409 # 409 = Conflict

    # Buat record Santri baru (snapshot)
    new_santri = Santri(
        api_student_id=data['id'],
        nis=data.get('nis', 'N/A'),
        nama=data.get('name', 'Tanpa Nama'),
        kabupaten=data.get('regency'),
        asrama=data.get('activeDormitory'),
        no_hp_wali=data.get('parrentPhone'),
        # Terapkan logika jenis kelamin: jika 'gender' tidak ada/null, default ke 'Putra'
        jenis_kelamin=data.get('gender') or 'Putra' 
    )
    
    db.session.add(new_santri)
    db.session.commit()
    log_activity('Tambah', 'Santri', f"Mengimpor santri individual: '{new_santri.nama}'")

    
    return jsonify({"success": True, "message": f"{new_santri.nama} berhasil diimpor."})

@admin_bp.route('/santri/impor-semua', methods=['POST'])
@login_required
@role_required('Korpus')
def impor_semua_santri():
    try:
        api_url = "https://sigap.amtsilatipusat.com/api/student?limit=2000"
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        santri_from_api = response.json().get('data', [])

        # 1. Ambil semua santri yang ada berdasarkan NIS sebagai patokan
        existing_santri_map_by_nis = {s.nis: s for s in Santri.query.all() if s.nis}
        
        updated_count = 0
        new_count = 0
        
        to_create_mappings = []
        
        for data in santri_from_api:
            api_nis = data.get('nis')
            if not api_nis:
                continue # Lewati data dari API yang tidak memiliki NIS

            leadership_data = data.get('leadership')
            
            # 2. Cek apakah santri sudah ada di database lokal berdasarkan NIS
            if api_nis in existing_santri_map_by_nis:
                # Jika ADA, update datanya
                santri_to_update = existing_santri_map_by_nis[api_nis]
                
                santri_to_update.api_student_id = data.get('id') # Sinkronkan ulang ID API
                santri_to_update.nama = data.get('name', 'Tanpa Nama')
                santri_to_update.kabupaten = data.get('regency')
                santri_to_update.asrama = data.get('activeDormitory')
                santri_to_update.no_hp_wali = data.get('parrentPhone')
                santri_to_update.jenis_kelamin = data.get('gender')
                santri_to_update.kelas_formal = data.get('formalClass')
                santri_to_update.kelas_ngaji = data.get('activeClass')
                santri_to_update.nama_jabatan = leadership_data.get('name') if leadership_data else None
                santri_to_update.status_jabatan = leadership_data.get('status') if leadership_data else None
                
                updated_count += 1
            else:
                # Jika TIDAK ADA, siapkan untuk dibuat sebagai data baru
                to_create_mappings.append({
                    'api_student_id': data.get('id'),
                    'nis': api_nis,
                    'nama': data.get('name', 'Tanpa Nama'),
                    'kabupaten': data.get('regency'),
                    'asrama': data.get('activeDormitory'),
                    'no_hp_wali': data.get('parrentPhone'),
                    'jenis_kelamin': data.get('gender'),
                    'kelas_formal': data.get('formalClass'),
                    'kelas_ngaji': data.get('activeClass'),
                    'nama_jabatan': leadership_data.get('name') if leadership_data else None,
                    'status_jabatan': leadership_data.get('status') if leadership_data else None,
                })

        # Proses pembuatan data baru secara massal
        if to_create_mappings:
            db.session.bulk_insert_mappings(Santri, to_create_mappings)
            new_count = len(to_create_mappings)

        db.session.commit()
        log_activity('Sinkronisasi', 'Santri', f"Sinkronisasi massal: {new_count} baru, {updated_count} diperbarui.")
        flash(f"Proses selesai! Berhasil mengimpor {new_count} santri baru dan memperbarui {updated_count} data santri.", "success")

    except requests.exceptions.RequestException as e:
        flash(f"Gagal mengambil data dari API Induk: {e}", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Terjadi error saat memproses data. Cek terminal untuk detail.", "danger")
        print("=====================================")
        print(f"Error detail impor santri: {e}")
        print("=====================================")

    return redirect(url_for('admin.manajemen_santri'))
                            
@admin_bp.route('/santri/edit/<int:id>', methods=['GET', 'POST'])
def edit_santri(id):
    # Fungsi ini sekarang hanya untuk mengedit data minor, pendaftaran dipindah
    # Anda bisa kembangkan ini nanti jika perlu edit data snapshot
    santri = Santri.query.get_or_404(id)
    flash("Fungsi edit santri akan dikembangkan lebih lanjut.", "info")
    return redirect(url_for('admin.manajemen_santri'))

@admin_bp.route('/santri/hapus/<int:id>', methods=['POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def hapus_santri(id):
    santri = Santri.query.get_or_404(id)
    nama_santri = santri.nama
    log_activity('Hapus', 'Santri', f"Menghapus data santri: '{nama_santri}' (ID: {santri.id})")
    db.session.delete(santri)
    db.session.commit()
    flash(f"Santri '{nama_santri}' berhasil dihapus dari sistem.", "info")
    return redirect(url_for('admin.manajemen_santri'))

@admin_bp.route('/pendaftaran', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda')
def pendaftaran_rombongan():
    form = PendaftaranForm()
    active_edisi = get_active_edisi()
    
    # Mengisi pilihan dropdown rombongan
    rombongan_choices = []
    if active_edisi:
        query = Rombongan.query.filter_by(edisi=active_edisi)
        if current_user.role.name == 'Korda':
            managed_ids = [r.id for r in current_user.managed_rombongan]
            query = query.filter(Rombongan.id.in_(managed_ids))
        rombongan_choices = [(r.id, r.nama_rombongan) for r in query.order_by(Rombongan.nama_rombongan).all()]
    form.rombongan.choices = [('', '-- Pilih Rombongan --')] + rombongan_choices

    # Mengisi pilihan dinamis untuk validasi saat POST
    if request.method == 'POST':
        rombongan_id_from_form = request.form.get('rombongan')
        if rombongan_id_from_form:
            selected_rombongan = Rombongan.query.get(rombongan_id_from_form)
            if selected_rombongan:
                form.titik_turun.choices = [(t.titik_turun, t.titik_turun) for t in selected_rombongan.tarifs]
                bus_choices = [('', '-- Pilih Bus --')] + [(bus.id, f"{bus.nama_armada} - {bus.nomor_lambung or bus.plat_nomor}") for bus in selected_rombongan.buses]
                form.bus_pulang.choices = bus_choices
                form.bus_kembali.choices = bus_choices

    if form.validate_on_submit():
        rombongan_id = int(form.rombongan.data)
        santri_id = form.santri.data
        
        rombongan = Rombongan.query.get(rombongan_id)
        santri = Santri.query.get(santri_id)

        if not santri or not rombongan:
            flash("ERROR: Santri atau Rombongan tidak ditemukan.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))

        # Gunakan HANYA pengecekan yang baru dan akurat
        existing_pendaftaran = santri.pendaftarans.filter(Pendaftaran.edisi_id == active_edisi.id).first()
        if existing_pendaftaran:
            flash(f"ERROR: {santri.nama} sudah terdaftar di edisi ini.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))
        
        if santri.status_santri == 'Izin':
            flash(f"ERROR: {santri.nama} sedang Izin dan tidak bisa didaftarkan.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))

        # Kalkulasi biaya
        selected_tarif = Tarif.query.filter_by(rombongan_id=rombongan_id, titik_turun=form.titik_turun.data).first()
        biaya_per_perjalanan = selected_tarif.harga_bus + selected_tarif.fee_korda + 10000 if selected_tarif else 0
        total_biaya = 0
        if form.status_pulang.data != 'Tidak Ikut': total_biaya += biaya_per_perjalanan
        if form.status_kembali.data != 'Tidak Ikut': total_biaya += biaya_per_perjalanan

        pendaftaran = Pendaftaran(
            edisi_id=active_edisi.id,santri_id=santri.id, rombongan_pulang_id=rombongan.id, rombongan_kembali_id=rombongan.id,
            status_pulang=form.status_pulang.data, metode_pembayaran_pulang=form.metode_pembayaran_pulang.data or None,
            bus_pulang_id=int(form.bus_pulang.data) if form.bus_pulang.data else None,
            titik_turun=form.titik_turun.data, status_kembali=form.status_kembali.data,
            metode_pembayaran_kembali=form.metode_pembayaran_kembali.data or None,
            bus_kembali_id=int(form.bus_kembali.data) if form.bus_kembali.data else None,
            titik_jemput_kembali=form.titik_turun.data,total_biaya=total_biaya
        )
        db.session.add(pendaftaran)
        log_activity('Tambah', 'Pendaftaran', f"Mendaftarkan santri '{santri.nama}' ke rombongan '{rombongan.nama_rombongan}'")
        db.session.commit()
        flash(f"{santri.nama} berhasil didaftarkan ke {rombongan.nama_rombongan}!", "success")
        return redirect(url_for('admin.daftar_peserta', rombongan_id=rombongan.id))
    
    return render_template('pendaftaran_rombongan.html', form=form)

@admin_bp.route('/pendaftaran/edit/<int:pendaftaran_id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda')
def edit_pendaftaran(pendaftaran_id):
    pendaftaran = Pendaftaran.query.options(
        joinedload(Pendaftaran.santri),
        joinedload(Pendaftaran.rombongan_pulang),
        joinedload(Pendaftaran.rombongan_kembali)
    ).get_or_404(pendaftaran_id)
    
    # Verifikasi Kepemilikan Korda
    if current_user.role.name == 'Korda':
        managed_ids = {r.id for r in current_user.managed_rombongan}
        if (pendaftaran.rombongan_pulang_id and pendaftaran.rombongan_pulang_id not in managed_ids) or \
           (pendaftaran.rombongan_kembali_id and pendaftaran.rombongan_kembali_id not in managed_ids):
            abort(403)
    
    form = PendaftaranEditForm(obj=pendaftaran)
    
     # --- LOGIKA PENGISIAN CHOICES DINAMIS ---
    # Selalu isi pilihan untuk perjalanan pulang
    if pendaftaran.rombongan_pulang:
        form.titik_turun.choices = [(t.titik_turun, t.titik_turun) for t in pendaftaran.rombongan_pulang.tarifs]
        form.bus_pulang.choices = [('', '-- Pilih Bus --')] + [(b.id, f"{b.nama_armada}...") for b in pendaftaran.rombongan_pulang.buses]

    # Tentukan rombongan kembali yang relevan (baik dari GET maupun POST)
    rombongan_kembali_terpilih = pendaftaran.rombongan_kembali
    if request.method == 'POST':
        rombongan_kembali_id_form = request.form.get('rombongan_kembali')
        if rombongan_kembali_id_form:
            rombongan_kembali_terpilih = Rombongan.query.get(rombongan_kembali_id_form)
    
    # Jika tidak ada rombongan kembali, gunakan rombongan pulang
    if not rombongan_kembali_terpilih:
        rombongan_kembali_terpilih = pendaftaran.rombongan_pulang

    # Isi pilihan untuk perjalanan kembali
    if rombongan_kembali_terpilih:
        form.titik_jemput_kembali.choices = [(t.titik_turun, t.titik_turun) for t in rombongan_kembali_terpilih.tarifs]
        form.bus_kembali.choices = [('', '-- Pilih Bus --')] + [(b.id, f"{b.nama_armada}...") for b in rombongan_kembali_terpilih.buses]
    # -----------------------------------------------

    if form.validate_on_submit():
        # Update data pendaftaran dari form
        pendaftaran.status_pulang = form.status_pulang.data
        pendaftaran.metode_pembayaran_pulang = form.metode_pembayaran_pulang.data or None
        pendaftaran.bus_pulang_id = int(form.bus_pulang.data) if form.bus_pulang.data else None
        pendaftaran.titik_turun = form.titik_turun.data
        
        pendaftaran.status_kembali = form.status_kembali.data
        pendaftaran.metode_pembayaran_kembali = form.metode_pembayaran_kembali.data or None
        pendaftaran.bus_kembali_id = int(form.bus_kembali.data) if form.bus_kembali.data else None
        pendaftaran.titik_jemput_kembali = form.titik_jemput_kembali.data
        
        # Tentukan rombongan kembali
        pendaftaran.rombongan_kembali = form.rombongan_kembali.data or pendaftaran.rombongan_pulang

        rombongan_kembali_terpilih = form.rombongan_kembali.data or pendaftaran.rombongan_pulang


         # Hitung ulang total biaya
        total_biaya = 0
        tarif_pulang = Tarif.query.filter_by(rombongan_id=pendaftaran.rombongan_pulang_id, titik_turun=form.titik_turun.data).first()
        if form.status_pulang.data != 'Tidak Ikut' and tarif_pulang:
            total_biaya += tarif_pulang.harga_bus + tarif_pulang.fee_korda + 10000
        
        if form.status_kembali.data != 'Tidak Ikut' and rombongan_kembali_terpilih and form.titik_jemput_kembali.data:
            tarif_kembali = Tarif.query.filter_by(rombongan_id=rombongan_kembali_terpilih.id, titik_turun=form.titik_jemput_kembali.data).first()
            if tarif_kembali:
                total_biaya += tarif_kembali.harga_bus + tarif_kembali.fee_korda + 10000

        # Bangun perintah UPDATE secara manual
        stmt = update(Pendaftaran).where(Pendaftaran.id == pendaftaran_id).values(
            status_pulang=form.status_pulang.data,
            metode_pembayaran_pulang=form.metode_pembayaran_pulang.data or None,
            bus_pulang_id=int(form.bus_pulang.data) if form.bus_pulang.data else None,
            titik_turun=form.titik_turun.data,
            
            rombongan_kembali_id=rombongan_kembali_terpilih.id if rombongan_kembali_terpilih else None,
            status_kembali=form.status_kembali.data,
            metode_pembayaran_kembali=form.metode_pembayaran_kembali.data or None,
            bus_kembali_id=int(form.bus_kembali.data) if form.bus_kembali.data else None,
            titik_jemput_kembali=form.titik_jemput_kembali.data or None,
            total_biaya=total_biaya
        )
        
        db.session.execute(stmt)
        log_activity('Edit', 'Pendaftaran', f"Mengubah pendaftaran untuk santri: '{pendaftaran.santri.nama}'")
        db.session.commit()
        
        flash(f"Data pendaftaran untuk {pendaftaran.santri.nama} berhasil diperbarui.", "success")
        return redirect(url_for('admin.daftar_peserta', rombongan_id=pendaftaran.rombongan_pulang_id))
    
    # Isi data form awal untuk ditampilkan saat request GET
    if request.method == 'GET':
        if pendaftaran.rombongan_pulang:
            form.rombongan_pulang_nama.data = pendaftaran.rombongan_pulang.nama_rombongan
        if pendaftaran.rombongan_pulang_id == pendaftaran.rombongan_kembali_id:
            form.rombongan_kembali.data = None
        else:
            form.rombongan_kembali.data = pendaftaran.rombongan_kembali
        
        form.titik_turun.data = pendaftaran.titik_turun
        form.titik_jemput_kembali.data = getattr(pendaftaran, 'titik_jemput_kembali', None)
        form.bus_pulang.data = str(pendaftaran.bus_pulang_id) if pendaftaran.bus_pulang_id else ''
        form.bus_kembali.data = str(pendaftaran.bus_kembali_id) if pendaftaran.bus_kembali_id else ''

    return render_template('edit_pendaftaran.html', form=form, pendaftaran=pendaftaran)

@admin_bp.route('/pendaftaran/hapus/<int:pendaftaran_id>', methods=['POST'])
@login_required
@role_required('Korpus')
def hapus_pendaftaran(pendaftaran_id):
    pendaftaran = Pendaftaran.query.get_or_404(pendaftaran_id)
    # Verifikasi Kepemilikan (menggunakan rombongan pulang sebagai acuan)
    if current_user.role.name == 'Korda':
        # Cek apakah Korda mengelola salah satu dari rombongan pendaftaran
        managed_ids = {r.id for r in current_user.managed_rombongan}
        if pendaftaran.rombongan_pulang_id not in managed_ids and pendaftaran.rombongan_kembali_id not in managed_ids:
            abort(403)

    # Simpan ID rombongan untuk redirect, utamakan rombongan pulang
    rombongan_id = pendaftaran.rombongan_pulang_id or pendaftaran.rombongan_kembali_id
    nama_santri = pendaftaran.santri.nama
    
    db.session.delete(pendaftaran)
    log_activity('Hapus', 'Pendaftaran', f"Menghapus pendaftaran untuk santri: '{nama_santri}'")
    db.session.commit()
    
    flash(f"Pendaftaran untuk '{nama_santri}' telah berhasil dihapus.", "info")
    return redirect(url_for('admin.daftar_peserta', rombongan_id=rombongan_id))

# Route API helper BARU untuk mengambil detail rombongan
@admin_bp.route('/api/rombongan-detail/<int:id>')
def rombongan_detail(id):
    rombongan = Rombongan.query.get_or_404(id)
    
    tarifs = [{'titik_turun': t.titik_turun, 'harga': t.harga_bus + t.fee_korda + 10000} for t in rombongan.tarifs]

    buses_data = []
    for bus in rombongan.buses:
        terisi_pulang = Pendaftaran.query.filter_by(bus_pulang_id=bus.id).count()
        terisi_kembali = Pendaftaran.query.filter_by(bus_kembali_id=bus.id).count()
        buses_data.append({
            'id': bus.id, 'nama_armada': bus.nama_armada,
            'nomor_lambung': bus.nomor_lambung, 'plat_nomor': bus.plat_nomor,
            'kuota': bus.kuota,
            'sisa_kuota_pulang': bus.kuota - terisi_pulang,
            'sisa_kuota_kembali': bus.kuota - terisi_kembali,
            'gmaps_share_url': bus.gmaps_share_url # <-- Pastikan ini ada

        })
    semua_pendaftar_objek = list(rombongan.pendaftar_pulang) + list(rombongan.pendaftar_kembali)
    unique_pendaftar_objek = {p.id: p for p in semua_pendaftar_objek}.values()

    pendaftar_data = [{'nama': p.santri.nama, 'nis': p.santri.nis, 'titik_turun': p.titik_turun, 'total_biaya': p.total_biaya} for p in unique_pendaftar_objek]

    return jsonify({
        'cakupan_wilayah': rombongan.cakupan_wilayah, 'tarifs': tarifs,
        'buses': buses_data, 'pendaftar': pendaftar_data
    })

@admin_bp.route('/api/search-santri')
def search_santri_api():
    query = request.args.get('q', '')
    query_id = request.args.get('q_id', type=int)

    if query_id:
        santri_results = Santri.query.filter_by(id=query_id).all()
    elif len(query) < 3:
        return jsonify({'results': []})
    else:
        santri_results = Santri.query.filter(
            Santri.nama.ilike(f'%{query}%'),
            Santri.pendaftarans == None
        ).limit(20).all()

    results = [
        {
            'id': santri.id,
            'nama': santri.nama,
            'asrama': santri.asrama,
            'kabupaten': santri.kabupaten,
            'jenis_kelamin': santri.jenis_kelamin,
            'status_santri': santri.status_santri
        } for santri in santri_results
    ]
    return jsonify({'results': results})

@admin_bp.route('/rombongan/<int:rombongan_id>/peserta')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Bendahara Pusat')
def daftar_peserta(rombongan_id):
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    pendaftar = Pendaftaran.query.filter(
        or_(
            Pendaftaran.rombongan_pulang_id == rombongan_id,
            Pendaftaran.rombongan_kembali_id == rombongan_id
        )
    ).options(
        joinedload(Pendaftaran.santri),
        joinedload(Pendaftaran.bus_pulang),
        joinedload(Pendaftaran.bus_kembali),
        joinedload(Pendaftaran.rombongan_kembali)
    ).all()

    # --- BLOK PERHITUNGAN STATISTIK BARU ---
    stats = {
        'total_peserta': 0,
        'sudah_bus_pulang': 0,
        'sudah_bus_kembali': 0,
        'lunas_pulang': 0,
        'lunas_kembali': 0, # Statistik baru untuk lunas kembali
    }
    
    managed_rombongan_ids = []
    is_manager = False
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        is_manager = True

    for p in pendaftar:
        # Hanya hitung peserta yang benar-benar ikut rombongan ini
        is_pulang_in_this_rombongan = p.rombongan_pulang_id == rombongan_id
        is_kembali_in_this_rombongan = (p.rombongan_kembali_id == rombongan_id) or \
                                       (p.rombongan_kembali_id is None and p.rombongan_pulang_id == rombongan_id)

        # Jika user adalah Korda/Korwil, pastikan rombongan ini milik mereka
        is_managed = not is_manager or rombongan_id in managed_rombongan_ids

        if is_managed and (is_pulang_in_this_rombongan or is_kembali_in_this_rombongan):
            stats['total_peserta'] += 1
            if is_pulang_in_this_rombongan:
                if p.bus_pulang:
                    stats['sudah_bus_pulang'] += 1
                if p.status_pulang == 'Lunas':
                    stats['lunas_pulang'] += 1
            
            if is_kembali_in_this_rombongan:
                if p.bus_kembali:
                    stats['sudah_bus_kembali'] += 1
                if p.status_kembali == 'Lunas':
                    stats['lunas_kembali'] += 1

    return render_template('daftar_peserta.html', 
                           rombongan=rombongan, 
                           pendaftar=pendaftar,
                           stats=stats) # Kirim statistik ke template

@admin_bp.route('/peserta-global')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan')
def daftar_peserta_global():
    active_edisi = get_active_edisi()
    if not active_edisi:
        return render_template('daftar_peserta_global.html', pagination=None, all_rombongan=[], stats={})

    # Siapkan filter dasar dan daftar rombongan untuk dropdown filter
    base_query = Pendaftaran.query.filter(Pendaftaran.edisi_id == active_edisi.id)
    all_rombongan_for_filter = Rombongan.query.filter_by(edisi_id=active_edisi.id).order_by(Rombongan.nama_rombongan).all()
    
    managed_rombongan_ids = []
    stats = {}

    # --- BAGIAN LOGIKA STATISTIK & FILTER BARU ---
    # Tentukan filter berdasarkan peran (role)
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        
        if not managed_rombongan_ids:
            base_query = base_query.filter(db.false())
            stats = {'total_peserta': 0, 'sudah_bus_pulang': 0, 'sudah_bus_kembali': 0, 'lunas_pulang': 0, 'lunas_kembali': 0}
        else:
            # Filter query utama untuk tabel
            base_query = base_query.filter(
                or_(
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                    Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                )
            )
            all_rombongan_for_filter = [r for r in all_rombongan_for_filter if r.id in managed_rombongan_ids]

            # Hitung statistik secara presisi untuk Korda/Korwil
            stats['total_peserta'] = base_query.count()
            stats['sudah_bus_pulang'] = Pendaftaran.query.filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.bus_pulang_id != None, Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids)).count()
            stats['lunas_pulang'] = Pendaftaran.query.filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.status_pulang == 'Lunas', Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids)).count()
            
            # Untuk kembali, perhitungkan kasus lintas rombongan
            kembali_filter = or_(
                Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids),
                and_(Pendaftaran.rombongan_kembali_id == None, Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids))
            )
            stats['sudah_bus_kembali'] = Pendaftaran.query.filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.bus_kembali_id != None, kembali_filter).count()
            stats['lunas_kembali'] = Pendaftaran.query.filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.status_kembali == 'Lunas', kembali_filter).count()

    else: # Logika untuk Korpus (melihat semua)
        stats['total_peserta'] = base_query.count()
        stats['sudah_bus_pulang'] = base_query.filter(Pendaftaran.bus_pulang_id != None).count()
        stats['sudah_bus_kembali'] = base_query.filter(Pendaftaran.bus_kembali_id != None).count()
        stats['lunas_pulang'] = base_query.filter(Pendaftaran.status_pulang == 'Lunas').count()
        stats['lunas_kembali'] = base_query.filter(Pendaftaran.status_kembali == 'Lunas').count()

    # Terapkan filter dari form ke query utama
    # (Logika filter ini tetap sama seperti sebelumnya)
    nama = request.args.get('nama')
    rombongan_id = request.args.get('rombongan_id', type=int)
    status_bayar = request.args.get('status_bayar')

    query = base_query.join(Pendaftaran.santri).options(
        joinedload(Pendaftaran.rombongan_pulang),
        joinedload(Pendaftaran.rombongan_kembali),
        joinedload(Pendaftaran.bus_pulang),
        joinedload(Pendaftaran.bus_kembali)
    )

    if nama:
        query = query.filter(Santri.nama.ilike(f'%{nama}%'))
    if rombongan_id:
        query = query.filter(or_(Pendaftaran.rombongan_pulang_id == rombongan_id, Pendaftaran.rombongan_kembali_id == rombongan_id))
    if status_bayar:
        if status_bayar == 'Lunas':
            query = query.filter(or_(Pendaftaran.status_pulang == 'Lunas', Pendaftaran.status_kembali == 'Lunas'))
        elif status_bayar == 'Belum Lunas':
            query = query.filter(or_(Pendaftaran.status_pulang == 'Belum Bayar', Pendaftaran.status_kembali == 'Belum Bayar'))

    # Lakukan paginasi
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Santri.nama).paginate(page=page, per_page=20, error_out=False)

    return render_template('daftar_peserta_global.html',
                           pagination=pagination,
                           all_rombongan=all_rombongan_for_filter,
                           stats=stats)

@admin_bp.route('/perizinan', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara', 'Bendahara Pusat')
def perizinan():
    form = IzinForm()
    active_edisi = get_active_edisi()

    view_mode = request.args.get('view', 'aktif')
    query = Izin.query.filter_by(edisi=active_edisi)

    if view_mode == 'riwayat':
        query = query.filter_by(status='Selesai')
    else: # Default ke 'aktif'
        query = query.filter_by(status='Aktif')

    search_nama = request.args.get('nama')
    # --- TAMBAHKAN FILTER BARU ---
    f_jenis_kelamin = request.args.get('jenis_kelamin')

    # Join dengan tabel Santri untuk bisa memfilter
    if search_nama or f_jenis_kelamin:
        query = query.join(Santri)
    
    if search_nama:
        query = query.filter(Santri.nama.ilike(f'%{search_nama}%'))
    
    if f_jenis_kelamin:
        query = query.filter(Santri.jenis_kelamin == f_jenis_kelamin)
    # --- AKHIR FILTER BARU ---
    
    semua_izin = query.order_by(Izin.tanggal_berakhir.desc()).all()

    if form.validate_on_submit():
        if not active_edisi:
            flash("Tidak bisa menambah izin karena tidak ada edisi aktif.", "danger")
            return redirect(url_for('admin.perizinan'))
        
        santri = Santri.query.get(form.santri.data)
        new_izin = Izin(
            edisi=active_edisi, # <-- Kaitkan dengan edisi aktif
            santri=santri,
            tanggal_berakhir=form.tanggal_berakhir.data,
            keterangan=form.keterangan.data
        )
        santri.status_santri = 'Izin'
        db.session.add(new_izin)
        log_activity('Tambah', 'Perizinan', f"Memberikan izin kepada santri: '{santri.nama}'")
        db.session.commit()
        flash(f"Izin untuk {santri.nama} telah berhasil dicatat.", "success")
        return redirect(url_for('admin.perizinan'))

    return render_template('perizinan.html', 
                           form=form, 
                           semua_izin=semua_izin,
                           view_mode=view_mode)

@admin_bp.route('/export/perizinan/<jenis_kelamin>')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
def export_perizinan(jenis_kelamin):
    """Export data perizinan ke Excel berdasarkan jenis kelamin"""
    
    # Validasi parameter jenis_kelamin
    if jenis_kelamin.upper() not in ['PUTRA', 'PUTRI']:
        flash("Jenis kelamin tidak valid!", "danger")
        return redirect(url_for('admin.perizinan'))
    
    active_edisi = get_active_edisi()
    if not active_edisi:
        flash("Tidak ada edisi aktif!", "danger")
        return redirect(url_for('admin.perizinan'))
    
    try:
        # Query semua izin (aktif dan riwayat) berdasarkan jenis kelamin
        query = db.session.query(Izin, Santri).join(Santri).filter(
            Izin.edisi == active_edisi,
            Santri.jenis_kelamin == jenis_kelamin.upper()
        ).order_by(Izin.tanggal_berakhir.desc())
        
        results = query.all()
        
        # Buat data untuk DataFrame
        data = []
        for i, (izin, santri) in enumerate(results, 1):
            data.append({
                'No': i,
                'Nama Santri': santri.nama,
                'Jenis Kelamin': 'Putra' if santri.jenis_kelamin == 'PUTRA' else 'Putri',
                'Asrama': santri.asrama or '-',
                'Kabupaten': santri.kabupaten or '-',
                'Izin Sampai': izin.tanggal_berakhir.strftime('%d/%m/%Y') if izin.tanggal_berakhir else '-',
                'Status': izin.status,
                'Keterangan': izin.keterangan or '-',
                'Dicatat Oleh': izin.user.username if hasattr(izin, 'user') and izin.user else '-'
            })
        
        # Buat DataFrame
        df = pd.DataFrame(data)
        
        # Buat Excel file dalam memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet utama dengan data
            sheet_name = f'Perizinan {jenis_kelamin.title()}'
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Ambil workbook dan worksheet untuk formatting
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # Format header
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Format header row
            for col_num, column in enumerate(df.columns, 1):
                cell = worksheet.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = border
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Format data rows
            for row in range(2, len(df) + 2):
                for col in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=row, column=col)
                    cell.border = border
                    cell.alignment = Alignment(horizontal='left', vertical='center')
            
            # Tambah sheet ringkasan
            summary_data = {
                'Informasi': [
                    'Total Izin',
                    'Izin Aktif', 
                    'Izin Selesai',
                    'Tanggal Export',
                    'Export Oleh',
                    'Edisi'
                ],
                'Value': [
                    len(df),
                    len(df[df['Status'] == 'Aktif']) if len(df) > 0 else 0,
                    len(df[df['Status'] == 'Selesai']) if len(df) > 0 else 0,
                    datetime.now().strftime('%d/%m/%Y %H:%M'),
                    current_user.username,
                    active_edisi.nama
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Ringkasan', index=False)
            
            # Format sheet ringkasan
            summary_sheet = writer.sheets['Ringkasan']
            for col_num in range(1, 3):
                cell = summary_sheet.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = border
            
            # Auto-adjust summary columns
            for column in summary_sheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = max_length + 2
                summary_sheet.column_dimensions[column_letter].width = adjusted_width
                
            # Format data rows di summary
            for row in range(2, len(summary_df) + 2):
                for col in range(1, 3):
                    cell = summary_sheet.cell(row=row, column=col)
                    cell.border = border
                    cell.alignment = Alignment(horizontal='left', vertical='center')
        
        output.seek(0)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'perizinan_{jenis_kelamin.lower()}_{active_edisi.nama}_{timestamp}.xlsx'
        
        # Log activity
        log_activity('Export', 'Perizinan', f"Export data perizinan {jenis_kelamin.title()} ke Excel: {len(df)} record")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f"Terjadi kesalahan saat mengexport data: {str(e)}", "danger")
        return redirect(url_for('admin.perizinan'))

@admin_bp.route('/izin/edit/<int:izin_id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Keamanan')
def edit_izin(izin_id):
    izin = Izin.query.get_or_404(izin_id)
    # Gunakan form yang sama, tapi isi dengan data yang ada
    form = IzinForm(obj=izin)
    # Nonaktifkan pilihan santri karena kita tidak mengubah santrinya
    form.santri.render_kw = {'disabled': 'disabled'}

    if form.validate_on_submit():
        # Karena field santri di-disable, kita perlu mengisinya manual
        izin.tanggal_berakhir = form.tanggal_berakhir.data
        izin.keterangan = form.keterangan.data
        db.session.commit()
        log_activity('Edit', 'Perizinan', f"Memperpanjang izin untuk santri '{izin.santri.nama}'.")
        flash(f"Data izin untuk {izin.santri.nama} berhasil diperbarui.", "success")
        return redirect(url_for('admin.perizinan'))
        
    return render_template('form_izin.html', form=form, title=f"Edit Izin: {izin.santri.nama}", is_edit=True, izin=izin)

@admin_bp.route('/izin/cabut/<int:izin_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'Keamanan') # Keamanan dan Korpus
def cabut_izin(izin_id):
    izin = Izin.query.get_or_404(izin_id)    
    santri = izin.santri
    nama_santri = santri.nama
    santri.status_santri = 'Aktif'
    
    log_activity('Hapus', 'Perizinan', f"Mencabut izin untuk santri: '{nama_santri}'")
    db.session.delete(izin)
    db.session.commit()
    
    flash(f"Izin untuk santri '{nama_santri}' telah berhasil dicabut.", "success")
    return redirect(url_for('admin.perizinan'))

@admin_bp.route('/api/search-active-santri')
def search_active_santri_api():
    query = request.args.get('q', '')
    if len(query) < 3:
        return jsonify({'results': []})

    # Cari santri yang namanya cocok DAN statusnya 'Aktif'
    santri_results = Santri.query.filter(
        Santri.nama.ilike(f'%{query}%'),
        Santri.status_santri == 'Aktif'
    ).limit(20).all()

    results = [{'id': s.id, 'nama': s.nama} for s in santri_results]
    return jsonify({'results': results})



@admin_bp.route('/partisipan')
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara', 'Bendahara Pusat')
@login_required
def data_partisipan():
    active_edisi = get_active_edisi()
    
    # Ambil semua data partisipan HANYA dari edisi yang aktif
    if active_edisi:
        semua_partisipan = Partisipan.query.filter_by(edisi=active_edisi).all()
    else:
        semua_partisipan = []
    
    # 2. Kelompokkan data berdasarkan kategori
    grouped_partisipan = defaultdict(list)
    for p in semua_partisipan:
        grouped_partisipan[p.kategori].append(p)
        
    return render_template('data_partisipan.html', grouped_partisipan=grouped_partisipan)

# Buat route placeholder untuk form tambah agar link-nya tidak error
@admin_bp.route('/partisipan/tambah', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'PJ Acara')
def tambah_partisipan():
    form = PartisipanForm()
    active_edisi = get_active_edisi()

    if form.validate_on_submit():
        if not active_edisi:
            flash("Tidak bisa menambah status partisipan karena tidak ada edisi yang aktif.", "danger")
            return redirect(url_for('admin.data_partisipan'))

        santri_id = form.santri.data
        santri = Santri.query.get(santri_id)

        if santri and santri.status_santri == 'Aktif':
            # Buat record partisipan baru dan kaitkan dengan edisi aktif
            new_partisipan = Partisipan(
                edisi=active_edisi,
                santri=santri,
                kategori=form.kategori.data
            )
            # Update status santri
            santri.status_santri = 'Partisipan'
            
            db.session.add(new_partisipan)
            log_activity('Tambah', 'Partisipan', f"Menetapkan santri '{santri.nama}' sebagai partisipan dengan kategori '{form.kategori.data}'")
            db.session.commit()
            flash(f"Status partisipan untuk {santri.nama} berhasil ditambahkan.", "success")
            return redirect(url_for('admin.data_partisipan'))
        else:
            flash("Santri tidak valid atau statusnya bukan 'Aktif'.", "danger")

    return render_template('tambah_partisipan.html', form=form)


# Tambahkan API Helper baru ini
@admin_bp.route('/api/search-santri-for-partisipan')
def search_santri_for_partisipan_api():
    query = request.args.get('q', '')
    if len(query) < 3:
        return jsonify({'results': []})

    # Cari santri yang namanya cocok DAN statusnya 'Aktif'
    santri_results = Santri.query.filter(
        Santri.nama.ilike(f'%{query}%'),
        Santri.status_santri == 'Aktif'
    ).limit(20).all()

    results = [
        {
            'id': s.id, 
            'nama': s.nama,
            'asrama': s.asrama,
            'kabupaten': s.kabupaten,
            'kelas_formal': s.kelas_formal,
            'kelas_ngaji': s.kelas_ngaji
        } for s in santri_results
    ]
    return jsonify({'results': results})

@admin_bp.route('/partisipan/edit/<int:partisipan_id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'PJ Acara')
def edit_partisipan(partisipan_id):
    partisipan = Partisipan.query.get_or_404(partisipan_id)
    form = PartisipanEditForm(obj=partisipan)

    if form.validate_on_submit():
        partisipan.kategori = form.kategori.data
        log_activity('Edit', 'Partisipan', f"Mengubah kategori partisipan untuk '{partisipan.santri.nama}' menjadi '{form.kategori.data}'")
        db.session.commit()
        flash(f"Kategori untuk {partisipan.santri.nama} berhasil diubah.", "success")
        return redirect(url_for('admin.data_partisipan'))

    return render_template('edit_partisipan.html', form=form, partisipan=partisipan)


@admin_bp.route('/partisipan/hapus/<int:partisipan_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'PJ Acara')
def hapus_partisipan(partisipan_id):
    partisipan = Partisipan.query.get_or_404(partisipan_id)
    santri = partisipan.santri
    nama_santri = santri.nama
    
    # Kembalikan status santri menjadi 'Aktif'
    santri.status_santri = 'Aktif'
    
    log_activity('Hapus', 'Partisipan', f"Menghapus status partisipan untuk '{nama_santri}'")
    db.session.delete(partisipan)
    
    db.session.commit()
    flash(f"Status partisipan untuk '{nama_santri}' telah berhasil dihapus.", "info")
    return redirect(url_for('admin.data_partisipan'))

# --- MANAJEMEN EDISI ---
@admin_bp.route('/edisi')
@login_required
@role_required('Korpus')
def manajemen_edisi():
    semua_edisi = Edisi.query.order_by(Edisi.tahun.desc()).all()
    return render_template('manajemen_edisi.html', semua_edisi=semua_edisi)

@admin_bp.route('/edisi/tambah', methods=['GET', 'POST'])
@login_required
@role_required('Korpus')
def tambah_edisi():
    form = EdisiForm()
    if form.validate_on_submit():
        # Jika edisi baru ini di-set sebagai aktif, nonaktifkan semua yang lain
        if form.is_active.data:
            Edisi.query.update({Edisi.is_active: False})
        
        new_edisi = Edisi(
            nama=form.nama.data,
            tahun=form.tahun.data,
            is_active=form.is_active.data,
            countdown_title=form.countdown_title.data,
            countdown_target_date=form.countdown_target_date.data
        )
        db.session.add(new_edisi)
        log_activity('Tambah', 'Edisi', f"Menambahkan edisi baru: '{form.nama.data}'")
        db.session.commit()
        flash('Edisi baru berhasil ditambahkan.', 'success')
        return redirect(url_for('admin.manajemen_edisi'))
    return render_template('form_edisi.html', form=form, title="Tambah Edisi Baru")

@admin_bp.route('/edisi/edit/<int:edisi_id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus')
def edit_edisi(edisi_id):
    edisi = Edisi.query.get_or_404(edisi_id)
    form = EdisiForm(obj=edisi)
    if form.validate_on_submit():
        # Jika edisi ini di-set sebagai aktif, nonaktifkan semua yang lain
        if form.is_active.data:
            Edisi.query.filter(Edisi.id != edisi_id).update({Edisi.is_active: False})

        edisi.nama = form.nama.data
        edisi.tahun = form.tahun.data
        edisi.is_active = form.is_active.data
        edisi.countdown_title = form.countdown_title.data
        edisi.countdown_target_date = form.countdown_target_date.data
        log_activity('Edit', 'Edisi', f"Mengubah data edisi: '{edisi.nama}'")
        db.session.commit()
        flash('Data edisi berhasil diperbarui.', 'success')
        return redirect(url_for('admin.manajemen_edisi'))
    return render_template('form_edisi.html', form=form, title="Edit Edisi")

@admin_bp.route('/edisi/hapus/<int:edisi_id>', methods=['POST'])
@login_required
@role_required('Korpus')
def hapus_edisi(edisi_id):
    edisi = Edisi.query.get_or_404(edisi_id)
    # Cek apakah edisi ini masih memiliki rombongan, jika iya jangan dihapus
    if edisi.rombongans:
        flash('Edisi ini tidak bisa dihapus karena masih memiliki data rombongan.', 'danger')
        return redirect(url_for('admin.manajemen_edisi'))
    
    nama_edisi = edisi.nama
    log_activity('Hapus', 'Edisi', f"Menghapus edisi: '{nama_edisi}'")
    db.session.delete(edisi)
    db.session.commit()
    flash('Edisi berhasil dihapus.', 'info')
    return redirect(url_for('admin.manajemen_edisi'))

def get_active_edisi():
    """Mencari dan mengembalikan edisi yang sedang aktif."""
    return Edisi.query.filter_by(is_active=True).first()

# --- CONTEXT PROCESSOR ---
# Ini membuat variabel 'active_edisi' tersedia di semua template secara otomatis
@admin_bp.context_processor
def inject_active_edisi():
    return dict(active_edisi=get_active_edisi())

@admin_bp.route('/riwayat')
@login_required
@role_required('Korpus')
def riwayat_edisi():
    # Ambil semua edisi yang statusnya tidak aktif
    arsip_edisi = Edisi.query.filter_by(is_active=False).order_by(Edisi.tahun.desc()).all()
    
    summary_arsip = []
    for edisi in arsip_edisi:
        # --- PERBAIKI QUERY DI SINI ---
        # JOIN secara eksplisit untuk menghindari ambiguitas
        # Kita bisa join pada salah satu (pulang/kembali) karena kita hanya butuh edisi_id
        base_query = Pendaftaran.query.join(
            Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id
        ).filter(Rombongan.edisi_id == edisi.id)

        # Hitung total peserta yang unik
        total_peserta = base_query.distinct(Pendaftaran.santri_id).count()
        
        # Hitung total pemasukan
        total_pemasukan = base_query.with_entities(db.func.sum(Pendaftaran.total_biaya)).scalar() or 0
        
        summary_arsip.append({
            'edisi': edisi,
            'total_peserta': total_peserta,
            'total_pemasukan': total_pemasukan
        })

    return render_template('riwayat_edisi.html', summary_arsip=summary_arsip)


@admin_bp.route('/riwayat/<int:edisi_id>')
@login_required
@role_required('Korpus')
def detail_arsip(edisi_id):
    arsip_edisi = Edisi.query.get_or_404(edisi_id)
    
    # --- MULAI KALKULASI LENGKAP (SAMA SEPERTI DASHBOARD) ---
    stats = {}
    # JOIN eksplisit untuk menghindari ambiguitas
    base_pendaftaran_query = Pendaftaran.query.join(
        Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id
    ).filter(Rombongan.edisi_id == arsip_edisi.id)
    
    pendaftar_list = base_pendaftaran_query.all()
    
    stats['total_peserta'] = len(pendaftar_list)
    stats['total_pemasukan'] = sum(p.total_biaya for p in pendaftar_list)
    
    # Kalkulasi Lunas (contoh sederhana)
    total_lunas = 0
    for p in pendaftar_list:
        if p.status_pulang == 'Lunas' and p.status_kembali in ['Lunas', 'Tidak Ikut']:
            total_lunas += p.total_biaya
        elif p.status_pulang in ['Lunas', 'Tidak Ikut'] and p.status_kembali == 'Lunas':
            total_lunas += p.total_biaya
    stats['total_lunas'] = total_lunas
    stats['total_belum_lunas'] = stats['total_pemasukan'] - stats['total_lunas']
    # Anda bisa tambahkan kalkulasi lain jika perlu...

    semua_rombongan = Rombongan.query.filter_by(edisi=arsip_edisi).order_by(Rombongan.nama_rombongan).all()
    # --- AKHIR KALKULASI ---
    
    return render_template('dashboard.html', 
                           stats=stats, 
                           semua_rombongan=semua_rombongan,
                           is_arsip=True,
                           arsip_edisi_nama=arsip_edisi.nama)

@admin_bp.route('/rombongan/<int:rombongan_id>/tambah-bus', methods=['POST'])
@login_required
@role_required('Korpus', 'Korda')
def tambah_bus(rombongan_id):
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    # Verifikasi kepemilikan untuk Korda
    if current_user.role.name == 'Korda' and rombongan not in current_user.managed_rombongan:
        abort(403)
    
    form = BusForm()
    if form.validate_on_submit():
        new_bus = Bus(
            rombongan_id=rombongan.id,
            nama_armada=form.nama_armada.data,
            nomor_lambung=form.nomor_lambung.data,
            plat_nomor=form.plat_nomor.data,
            kuota=form.kuota.data,
            keterangan=form.keterangan.data
        )
        db.session.add(new_bus)
        log_activity('Tambah', 'Bus', f"Menambah bus '{form.nama_armada.data}' ke rombongan '{rombongan.nama_rombongan}'")
        db.session.commit()
        flash('Bus baru berhasil ditambahkan.', 'success')
    else:
        flash('Gagal menambahkan bus. Pastikan semua field terisi.', 'danger')
    
    return redirect(url_for('admin.edit_rombongan', id=rombongan_id))

@admin_bp.route('/bus/hapus/<int:bus_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'Korda')
def hapus_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    rombongan_id = bus.rombongan_id
    # Verifikasi kepemilikan untuk Korda
    if current_user.role.name == 'Korda' and bus.rombongan not in current_user.managed_rombongan:
        abort(403)

    nama_bus = f"{bus.nama_armada} ({bus.nomor_lambung or bus.plat_nomor})"
    db.session.delete(bus)
    log_activity('Hapus', 'Bus', f"Menghapus bus '{nama_bus}' dari rombongan '{bus.rombongan.nama_rombongan}'")
    db.session.commit()
    flash('Bus berhasil dihapus.', 'info')
    return redirect(url_for('admin.edit_rombongan', id=rombongan_id))

@admin_bp.route('/bus/<int:bus_id>/detail')
@login_required
@role_required('Korpus', 'Korwil', 'Korda', 'Bendahara Pusat')
def detail_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    
    # Verifikasi kepemilikan untuk Korda/Korwil
    if current_user.role.name in ['Korwil', 'Korda']:
        if bus.rombongan not in current_user.managed_rombongan:
            abort(403)

     # Ambil semua pendaftar untuk bus ini
    peserta_pulang = Pendaftaran.query.filter_by(bus_pulang_id=bus.id).all()
    peserta_kembali = Pendaftaran.query.filter_by(bus_kembali_id=bus.id).all()
    
    # --- PENGELOMPOKAN BERDASARKAN TITIK TURUN ---
    grouped_peserta_pulang = defaultdict(list)
    for p in peserta_pulang:
        grouped_peserta_pulang[p.titik_turun].append(p)
    # -----------------------------------------------

    grouped_peserta_kembali = defaultdict(list)
    for p in peserta_kembali:
        grouped_peserta_kembali[p.titik_turun].append(p)

    return render_template('detail_bus.html', 
                           bus=bus, 
                           grouped_peserta_pulang=grouped_peserta_pulang, # Kirim data terkelompok
                           grouped_peserta_kembali=grouped_peserta_kembali,
                           jumlah_peserta_pulang=len(peserta_pulang),
                           jumlah_peserta_kembali=len(peserta_kembali))

@admin_bp.route('/keuangan')
@login_required
@role_required('Korpus', 'Korwil', 'Korda', 'Bendahara Pusat')
def manajemen_keuangan():
    active_edisi = get_active_edisi()
    
    # Inisialisasi dictionary yang lengkap
    financial_data = {
        'global_total': 0, 'global_lunas': 0, 'global_belum_lunas': 0,
        'pulang_total': 0, 'pulang_lunas': 0, 'pulang_belum_lunas': 0,
        'pulang_cash_lunas': 0, 'pulang_transfer_lunas': 0,
        'pulang_cash_belum': 0, 'pulang_transfer_belum': 0,
        'kembali_total': 0, 'kembali_lunas': 0, 'kembali_belum_lunas': 0,
        'kembali_cash_lunas': 0, 'kembali_transfer_lunas': 0,
        'kembali_cash_belum': 0, 'kembali_transfer_belum': 0,
        'alokasi_bus_pulang': 0, 'alokasi_korda_pulang': 0, 'alokasi_pondok_pulang': 0,
        'alokasi_bus_kembali': 0, 'alokasi_korda_kembali': 0, 'alokasi_pondok_kembali': 0
    }

    if active_edisi:
        pendaftaran_query = Pendaftaran.query.join(
            Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id
        ).filter(Rombongan.edisi_id == active_edisi.id)

        managed_rombongan_ids = set()
        if current_user.role.name in ['Korwil', 'Korda']:
            managed_rombongan_ids = {r.id for r in current_user.managed_rombongan}
            if not managed_rombongan_ids:
                pendaftaran_query = pendaftaran_query.filter(db.false())
            else:
                pendaftaran_query = pendaftaran_query.filter(
                    or_(
                        Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                        Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                    )
                )
        
        all_pendaftaran = pendaftaran_query.all()

        for p in all_pendaftaran:
            # Kalkulasi untuk perjalanan pulang
            if p.status_pulang != 'Tidak Ikut' and p.rombongan_pulang_id:
                if current_user.role.name == 'Korpus' or p.rombongan_pulang_id in managed_rombongan_ids:
                    tarif_pulang = Tarif.query.filter_by(rombongan_id=p.rombongan_pulang_id, titik_turun=p.titik_turun).first()
                    if tarif_pulang:
                        biaya_pulang = tarif_pulang.harga_bus + tarif_pulang.fee_korda + 10000
                        financial_data['pulang_total'] += biaya_pulang
                        financial_data['alokasi_bus_pulang'] += tarif_pulang.harga_bus
                        financial_data['alokasi_korda_pulang'] += tarif_pulang.fee_korda
                        financial_data['alokasi_pondok_pulang'] += 10000
                        if p.status_pulang == 'Lunas':
                            financial_data['pulang_lunas'] += biaya_pulang
                            if p.metode_pembayaran_pulang == 'Cash':
                                financial_data['pulang_cash_lunas'] += biaya_pulang
                            elif p.metode_pembayaran_pulang == 'Transfer':
                                financial_data['pulang_transfer_lunas'] += biaya_pulang
                        else: # Belum Bayar
                            financial_data['pulang_belum_lunas'] += biaya_pulang

            # Kalkulasi untuk perjalanan kembali
            if p.status_kembali != 'Tidak Ikut' and p.rombongan_kembali_id and p.titik_jemput_kembali:
                if current_user.role.name == 'Korpus' or p.rombongan_kembali_id in managed_rombongan_ids:
                    tarif_kembali = Tarif.query.filter_by(rombongan_id=p.rombongan_kembali_id, titik_turun=p.titik_jemput_kembali).first()
                    if tarif_kembali:
                        biaya_kembali = tarif_kembali.harga_bus + tarif_kembali.fee_korda + 10000
                        financial_data['kembali_total'] += biaya_kembali
                        financial_data['alokasi_bus_kembali'] += tarif_kembali.harga_bus
                        financial_data['alokasi_korda_kembali'] += tarif_kembali.fee_korda
                        financial_data['alokasi_pondok_kembali'] += 10000
                        if p.status_kembali == 'Lunas':
                            financial_data['kembali_lunas'] += biaya_kembali
                            if p.metode_pembayaran_kembali == 'Cash':
                                financial_data['kembali_cash_lunas'] += biaya_kembali
                            elif p.metode_pembayaran_kembali == 'Transfer':
                                financial_data['kembali_transfer_lunas'] += biaya_kembali
                        else: # Belum Bayar
                            financial_data['kembali_belum_lunas'] += biaya_kembali
        
        # Kalkulasi total global
        financial_data['global_total'] = financial_data['pulang_total'] + financial_data['kembali_total']
        financial_data['global_lunas'] = financial_data['pulang_lunas'] + financial_data['kembali_lunas']
        financial_data['global_belum_lunas'] = financial_data['global_total'] - financial_data['global_lunas']

    return render_template('manajemen_keuangan.html', data=financial_data)

@admin_bp.route('/keuangan/export-pdf')
@login_required
@role_required('Korpus', 'Korwil', 'Korda')
def export_keuangan_pdf():
    active_edisi = get_active_edisi()
    
    # 1. Inisialisasi dictionary data yang lengkap
    data = {
        'global_total': 0, 'global_lunas': 0, 'global_belum_lunas': 0,
        'pulang_total': 0, 'pulang_lunas': 0, 'pulang_belum_lunas': 0,
        'kembali_total': 0, 'kembali_lunas': 0, 'kembali_belum_lunas': 0,
        'alokasi_bus_pulang': 0, 'alokasi_korda_pulang': 0, 'alokasi_pondok_pulang': 0,
        'alokasi_bus_kembali': 0, 'alokasi_korda_kembali': 0, 'alokasi_pondok_kembali': 0,
        'pulang_cash_lunas_rp': 0, 'pulang_cash_belum_lunas_rp': 0,
        'pulang_transfer_lunas_rp': 0, 'pulang_transfer_belum_lunas_rp': 0,
        'kembali_cash_lunas_rp': 0, 'kembali_cash_belum_lunas_rp': 0,
        'kembali_transfer_lunas_rp': 0, 'kembali_transfer_belum_lunas_rp': 0,
    }

    if active_edisi:
        # 2. Query data pendaftaran secara efisien dengan filter Korda/Korwil
        pendaftaran_query = Pendaftaran.query.options(
            selectinload(Pendaftaran.rombongan_pulang).selectinload(Rombongan.tarifs),
            selectinload(Pendaftaran.rombongan_kembali).selectinload(Rombongan.tarifs)
        ).filter(Pendaftaran.edisi_id == active_edisi.id)

        managed_rombongan_ids = []
        if current_user.role.name in ['Korwil', 'Korda']:
            managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
            if not managed_rombongan_ids:
                pendaftaran_query = pendaftaran_query.filter(db.false())
            else:
                pendaftaran_query = pendaftaran_query.filter(
                    or_(
                        Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                        Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                    )
                )
        
        all_pendaftaran = pendaftaran_query.all()

        # 3. Loop dan lakukan semua kalkulasi secara lengkap dan andal
        for p in all_pendaftaran:
            # Kalkulasi untuk perjalanan pulang
            if p.status_pulang != 'Tidak Ikut' and p.rombongan_pulang:
                if current_user.role.name == 'Korpus' or p.rombongan_pulang_id in managed_rombongan_ids:
                    tarif_pulang = next((t for t in p.rombongan_pulang.tarifs if t.titik_turun == p.titik_turun), None)
                    if tarif_pulang:
                        biaya_pulang = tarif_pulang.harga_bus + tarif_pulang.fee_korda + 10000
                        data['pulang_total'] += biaya_pulang
                        if p.status_pulang == 'Lunas':
                            data['pulang_lunas'] += biaya_pulang
                            data['alokasi_bus_pulang'] += tarif_pulang.harga_bus
                            data['alokasi_korda_pulang'] += tarif_pulang.fee_korda
                            data['alokasi_pondok_pulang'] += 10000
                            if p.metode_pembayaran_pulang == 'Cash': 
                                data['pulang_cash_lunas_rp'] += biaya_pulang
                            elif p.metode_pembayaran_pulang == 'Transfer': 
                                data['pulang_transfer_lunas_rp'] += biaya_pulang
                        else: # Belum Bayar
                            if p.metode_pembayaran_pulang == 'Cash': 
                                data['pulang_cash_belum_lunas_rp'] += biaya_pulang
                            elif p.metode_pembayaran_pulang == 'Transfer': 
                                data['pulang_transfer_belum_lunas_rp'] += biaya_pulang
            
            # Kalkulasi untuk perjalanan kembali
            rombongan_kembali = p.rombongan_kembali or p.rombongan_pulang
            titik_jemput = p.titik_jemput_kembali or p.titik_turun
            if p.status_kembali != 'Tidak Ikut' and rombongan_kembali and titik_jemput:
                if current_user.role.name == 'Korpus' or rombongan_kembali.id in managed_rombongan_ids:
                    tarif_kembali = next((t for t in rombongan_kembali.tarifs if t.titik_turun == titik_jemput), None)
                    if tarif_kembali:
                        biaya_kembali = tarif_kembali.harga_bus + tarif_kembali.fee_korda + 10000
                        data['kembali_total'] += biaya_kembali
                        if p.status_kembali == 'Lunas':
                            data['kembali_lunas'] += biaya_kembali
                            data['alokasi_bus_kembali'] += tarif_kembali.harga_bus
                            data['alokasi_korda_kembali'] += tarif_kembali.fee_korda
                            data['alokasi_pondok_kembali'] += 10000
                            if p.metode_pembayaran_kembali == 'Cash': 
                                data['kembali_cash_lunas_rp'] += biaya_kembali
                            elif p.metode_pembayaran_kembali == 'Transfer': 
                                data['kembali_transfer_lunas_rp'] += biaya_kembali
                        else: # Belum Bayar
                            if p.metode_pembayaran_kembali == 'Cash': 
                                data['kembali_cash_belum_lunas_rp'] += biaya_kembali
                            elif p.metode_pembayaran_kembali == 'Transfer': 
                                data['kembali_transfer_belum_lunas_rp'] += biaya_kembali

        # Kalkulasi total turunan
        data['pulang_belum_lunas'] = data['pulang_total'] - data['pulang_lunas']
        data['kembali_belum_lunas'] = data['kembali_total'] - data['kembali_lunas']
        data['global_total'] = data['pulang_total'] + data['kembali_total']
        data['global_lunas'] = data['pulang_lunas'] + data['kembali_lunas']
        data['global_belum_lunas'] = data['global_total'] - data['global_lunas']

    # 4. Proses Pembuatan PDF dengan tampilan yang enhanced
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=1.5*cm, 
        leftMargin=1.5*cm, 
        topMargin=2*cm, 
        bottomMargin=2*cm
    )
    elements = []
    styles = getSampleStyleSheet()

    # Custom styles untuk tampilan yang lebih menarik
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        textColor=colors.HexColor('#2c3e50'),
        alignment=1,  # Center alignment
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.HexColor('#34495e'),
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        alignment=1  # Center for subtitle
    )

    def format_rupiah(amount):
        return f"Rp {int(amount):,.0f}".replace(',', '.')

    # Header PDF dengan styling yang menarik
    title = Paragraph("LAPORAN MANAJEMEN KEUANGAN", title_style)
    elements.append(title)
    
    if active_edisi:
        subtitle_text = f"<b>Edisi: {active_edisi.nama}</b><br/>"
        subtitle_text += f"Tanggal Cetak: {datetime.now().strftime('%d %B %Y, %H:%M')} WIB<br/>"
        subtitle_text += f"Dicetak oleh: {current_user.username} ({current_user.role.name})"
        subtitle = Paragraph(subtitle_text, normal_style)
    else:
        subtitle = Paragraph("<b>Tidak ada edisi aktif</b>", normal_style)
    
    elements.append(subtitle)
    elements.append(Spacer(1, 1*cm))

    # Konten PDF yang lebih lengkap dan menarik
    if active_edisi and data['global_total'] > 0:
        
        # 1. RINGKASAN GLOBAL
        elements.append(Paragraph("RINGKASAN KEUANGAN GLOBAL", heading_style))
        
        global_data = [
            ['Kategori', 'Jumlah', 'Persentase'],
            ['Total Pemasukan', format_rupiah(data['global_total']), '100%'],
            ['Total Diterima (Lunas)', format_rupiah(data['global_lunas']), 
             f"{(data['global_lunas']/data['global_total']*100):.1f}%" if data['global_total'] > 0 else "0%"],
            ['Sisa Tagihan (Belum Lunas)', format_rupiah(data['global_belum_lunas']), 
             f"{(data['global_belum_lunas']/data['global_total']*100):.1f}%" if data['global_total'] > 0 else "0%"],
        ]
        
        global_table = Table(global_data, colWidths=[6*cm, 4*cm, 3*cm])
        global_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ecf0f1')),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#d5f4e6')),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#fadbd8')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(global_table)
        elements.append(Spacer(1, 0.8*cm))

        # 2. RINCIAN PERJALANAN PULANG
        elements.append(Paragraph("RINCIAN PERJALANAN PULANG", heading_style))
        
        pulang_summary_data = [
            ['Kategori', 'Jumlah'],
            ['Total Pemasukan', format_rupiah(data['pulang_total'])],
            ['Jumlah Lunas', format_rupiah(data['pulang_lunas'])],
            ['Jumlah Belum Lunas', format_rupiah(data['pulang_belum_lunas'])],
        ]
        
        pulang_summary_table = Table(pulang_summary_data, colWidths=[7*cm, 4*cm])
        pulang_summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ebf3fd')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(pulang_summary_table)
        elements.append(Spacer(1, 0.5*cm))

        # Detail metode pembayaran pulang
        pulang_detail_data = [
            ['Metode Pembayaran', 'Status', 'Jumlah'],
            ['Cash', 'Lunas', format_rupiah(data['pulang_cash_lunas_rp'])],
            ['Cash', 'Belum Lunas', format_rupiah(data['pulang_cash_belum_lunas_rp'])],
            ['Transfer', 'Lunas', format_rupiah(data['pulang_transfer_lunas_rp'])],
            ['Transfer', 'Belum Lunas', format_rupiah(data['pulang_transfer_belum_lunas_rp'])],
        ]
        
        pulang_detail_table = Table(pulang_detail_data, colWidths=[4*cm, 3*cm, 4*cm])
        pulang_detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (0, 2), colors.HexColor('#f8f9fa')),  # Cash rows
            ('BACKGROUND', (0, 3), (0, 4), colors.HexColor('#e3f2fd')),  # Transfer rows
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#d5f4e6')),  # Lunas
            ('BACKGROUND', (1, 2), (1, 2), colors.HexColor('#fadbd8')),  # Belum Lunas
            ('BACKGROUND', (1, 3), (1, 3), colors.HexColor('#d5f4e6')),  # Lunas
            ('BACKGROUND', (1, 4), (1, 4), colors.HexColor('#fadbd8')),  # Belum Lunas
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(pulang_detail_table)
        elements.append(Spacer(1, 0.8*cm))

        # 3. RINCIAN PERJALANAN KEMBALI
        elements.append(Paragraph("RINCIAN PERJALANAN KEMBALI", heading_style))
        
        kembali_summary_data = [
            ['Kategori', 'Jumlah'],
            ['Total Pemasukan', format_rupiah(data['kembali_total'])],
            ['Jumlah Lunas', format_rupiah(data['kembali_lunas'])],
            ['Jumlah Belum Lunas', format_rupiah(data['kembali_belum_lunas'])],
        ]
        
        kembali_summary_table = Table(kembali_summary_data, colWidths=[7*cm, 4*cm])
        kembali_summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fdeaea')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(kembali_summary_table)
        elements.append(Spacer(1, 0.5*cm))

        # Detail metode pembayaran kembali
        kembali_detail_data = [
            ['Metode Pembayaran', 'Status', 'Jumlah'],
            ['Cash', 'Lunas', format_rupiah(data['kembali_cash_lunas_rp'])],
            ['Cash', 'Belum Lunas', format_rupiah(data['kembali_cash_belum_lunas_rp'])],
            ['Transfer', 'Lunas', format_rupiah(data['kembali_transfer_lunas_rp'])],
            ['Transfer', 'Belum Lunas', format_rupiah(data['kembali_transfer_belum_lunas_rp'])],
        ]
        
        kembali_detail_table = Table(kembali_detail_data, colWidths=[4*cm, 3*cm, 4*cm])
        kembali_detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0392b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (0, 2), colors.HexColor('#f8f9fa')),  # Cash rows
            ('BACKGROUND', (0, 3), (0, 4), colors.HexColor('#ffe8e8')),  # Transfer rows
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#d5f4e6')),  # Lunas
            ('BACKGROUND', (1, 2), (1, 2), colors.HexColor('#fadbd8')),  # Belum Lunas
            ('BACKGROUND', (1, 3), (1, 3), colors.HexColor('#d5f4e6')),  # Lunas
            ('BACKGROUND', (1, 4), (1, 4), colors.HexColor('#fadbd8')),  # Belum Lunas
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(kembali_detail_table)
        elements.append(Spacer(1, 0.8*cm))

        # 4. ALOKASI FEE
        elements.append(Paragraph("ALOKASI FEE", heading_style))
        
        fee_data = [
            ['Kategori', 'Pulang', 'Kembali', 'Total'],
            ['Biaya Bus', 
             format_rupiah(data['alokasi_bus_pulang']), 
             format_rupiah(data['alokasi_bus_kembali']), 
             format_rupiah(data['alokasi_bus_pulang'] + data['alokasi_bus_kembali'])],
            ['Fee Korda', 
             format_rupiah(data['alokasi_korda_pulang']), 
             format_rupiah(data['alokasi_korda_kembali']), 
             format_rupiah(data['alokasi_korda_pulang'] + data['alokasi_korda_kembali'])],
            ['Fee Pondok', 
             format_rupiah(data['alokasi_pondok_pulang']), 
             format_rupiah(data['alokasi_pondok_kembali']), 
             format_rupiah(data['alokasi_pondok_pulang'] + data['alokasi_pondok_kembali'])],
            ['TOTAL ALOKASI', 
             format_rupiah(data['pulang_total']), 
             format_rupiah(data['kembali_total']), 
             format_rupiah(data['global_total'])],
        ]
        
        fee_table = Table(fee_data, colWidths=[4*cm, 3*cm, 3*cm, 3*cm])
        fee_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9b59b6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 3), colors.HexColor('#f4ecf7')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#8e44ad')),
            ('TEXTCOLOR', (0, 4), (-1, 4), colors.whitesmoke),
            ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(fee_table)

    else:
        # No data available
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['Normal'],
            fontSize=12,
            alignment=1,
            spaceAfter=20,
            textColor=colors.HexColor('#e74c3c')
        )
        elements.append(Paragraph("Tidak ada data keuangan untuk ditampilkan.", no_data_style))
        elements.append(Paragraph("Pastikan ada edisi yang aktif dan terdapat data pendaftaran.", styles['Normal']))

    # Footer
    elements.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1,
        borderWidth=1,
        borderColor=colors.grey,
        borderPadding=5
    )
    
    footer_text = f"Laporan ini digenerate secara otomatis oleh sistem pada {datetime.now().strftime('%d %B %Y, %H:%M:%S')} WIB"
    elements.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"laporan_keuangan_{active_edisi.nama if active_edisi else 'no_edition'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@admin_bp.route('/api/rombongan-detail/<int:rombongan_id>')
@login_required
def api_rombongan_detail(rombongan_id):
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    
    tarifs_data = [{'titik_turun': t.titik_turun} for t in rombongan.tarifs]
    
    buses_data = []
    for bus in rombongan.buses:
        terisi_kembali = Pendaftaran.query.filter_by(bus_kembali_id=bus.id).count()
        sisa_kuota_kembali = bus.kuota - terisi_kembali
        buses_data.append({
            'id': bus.id,
            'nama_armada': bus.nama_armada,
            'nomor_lambung': bus.nomor_lambung,
            'plat_nomor': bus.plat_nomor,
            'sisa_kuota_kembali': sisa_kuota_kembali
        })

    return jsonify({
        'tarifs': tarifs_data,
        'buses': buses_data
    })

@admin_bp.route('/korlapda')
@login_required
@role_required('Korpus', 'Korda')
def manajemen_korlapda():
    active_edisi = get_active_edisi()
    
    # Query dasar untuk user dengan peran Korlapda
    users_query = User.query.join(Role).filter(Role.name == 'Korlapda')

    # Filter berdasarkan edisi aktif
    if active_edisi:
        users_query = users_query.join(Bus).join(Rombongan).filter(Rombongan.edisi_id == active_edisi.id)
    else:
        users_query = users_query.filter(db.false()) # Tampilkan kosong jika tidak ada edisi aktif

    # Terapkan filter hak akses untuk Korda
    if current_user.role.name == 'Korda':
        managed_bus_ids = [bus.id for rombongan in current_user.managed_rombongan for bus in rombongan.buses]
        users_query = users_query.filter(User.bus_id.in_(managed_bus_ids))

    all_korlapda = users_query.all()
    return render_template('manajemen_korlapda.html', all_korlapda=all_korlapda)

@admin_bp.route('/korlapda/tambah', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda')
def tambah_korlapda():
    form = KorlapdaForm()
    active_edisi = get_active_edisi()

    # Logika untuk mengisi pilihan bus
    bus_choices = []
    if active_edisi:
        if current_user.role.name == 'Korda':
            bus_choices = [
                (bus.id, f"{bus.rombongan.nama_rombongan}: {bus.nama_armada} - {bus.nomor_lambung or bus.plat_nomor}")
                for rombongan in current_user.managed_rombongan for bus in rombongan.buses
            ]
        else: # Untuk Korpus
            all_buses = Bus.query.join(Rombongan).filter(Rombongan.edisi_id == active_edisi.id).all()
            bus_choices = [(bus.id, f"{bus.rombongan.nama_rombongan}: {bus.nama_armada}...") for bus in all_buses]
    
    form.bus.choices = [('', '-- Pilih Bus --')] + bus_choices
    
    if form.validate_on_submit():
        if not active_edisi:
            flash("Tidak bisa menambah Korlapda karena tidak ada edisi aktif.", "danger")
            return redirect(url_for('admin.manajemen_korlapda'))

        korlapda_role = Role.query.filter_by(name='Korlapda').first()
        if not korlapda_role:
            # Buat role jika belum ada
            korlapda_role = Role(name='Korlapda')
            db.session.add(korlapda_role)
            db.session.commit()
            
        new_user = User(
            username=form.username.data,
            role=korlapda_role,
            bus_id=form.bus.data
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User Korlapda "{new_user.username}" berhasil dibuat.', 'success')
        return redirect(url_for('admin.manajemen_korlapda'))
        
    return render_template('form_korlapda.html', form=form, title="Tambah Korlapda Baru")

@admin_bp.route('/korlapda/hapus/<int:user_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'Korda')
def hapus_korlapda(user_id):
    user = User.query.get_or_404(user_id)
    # Verifikasi kepemilikan untuk Korda
    if current_user.role.name == 'Korda':
        managed_bus_ids = [bus.id for rombongan in current_user.managed_rombongan for bus in rombongan.buses]
        if user.bus_id not in managed_bus_ids:
            abort(403)
            
    db.session.delete(user)
    db.session.commit()
    flash(f'User Korlapda "{user.username}" berhasil dihapus.', 'info')
    return redirect(url_for('admin.manajemen_korlapda'))

def log_activity(action_type, feature, description):
    """Fungsi untuk mencatat aktivitas user."""
    try:
        log = ActivityLog(
            user_id=current_user.id,
            action_type=action_type,
            feature=feature,
            description=description
        )
        db.session.add(log)
    except Exception as e:
        print(f"Error saat mencatat log: {e}")

@admin_bp.route('/log-aktivitas')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara', 'Bendahara Pusat')
def log_aktivitas():
    page = request.args.get('page', 1, type=int)
    
    # Query dasar untuk semua log
    query = ActivityLog.query.order_by(ActivityLog.timestamp.desc())

    # --- FILTER BERDASARKAN HAK AKSES ---
    role = current_user.role.name
    if role == 'Korwil' or role == 'Korda':
        # Filter log yang deskripsinya mengandung nama rombongan yang dikelola
        managed_rombongan_names = [r.nama_rombongan for r in current_user.managed_rombongan]
        if managed_rombongan_names:
            query = query.filter(or_(*[ActivityLog.description.like(f'%{name}%') for name in managed_rombongan_names]))
        else:
            query = query.filter(db.false()) # Jika tidak kelola rombongan, jangan tampilkan apa-apa
    elif role == 'Keamanan':
        query = query.filter(ActivityLog.feature == 'Perizinan')
    elif role == 'PJ Acara':
        query = query.filter(ActivityLog.feature == 'Partisipan')
    
    # --- FILTER DARI INPUT USER ---
    f_user_id = request.args.get('user_id', type=int)
    f_action_type = request.args.get('action_type')
    f_start_date = request.args.get('start_date')
    
    if f_user_id:
        query = query.filter_by(user_id=f_user_id)
    if f_action_type:
        query = query.filter_by(action_type=f_action_type)
    if f_start_date:
        start_date = datetime.strptime(f_start_date, '%Y-%m-%d')
        query = query.filter(ActivityLog.timestamp >= start_date)

    logs = query.paginate(page=page, per_page=50, error_out=False)
    
    # Ambil data untuk mengisi dropdown filter
    all_users = User.query.order_by(User.username).all()
    action_types = db.session.query(ActivityLog.action_type).distinct().all()

    return render_template(
        'log_aktivitas.html', 
        logs=logs,
        all_users=all_users,
        action_types=[a[0] for a in action_types]
    )

@admin_bp.route('/santri-wilayah')
@login_required
@role_required('Korpus', 'Korwil', 'Korda', 'Bendahara Pusat')
def manajemen_santri_wilayah():
    """Menampilkan daftar santri yang relevan dengan wilayah Korda/Korwil dengan statistik dan filter detail."""
    active_edisi = get_active_edisi()
    if not active_edisi:
        flash('Tidak ada edisi yang aktif.', 'warning')
        return render_template('manajemen_santri_wilayah.html', pagination=None, stats={}, pendaftaran_map={})

    # 1. Tentukan santri dan rombongan yang relevan berdasarkan cakupan wilayah user
    santri_in_wilayah_ids = []
    managed_rombongan_ids = []
    
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        wilayah_kelolaan = set()
        for rombongan in current_user.managed_rombongan:
            if rombongan.cakupan_wilayah:
                for wilayah in rombongan.cakupan_wilayah:
                    wilayah_kelolaan.add(wilayah.get('label'))
        
        if wilayah_kelolaan:
            santri_in_wilayah_ids = [s.id for s in Santri.query.with_entities(Santri.id).filter(Santri.kabupaten.in_(list(wilayah_kelolaan))).all()]
    else: # Korpus melihat semua santri
        santri_in_wilayah_ids = [s.id for s in Santri.query.with_entities(Santri.id).all()]

    # 2. Hitung semua statistik yang dibutuhkan
    stats = {}
    if santri_in_wilayah_ids:
        # Statistik Total Santri di Wilayah
        stats['total_putra'] = Santri.query.filter(Santri.id.in_(santri_in_wilayah_ids), Santri.jenis_kelamin == 'PUTRA').count()
        stats['total_putri'] = Santri.query.filter(Santri.id.in_(santri_in_wilayah_ids), Santri.jenis_kelamin == 'PUTRI').count()
        
        # Logika perhitungan statistik pendaftaran yang presisi
        base_pendaftaran_query = Pendaftaran.query.filter(
            Pendaftaran.edisi_id == active_edisi.id,
            Pendaftaran.santri_id.in_(santri_in_wilayah_ids)
        )

        if current_user.role.name in ['Korwil', 'Korda'] and managed_rombongan_ids:
            # Untuk Korda/Korwil, hitung hanya yang terkait rombongan mereka
            pendaftar_ids_managed = db.session.query(Pendaftaran.santri_id).filter(
                Pendaftaran.edisi_id == active_edisi.id,
                Pendaftaran.santri_id.in_(santri_in_wilayah_ids),
                or_(
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                    Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                )
            ).distinct().all()
            pendaftar_ids = [p[0] for p in pendaftar_ids_managed]

            # Detail Perjalanan (hanya dari rombongan yang dikelola)
            stats['total_pulang_putra'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids), Pendaftaran.status_pulang != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRA').count()
            stats['total_pulang_putri'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids), Pendaftaran.status_pulang != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRI').count()
            stats['total_kembali_putra'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids), Pendaftaran.status_kembali != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRA').count()
            stats['total_kembali_putri'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids), Pendaftaran.status_kembali != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRI').count()
        else: # Untuk Korpus, hitung semua pendaftaran di wilayah tersebut
            pendaftar_ids_all = db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids)).distinct().all()
            pendaftar_ids = [p[0] for p in pendaftar_ids_all]
            stats['total_pulang_putra'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.status_pulang != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRA').count()
            stats['total_pulang_putri'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.status_pulang != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRI').count()
            stats['total_kembali_putra'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.status_kembali != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRA').count()
            stats['total_kembali_putri'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(Pendaftaran.status_kembali != 'Tidak Ikut', Santri.jenis_kelamin == 'PUTRI').count()
        if current_user.role.name in ['Korwil', 'Korda'] and managed_rombongan_ids:
    # Hitung yang sudah daftar pulang per jenis kelamin (dari rombongan yang dikelola)
            stats['putra_daftar_pulang'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids), 
                Pendaftaran.status_pulang != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRA'
            ).distinct(Pendaftaran.santri_id).count()
    
            stats['putri_daftar_pulang'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids), 
                Pendaftaran.status_pulang != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRI'
            ).distinct(Pendaftaran.santri_id).count()
    
    # Hitung yang sudah daftar kembali per jenis kelamin (dari rombongan yang dikelola)
            stats['putra_daftar_kembali'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids), 
                Pendaftaran.status_kembali != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRA'
            ).distinct(Pendaftaran.santri_id).count()
    
            stats['putri_daftar_kembali'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids), 
                Pendaftaran.status_kembali != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRI'
            ).distinct(Pendaftaran.santri_id).count()
    
        else:  # Untuk Korpus
            stats['putra_daftar_pulang'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.status_pulang != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRA'
            ).distinct(Pendaftaran.santri_id).count()
    
            stats['putri_daftar_pulang'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.status_pulang != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRI'
            ).distinct(Pendaftaran.santri_id).count()
    
            stats['putra_daftar_kembali'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.status_kembali != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRA'
            ).distinct(Pendaftaran.santri_id).count()
    
            stats['putri_daftar_kembali'] = base_pendaftaran_query.join(Pendaftaran.santri).filter(
                Pendaftaran.status_kembali != 'Tidak Ikut', 
                Santri.jenis_kelamin == 'PUTRI'
            ).distinct(Pendaftaran.santri_id).count()
        # Update stats turunan berdasarkan pendaftar yang relevan
        stats['putra_terdaftar'] = Santri.query.filter(Santri.id.in_(pendaftar_ids), Santri.jenis_kelamin == 'PUTRA').count()
        stats['putri_terdaftar'] = Santri.query.filter(Santri.id.in_(pendaftar_ids), Santri.jenis_kelamin == 'PUTRI').count()
        stats['putra_belum_daftar'] = stats['total_putra'] - stats['putra_terdaftar']
        stats['putri_belum_daftar'] = stats['total_putri'] - stats['putri_terdaftar']
        stats['total_pendaftaran'] = len(pendaftar_ids)

    # 3. Siapkan query dasar untuk daftar santri di tabel
    query = Santri.query.filter(Santri.id.in_(santri_in_wilayah_ids))

    # 4. Terapkan filter dari form
    nama_filter = request.args.get('nama')
    gender_filter = request.args.get('jenis_kelamin')
    status_santri_filter = request.args.get('status_santri')
    status_daftar_filter = request.args.get('status_daftar')

    if nama_filter:
        query = query.filter(Santri.nama.ilike(f'%{nama_filter}%'))
    if gender_filter:
        query = query.filter(Santri.jenis_kelamin == gender_filter)
    if status_santri_filter:
        query = query.filter(Santri.status_santri == status_santri_filter)
    
    # Blok logika filter pendaftaran baru yang andal
    if status_daftar_filter and santri_in_wilayah_ids:
        rombongan_filter_pulang = db.true()
        rombongan_filter_kembali = db.true()
        if current_user.role.name in ['Korwil', 'Korda'] and managed_rombongan_ids:
            rombongan_filter_pulang = Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids)
            rombongan_filter_kembali = or_(
                Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids),
                and_(Pendaftaran.rombongan_kembali_id.is_(None), Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids))
            )

        if status_daftar_filter == 'sudah_pulang':
            santri_ids = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_pulang != 'Tidak Ikut', rombongan_filter_pulang).distinct()]
            query = query.filter(Santri.id.in_(santri_ids))
        elif status_daftar_filter == 'belum_pulang':
            santri_ids_sudah = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_pulang != 'Tidak Ikut', rombongan_filter_pulang).distinct()]
            query = query.filter(Santri.id.notin_(santri_ids_sudah))
        elif status_daftar_filter == 'sudah_kembali':
            santri_ids = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_kembali != 'Tidak Ikut', rombongan_filter_kembali).distinct()]
            query = query.filter(Santri.id.in_(santri_ids))
        elif status_daftar_filter == 'belum_kembali':
            santri_ids_sudah = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_kembali != 'Tidak Ikut', rombongan_filter_kembali).distinct()]
            query = query.filter(Santri.id.notin_(santri_ids_sudah))
    
    # 5. Lakukan paginasi
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pagination = query.order_by(Santri.nama).paginate(page=page, per_page=per_page, error_out=False)
    
    # 6. Ambil data pendaftaran yang relevan untuk santri di halaman saat ini
    santri_ids_on_page = [s.id for s in pagination.items]
    pendaftaran_map = {}
    if santri_ids_on_page:
        pendaftarans_on_page = Pendaftaran.query.options(
            selectinload(Pendaftaran.bus_pulang),
            selectinload(Pendaftaran.bus_kembali)
        ).filter(
            Pendaftaran.edisi_id == active_edisi.id,
            Pendaftaran.santri_id.in_(santri_ids_on_page)
        ).all()
        pendaftaran_map = {p.santri_id: p for p in pendaftarans_on_page}

    # 7. Render template dengan semua data
    return render_template('manajemen_santri_wilayah.html',
                           pagination=pagination,
                           stats=stats,
                           pendaftaran_map=pendaftaran_map,
                           active_edisi=active_edisi)


@admin_bp.route('/export-santri-wilayah')
@login_required
@role_required('Korpus', 'Korwil', 'Korda')
def export_santri_wilayah():
    """Export data santri wilayah ke Excel dengan filter yang sama - SEMUA SANTRI AKAN TERMUAT"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import make_response
    from io import BytesIO
    import datetime
    
    # Get active edition
    active_edisi = get_active_edisi()
    if not active_edisi:
        flash('Tidak ada edisi yang aktif.', 'warning')
        return redirect(url_for('admin.manajemen_santri_wilayah'))

    # Get export type (pulang atau kembali)
    export_type = request.args.get('type', 'pulang')  # default pulang
    
    # Get the same santri and rombongan data as the main view
    santri_in_wilayah_ids = []
    managed_rombongan_ids = []
    
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        wilayah_kelolaan = set()
        for rombongan in current_user.managed_rombongan:
            if rombongan.cakupan_wilayah:
                for wilayah in rombongan.cakupan_wilayah:
                    wilayah_kelolaan.add(wilayah.get('label'))
        
        if wilayah_kelolaan:
            santri_in_wilayah_ids = [s.id for s in Santri.query.with_entities(Santri.id).filter(Santri.kabupaten.in_(list(wilayah_kelolaan))).all()]
    else:
        santri_in_wilayah_ids = [s.id for s in Santri.query.with_entities(Santri.id).all()]

    # MODIFIED: Get ALL santri in wilayah first (no registration filter)
    base_query = Santri.query.filter(Santri.id.in_(santri_in_wilayah_ids))
    
    # Apply basic filters (nama, gender, status_santri)
    nama_filter = request.args.get('nama')
    gender_filter = request.args.get('jenis_kelamin')
    status_santri_filter = request.args.get('status_santri')
    status_daftar_filter = request.args.get('status_daftar')

    if nama_filter:
        base_query = base_query.filter(Santri.nama.ilike(f'%{nama_filter}%'))
    if gender_filter:
        base_query = base_query.filter(Santri.jenis_kelamin == gender_filter)
    if status_santri_filter:
        base_query = base_query.filter(Santri.status_santri == status_santri_filter)
    
    # Get all santri matching basic filters
    all_santri = base_query.order_by(Santri.nama).all()
    
    # MODIFIED: Apply registration status filter ONLY for filtering, but keep all santri for export
    filtered_santri_ids = set([s.id for s in all_santri])  # Start with all santri
    
    if status_daftar_filter and santri_in_wilayah_ids:
        rombongan_filter_pulang = db.true()
        rombongan_filter_kembali = db.true()
        if current_user.role.name in ['Korwil', 'Korda'] and managed_rombongan_ids:
            rombongan_filter_pulang = Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids)
            rombongan_filter_kembali = or_(
                Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids),
                and_(Pendaftaran.rombongan_kembali_id.is_(None), Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids))
            )

        if status_daftar_filter == 'sudah_pulang':
            santri_ids = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_pulang != 'Tidak Ikut', rombongan_filter_pulang).distinct()]
            filtered_santri_ids = set(santri_ids)
        elif status_daftar_filter == 'belum_pulang':
            santri_ids_sudah = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_pulang != 'Tidak Ikut', rombongan_filter_pulang).distinct()]
            filtered_santri_ids = filtered_santri_ids - set(santri_ids_sudah)
        elif status_daftar_filter == 'sudah_kembali':
            santri_ids = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_kembali != 'Tidak Ikut', rombongan_filter_kembali).distinct()]
            filtered_santri_ids = set(santri_ids)
        elif status_daftar_filter == 'belum_kembali':
            santri_ids_sudah = [s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(Pendaftaran.edisi_id == active_edisi.id, Pendaftaran.santri_id.in_(santri_in_wilayah_ids), Pendaftaran.status_kembali != 'Tidak Ikut', rombongan_filter_kembali).distinct()]
            filtered_santri_ids = filtered_santri_ids - set(santri_ids_sudah)
    
    # MODIFIED: For export, show all santri but apply additional rombongan filter if needed
    export_santri_ids = filtered_santri_ids.copy()
    
    # ADDITIONAL FILTER: Only include santri registered in managed rombongan for specific export type
    # BUT keep unregistered santri as well
    if current_user.role.name in ['Korwil', 'Korda'] and managed_rombongan_ids:
        if export_type == 'pulang':
            # Get santri registered in managed rombongan for pulang
            santri_ids_in_managed_rombongan = [
                s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(
                    Pendaftaran.edisi_id == active_edisi.id,
                    Pendaftaran.santri_id.in_(santri_in_wilayah_ids),
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids)
                ).distinct()
            ]
        else:  # kembali
            # Get santri registered in managed rombongan for kembali
            santri_ids_in_managed_rombongan = [
                s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(
                    Pendaftaran.edisi_id == active_edisi.id,
                    Pendaftaran.santri_id.in_(santri_in_wilayah_ids),
                    or_(
                        Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids),
                        and_(
                            Pendaftaran.rombongan_kembali_id.is_(None), 
                            Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids)
                        )
                    )
                ).distinct()
            ]
        
        # Get unregistered santri in the filtered list
        all_registered_santri = [
            s_id for s_id, in db.session.query(Pendaftaran.santri_id).filter(
                Pendaftaran.edisi_id == active_edisi.id,
                Pendaftaran.santri_id.in_(list(filtered_santri_ids))
            ).distinct()
        ]
        unregistered_santri_ids = filtered_santri_ids - set(all_registered_santri)
        
        # Combine registered santri in managed rombongan + all unregistered santri
        export_santri_ids = set(santri_ids_in_managed_rombongan) | unregistered_santri_ids
    
    # Get final santri list for export
    santri_list = [s for s in all_santri if s.id in export_santri_ids]
    
    # Get pendaftaran data for all santri with tarif data
    santri_ids = [s.id for s in santri_list]
    pendaftaran_map = {}
    tarif_map = {}
    
    if santri_ids:
        pendaftarans = Pendaftaran.query.options(
            selectinload(Pendaftaran.bus_pulang),
            selectinload(Pendaftaran.bus_kembali),
            selectinload(Pendaftaran.rombongan_pulang),
            selectinload(Pendaftaran.rombongan_kembali)
        ).filter(
            Pendaftaran.edisi_id == active_edisi.id,
            Pendaftaran.santri_id.in_(santri_ids)
        ).all()
        pendaftaran_map = {p.santri_id: p for p in pendaftarans}
        
        # Get tarif data untuk kalkulasi biaya
        for p in pendaftarans:
            if p.rombongan_pulang_id and p.titik_turun:
                tarif = Tarif.query.filter_by(
                    rombongan_id=p.rombongan_pulang_id, 
                    titik_turun=p.titik_turun
                ).first()
                if tarif:
                    tarif_map[f"{p.rombongan_pulang_id}_{p.titik_turun}"] = tarif

    # Create workbook
    wb = Workbook()
    ws = wb.active
    
    # Set worksheet title based on export type
    if export_type == 'pulang':
        ws.title = "Data Perjalanan Pulang"
    else:
        ws.title = "Data Perjalanan Kembali"

    # Define styles
    header_font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                   top=Side(style='thin'), bottom=Side(style='thin'))
    
    # Style for unpaid santri (red background)
    unpaid_fill = PatternFill(start_color='FFCCCC', end_color='FFCCCC', fill_type='solid')
    unpaid_font = Font(name='Arial', size=10, bold=True, color='CC0000')
    
    # ADDED: Style for unregistered santri (yellow background)
    unregistered_fill = PatternFill(start_color='FFFFCC', end_color='FFFFCC', fill_type='solid')
    unregistered_font = Font(name='Arial', size=10, bold=False, color='CC6600')

    # Set headers based on export type
    if export_type == 'pulang':
        headers = [
            'No', 'Nama Santri', 'Jenis Kelamin', 'Kabupaten', 'Status Santri', 
            'Jabatan', 'Status Pulang', 'Metode Pembayaran', 'Rombongan', 
            'Nama Bus', 'Biaya Pulang'
        ]
    else:  # kembali
        headers = [
            'No', 'Nama Santri', 'Jenis Kelamin', 'Kabupaten', 'Status Santri',
            'Jabatan', 'Status Kembali', 'Metode Pembayaran', 'Rombongan',
            'Nama Bus', 'Biaya Kembali'
        ]

    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    # Initialize counters for summary
    total_transfer = 0
    total_cash = 0
    total_biaya_pulang = 0
    total_biaya_kembali = 0
    count_transfer = 0
    count_cash = 0
    count_belum_lunas = 0
    count_belum_terdaftar = 0  # ADDED: Counter for unregistered santri

    # Write data
    for idx, santri in enumerate(santri_list, 2):
        pendaftaran = pendaftaran_map.get(santri.id)
        
        # Base data
        row_data = [
            idx - 1,  # No
            santri.nama,
            santri.jenis_kelamin,
            santri.kabupaten,
            santri.status_santri,
            santri.nama_jabatan or 'Santri'
        ]
        
        # Determine santri status
        is_unpaid = False
        is_unregistered = False
        
        if not pendaftaran:
            is_unregistered = True
            count_belum_terdaftar += 1
        
        # Add specific data based on export type
        if export_type == 'pulang':
            if pendaftaran:
                # Calculate biaya pulang - sesuai logika di pendaftaran_rombongan
                biaya_pulang = 0
                if pendaftaran.status_pulang and pendaftaran.status_pulang != 'Tidak Ikut':
                    if pendaftaran.rombongan_pulang_id and pendaftaran.titik_turun:
                        tarif_key = f"{pendaftaran.rombongan_pulang_id}_{pendaftaran.titik_turun}"
                        tarif = tarif_map.get(tarif_key)
                        if not tarif:
                            # Fetch tarif if not in map
                            tarif = Tarif.query.filter_by(
                                rombongan_id=pendaftaran.rombongan_pulang_id, 
                                titik_turun=pendaftaran.titik_turun
                            ).first()
                        if tarif:
                            biaya_pulang = tarif.harga_bus + tarif.fee_korda + 10000
                            total_biaya_pulang += biaya_pulang
                
                # Determine if unpaid based on status_pulang = 'Belum Bayar'
                if pendaftaran.status_pulang == 'Belum Bayar':
                    is_unpaid = True
                    count_belum_lunas += 1
                elif pendaftaran.status_pulang and pendaftaran.status_pulang not in ['Tidak Ikut', 'Belum Bayar']:
                    # Count payment methods for paid santri
                    if pendaftaran.metode_pembayaran_pulang:
                        if 'transfer' in pendaftaran.metode_pembayaran_pulang.lower():
                            count_transfer += 1
                            total_transfer += biaya_pulang
                        elif 'cash' in pendaftaran.metode_pembayaran_pulang.lower():
                            count_cash += 1
                            total_cash += biaya_pulang
                
                row_data.extend([
                    pendaftaran.status_pulang,
                    pendaftaran.metode_pembayaran_pulang or '-',
                    pendaftaran.rombongan_pulang.nama_rombongan if pendaftaran.rombongan_pulang else '-',
                    f"{pendaftaran.bus_pulang.nama_armada} - {pendaftaran.bus_pulang.nomor_lambung}" if pendaftaran.bus_pulang else '-',
                    f"Rp {biaya_pulang:,.0f}".replace(',', '.') if biaya_pulang > 0 else 'Rp 0',
                ])
            else:
                row_data.extend(['Belum Terdaftar', '-', '-', '-', 'Rp 0'])
                
        else:  # kembali
            if pendaftaran:
                # Calculate biaya kembali - sesuai logika di pendaftaran_rombongan
                biaya_kembali = 0
                if pendaftaran.status_kembali and pendaftaran.status_kembali != 'Tidak Ikut':
                    # Tentukan rombongan dan titik untuk kembali
                    rombongan_kembali_id = pendaftaran.rombongan_kembali_id or pendaftaran.rombongan_pulang_id
                    titik_jemput_kembali = pendaftaran.titik_jemput_kembali or pendaftaran.titik_turun
                    
                    if rombongan_kembali_id and titik_jemput_kembali:
                        tarif_key = f"{rombongan_kembali_id}_{titik_jemput_kembali}"
                        tarif = tarif_map.get(tarif_key)
                        if not tarif:
                            # Fetch tarif if not in map
                            tarif = Tarif.query.filter_by(
                                rombongan_id=rombongan_kembali_id, 
                                titik_turun=titik_jemput_kembali
                            ).first()
                            if tarif:
                                tarif_map[tarif_key] = tarif
                        if tarif:
                            biaya_kembali = tarif.harga_bus + tarif.fee_korda + 10000
                            total_biaya_kembali += biaya_kembali
                
                # Determine payment status for kembali
                if pendaftaran.status_kembali and pendaftaran.status_kembali != 'Tidak Ikut':
                    if not pendaftaran.metode_pembayaran_kembali:
                        is_unpaid = True
                        count_belum_lunas += 1
                    else:
                        # Count payment methods for kembali
                        if 'transfer' in pendaftaran.metode_pembayaran_kembali.lower():
                            count_transfer += 1
                            total_transfer += biaya_kembali
                        elif 'cash' in pendaftaran.metode_pembayaran_kembali.lower():
                            count_cash += 1
                            total_cash += biaya_kembali
                
                row_data.extend([
                    pendaftaran.status_kembali,
                    pendaftaran.metode_pembayaran_kembali or '-',
                    pendaftaran.rombongan_kembali.nama_rombongan if pendaftaran.rombongan_kembali else 
                    (pendaftaran.rombongan_pulang.nama_rombongan if pendaftaran.rombongan_pulang else '-'),
                    f"{pendaftaran.bus_kembali.nama_armada} - {pendaftaran.bus_kembali.nomor_lambung}" if pendaftaran.bus_kembali else '-',
                    f"Rp {biaya_kembali:,.0f}".replace(',', '.') if biaya_kembali > 0 else 'Rp 0',
                ])
            else:
                row_data.extend(['Belum Terdaftar', '-', '-', '-', 'Rp 0'])
        
        # Write row data with conditional styling
        for col, value in enumerate(row_data, 1):
            cell = ws.cell(row=idx, column=col, value=value)
            cell.border = border
            cell.alignment = Alignment(vertical='center')
            
            # MODIFIED: Apply styling based on status
            if is_unregistered:
                cell.fill = unregistered_fill
                cell.font = unregistered_font
            elif is_unpaid:
                cell.fill = unpaid_fill
                cell.font = unpaid_font

    # Add summary section at the bottom
    summary_row_start = len(santri_list) + 4  # Start 3 rows after the last data
    
    # Summary styles
    summary_header_font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
    summary_header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    summary_value_font = Font(name='Arial', size=11, bold=True, color='000000')
    summary_label_font = Font(name='Arial', size=11, bold=False, color='000000')
    
    # MODIFIED: Enhanced summary data with unregistered count
    summary_data = [
        ('RINGKASAN PEMBAYARAN', '', True),
        ('Total Pembayaran Transfer:', f"{count_transfer} orang - Rp {total_transfer:,.0f}".replace(',', '.'), False),
        ('Total Pembayaran Cash:', f"{count_cash} orang - Rp {total_cash:,.0f}".replace(',', '.'), False),
        ('Total Belum Lunas:', f"{count_belum_lunas} orang", False),
        ('Total Belum Terdaftar:', f"{count_belum_terdaftar} orang", False),  # ADDED
        ('', '', False),
        ('RINGKASAN BIAYA', '', True),
    ]
    
    if export_type == 'pulang':
        summary_data.append(('Total Biaya Pulang:', f"Rp {total_biaya_pulang:,.0f}".replace(',', '.'), False))
    else:
        summary_data.append(('Total Biaya Kembali:', f"Rp {total_biaya_kembali:,.0f}".replace(',', '.'), False))
    
    # ADDED: Legend section
    summary_data.extend([
        ('', '', False),
        ('KETERANGAN WARNA', '', True),
        ('Kuning:', 'Santri Belum Terdaftar', False),
        ('Merah:', 'Santri Belum Lunas Pembayaran', False),
        ('Putih:', 'Santri Sudah Lunas', False),
    ])
    
    # Write summary
    for i, (label, value, is_header) in enumerate(summary_data):
        row_idx = summary_row_start + i
        
        # Write label
        if label:  # Only write if label is not empty
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            if is_header:
                label_cell.font = summary_header_font
                label_cell.fill = summary_header_fill
                # Merge cells for headers
                ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
            else:
                label_cell.font = summary_label_font
        
        # Write value
        if value and not is_header:
            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = summary_value_font

    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Save to memory
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Create response
    response = make_response(output.read())
    
    # Generate filename
    filename = f"Santri_Wilayah_Lengkap_{export_type.title()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

@admin_bp.route('/rombongan/salin-dari-sebelumnya', methods=['POST'])
@login_required
@role_required('Korpus')
def salin_rombongan():
    active_edisi = get_active_edisi()
    if not active_edisi or Rombongan.query.filter_by(edisi_id=active_edisi.id).first():
        flash("Aksi tidak diizinkan.", "danger")
        return redirect(url_for('admin.manajemen_rombongan'))

    sumber_edisi = Edisi.query.filter_by(is_active=False).order_by(Edisi.tahun.desc()).first()
    if not sumber_edisi:
        flash("Tidak ditemukan edisi sebelumnya untuk menyalin data.", "warning")
        return redirect(url_for('admin.manajemen_rombongan'))

    # Kamus untuk memetakan ID rombongan lama ke objek rombongan baru
    old_to_new_rombongan_map = {}

    for rombongan_lama in sumber_edisi.rombongans:
        # Salin data utama rombongan
        rombongan_baru = Rombongan(
            edisi_id=active_edisi.id,
            nama_rombongan=rombongan_lama.nama_rombongan,
            penanggung_jawab_putra=rombongan_lama.penanggung_jawab_putra,
            kontak_person_putra=rombongan_lama.kontak_person_putra,
            penanggung_jawab_putri=rombongan_lama.penanggung_jawab_putri,
            kontak_person_putri=rombongan_lama.kontak_person_putri,
            nomor_rekening=rombongan_lama.nomor_rekening,
            cakupan_wilayah=rombongan_lama.cakupan_wilayah
            # Jadwal dan batas bayar sengaja dikosongkan
        )
        for tarif_lama in rombongan_lama.tarifs:
            rombongan_baru.tarifs.append(Tarif(
                titik_turun=tarif_lama.titik_turun,
                harga_bus=tarif_lama.harga_bus,
                fee_korda=tarif_lama.fee_korda
            ))
        
        db.session.add(rombongan_baru)
        db.session.flush() # Penting: untuk mendapatkan ID rombongan_baru
        old_to_new_rombongan_map[rombongan_lama.id] = rombongan_baru

    # --- LOGIKA BARU: PERBARUI RELASI KORDA/KORWIL ---
    # Cari semua user yang merupakan Korda atau Korwil
    coordinators = User.query.join(Role).filter(Role.name.in_(['Korda', 'Korwil'])).all()
    for user in coordinators:
        # Cek rombongan lama mana saja yang dikelola oleh user ini
        old_managed_ids = {r.id for r in user.managed_rombongan}
        
        # Cari padanan rombongan baru dari peta yang sudah kita buat
        new_rombongan_to_assign = [
            old_to_new_rombongan_map[old_id] 
            for old_id in old_managed_ids 
            if old_id in old_to_new_rombongan_map
        ]
        
        # Tambahkan relasi baru ke user
        if new_rombongan_to_assign:
            user.managed_rombongan.extend(new_rombongan_to_assign)
    # --- AKHIR LOGIKA BARU ---

    log_activity('Salin Data', 'Rombongan', f"Menyalin {len(old_to_new_rombongan_map)} rombongan dari edisi '{sumber_edisi.nama}'")
    db.session.commit()
    
    flash(f"Berhasil menyalin {len(old_to_new_rombongan_map)} rombongan dari edisi sebelumnya.", "success")
    return redirect(url_for('admin.manajemen_rombongan'))

@admin_bp.route('/cetak-kartu')
@login_required
@role_required('Korpus', 'Korda', 'Korwil')
def cetak_kartu():
    active_edisi = get_active_edisi()
    
    # --- PERBAIKI QUERY DASAR DI SINI ---
    # Mulai query dari Pendaftaran dan langsung JOIN ke Santri
    query = Pendaftaran.query.join(Santri)

    if active_edisi:
        # Filter berdasarkan edisi aktif
        query = query.join(Rombongan, or_(
            Pendaftaran.rombongan_pulang_id == Rombongan.id,
            Pendaftaran.rombongan_kembali_id == Rombongan.id
        )).filter(Rombongan.edisi_id == active_edisi.id)
    else:
        query = query.filter(db.false())

    # Filter berdasarkan hak akses
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        if not managed_rombongan_ids:
            query = query.filter(db.false())
        else:
            query = query.filter(
                or_(
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                    Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                )
            )
    
    # Ambil semua pendaftar yang relevan dan urutkan
    semua_pendaftar = query.options(
        joinedload(Pendaftaran.santri),
        joinedload(Pendaftaran.rombongan_pulang),
        joinedload(Pendaftaran.bus_pulang)
    ).order_by(Santri.nama).all() # Sekarang order_by akan berfungsi

    # Hilangkan duplikat jika perlu
    unique_pendaftar = list({p.santri_id: p for p in semua_pendaftar}.values())

    return render_template('cetak_kartu.html', semua_pendaftar=unique_pendaftar)

@admin_bp.route('/cetak-tiket')
@login_required
@role_required('Korpus', 'Korda', 'Korwil')
def cetak_tiket():
    active_edisi = get_active_edisi()
    query = Pendaftaran.query.join(Santri)

    if not active_edisi:
        flash("Tidak ada edisi yang aktif untuk mencetak tiket.", "warning")
        return redirect(url_for('admin.dashboard'))

    # Filter berdasarkan edisi aktif
    query = query.join(Rombongan, or_(
        Pendaftaran.rombongan_pulang_id == Rombongan.id,
        Pendaftaran.rombongan_kembali_id == Rombongan.id
    )).filter(Rombongan.edisi_id == active_edisi.id)

    # Filter berdasarkan hak akses Korda/Korwil
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        if not managed_rombongan_ids:
            query = query.filter(db.false())
        else:
            query = query.filter(
                or_(
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                    Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                )
            )
    
    # Ambil semua pendaftar yang relevan
    semua_pendaftar = query.options(
        joinedload(Pendaftaran.santri),
        joinedload(Pendaftaran.rombongan_pulang),
        joinedload(Pendaftaran.bus_pulang)
    ).order_by(Santri.nama).all()

    # Hilangkan duplikat
    unique_pendaftar = list({p.santri_id: p for p in semua_pendaftar}.values())

    return render_template('cetak_tiket.html', semua_pendaftar=unique_pendaftar)

# 1. Halaman Utama Manajemen Wisuda (termasuk logika impor)
@admin_bp.route('/manajemen-wisuda', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'PJ Acara', 'Korwil', 'Korda', 'Bendahara Pusat')
def manajemen_wisuda():
    active_edisi = get_active_edisi()
    import_form = ImportWisudaForm()

    if import_form.validate_on_submit():
        file = import_form.file.data
        kategori = import_form.kategori_wisuda.data

        try:
            df = pd.read_excel(file)
            if 'NIS' not in df.columns:
                flash('File Excel harus memiliki kolom bernama "NIS".', 'danger')
                return redirect(url_for('admin.manajemen_wisuda'))

            all_nis = df['NIS'].dropna().astype(str).tolist()

            # Cari semua santri yang cocok dalam satu query
            santri_map = {s.nis: s for s in Santri.query.filter(Santri.nis.in_(all_nis)).all()}

            newly_graduated = []
            for nis in all_nis:
                if nis in santri_map:
                    santri = santri_map[nis]
                    # Cek apakah sudah ada data wisuda
                    if not santri.wisuda_info:
                        santri.status_santri = 'Wisuda'
                        new_wisuda = Wisuda(
                            santri_nis=santri.nis,
                            edisi_id=active_edisi.id,
                            kategori_wisuda=kategori
                        )
                        newly_graduated.append(new_wisuda)

            if newly_graduated:
                db.session.add_all(newly_graduated)
                db.session.commit()
                flash(f'{len(newly_graduated)} santri berhasil diimpor dan statusnya diubah menjadi Wisuda.', 'success')
            else:
                flash('Tidak ada santri baru yang diimpor. Mungkin semua sudah terdata.', 'info')

        except Exception as e:
            flash(f'Terjadi error saat memproses file: {e}', 'danger')

        return redirect(url_for('admin.manajemen_wisuda'))

    wisudawan_list = Wisuda.query.filter_by(edisi_id=active_edisi.id).options(joinedload(Wisuda.santri)).all()
    
    # 2. Kelompokkan data berdasarkan kategori
    grouped_wisudawan = {}
    for w in wisudawan_list:
        kategori = w.kategori_wisuda
        if kategori not in grouped_wisudawan:
            grouped_wisudawan[kategori] = []
        grouped_wisudawan[kategori].append(w)
    # ------------------------------------

    return render_template('manajemen_wisuda.html', 
                           import_form=import_form, 
                           grouped_wisudawan=grouped_wisudawan, # Kirim data yang sudah dikelompokkan
                           active_edisi=active_edisi)

# 2. Halaman untuk menambah wisudawan manual
@admin_bp.route('/tambah-wisudawan', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'PJ Acara')
def tambah_wisudawan():
    form = WisudaForm()
    if form.validate_on_submit():
        santri = Santri.query.filter_by(nis=form.santri.data).first()
        if santri and not santri.wisuda_info:
            santri.status_santri = 'Wisuda'
            new_wisuda = Wisuda(
                santri_nis=santri.nis,
                edisi_id=get_active_edisi().id,
                kategori_wisuda=form.kategori_wisuda.data
            )
            db.session.add(new_wisuda)
            db.session.commit()
            flash(f'{santri.nama} berhasil ditandai sebagai wisudawan.', 'success')
            return redirect(url_for('admin.manajemen_wisuda'))
        else:
            flash('Santri tidak ditemukan atau sudah menjadi wisudawan.', 'warning')
    return render_template('tambah_wisudawan.html', form=form, title="Tambah Wisudawan Manual")

# 3. Route untuk menghapus status wisuda
@admin_bp.route('/hapus-wisuda/<int:wisuda_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'PJ Acara')
def hapus_wisuda(wisuda_id):
    wisuda = Wisuda.query.get_or_404(wisuda_id)
    santri = wisuda.santri
    santri.status_santri = 'Aktif' # Kembalikan statusnya
    db.session.delete(wisuda)
    db.session.commit()
    flash(f'Status wisuda untuk {santri.nama} berhasil dihapus.', 'success')
    return redirect(url_for('admin.manajemen_wisuda'))

# 4. API endpoint baru untuk pencarian santri di form tambah
@admin_bp.route('/api/search-santri-for-wisuda')
@login_required
def api_search_santri_for_wisuda():
    q = request.args.get('q', '')
    query = Santri.query.filter(
        Santri.status_santri == 'Aktif',
        Santri.wisuda_info == None,
        Santri.nama.ilike(f'%{q}%')
    ).limit(20)

    results = [{
        'id': s.id,
        'nis': s.nis,
        'nama': s.nama,
        'asrama': s.asrama, 
        'kabupaten': s.kabupaten
    } for s in query.all()]
    return jsonify({'results': results})

@admin_bp.route('/santri/update-wali/<int:santri_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'Korda', 'Korwil')
def update_nomor_wali(santri_id):
    santri = Santri.query.get_or_404(santri_id)
    new_phone_number = request.json.get('no_hp_wali')

    if not new_phone_number:
        return jsonify({'success': False, 'message': 'Nomor HP tidak boleh kosong.'}), 400

    # --- Bagian Sinkronisasi ke API Induk (Sudah Disederhanakan) ---
    try:
        if not santri.nis:
            return jsonify({'success': False, 'message': f'Santri {santri.nama} tidak memiliki NIS untuk sinkronisasi.'}), 400

        api_url = f"{current_app.config['API_INDUK_URL']}/{santri.nis}"
        payload = json.dumps({"parrentPhone": new_phone_number})
        headers = {
            'Content-Type': 'application/json' # Header yang lebih sederhana
        }

        print(api_url, payload)  # Debugging output
        
        response = requests.request("PATCH", api_url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()

        print(response.text)

    except requests.exceptions.RequestException as e:
        error_message = f"Gagal sinkronisasi ke server induk. Respon: {e.response.text if e.response else 'Tidak ada respon'}"
        return jsonify({'success': False, 'message': error_message}), 500
    # --- Akhir Bagian Sinkronisasi ---

    # Jika sinkronisasi berhasil, update database lokal kita
    santri.no_hp_wali = new_phone_number
    log_activity('Edit', 'Santri', f"Mengubah nomor HP wali untuk santri: '{santri.nama}'")
    db.session.commit()

    return jsonify({'success': True, 'message': 'Nomor HP wali berhasil diperbarui dan disinkronkan.'})

# Ganti fungsi bendahara_dashboard dan konfirmasi_setor dengan ini

@admin_bp.route('/bendahara')
@login_required
@role_required('Bendahara Pusat', 'Korpus')
def bendahara_dashboard():
    active_edisi = get_active_edisi()
    if not active_edisi:
        return render_template('bendahara_dashboard.html', active_edisi=None)

    # Hitung saldo rekening virtual dari tabel Transaksi
    def get_saldo(rekening):
        pemasukan = db.session.query(func.sum(Transaksi.jumlah)).filter_by(edisi_id=active_edisi.id, tipe='PEMASUKAN', rekening=rekening).scalar() or 0
        pengeluaran = db.session.query(func.sum(Transaksi.jumlah)).filter_by(edisi_id=active_edisi.id, tipe='PENGELUARAN', rekening=rekening).scalar() or 0
        return pemasukan - pengeluaran

    saldo_rekening_saya = get_saldo('REKENING_SAYA')
    saldo_bus_pulang = get_saldo('REKENING_BUS_PULANG')
    saldo_bus_kembali = get_saldo('REKENING_BUS_KEMBALI')

    # Siapkan data untuk setiap rombongan
    all_rombongan = Rombongan.query.filter_by(edisi_id=active_edisi.id).all()
    rombongan_data_list = []
    for rombongan in all_rombongan:
        # --- BLOK PERHITUNGAN BARU: Menghitung dari SEMUA PENDAFTAR ---

        # 1. Hitung Total Biaya Bus Seharusnya (dari semua yang statusnya bukan 'Tidak Ikut')
        total_bus_pulang_seharusnya = db.session.query(func.sum(Tarif.harga_bus)).select_from(Pendaftaran).join(
            Tarif, and_(
                Pendaftaran.rombongan_pulang_id == Tarif.rombongan_id,
                Pendaftaran.titik_turun == Tarif.titik_turun
            )
        ).filter(Pendaftaran.rombongan_pulang_id == rombongan.id, Pendaftaran.status_pulang != 'Tidak Ikut').scalar() or 0
        
        total_bus_kembali_seharusnya = db.session.query(func.sum(Tarif.harga_bus)).select_from(Pendaftaran).join(
            Tarif, and_(
                (Pendaftaran.rombongan_kembali_id == Tarif.rombongan_id),
                (Pendaftaran.titik_jemput_kembali == Tarif.titik_turun)
            )
        ).filter(Pendaftaran.rombongan_kembali_id == rombongan.id, Pendaftaran.status_kembali != 'Tidak Ikut').scalar() or 0
        
        # 2. Hitung Total Fee Pondok Seharusnya (dari semua yang statusnya bukan 'Tidak Ikut')
        total_pondok_pulang_seharusnya = Pendaftaran.query.filter_by(rombongan_pulang_id=rombongan.id).filter(Pendaftaran.status_pulang != 'Tidak Ikut').count() * 10000
        total_pondok_kembali_seharusnya = Pendaftaran.query.filter_by(rombongan_kembali_id=rombongan.id).filter(Pendaftaran.status_kembali != 'Tidak Ikut').count() * 10000
        
        # 3. Hitung Sisa Setoran berdasarkan total yang seharusnya
        sisa_setoran_bus_pulang = total_bus_pulang_seharusnya - (rombongan.total_setoran_bus_pulang or 0)
        sisa_setoran_bus_kembali = total_bus_kembali_seharusnya - (rombongan.total_setoran_bus_kembali or 0)
        sisa_setoran_pondok_pulang = total_pondok_pulang_seharusnya - (rombongan.total_setoran_pondok_pulang or 0)
        sisa_setoran_pondok_kembali = total_pondok_kembali_seharusnya - (rombongan.total_setoran_pondok_kembali or 0)
        
        # 4. Hitung peserta belum lunas (logika ini tetap sama)
        peserta_belum_lunas = Pendaftaran.query.filter(
            or_(Pendaftaran.rombongan_pulang_id == rombongan.id, Pendaftaran.rombongan_kembali_id == rombongan.id),
            or_(Pendaftaran.status_pulang == 'Belum Bayar', Pendaftaran.status_kembali == 'Belum Bayar')
        ).count()

        rombongan_data_list.append({
            'rombongan': rombongan,
            'total_bus_pulang_seharusnya': total_bus_pulang_seharusnya,
            'total_bus_kembali_seharusnya': total_bus_kembali_seharusnya,
            'total_pondok_pulang_seharusnya': total_pondok_pulang_seharusnya,
            'total_pondok_kembali_seharusnya': total_pondok_kembali_seharusnya,
            'sisa_setoran_bus_pulang': sisa_setoran_bus_pulang,
            'sisa_setoran_bus_kembali': sisa_setoran_bus_kembali,
            'sisa_setoran_pondok_pulang': sisa_setoran_pondok_pulang,
            'sisa_setoran_pondok_kembali': sisa_setoran_pondok_kembali,
            'peserta_belum_lunas': peserta_belum_lunas
        })

    form_setoran = KonfirmasiSetoranForm()
    return render_template('bendahara_dashboard.html', 
                           saldo_rekening_saya=saldo_rekening_saya,
                           saldo_bus_pulang=saldo_bus_pulang,
                           saldo_bus_kembali=saldo_bus_kembali,
                           rombongan_data_list=rombongan_data_list,
                           active_edisi=active_edisi,
                           form_setoran=form_setoran)

@admin_bp.route('/bendahara/konfirmasi-setor/<int:rombongan_id>', methods=['POST'])
@login_required
@role_required('Bendahara Pusat', 'Korpus')
def konfirmasi_setor(rombongan_id):
    tipe = request.args.get('tipe')
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    form = KonfirmasiSetoranForm()

    if form.validate_on_submit():
        jumlah = form.jumlah_disetor.data
        
        rekening_map = {
            'bus_pulang': ('REKENING_BUS_PULANG', 'Biaya Bus Pulang'),
            'bus_kembali': ('REKENING_BUS_KEMBALI', 'Biaya Bus Kembali'),
            'pondok_pulang': ('REKENING_SAYA', 'Fee Pondok Pulang'),
            'pondok_kembali': ('REKENING_SAYA', 'Fee Pondok Kembali')
        }
        
        if tipe in rekening_map:
            rekening, deskripsi_prefix = rekening_map[tipe]
            
            # --- BLOK KODE BARU UNTUK MENCATAT PEMASUKAN ---
            # 1. Buat record transaksi baru
            transaksi = Transaksi(
                edisi_id=get_active_edisi().id,
                deskripsi=f"Setoran {deskripsi_prefix} dari {rombongan.nama_rombongan}",
                jumlah=jumlah,
                tipe='PEMASUKAN', # Menandakan ini adalah uang masuk
                rekening=rekening,
                user_id=current_user.id,
                rombongan_id=rombongan.id
            )
            db.session.add(transaksi)
            # --- AKHIR BLOK KODE BARU ---
            
            # 2. Update total setoran di rombongan (logika ini tetap sama)
            if tipe == 'bus_pulang':
                if rombongan.total_setoran_bus_pulang is None:
                    rombongan.total_setoran_bus_pulang = 0
                rombongan.total_setoran_bus_pulang += jumlah
    
            elif tipe == 'bus_kembali':
                if rombongan.total_setoran_bus_kembali is None:
                    rombongan.total_setoran_bus_kembali = 0
                rombongan.total_setoran_bus_kembali += jumlah
    
            elif tipe == 'pondok_pulang':
                if rombongan.total_setoran_pondok_pulang is None:
                    rombongan.total_setoran_pondok_pulang = 0
                rombongan.total_setoran_pondok_pulang += jumlah
    
            elif tipe == 'pondok_kembali':
                if rombongan.total_setoran_pondok_kembali is None:
                    rombongan.total_setoran_pondok_kembali = 0
                rombongan.total_setoran_pondok_kembali += jumlah
            
            db.session.commit()
            flash(f"Setoran sebesar Rp {jumlah:,} berhasil dikonfirmasi dan dicatat sebagai pemasukan.", 'success')
        else:
            flash("Tipe setoran tidak valid.", "danger")
    else:
        # Menampilkan error validasi form jika ada
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error pada input '{getattr(form, field).label.text}': {error}", 'danger')

    return redirect(url_for('admin.bendahara_dashboard'))

# 3. Rute Halaman Pengeluaran
# Ganti fungsi bendahara_pengeluaran dengan ini
@admin_bp.route('/bendahara/buku-kas', methods=['GET', 'POST'])
@login_required
@role_required('Bendahara Pusat', 'Korpus')
def bendahara_buku_kas():
    active_edisi = get_active_edisi()
    form = TransaksiForm()
    
    if form.validate_on_submit():
        pengeluaran = Transaksi(
            edisi_id=active_edisi.id,
            deskripsi=form.deskripsi.data,
            jumlah=form.jumlah.data,
            tipe='PENGELUARAN',
            rekening='REKENING_SAYA',
            user_id=current_user.id
        )
        db.session.add(pengeluaran)
        db.session.commit()
        flash('Data pengeluaran berhasil dicatat.', 'success')
        return redirect(url_for('admin.bendahara_buku_kas'))

    # Hitung saldo untuk ditampilkan
    pemasukan_saya = db.session.query(func.sum(Transaksi.jumlah)).filter_by(edisi_id=active_edisi.id, tipe='PEMASUKAN', rekening='REKENING_SAYA').scalar() or 0
    pengeluaran_saya = db.session.query(func.sum(Transaksi.jumlah)).filter_by(edisi_id=active_edisi.id, tipe='PENGELUARAN', rekening='REKENING_SAYA').scalar() or 0
    saldo_rekening_saya = pemasukan_saya - pengeluaran_saya
    
    # --- PERUBAHAN DI SINI ---
    # Ambil riwayat SEMUA transaksi (Pemasukan dan Pengeluaran)
    riwayat_transaksi = Transaksi.query.filter(
        Transaksi.edisi_id == active_edisi.id,
        Transaksi.rekening == 'REKENING_SAYA' # Hanya dari Rekening Saya
    ).order_by(Transaksi.tanggal.desc()).all()

    return render_template('bendahara_buku_kas.html', 
                           form=form, 
                           saldo_rekening_saya=saldo_rekening_saya,
                           riwayat_transaksi=riwayat_transaksi)


# Ganti fungsi bendahara_buku_kas_bus dengan ini
@admin_bp.route('/bendahara/buku-kas-bus', methods=['GET', 'POST'])
@login_required
@role_required('Bendahara Pusat')
def bendahara_buku_kas_bus():
    active_edisi = get_active_edisi()
    form = PengeluaranBusForm() # Gunakan form baru

    if form.validate_on_submit():
        pengeluaran = Transaksi(
            edisi_id=active_edisi.id,
            deskripsi=form.deskripsi.data,
            jumlah=form.jumlah.data,
            tipe='PENGELUARAN', # Tandai sebagai pengeluaran
            rekening=form.rekening.data, # Ambil rekening dari pilihan dropdown
            user_id=current_user.id
        )
        db.session.add(pengeluaran)
        db.session.commit()
        flash('Data pengeluaran bus berhasil dicatat.', 'success')
        return redirect(url_for('admin.bendahara_buku_kas_bus'))

    # Logika untuk menghitung saldo dan mengambil riwayat (tidak berubah)
    def get_saldo(rekening):
        pemasukan = db.session.query(func.sum(Transaksi.jumlah)).filter_by(edisi_id=active_edisi.id, tipe='PEMASUKAN', rekening=rekening).scalar() or 0
        pengeluaran = db.session.query(func.sum(Transaksi.jumlah)).filter_by(edisi_id=active_edisi.id, tipe='PENGELUARAN', rekening=rekening).scalar() or 0
        return pemasukan - pengeluaran

    saldo_bus_pulang = get_saldo('REKENING_BUS_PULANG')
    saldo_bus_kembali = get_saldo('REKENING_BUS_KEMBALI')

    riwayat_transaksi_bus = Transaksi.query.filter(
        Transaksi.edisi_id == active_edisi.id,
        Transaksi.rekening.in_(['REKENING_BUS_PULANG', 'REKENING_BUS_KEMBALI'])
    ).order_by(Transaksi.tanggal.desc()).all()
    total_saldo_bus = saldo_bus_pulang + saldo_bus_kembali

    return render_template('bendahara_buku_kas_bus.html', 
                           saldo_bus_pulang=saldo_bus_pulang,
                           saldo_bus_kembali=saldo_bus_kembali,
                           riwayat_transaksi_bus=riwayat_transaksi_bus,
                           form=form,
                           total_saldo_bus=total_saldo_bus) # Kirim form ke template


# Di dalam file app/admin/routes.py

@admin_bp.route('/ganti-password', methods=['GET', 'POST'])
@login_required # Hanya untuk user yang sudah login
def ganti_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        user = current_user # Ambil data user yang sedang login

        # 1. Verifikasi password saat ini
        if not user.check_password(form.current_password.data):
            flash('Password saat ini yang Anda masukkan salah.', 'danger')
            return redirect(url_for('admin.ganti_password'))

        # 2. Pastikan password baru tidak sama dengan password lama
        if user.check_password(form.new_password.data):
            flash('Password baru tidak boleh sama dengan password lama.', 'warning')
            return redirect(url_for('admin.ganti_password'))

        # 3. Jika semua valid, ganti password
        user.set_password(form.new_password.data)
        db.session.commit()
        
        log_activity('Keamanan', 'Akun', f"User '{user.username}' berhasil mengganti passwordnya sendiri.")
        flash('Password Anda telah berhasil diperbarui!', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('ganti_password.html', title="Ganti Password", form=form)

# Di dalam file app/admin/routes.py

@admin_bp.route('/profil-saya')
@login_required
def profil_saya():
    # Logika untuk panduan akan ditambahkan di sini nanti
    # Untuk sekarang, kita hanya menampilkan data user
    return render_template('profil_saya.html', title="Profil Saya")