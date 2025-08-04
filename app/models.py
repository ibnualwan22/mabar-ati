from . import db
from datetime import datetime

class Pendaftaran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    # ... (kolom lain di Pendaftaran tetap sama) ...
    titik_turun = db.Column(db.String(100), nullable=False)
    jenis_perjalanan = db.Column(db.String(20), default='Pulang Saja')
    nomor_bus = db.Column(db.String(20))
    status_pembayaran = db.Column(db.String(20), default='Belum Lunas')
    metode_pembayaran = db.Column(db.String(20))
    total_biaya = db.Column(db.Integer, nullable=False)
    tanggal_pendaftaran = db.Column(db.DateTime, server_default=db.func.now())

    # --- PERUBAHAN DARI 'backref' ---
    rombongan = db.relationship('Rombongan', back_populates='pendaftar')
    santri = db.relationship('Santri', back_populates='pendaftaran')


class Rombongan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # ... (kolom lain di Rombongan tetap sama) ...
    nama_rombongan = db.Column(db.String(100), nullable=False)
    penanggung_jawab = db.Column(db.String(100), nullable=False)
    kontak_person = db.Column(db.String(20), nullable=False)
    nomor_rekening = db.Column(db.String(50), nullable=False)
    jadwal_keberangkatan = db.Column(db.DateTime, nullable=False)
    titik_kumpul = db.Column(db.String(200), nullable=False)
    nama_armada = db.Column(db.String(100))
    keterangan_armada = db.Column(db.Text)
    cakupan_wilayah = db.Column(db.JSON)

    tarifs = db.relationship('Tarif', backref='rombongan', lazy=True, cascade="all, delete-orphan")
    # --- PERUBAHAN DARI 'backref' ---
    pendaftar = db.relationship('Pendaftaran', back_populates='rombongan', cascade="all, delete-orphan")


class Tarif(db.Model):
    # ... (tidak ada perubahan) ...
    id = db.Column(db.Integer, primary_key=True)
    titik_turun = db.Column(db.String(100), nullable=False)
    harga_bus = db.Column(db.Integer, nullable=False)
    fee_korda = db.Column(db.Integer, default=0)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)

class Izin(db.Model):
    # ... (tidak ada perubahan) ...
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    tanggal_berakhir = db.Column(db.Date, nullable=False)
    keterangan = db.Column(db.Text, nullable=False)

class Partisipan(db.Model):
    # ... (tidak ada perubahan) ...
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    kategori = db.Column(db.String(100), nullable=False)
    tanggal_ditetapkan = db.Column(db.DateTime, server_default=db.func.now())

class Santri(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # ... (kolom lain di Santri tetap sama) ...
    api_student_id = db.Column(db.String(50), unique=True, nullable=False)
    nis = db.Column(db.String(30), unique=True, nullable=False)
    nama = db.Column(db.String(150), nullable=False)
    kabupaten = db.Column(db.String(100))
    asrama = db.Column(db.String(50))
    no_hp_wali = db.Column(db.String(20))
    jenis_kelamin = db.Column(db.String(10), default='Putra')
    kelas_formal = db.Column(db.String(50))
    kelas_ngaji = db.Column(db.String(50))
    status_santri = db.Column(db.String(20), default='Aktif') 

    # --- PERUBAHAN DARI 'backref' ---
    pendaftaran = db.relationship('Pendaftaran', back_populates='santri', uselist=False, cascade="all, delete-orphan")
    izin = db.relationship('Izin', backref='santri', uselist=False, cascade="all, delete-orphan")
    partisipan = db.relationship('Partisipan', backref='santri', uselist=False, cascade="all, delete-orphan")