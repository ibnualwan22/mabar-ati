from . import admin_bp
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from app.models import Rombongan, Tarif, Santri, Pendaftaran, Izin, Partisipan, User
from app.admin.forms import RombonganForm, SantriEditForm, PendaftaranForm, PendaftaranEditForm, IzinForm, PartisipanForm, PartisipanEditForm, LoginForm, UserForm, UserEditForm
from app import db, login_manager
import json, requests
from collections import defaultdict
from sqlalchemy import update, text
from datetime import date
from flask_login import login_user, logout_user, current_user, login_required
from functools import wraps




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

def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role.name != role_name:
                abort(403) # Forbidden
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

@admin_bp.route('/')
@login_required
def dashboard():
    # Ambil daftar ID rombongan yang dikelola user
    managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]

    # Query dasar
    base_pendaftaran_query = Pendaftaran.query
    
    # Jika user bukan Korpus, filter query-nya
    if current_user.role.name in ['Korwil', 'Korda']:
        if not managed_rombongan_ids:
             base_pendaftaran_query = base_pendaftaran_query.filter(db.false()) # Return empty query
        else:
            base_pendaftaran_query = base_pendaftaran_query.filter(Pendaftaran.rombongan_id.in_(managed_rombongan_ids))

    # --- Kalkulasi Statistik Utama ---
    total_peserta = base_pendaftaran_query.count()
    total_izin = Santri.query.filter_by(status_santri='Izin').count()
    santri_belum_terdaftar = Santri.query.filter(Santri.status_santri == 'Aktif', Santri.pendaftaran == None).count()
    
    # --- Kalkulasi Keuangan Global berdasarkan data yang boleh dilihat ---
    total_pemasukan = base_pendaftaran_query.with_entities(db.func.sum(Pendaftaran.total_biaya)).scalar() or 0
    total_lunas = base_pendaftaran_query.filter(Pendaftaran.status_pembayaran == 'Lunas').with_entities(db.func.sum(Pendaftaran.total_biaya)).scalar() or 0
    total_belum_lunas = total_pemasukan - total_lunas
    jumlah_cash = base_pendaftaran_query.filter_by(metode_pembayaran='Cash').count()
    jumlah_transfer = base_pendaftaran_query.filter_by(metode_pembayaran='Transfer').count()
    
    # --- Pendaftar Terlambat Bayar ---
    pendaftar_terlambat_query = base_pendaftaran_query.join(Rombongan).filter(
        Pendaftaran.status_pembayaran == 'Belum Lunas',
        Rombongan.batas_pembayaran != None,
        Rombongan.batas_pembayaran < date.today()
    )
    pendaftar_terlambat = pendaftar_terlambat_query.all()

    # --- Tabel Ringkasan per Rombongan ---
    rombongan_query = Rombongan.query
    if current_user.role.name in ['Korwil', 'Korda']:
        if not managed_rombongan_ids:
            rombongan_query = rombongan_query.filter(db.false())
        else:
            rombongan_query = rombongan_query.filter(Rombongan.id.in_(managed_rombongan_ids))
    
    semua_rombongan = rombongan_query.order_by(Rombongan.nama_rombongan).all()
    
    stats = { 'total_peserta': total_peserta, 'total_izin': total_izin, 'santri_belum_terdaftar': santri_belum_terdaftar, 'total_pemasukan': total_pemasukan, 'total_lunas': total_lunas, 'total_belum_lunas': total_belum_lunas, 'jumlah_cash': jumlah_cash, 'jumlah_transfer': jumlah_transfer, 'pendaftar_terlambat': pendaftar_terlambat }
    return render_template('dashboard.html', stats=stats, semua_rombongan=semua_rombongan)

# --- BUAT FUNGSI BARU INI ---
@admin_bp.route('/rombongan')
@login_required
@role_required('Korpus', 'Korwil', 'Korda')
def manajemen_rombongan():
    query = Rombongan.query
    if current_user.role.name in ['Korwil', 'Korda']:
        managed_rombongan_ids = [r.id for r in current_user.managed_rombongan]
        if not managed_rombongan_ids:
            query = query.filter(db.false())
        else:
            query = query.filter(Rombongan.id.in_(managed_rombongan_ids))
    
    semua_rombongan = query.order_by(Rombongan.jadwal_keberangkatan.desc()).all()
    return render_template('manajemen_rombongan.html', semua_rombongan=semua_rombongan)

