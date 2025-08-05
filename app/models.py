from . import db
from datetime import datetime
from flask_login import UserMixin # <-- Import UserMixin
from app import bcrypt # <-- Import bcrypt dari app

class Edisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), unique=True, nullable=False)
    tahun = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    # Relasi ke rombongan, izin, dan partisipan yang ada di edisi ini
    rombongans = db.relationship('Rombongan', backref='edisi', lazy=True)
    izins = db.relationship('Izin', backref='edisi', lazy=True)
    partisipans = db.relationship('Partisipan', backref='edisi', lazy=True)

    def __repr__(self):
        return f'<Edisi {self.nama}>'

# Tabel perantara untuk relasi many-to-many antara User dan Rombongan
user_rombongan = db.Table('user_rombongan',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('rombongan_id', db.Integer, db.ForeignKey('rombongan.id'), primary_key=True)
)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    users = db.relationship('User', backref='role', lazy=True)

    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model, UserMixin): # UserMixin adalah tambahan dari Flask-Login
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    
    # Relasi many-to-many ke Rombongan yang dikelola
    managed_rombongan = db.relationship('Rombongan', secondary=user_rombongan, lazy='subquery',
        backref=db.backref('managers', lazy=True))

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Pendaftaran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
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
    nama_rombongan = db.Column(db.String(100), nullable=False)
    penanggung_jawab = db.Column(db.String(100), nullable=False)
    kontak_person = db.Column(db.String(20), nullable=False)
    nomor_rekening = db.Column(db.String(50), nullable=False)
    jadwal_keberangkatan = db.Column(db.DateTime, nullable=False)
    batas_pembayaran = db.Column(db.Date) # Kolom untuk tanggal
    kuota = db.Column(db.Integer, default=0)
    titik_kumpul = db.Column(db.String(200), nullable=False)
    nama_armada = db.Column(db.String(100))
    keterangan_armada = db.Column(db.Text)
    cakupan_wilayah = db.Column(db.JSON)

    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    tarifs = db.relationship('Tarif', backref='rombongan', lazy=True, cascade="all, delete-orphan")
    pendaftar = db.relationship('Pendaftaran', back_populates='rombongan', cascade="all, delete-orphan")


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

    # --- PERUBAHAN DARI 'backref' ---
    pendaftaran = db.relationship('Pendaftaran', back_populates='santri', uselist=False, cascade="all, delete-orphan")
    izin = db.relationship('Izin', backref='santri', uselist=False, cascade="all, delete-orphan")
    partisipan = db.relationship('Partisipan', backref='santri', uselist=False, cascade="all, delete-orphan")