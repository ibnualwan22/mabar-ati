from . import admin_bp
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from app.models import ActivityLog, Rombongan, Tarif, Santri, Pendaftaran, Izin, Partisipan, User, Edisi, Bus, Role
from app.admin.forms import RombonganForm, SantriEditForm, PendaftaranForm, PendaftaranEditForm, IzinForm, PartisipanForm, PartisipanEditForm, LoginForm, UserForm, UserEditForm, EdisiForm, BusForm, KorlapdaForm
from app import db, login_manager
import json, requests
from collections import defaultdict
from sqlalchemy import update, text, or_
from datetime import date, datetime
from flask_login import login_user, logout_user, current_user, login_required
from functools import wraps
from sqlalchemy.orm import joinedload # <-- Tambahkan import ini di atas






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
            
        # Simpan semua perubahan
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
    db.session.delete(user)
    db.session.commit()
    flash('User berhasil dihapus.', 'info')
    return redirect(url_for('admin.manajemen_user'))


@admin_bp.route('/')
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
def dashboard():
    active_edisi = get_active_edisi()
    stats = { 'total_peserta': 0, 'total_izin': 0, 'santri_belum_terdaftar': 0, 
              'total_pemasukan': 0, 'total_lunas': 0, 'total_belum_lunas': 0, 
              'pendaftar_terlambat': [], 'total_partisipan': 0 }
    semua_rombongan = []

    if not active_edisi:
        flash("Tidak ada edisi yang aktif. Silakan aktifkan satu edisi di Manajemen Edisi.", "warning")
        stats['santri_belum_terdaftar'] = Santri.query.filter(Santri.status_santri == 'Aktif', Santri.pendaftaran == None).count()
        return render_template('dashboard.html', stats=stats, semua_rombongan=semua_rombongan)

    # --- MULAI KALKULASI JIKA EDISI AKTIF ---
    
    # Query dasar untuk semua pendaftaran di edisi aktif
    # Bergabung dengan rombongan melalui salah satu foreign key (pulang) sebagai titik awal
    base_pendaftaran_query = Pendaftaran.query.join(
        Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id
    ).filter(Rombongan.edisi_id == active_edisi.id)

    # Terapkan filter hak akses untuk Korda/Korwil
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        if not managed_rombongan_ids:
            base_pendaftaran_query = base_pendaftaran_query.filter(db.false())
        else:
            from sqlalchemy import or_
            base_pendaftaran_query = base_pendaftaran_query.filter(
                or_(
                    Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                    Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                )
            )
    
    pendaftar_list = base_pendaftaran_query.options(joinedload(Pendaftaran.santri), joinedload(Pendaftaran.rombongan_pulang), joinedload(Pendaftaran.rombongan_kembali)).all()
    
    # Kalkulasi Statistik Peserta
    stats['total_peserta'] = len(pendaftar_list)
    stats['total_izin'] = Izin.query.filter_by(edisi=active_edisi).count()
    stats['total_partisipan'] = Partisipan.query.filter_by(edisi=active_edisi).count()

    # Kalkulasi keuangan
    total_pemasukan = sum(p.total_biaya for p in pendaftar_list)
    total_lunas = 0
    for p in pendaftar_list:
        tarif_pulang = Tarif.query.filter_by(rombongan_id=p.rombongan_pulang_id, titik_turun=p.titik_turun).first()
        biaya_pulang = tarif_pulang.harga_bus + tarif_pulang.fee_korda + 10000 if tarif_pulang else 0
        
        tarif_kembali = Tarif.query.filter_by(rombongan_id=p.rombongan_kembali_id, titik_turun=p.titik_jemput_kembali).first()
        biaya_kembali = tarif_kembali.harga_bus + tarif_kembali.fee_korda + 10000 if tarif_kembali else 0

        if p.status_pulang == 'Lunas':
            total_lunas += biaya_pulang
        if p.status_kembali == 'Lunas':
            total_lunas += biaya_kembali
    
    stats['total_pemasukan'] = total_pemasukan
    stats['total_lunas'] = total_lunas
    stats['total_belum_lunas'] = total_pemasukan - total_lunas
    
    # Kalkulasi santri belum terdaftar
    # Subquery eksplisit untuk menghindari ambiguitas
    all_registered_santri_ids = db.session.query(Pendaftaran.santri_id).join(Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id).filter(Rombongan.edisi_id == active_edisi.id)
    
    query_belum_terdaftar = Santri.query.filter(
        Santri.status_santri == 'Aktif',
        ~Santri.id.in_(all_registered_santri_ids)
    )

    if current_user.role.name in ['Korwil', 'Korda']:
        managed_regions = {w.get('label') for r in current_user.managed_rombongan if r.cakupan_wilayah for w in r.cakupan_wilayah}
        if managed_regions:
            query_belum_terdaftar = query_belum_terdaftar.filter(Santri.kabupaten.in_(list(managed_regions)))
        else:
            query_belum_terdaftar = query_belum_terdaftar.filter(db.false())
    
    stats['santri_belum_terdaftar'] = query_belum_terdaftar.count()

    # Ambil data rombongan sesuai hak akses (untuk tabel ringkasan)
    rombongan_query = Rombongan.query.filter_by(edisi=active_edisi)
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        if not managed_rombongan_ids:
            rombongan_query = rombongan_query.filter(db.false())
        else:
            rombongan_query = rombongan_query.filter(Rombongan.id.in_(managed_rombongan_ids))
    semua_rombongan = rombongan_query.order_by(Rombongan.nama_rombongan).all()
    
    for r in semua_rombongan:
        r.jumlah_peserta_pulang = Pendaftaran.query.filter(
            Pendaftaran.rombongan_pulang_id == r.id,
            Pendaftaran.status_pulang != 'Tidak Ikut'
        ).count()
        r.jumlah_peserta_kembali = Pendaftaran.query.filter(
            Pendaftaran.rombongan_kembali_id == r.id,
            Pendaftaran.status_kembali != 'Tidak Ikut'
        ).count()

    return render_template('dashboard.html', stats=stats, semua_rombongan=semua_rombongan)

