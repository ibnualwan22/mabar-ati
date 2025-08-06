from . import db
from datetime import datetime
from flask_login import UserMixin
from app import bcrypt

# --- Model yang tidak banyak berubah ---
class Edisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), unique=True, nullable=False)
    tahun = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    rombongans = db.relationship('Rombongan', backref='edisi', lazy='dynamic')
    izins = db.relationship('Izin', backref='edisi', lazy='dynamic')
    partisipans = db.relationship('Partisipan', backref='edisi', lazy='dynamic')

user_rombongan = db.Table('user_rombongan',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('rombongan_id', db.Integer, db.ForeignKey('rombongan.id'), primary_key=True)
)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    users = db.relationship('User', backref='role', lazy=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    managed_rombongan = db.relationship('Rombongan', secondary=user_rombongan, lazy='subquery', backref=db.backref('managers', lazy=True))
    def set_password(self, password): self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    def check_password(self, password): return bcrypt.check_password_hash(self.password_hash, password)

class Tarif(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titik_turun = db.Column(db.String(100), nullable=False)
    harga_bus = db.Column(db.Integer, nullable=False)
    fee_korda = db.Column(db.Integer, default=0)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)

class Izin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    tanggal_berakhir = db.Column(db.Date, nullable=False)
    keterangan = db.Column(db.Text, nullable=False)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)

class Partisipan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    kategori = db.Column(db.String(100), nullable=False)
    tanggal_ditetapkan = db.Column(db.DateTime, server_default=db.func.now())
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)

class Santri(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
    pendaftaran = db.relationship('Pendaftaran', back_populates='santri', uselist=False, cascade="all, delete-orphan")
    izin = db.relationship('Izin', backref='santri', uselist=False, cascade="all, delete-orphan")
    partisipan = db.relationship('Partisipan', backref='santri', uselist=False, cascade="all, delete-orphan")

# --- MODEL BARU DAN YANG DIMODIFIKASI ---

class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    nama_armada = db.Column(db.String(100))
    nomor_lambung = db.Column(db.String(50))
    plat_nomor = db.Column(db.String(20))
    kuota = db.Column(db.Integer, default=50, nullable=False)
    keterangan = db.Column(db.Text)

class Rombongan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    nama_rombongan = db.Column(db.String(100), nullable=False)
    penanggung_jawab = db.Column(db.String(100), nullable=False)
    kontak_person = db.Column(db.String(20), nullable=False)
    nomor_rekening = db.Column(db.String(50), nullable=False)
    cakupan_wilayah = db.Column(db.JSON)
    jadwal_keberangkatan = db.Column(db.DateTime) # Pulang
    titik_kumpul = db.Column(db.String(200)) # Pulang
    jadwal_kembali = db.Column(db.DateTime) # Kembali
    titik_kumpul_kembali = db.Column(db.String(200)) # Kembali
    batas_pembayaran = db.Column(db.Date)
    tarifs = db.relationship('Tarif', backref='rombongan', lazy='dynamic', cascade="all, delete-orphan")
    buses = db.relationship('Bus', backref='rombongan', lazy='dynamic', cascade="all, delete-orphan")
    pendaftar = db.relationship('Pendaftaran', back_populates='rombongan', cascade="all, delete-orphan")

class Pendaftaran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    
    # Detail Perjalanan Pulang
    status_pulang = db.Column(db.String(20), default='Belum Bayar') # Belum Bayar, Lunas, Tidak Ikut
    metode_pembayaran_pulang = db.Column(db.String(20))
    bus_pulang_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=True)
    titik_turun = db.Column(db.String(100))
    
    # Detail Perjalanan Kembali
    status_kembali = db.Column(db.String(20), default='Belum Bayar') # Belum Bayar, Lunas, Tidak Ikut
    metode_pembayaran_kembali = db.Column(db.String(20))
    bus_kembali_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=True)
    
    total_biaya = db.Column(db.Integer, nullable=False, default=0)
    tanggal_pendaftaran = db.Column(db.DateTime, server_default=db.func.now())

    rombongan = db.relationship('Rombongan', back_populates='pendaftar')
    santri = db.relationship('Santri', back_populates='pendaftaran')
    bus_pulang = db.relationship('Bus', foreign_keys=[bus_pulang_id])
    bus_kembali = db.relationship('Bus', foreign_keys=[bus_kembali_id])