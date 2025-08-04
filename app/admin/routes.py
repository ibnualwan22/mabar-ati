from . import admin_bp
from flask import render_template, redirect, url_for, flash, request
from app.models import Rombongan, Tarif, Santri, Pendaftaran, Izin
from app.admin.forms import RombonganForm, SantriEditForm, PendaftaranForm, PendaftaranEditForm, IzinForm
from app import db # Import db dari level atas
import json, requests
from flask import request, jsonify


@admin_bp.route('/')
def dashboard():
    semua_rombongan = Rombongan.query.order_by(Rombongan.jadwal_keberangkatan.desc()).all()
    return render_template('dashboard.html', semua_rombongan=semua_rombongan)


# --- KODE BARU DIMULAI DI SINI ---

@admin_bp.route('/rombongan/tambah', methods=['GET', 'POST'])
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
    
@admin_bp.route('/rombongan/<int:rombongan_id>/kelola-santri')
def kelola_santri(rombongan_id):
    # Ambil data rombongan saat ini
    rombongan = Rombongan.query.get_or_404(rombongan_id)
    
    # Untuk saat ini, kita hanya akan menampilkan halaman kosong
    # Logika untuk filter dan search akan ditambahkan nanti
    
    # Ambil semua santri yang terhubung dengan rombongan ini
    # (Relasi `rombongan.santris` sudah kita buat di model)
    peserta = rombongan.santris

    return render_template('kelola_santri.html', rombongan=rombongan, peserta=peserta)