@admin_bp.route('/rombongan')
@login_required
@role_required('Korpus', 'Korwil', 'Korda')
def manajemen_rombongan():
    active_edisi = get_active_edisi()
    semua_rombongan = [] # Inisialisasi daftar kosong di awal

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
    active_edisi = get_active_edisi()
    rombongan = Rombongan.query.get_or_404(id)
    bus_form = BusForm()

    if active_edisi and rombongan.edisi_id != active_edisi.id:
        flash("Anda tidak bisa mengedit rombongan dari edisi yang sudah selesai.", "danger")
        return redirect(url_for('admin.manajemen_rombongan'))
    
    if current_user.role.name == 'Korda' and rombongan not in current_user.managed_rombongan:
        abort(403)

    form = RombonganForm(obj=rombongan)

    if form.validate_on_submit():
        # Update semua field dari form ke objek rombongan
        rombongan.nama_rombongan=form.nama_rombongan.data
        rombongan.penanggung_jawab_putra=form.penanggung_jawab_putra.data
        rombongan.kontak_person_putra=form.kontak_person_putra.data
        rombongan.penanggung_jawab_putri=form.penanggung_jawab_putri.data
        rombongan.kontak_person_putri=form.kontak_person_putri.data
        rombongan.nomor_rekening=form.nomor_rekening.data
        rombongan.cakupan_wilayah=json.loads(form.cakupan_wilayah.data or '[]')
        rombongan.jadwal_pulang=form.jadwal_pulang.data
        rombongan.batas_pembayaran_pulang=form.batas_pembayaran_pulang.data
        rombongan.jadwal_berangkat=form.jadwal_berangkat.data
        rombongan.batas_pembayaran_berangkat=form.batas_pembayaran_berangkat.data
        rombongan.titik_jemput_berangkat=form.titik_jemput_berangkat.data
        
        # Update tarif
        # Hapus tarif lama dan ganti dengan yang baru dari form 
        for tarif in rombongan.tarifs:
            db.session.delete(tarif)

        for tarif_data in form.tarifs.data:
            if tarif_data['titik_turun'] and tarif_data['harga_bus'] is not None:
                rombongan.tarifs.append(Tarif(**tarif_data))
        
        log_activity('Edit', 'Pendaftaran', f"Mengubah detail pendaftaran untuk santri: '{Pendaftaran.santri.nama}'")
        db.session.commit()
        flash('Data rombongan berhasil diperbarui!', 'success')
        return redirect(url_for('admin.manajemen_rombongan'))

    # Isi data untuk request GET (pertama kali halaman dibuka)
    form.cakupan_wilayah.data = json.dumps(rombongan.cakupan_wilayah or [])
    while len(form.tarifs) > 0:
        form.tarifs.pop_entry()
    for tarif in rombongan.tarifs:
        form.tarifs.append_entry(tarif)

    return render_template('form_rombongan.html', form=form, title=f"Edit Rombongan", rombongan=rombongan, bus_form=bus_form)