# --- KODE BARU DIMULAI DI SINI ---

@admin_bp.route('/rombongan/tambah', methods=['GET', 'POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def tambah_rombongan():
    form = RombonganForm()
    if form.validate_on_submit():
        # Buat objek Rombongan baru
        new_rombongan = Rombongan(
            nama_rombongan=form.nama_rombongan.data,
            penanggung_jawab=form.penanggung_jawab.data,
            kontak_person=form.kontak_person.data,
            nomor_rekening=form.nomor_rekening.data,
            jadwal_keberangkatan=form.jadwal_keberangkatan.data,
            batas_pembayaran=form.batas_pembayaran.data,
            kuota=form.kuota.data,
            titik_kumpul=form.titik_kumpul.data,
            nama_armada=form.nama_armada.data,
            keterangan_armada=form.keterangan_armada.data,
            cakupan_wilayah=json.loads(form.cakupan_wilayah.data or '[]')
        )

        # Loop melalui data tarif dan buat objek Tarif
        for tarif_data in form.tarifs.data:
            new_tarif = Tarif(
                titik_turun=tarif_data['titik_turun'],
                harga_bus=tarif_data['harga_bus'],
                fee_korda=tarif_data['fee_korda']
            )
            # Hubungkan tarif ini dengan rombongan
            new_rombongan.tarifs.append(new_tarif)
        
        # Simpan ke database
        db.session.add(new_rombongan)
        db.session.commit()
        
        flash('Rombongan baru berhasil ditambahkan!', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('form_rombongan.html', form=form, title='Tambah Rombongan Baru')

@admin_bp.route('/rombongan/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus') # Hanya Korpus yang bisa buat rombongan baru
def edit_rombongan(id):
    # Ambil data rombongan dari database berdasarkan ID
    rombongan = Rombongan.query.get_or_404(id)
    form = RombonganForm()

    # Jika form disubmit dan valid
    if form.validate_on_submit():
        # Update data rombongan dengan data dari form
        rombongan.nama_rombongan = form.nama_rombongan.data
        rombongan.penanggung_jawab = form.penanggung_jawab.data
        rombongan.kontak_person = form.kontak_person.data
        rombongan.nomor_rekening = form.nomor_rekening.data
        rombongan.jadwal_keberangkatan = form.jadwal_keberangkatan.data
        rombongan.batas_pembayaran = form.batas_pembayaran.data
        rombongan.kuota = form.kuota.data
        rombongan.titik_kumpul = form.titik_kumpul.data
        rombongan.nama_armada = form.nama_armada.data
        rombongan.keterangan_armada = form.keterangan_armada.data
        rombongan.cakupan_wilayah = json.loads(form.cakupan_wilayah.data or '[]')


        # Hapus tarif lama dan ganti dengan yang baru dari form
        rombongan.tarifs.clear()
        for tarif_data in form.tarifs.data:
            new_tarif = Tarif(
                titik_turun=tarif_data['titik_turun'],
                harga_bus=tarif_data['harga_bus'],
                fee_korda=tarif_data['fee_korda']
            )
            rombongan.tarifs.append(new_tarif)
        
        db.session.commit()
        flash('Data rombongan berhasil diperbarui!', 'success')
        return redirect(url_for('admin.dashboard'))

    # Jika request adalah GET (pertama kali halaman dibuka)
    # Isi form dengan data yang ada di database
    form.nama_rombongan.data = rombongan.nama_rombongan
    form.penanggung_jawab.data = rombongan.penanggung_jawab
    form.kontak_person.data = rombongan.kontak_person
    form.nomor_rekening.data = rombongan.nomor_rekening
    form.jadwal_keberangkatan.data = rombongan.jadwal_keberangkatan
    form.batas_pembayaran.data = rombongan.batas_pembayaran
    form.kuota.data = rombongan.kuota
    form.titik_kumpul.data = rombongan.titik_kumpul
    form.nama_armada.data = rombongan.nama_armada
    form.keterangan_armada.data = rombongan.keterangan_armada
    form.cakupan_wilayah.data = json.dumps(rombongan.cakupan_wilayah or [])


    # Hapus entry default di form tarif dan isi dengan data dari DB
    while len(form.tarifs) > 0:
        form.tarifs.pop_entry()
    for tarif in rombongan.tarifs:
        tarif_form_data = {
            'titik_turun': tarif.titik_turun,
            'harga_bus': tarif.harga_bus,
            'fee_korda': tarif.fee_korda
        }
        form.tarifs.append_entry(tarif_form_data)

    return render_template('form_rombongan.html', form=form, title='Edit Rombongan')


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
    
# @admin_bp.route('/rombongan/<int:rombongan_id>/kelola-santri')
# def kelola_santri(rombongan_id):
#     # Ambil data rombongan saat ini
#     rombongan = Rombongan.query.get_or_404(rombongan_id)
    
#     # Untuk saat ini, kita hanya akan menampilkan halaman kosong
#     # Logika untuk filter dan search akan ditambahkan nanti
    
#     # Ambil semua santri yang terhubung dengan rombongan ini
#     # (Relasi `rombongan.santris` sudah kita buat di model)
#     peserta = rombongan.santris

#     return render_template('kelola_santri.html', rombongan=rombongan, peserta=peserta)

@admin_bp.route('/santri')
def manajemen_santri():
    page = request.args.get('page', 1, type=int)
    
    # Query dasar, kita akan join dengan Pendaftaran jika diperlukan
    query = Santri.query

    # Ambil parameter filter
    search_nama = request.args.get('nama')
    search_asrama = request.args.get('asrama')
    search_status = request.args.get('status')
    f_rombongan_id = request.args.get('rombongan_id') # Ambil sebagai string dulu

    # Terapkan filter
    if search_nama:
        query = query.filter(Santri.nama.ilike(f'%{search_nama}%'))
    if search_asrama:
        query = query.filter(Santri.asrama.ilike(f'%{search_asrama}%'))
    if search_status:
        query = query.filter(Santri.status_santri == search_status)

    # --- LOGIKA FILTER ROMBONGAN BARU ---
    if f_rombongan_id:
        if f_rombongan_id == 'belum_terdaftar':
            # Gunakan outerjoin untuk mencari santri yang tidak punya record pendaftaran
            query = query.outerjoin(Pendaftaran).filter(Pendaftaran.id == None)
        else:
            # Gunakan join biasa untuk mencari santri di rombongan spesifik
            query = query.join(Pendaftaran).filter(Pendaftaran.rombongan_id == f_rombongan_id)

    pagination = query.order_by(Santri.nama).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Ambil semua rombongan untuk mengisi dropdown filter
    all_rombongan = Rombongan.query.order_by(Rombongan.nama_rombongan).all()
    
    return render_template('manajemen_santri.html', 
                           pagination=pagination, 
                           all_rombongan=all_rombongan)

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

# Ganti route pendaftaran_rombongan yang lama dengan ini
@admin_bp.route('/pendaftaran', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda')
def pendaftaran_rombongan():
    form = PendaftaranForm()
    
    # Mengisi pilihan dropdown rombongan berdasarkan peran user
    if current_user.role.name == 'Korda':
        form.rombongan.choices = [(r.id, r.nama_rombongan) for r in current_user.managed_rombongan]
    else: # Untuk Korpus, tampilkan semua
        form.rombongan.choices = [(0, '-- Pilih Rombongan --')] + [(r.id, r.nama_rombongan) for r in Rombongan.query.order_by(Rombongan.nama_rombongan).all()]

    # Jika ini adalah request POST, kita perlu mengisi pilihan 'titik_turun' sebelum validasi
    if request.method == 'POST':
        rombongan_id_from_form = request.form.get('rombongan')
        if rombongan_id_from_form:
            selected_rombongan = Rombongan.query.get(rombongan_id_from_form)
            if selected_rombongan:
                form.titik_turun.choices = [(t.titik_turun, t.titik_turun) for t in selected_rombongan.tarifs]

    if form.validate_on_submit():
        # Ambil ID dari form
        rombongan_id = form.rombongan.data
        santri_id = form.santri.data
        
        # Ambil objek lengkap dari database
        rombongan = Rombongan.query.get(rombongan_id)
        santri = Santri.query.get(santri_id)

        if not santri or not rombongan:
            flash("ERROR: Santri atau Rombongan tidak ditemukan.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))

        # Lakukan validasi status santri
        if santri.status_santri == 'Izin':
            flash(f"ERROR: {santri.nama} sedang Izin dan tidak bisa didaftarkan.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))

        # Gunakan rombongan_id langsung untuk query tarif
        selected_tarif = Tarif.query.filter_by(rombongan_id=rombongan_id, titik_turun=form.titik_turun.data).first()
        if not selected_tarif:
            flash("Terjadi error: Titik turun tidak valid.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))
        
        # Kalkulasi biaya
        total_biaya = selected_tarif.harga_bus + selected_tarif.fee_korda + 10000
        if form.jenis_perjalanan.data == 'Pulang Pergi':
            total_biaya *= 2

        # Buat objek Pendaftaran dengan objek lengkap
        pendaftaran = Pendaftaran(
            santri=santri, rombongan=rombongan, titik_turun=form.titik_turun.data,
            jenis_perjalanan=form.jenis_perjalanan.data, status_pembayaran=form.status_pembayaran.data,
            metode_pembayaran=form.metode_pembayaran.data,
            nomor_bus=form.nomor_bus.data, total_biaya=total_biaya
        )
        db.session.add(pendaftaran)
        db.session.commit()
        
        flash(f"{santri.nama} berhasil didaftarkan ke {rombongan.nama_rombongan}!", "success")
        return redirect(url_for('admin.daftar_peserta', rombongan_id=pendaftaran.rombongan.id))
    
    # Logika untuk menampilkan daftar peserta di bawah (jika ada rombongan_id di URL)
    peserta_terdaftar = []
    rombongan_id_get = request.args.get('rombongan_id', type=int)
    if rombongan_id_get:
        rombongan_terpilih = Rombongan.query.get(rombongan_id_get)
        if rombongan_terpilih:
            peserta_terdaftar = rombongan_terpilih.pendaftar

    return render_template('pendaftaran_rombongan.html', form=form, peserta=peserta_terdaftar)

@admin_bp.route('/pendaftaran/edit/<int:pendaftaran_id>', methods=['GET', 'POST'])
@login_required
@role_required('Korpus', 'Korda')
def edit_pendaftaran(pendaftaran_id):
    pendaftaran = Pendaftaran.query.get_or_404(pendaftaran_id)
    if current_user.role.name == 'Korda' and pendaftaran.rombongan not in current_user.managed_rombongan:
        abort(403)
        if pendaftaran.rombongan not in current_user.managed_rombongan:
            abort(403) # Akses ditolak jika mencoba mengedit pendaftaran di luar rombongannya
    form = PendaftaranEditForm(obj=pendaftaran)
    
    # Isi pilihan titik turun secara dinamis berdasarkan rombongan pendaftaran
    form.titik_turun.choices = [(t.titik_turun, t.titik_turun) for t in pendaftaran.rombongan.tarifs]

    if form.validate_on_submit():
        # Update data pendaftaran dari form
        pendaftaran.titik_turun = form.titik_turun.data
        pendaftaran.jenis_perjalanan = form.jenis_perjalanan.data
        pendaftaran.status_pembayaran = form.status_pembayaran.data
        pendaftaran.metode_pembayaran = form.metode_pembayaran.data
        pendaftaran.nomor_bus = form.nomor_bus.data
        
        # Hitung ulang total biaya jika ada perubahan
        selected_tarif = Tarif.query.filter_by(rombongan_id=pendaftaran.rombongan_id, titik_turun=pendaftaran.titik_turun).first()
        total_biaya = selected_tarif.harga_bus + selected_tarif.fee_korda + 10000
        if pendaftaran.jenis_perjalanan == 'Pulang Pergi':
            total_biaya *= 2
        pendaftaran.total_biaya = total_biaya

        db.session.commit()
        flash(f"Data pendaftaran untuk {pendaftaran.santri.nama} berhasil diperbarui.", "success")
        return redirect(url_for('admin.daftar_peserta', rombongan_id=pendaftaran.rombongan_id))

    return render_template('edit_pendaftaran.html', form=form, pendaftaran=pendaftaran)


@admin_bp.route('/pendaftaran/hapus/<int:pendaftaran_id>', methods=['POST'])
@login_required
@role_required('Korpus', 'Korda')
def hapus_pendaftaran(pendaftaran_id):
    pendaftaran = Pendaftaran.query.get_or_404(pendaftaran_id)
    if current_user.role.name == 'Korda' and pendaftaran.rombongan not in current_user.managed_rombongan:
        abort(403)
    rombongan_id = pendaftaran.rombongan_id # Simpan ID rombongan untuk redirect
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
    
    # Ambil data pendaftar untuk ditampilkan di tabel
    pendaftar_data = []
    for p in rombongan.pendaftar:
        pendaftar_data.append({
            'nama': p.santri.nama,
            'nis': p.santri.nis,
            'titik_turun': p.titik_turun,
            'total_biaya': p.total_biaya
        })

    return jsonify({
        'cakupan_wilayah': rombongan.cakupan_wilayah,
        'tarifs': tarifs,
        'pendaftar': pendaftar_data
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
def daftar_peserta(rombongan_id):
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    # --- VERIFIKASI KEPEMILIKAN ---
    if current_user.role.name in ['Korwil', 'Korda']:
        if rombongan not in current_user.managed_rombongan:
            abort(403)
    # `rombongan.pendaftar` adalah backref yang kita buat di model Pendaftaran
    # Ini akan berisi semua data pendaftaran untuk rombongan ini
    return render_template('daftar_peserta.html', rombongan=rombongan)

@admin_bp.route('/peserta')
def daftar_peserta_global():
    # Query dasar yang menghubungkan Pendaftaran dengan Santri
    query = db.session.query(Pendaftaran).join(Santri)

    # Ambil semua parameter filter dari URL
    f_nama = request.args.get('nama')
    f_alamat = request.args.get('alamat')
    f_titik_turun = request.args.get('titik_turun')
    f_status_bayar = request.args.get('status_bayar')
    f_metode_bayar = request.args.get('metode_bayar')
    f_rombongan_id = request.args.get('rombongan_id', type=int) # <-- FILTER BARU

    # Terapkan filter ke query jika ada
    if f_nama:
        query = query.filter(Santri.nama.ilike(f'%{f_nama}%'))
    if f_alamat:
        query = query.filter(Santri.kabupaten.ilike(f'%{f_alamat}%'))
    if f_titik_turun:
        query = query.filter(Pendaftaran.titik_turun.ilike(f'%{f_titik_turun}%'))
    if f_status_bayar:
        query = query.filter(Pendaftaran.status_pembayaran == f_status_bayar)
    if f_metode_bayar:
        query = query.filter(Pendaftaran.metode_pembayaran == f_metode_bayar)
    if f_rombongan_id: # <-- LOGIKA FILTER BARU
        query = query.filter(Pendaftaran.rombongan_id == f_rombongan_id)

    # Eksekusi query final dan urutkan berdasarkan nama santri
    semua_pendaftar = query.order_by(Santri.nama).all()

    # Ambil semua rombongan untuk mengisi dropdown filter
    all_rombongan = Rombongan.query.order_by(Rombongan.nama_rombongan).all()

    return render_template('daftar_peserta_global.html', 
                           semua_pendaftar=semua_pendaftar, 
                           all_rombongan=all_rombongan)

@admin_bp.route('/perizinan', methods=['GET', 'POST'])
@login_required
def perizinan():
    form = IzinForm()
    if form.validate_on_submit():
        # 1. Ambil ID santri dari form
        santri_id = form.santri.data
        # 2. Ambil objek santri lengkap dari database
        santri = Santri.query.get(santri_id)

        if not santri:
            flash(f"ERROR: Santri dengan ID {santri_id} tidak ditemukan.", "danger")
            return redirect(url_for('admin.perizinan'))

        # 3. Buat record izin baru menggunakan objek santri yang sudah diambil
        new_izin = Izin(
            santri=santri,
            tanggal_berakhir=form.tanggal_berakhir.data,
            keterangan=form.keterangan.data
        )
        # Update status santri menjadi 'Izin'
        santri.status_santri = 'Izin'
        
        db.session.add(new_izin)
        db.session.commit()
        flash(f"Izin untuk {santri.nama} telah berhasil dicatat.", "success")
        return redirect(url_for('admin.perizinan'))

    # Logika untuk filter
    query = Izin.query
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
def data_partisipan():
    # 1. Ambil semua data partisipan
    semua_partisipan = Partisipan.query.all()
    
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
    if form.validate_on_submit():
        santri_id = form.santri.data
        santri = Santri.query.get(santri_id)

        if santri and santri.status_santri == 'Aktif':
            # Buat record partisipan baru
            new_partisipan = Partisipan(
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