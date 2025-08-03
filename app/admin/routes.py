from . import admin_bp
from flask import render_template, redirect, url_for, flash, request
from app.models import Rombongan, Tarif, Santri
from app.admin.forms import RombonganForm, SantriEditForm
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