@admin_bp.route('/rombongan/hapus/<int:id>', methods=['POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def hapus_rombongan(id):
    rombongan = Rombongan.query.get_or_404(id)
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

    pagination = query.order_by(Santri.nama).paginate(page=page, per_page=50, error_out=False)
    
    all_rombongan = Rombongan.query.filter_by(edisi=active_edisi).order_by(Rombongan.nama_rombongan).all() if active_edisi else []
    all_kabupaten = [k[0] for k in db.session.query(Santri.kabupaten).distinct().order_by(Santri.kabupaten).all() if k[0] is not None]
    
    return render_template('manajemen_santri.html', 
                           pagination=pagination, 
                           all_rombongan=all_rombongan,
                           all_kabupaten=all_kabupaten)

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
    
    return jsonify({"success": True, "message": f"{new_santri.nama} berhasil diimpor."})

@admin_bp.route('/santri/impor-semua', methods=['POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def impor_semua_santri():
    try:
        api_url = "https://dev.amtsilatipusat.com/api/student?limit=2000"
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        santri_from_api = response.json().get('data', [])

        existing_ids = {s.api_student_id for s in Santri.query.with_entities(Santri.api_student_id).all()}
        
        new_count = 0
        updated_count = 0
        to_create = []

        for data in santri_from_api:
            api_id = data.get('id')
            if not api_id:
                continue

            if api_id in existing_ids:
                # --- METODE UPDATE DENGAN RAW SQL ---
                sql = text("""
                    UPDATE santri SET
                        nama = :nama, nis = :nis, kabupaten = :kabupaten, asrama = :asrama,
                        no_hp_wali = :no_hp_wali, jenis_kelamin = :jenis_kelamin,
                        kelas_formal = :kelas_formal, kelas_ngaji = :kelas_ngaji
                    WHERE api_student_id = :api_id
                """)
                
                db.session.execute(sql, {
                    'nama': data.get('name', 'Tanpa Nama'),
                    'nis': data.get('nis', 'N/A'),
                    'kabupaten': data.get('regency'),
                    'asrama': data.get('activeDormitory'),
                    'no_hp_wali': data.get('parrentPhone'),
                    'jenis_kelamin': data.get('gender') or 'Putra',
                    'kelas_formal': data.get('formalClass'),
                    'kelas_ngaji': data.get('activeClass'),
                    'api_id': api_id
                })
                updated_count += 1
            else:
                # Logika 'create' tetap menggunakan bulk insert karena efisien dan sudah terbukti bekerja
                new_santri_data = {
                    'api_student_id': api_id,
                    'nis': data.get('nis', 'N/A'),
                    'nama': data.get('name', 'Tanpa Nama'),
                    'kabupaten': data.get('regency'),
                    'asrama': data.get('activeDormitory'),
                    'no_hp_wali': data.get('parrentPhone'),
                    'jenis_kelamin': data.get('gender') or 'Putra',
                    'kelas_formal': data.get('formalClass'),
                    'kelas_ngaji': data.get('activeClass')
                }
                to_create.append(new_santri_data)
        
        if to_create:
            db.session.bulk_insert_mappings(Santri, to_create)
            new_count = len(to_create)

        db.session.commit()
        flash(f"Proses selesai! Berhasil mengimpor {new_count} santri baru dan memperbarui {updated_count} data santri.", "success")

    except requests.exceptions.RequestException as e:
        flash(f"Gagal mengambil data dari API Induk: {e}", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Terjadi error saat memproses data: {e}", "danger")
        print(f"Error detail: {e}")

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
        
        # Validasi lain
        if santri.pendaftaran:
            flash(f"ERROR: {santri.nama} sudah terdaftar di sebuah rombongan pada edisi ini.", "danger")
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
            santri_id=santri.id, rombongan_pulang_id=rombongan.id, rombongan_kembali_id=rombongan.id,
            status_pulang=form.status_pulang.data, metode_pembayaran_pulang=form.metode_pembayaran_pulang.data or None,
            bus_pulang_id=int(form.bus_pulang.data) if form.bus_pulang.data else None,
            titik_turun=form.titik_turun.data, status_kembali=form.status_kembali.data,
            metode_pembayaran_kembali=form.metode_pembayaran_kembali.data or None,
            bus_kembali_id=int(form.bus_kembali.data) if form.bus_kembali.data else None,
            total_biaya=total_biaya
        )
        db.session.add(pendaftaran)
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
@role_required('Korpus', 'Korda')
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
            'sisa_kuota_kembali': bus.kuota - terisi_kembali
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
            Santri.pendaftaran == None
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
@role_required('Korpus', 'Korwil', 'Korda')
def daftar_peserta(rombongan_id):
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    # Verifikasi Kepemilikan
    if current_user.role.name in ['Korwil', 'Korda']:
        if rombongan not in current_user.managed_rombongan:
            abort(403)
    
    # Query baru untuk mencari pendaftar baik dari perjalanan pulang maupun kembali
    pendaftar = Pendaftaran.query.options(
        joinedload(Pendaftaran.santri),
        joinedload(Pendaftaran.bus_pulang),
        joinedload(Pendaftaran.bus_kembali),
        joinedload(Pendaftaran.rombongan_kembali) # <-- Tambahkan ini untuk akses nama rombongan kembali
    ).filter(
        or_(
            Pendaftaran.rombongan_pulang_id == rombongan.id,
            Pendaftaran.rombongan_kembali_id == rombongan.id
        )
    ).all()

    # Hilangkan duplikat jika ada santri yang PP di rombongan yang sama
    unique_pendaftar = {p.id: p for p in pendaftar}.values()

    return render_template('daftar_peserta.html', rombongan=rombongan, pendaftar=unique_pendaftar)

@admin_bp.route('/peserta')
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
@login_required
def daftar_peserta_global():
    page = request.args.get('page', 1, type=int)
    active_edisi = get_active_edisi()
    
    # Query dasar yang menghubungkan Pendaftaran, Rombongan, dan Santri
    query = db.session.query(Pendaftaran).join(Santri).join(Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id)

    if active_edisi:
        query = query.filter(Rombongan.edisi_id == active_edisi.id)
    else:
        query = query.filter(db.false())

    # Ambil semua parameter filter dari URL
    f_nama = request.args.get('nama')
    f_rombongan_id = request.args.get('rombongan_id', type=int)
    f_status_bayar = request.args.get('status_bayar')
    
    # Terapkan filter ke query jika ada
    if f_nama:
        # Join eksplisit ke Santri diperlukan untuk filter nama
        query = query.join(Santri).filter(Santri.nama.ilike(f'%{f_nama}%'))
    if f_rombongan_id:
        # Filter berdasarkan rombongan pulang ATAU rombongan kembali
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Pendaftaran.rombongan_pulang_id == f_rombongan_id,
                Pendaftaran.rombongan_kembali_id == f_rombongan_id
            )
        )
    # Perbaiki filter status bayar untuk model baru
    if f_status_bayar:
        if f_status_bayar == 'Lunas':
            query = query.filter(Pendaftaran.status_pulang == 'Lunas', Pendaftaran.status_kembali.in_(['Lunas', 'Tidak Ikut']))
        elif f_status_bayar == 'Belum Lunas':
            query = query.filter((Pendaftaran.status_pulang == 'Belum Bayar') | (Pendaftaran.status_kembali == 'Belum Bayar'))

    pagination = query.order_by(Santri.nama).paginate(page=page, per_page=50, error_out=False)


    # Ambil semua rombongan untuk mengisi dropdown filter
    all_rombongan = Rombongan.query.filter_by(edisi=active_edisi).order_by(Rombongan.nama_rombongan).all() if active_edisi else []

    return render_template('daftar_peserta_global.html', 
                           pagination=pagination, # Kirim objek pagination
                           all_rombongan=all_rombongan)

@admin_bp.route('/perizinan', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
def perizinan():
    form = IzinForm()
    active_edisi = get_active_edisi()

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
        db.session.commit()
        flash(f"Izin untuk {santri.nama} telah berhasil dicatat.", "success")
        return redirect(url_for('admin.perizinan'))

    # Logika untuk filter
    query = Izin.query.filter_by(edisi=active_edisi)
    search_nama = request.args.get('nama')
    if search_nama:
        query = query.join(Santri).filter(Santri.nama.ilike(f'%{search_nama}%'))
    
    semua_izin = query.order_by(Izin.tanggal_berakhir).all()

    return render_template('perizinan.html', form=form, semua_izin=semua_izin)

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

@admin_bp.route('/izin/cabut/<int:izin_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'Keamanan') # Keamanan dan Korpus
def cabut_izin(izin_id):
    # 1. Cari data izin berdasarkan ID-nya
    izin = Izin.query.get_or_404(izin_id)
    
    # 2. Ambil data santri yang terhubung
    santri = izin.santri
    nama_santri = santri.nama
    
    # 3. Kembalikan status santri menjadi 'Aktif'
    santri.status_santri = 'Aktif'
    
    # 4. Hapus record izin dari database
    db.session.delete(izin)
    
    # 5. Simpan semua perubahan
    db.session.commit()
    
    flash(f"Izin untuk santri '{nama_santri}' telah berhasil dicabut.", "success")
    return redirect(url_for('admin.perizinan'))

@admin_bp.route('/partisipan')
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
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
    
    # Hapus record partisipan
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
            is_active=form.is_active.data
        )
        db.session.add(new_edisi)
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
@role_required('Korpus', 'Korwil', 'Korda')
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
@role_required('Korpus', 'Korwil', 'Korda')
def manajemen_keuangan():
    active_edisi = get_active_edisi()
    
    financial_data = {
        'global_total': 0, 'global_lunas': 0, 'global_belum_lunas': 0,
        'pulang_total': 0, 'pulang_lunas': 0, 'pulang_belum_lunas': 0,
        'kembali_total': 0, 'kembali_lunas': 0, 'kembali_belum_lunas': 0,
        'alokasi_bus_pulang': 0, 'alokasi_korda_pulang': 0, 'alokasi_pondok_pulang': 0,
        'alokasi_bus_kembali': 0, 'alokasi_korda_kembali': 0, 'alokasi_pondok_kembali': 0
    }

    if active_edisi:
        pendaftaran_query = Pendaftaran.query.join(Rombongan, Pendaftaran.rombongan_pulang_id == Rombongan.id).filter(Rombongan.edisi_id == active_edisi.id)

        if current_user.role.name in ['Korwil', 'Korda']:
            managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
            if not managed_rombongan_ids:
                pendaftaran_query = pendaftaran_query.filter(db.false())
            else:
                from sqlalchemy import or_
                pendaftaran_query = pendaftaran_query.filter(
                    or_(
                        Pendaftaran.rombongan_pulang_id.in_(managed_rombongan_ids),
                        Pendaftaran.rombongan_kembali_id.in_(managed_rombongan_ids)
                    )
                )
        
        all_pendaftaran = pendaftaran_query.all()

        for p in all_pendaftaran:
            # --- PERBAIKAN LOGIKA DI SINI ---
            
            # Kalkulasi untuk perjalanan pulang
            if p.status_pulang != 'Tidak Ikut' and p.rombongan_pulang_id and p.titik_turun:
                tarif_pulang = Tarif.query.filter_by(rombongan_id=p.rombongan_pulang_id, titik_turun=p.titik_turun).first()
                if tarif_pulang:
                    biaya_pulang = tarif_pulang.harga_bus + tarif_pulang.fee_korda + 10000
                    financial_data['pulang_total'] += biaya_pulang
                    financial_data['alokasi_bus_pulang'] += tarif_pulang.harga_bus
                    financial_data['alokasi_korda_pulang'] += tarif_pulang.fee_korda
                    financial_data['alokasi_pondok_pulang'] += 10000
                    if p.status_pulang == 'Lunas':
                        financial_data['pulang_lunas'] += biaya_pulang
            
            # Kalkulasi untuk perjalanan kembali
            if p.status_kembali != 'Tidak Ikut' and p.rombongan_kembali_id and p.titik_jemput_kembali:
                tarif_kembali = Tarif.query.filter_by(rombongan_id=p.rombongan_kembali_id, titik_turun=p.titik_jemput_kembali).first()
                if tarif_kembali:
                    biaya_kembali = tarif_kembali.harga_bus + tarif_kembali.fee_korda + 10000
                    financial_data['kembali_total'] += biaya_kembali
                    financial_data['alokasi_bus_kembali'] += tarif_kembali.harga_bus
                    financial_data['alokasi_korda_kembali'] += tarif_kembali.fee_korda
                    financial_data['alokasi_pondok_kembali'] += 10000
                    if p.status_kembali == 'Lunas':
                        financial_data['kembali_lunas'] += biaya_kembali
            
        financial_data['pulang_belum_lunas'] = financial_data['pulang_total'] - financial_data['pulang_lunas']
        financial_data['kembali_belum_lunas'] = financial_data['kembali_total'] - financial_data['kembali_lunas']
        financial_data['global_total'] = financial_data['pulang_total'] + financial_data['kembali_total']
        financial_data['global_lunas'] = financial_data['pulang_lunas'] + financial_data['kembali_lunas']
        financial_data['global_belum_lunas'] = financial_data['pulang_belum_lunas'] + financial_data['kembali_belum_lunas']

    return render_template('manajemen_keuangan.html', data=financial_data)

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
@role_required('Korpus', 'Korda', 'Korwil', 'Keamanan', 'PJ Acara')
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