@admin_bp.route('/santri')
def manajemen_santri():
    # Mulai dengan query dasar untuk semua santri
    query = Santri.query

    # Ambil parameter filter dari URL
    search_nama = request.args.get('nama')
    search_alamat = request.args.get('alamat')
    search_asrama = request.args.get('asrama')
    search_status = request.args.get('status')

    # Terapkan filter ke query jika ada
    if search_nama:
        query = query.filter(Santri.nama.ilike(f'%{search_nama}%'))
    if search_alamat:
        query = query.filter(Santri.kabupaten.ilike(f'%{search_alamat}%'))
    if search_asrama:
        query = query.filter(Santri.asrama.ilike(f'%{search_asrama}%'))
    if search_status:
        query = query.filter(Santri.status_rombongan == search_status)

    # Eksekusi query yang sudah difilter
    semua_santri = query.order_by(Santri.nama).all()
    
    return render_template('manajemen_santri.html', semua_santri=semua_santri)

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
def impor_semua_santri():
    try:
        # 1. Ambil semua data dari API Induk
        api_url = "https://dev.amtsilatipusat.com/api/student?limit=2000" # Ambil hingga 2000 data
        response = requests.get(api_url, timeout=30) # Tambah timeout karena data besar
        response.raise_for_status()
        santri_from_api = response.json().get('data', [])

        # 2. Ambil semua santri yang sudah ada di DB lokal untuk perbandingan
        # Gunakan dictionary untuk pencarian cepat: {api_id: santri_objek}
        existing_santri_map = {s.api_student_id: s for s in Santri.query.all()}
        
        new_count = 0
        updated_count = 0

        # 3. Loop melalui data dari API
        for data in santri_from_api:
            api_id = data.get('id')
            if not api_id:
                continue

            # Cek apakah santri sudah ada di map kita
            if api_id in existing_santri_map:
                # Jika ADA, update datanya (Sinkronisasi)
                santri_to_update = existing_santri_map[api_id]
                santri_to_update.nis = data.get('nis', santri_to_update.nis)
                santri_to_update.nama = data.get('name', santri_to_update.nama)
                santri_to_update.kabupaten = data.get('regency', santri_to_update.kabupaten)
                santri_to_update.asrama = data.get('activeDormitory', santri_to_update.asrama)
                santri_to_update.no_hp_wali = data.get('parrentPhone', santri_to_update.no_hp_wali)
                santri_to_update.jenis_kelamin = data.get('gender') or 'Putra'
                updated_count += 1
            else:
                # Jika TIDAK ADA, buat record baru (Impor)
                new_santri = Santri(
                    api_student_id=api_id,
                    nis=data.get('nis', 'N/A'),
                    nama=data.get('name', 'Tanpa Nama'),
                    kabupaten=data.get('regency'),
                    asrama=data.get('activeDormitory'),
                    no_hp_wali=data.get('parrentPhone'),
                    jenis_kelamin=data.get('gender') or 'Putra'
                )
                db.session.add(new_santri)
                new_count += 1
        
        # 4. Simpan semua perubahan ke database
        db.session.commit()
        
        flash(f"Proses selesai! Berhasil mengimpor {new_count} santri baru dan memperbarui {updated_count} data santri.", "success")

    except requests.exceptions.RequestException as e:
        flash(f"Gagal mengambil data dari API Induk: {e}", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Terjadi error saat memproses data: {e}", "danger")

    return redirect(url_for('admin.manajemen_santri'))

@admin_bp.route('/santri/edit/<int:id>', methods=['GET', 'POST'])
def edit_santri(id):
    santri = Santri.query.get_or_404(id)
    form = SantriEditForm(obj=santri) # 'obj=santri' akan mengisi form dengan data awal

    if form.validate_on_submit():
        # Daftarkan santri ke rombongan yang dipilih
        santri.rombongan = form.rombongan.data
        # Update status-statusnya
        santri.status_rombongan = form.status_rombongan.data
        santri.status_pembayaran = form.status_pembayaran.data
        
        db.session.commit()
        flash(f"Data {santri.nama} berhasil diperbarui.", "success")
        return redirect(url_for('admin.manajemen_santri'))

    return render_template('edit_santri.html', form=form, santri=santri)

@admin_bp.route('/santri/hapus/<int:id>', methods=['POST'])
def hapus_santri(id):
    santri = Santri.query.get_or_404(id)
    nama_santri = santri.nama
    db.session.delete(santri)
    db.session.commit()
    flash(f"Santri '{nama_santri}' berhasil dihapus dari sistem.", "info")
    return redirect(url_for('admin.manajemen_santri'))

# Ganti route pendaftaran_rombongan yang lama dengan ini
@admin_bp.route('/pendaftaran', methods=['GET', 'POST'])
def pendaftaran_rombongan():
    form = PendaftaranForm()
    
    # --- BLOK KODE BARU UNTUK MENGATASI VALIDASI ---
    # Ambil rombongan_id dari form yang disubmit
    if request.method == 'POST':
        rombongan_id_from_form = request.form.get('rombongan')
        if rombongan_id_from_form:
            selected_rombongan = Rombongan.query.get(rombongan_id_from_form)
            if selected_rombongan:
                # Isi choices untuk titik_turun SEBELUM validasi
                form.titik_turun.choices = [(t.titik_turun, t.titik_turun) for t in selected_rombongan.tarifs]
    # --- AKHIR BLOK KODE BARU ---

    if form.validate_on_submit():
        # 1. Ambil ID santri dari form
        santri_id = form.santri.data
        # 2. Ambil objek santri lengkap dari database menggunakan ID
        santri = Santri.query.get(santri_id)

        if not santri:
            flash(f"ERROR: Santri dengan ID {santri_id} tidak ditemukan.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))

        # 3. Sekarang kita bisa cek statusnya dengan aman
        if santri.status_santri == 'Izin':
            flash(f"ERROR: {santri.nama} sedang Izin dan tidak bisa didaftarkan.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))

        selected_tarif = Tarif.query.filter_by(rombongan_id=form.rombongan.data.id, titik_turun=form.titik_turun.data).first()
        if not selected_tarif:
            flash("Terjadi error: Titik turun tidak valid.", "danger")
            return redirect(url_for('admin.pendaftaran_rombongan'))
        
        total_biaya = selected_tarif.harga_bus + selected_tarif.fee_korda + 10000
        if form.jenis_perjalanan.data == 'Pulang Pergi':
            total_biaya *= 2

        pendaftaran = Pendaftaran(
            santri=santri, rombongan=form.rombongan.data, titik_turun=form.titik_turun.data,
            jenis_perjalanan=form.jenis_perjalanan.data, status_pembayaran=form.status_pembayaran.data,
            metode_pembayaran=form.metode_pembayaran.data, # <-- TAMBAHKAN INI
            nomor_bus=form.nomor_bus.data, total_biaya=total_biaya
        )
        db.session.add(pendaftaran)
        db.session.commit()
        flash(f"{santri.nama} berhasil didaftarkan!", "success")
        return redirect(url_for('admin.daftar_peserta', rombongan_id=pendaftaran.rombongan.id))
    
    peserta_terdaftar = []
    rombongan_id_get = request.args.get('rombongan_id', type=int)
    if rombongan_id_get:
        rombongan_terpilih = Rombongan.query.get(rombongan_id_get)
        if rombongan_terpilih:
            peserta_terdaftar = rombongan_terpilih.pendaftar

    return render_template('pendaftaran_rombongan.html', form=form, peserta=peserta_terdaftar)

@admin_bp.route('/pendaftaran/edit/<int:pendaftaran_id>', methods=['GET', 'POST'])
def edit_pendaftaran(pendaftaran_id):
    pendaftaran = Pendaftaran.query.get_or_404(pendaftaran_id)
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
def hapus_pendaftaran(pendaftaran_id):
    pendaftaran = Pendaftaran.query.get_or_404(pendaftaran_id)
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
    if len(query) < 3:
        return jsonify({'results': []})

    # Cari santri yang namanya cocok DAN belum terdaftar di pendaftaran manapun
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