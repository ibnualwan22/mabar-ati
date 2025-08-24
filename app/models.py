from sqlalchemy import UniqueConstraint
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
    countdown_title = db.Column(db.String(200))
    countdown_target_date = db.Column(db.DateTime)
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
    bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=True)
    bus = db.relationship('Bus', backref='korlapda')
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
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False)
    tanggal_berakhir = db.Column(db.Date, nullable=False)
    keterangan = db.Column(db.Text, nullable=False)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    status = db.Column(db.String(20), default='Aktif', nullable=False)
    __table_args__ = (
        UniqueConstraint('santri_id', 'edisi_id', name='uq_izin_santri_edisi'),
    )

class Partisipan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False)
    kategori = db.Column(db.String(100), nullable=False)
    tanggal_ditetapkan = db.Column(db.DateTime, server_default=db.func.now())
    __table_args__ = (
        UniqueConstraint('santri_id', 'edisi_id', name='uq_partisipan_santri_edisi'),
    )

class Santri(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    api_student_id = db.Column(db.String(50), unique=True, nullable=False)
    nis = db.Column(db.String(30), unique=True, nullable=False)
    nama = db.Column(db.String(150), nullable=False)
    kabupaten = db.Column(db.String(100))
    provinsi = db.Column(db.String(100), nullable=True)
    asrama = db.Column(db.String(50))
    no_hp_wali = db.Column(db.String(20))
    jenis_kelamin = db.Column(db.String(10), default='Putra')
    kelas_formal = db.Column(db.String(50))
    kelas_ngaji = db.Column(db.String(50))
    status_santri = db.Column(db.String(20), default='Aktif')
    nama_jabatan = db.Column(db.String(100), nullable=True)
    status_jabatan = db.Column(db.String(100), nullable=True)
    wisuda_info = db.relationship('Wisuda', 
                                  foreign_keys='Wisuda.santri_nis', 
                                  primaryjoin='Santri.nis == Wisuda.santri_nis', 
                                  backref='santri', 
                                  uselist=False, 
                                  cascade="all, delete-orphan")

    pendaftarans = db.relationship('Pendaftaran', back_populates='santri', lazy='dynamic', cascade="all, delete-orphan")
    izins = db.relationship('Izin', backref='santri', lazy='dynamic', cascade="all, delete-orphan")
    partisipans = db.relationship('Partisipan', backref='santri', lazy='dynamic', cascade="all, delete-orphan")

# --- MODEL BARU DAN YANG DIMODIFIKASI ---

class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    nama_armada = db.Column(db.String(100))
    nomor_lambung = db.Column(db.String(50))
    plat_nomor = db.Column(db.String(20))
    kuota = db.Column(db.Integer, default=50, nullable=False)
    keterangan = db.Column(db.Text)
    gmaps_share_url = db.Column(db.Text, nullable=True) # Untuk menyimpan URL Google Maps
    traccar_device_id = db.Column(db.String(100), nullable=True, unique=True)
    pendaftar_pulang = db.relationship('Pendaftaran', foreign_keys='Pendaftaran.bus_pulang_id', back_populates='bus_pulang')
    pendaftar_kembali = db.relationship('Pendaftaran', foreign_keys='Pendaftaran.bus_kembali_id', back_populates='bus_kembali')

class Rombongan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    nama_rombongan = db.Column(db.String(100), nullable=False)
    penanggung_jawab_putra = db.Column(db.String(100))
    kontak_person_putra = db.Column(db.String(20))
    penanggung_jawab_putri = db.Column(db.String(100))
    kontak_person_putri = db.Column(db.String(20))
    nomor_rekening = db.Column(db.String(50))
    cakupan_wilayah = db.Column(db.JSON)

    # Info Perjalanan Pulang
    jadwal_pulang = db.Column(db.DateTime)
    batas_pembayaran_pulang = db.Column(db.Date)
    
    # Info Perjalanan Kembali (Berangkat)
    jadwal_berangkat = db.Column(db.DateTime)
    batas_pembayaran_berangkat = db.Column(db.Date)
    titik_jemput_berangkat = db.Column(db.String(200))
    total_setoran_bus_pulang = db.Column(db.Integer, default=0)
    total_setoran_bus_kembali = db.Column(db.Integer, default=0)
    total_setoran_pondok_pulang = db.Column(db.Integer, default=0)
    total_setoran_pondok_kembali = db.Column(db.Integer, default=0)

    # Relasi
    tarifs = db.relationship('Tarif', backref='rombongan', cascade="all, delete-orphan")
    buses = db.relationship('Bus', backref='rombongan', cascade="all, delete-orphan")
    pendaftar_pulang = db.relationship('Pendaftaran', foreign_keys='Pendaftaran.rombongan_pulang_id', back_populates='rombongan_pulang')
    pendaftar_kembali = db.relationship('Pendaftaran', foreign_keys='Pendaftaran.rombongan_kembali_id', back_populates='rombongan_kembali')

    
class Pendaftaran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False)
    
    # --- PERUBAHAN UTAMA DI SINI ---
    rombongan_pulang_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=True)
    rombongan_kembali_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=True)
    
    # Detail Perjalanan Pulang
    status_pulang = db.Column(db.String(20), default='Tidak Ikut') # Belum Bayar, Lunas, Tidak Ikut
    metode_pembayaran_pulang = db.Column(db.String(20))
    bus_pulang_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=True)
    titik_turun = db.Column(db.String(100))
    
    # Detail Perjalanan Kembali
    status_kembali = db.Column(db.String(20), default='Tidak Ikut') # Belum Bayar, Lunas, Tidak Ikut
    metode_pembayaran_kembali = db.Column(db.String(20))
    bus_kembali_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=True)
    titik_jemput_kembali = db.Column(db.String(100), nullable=True)

    
    total_biaya = db.Column(db.Integer, nullable=False, default=0)
    tanggal_pendaftaran = db.Column(db.DateTime, server_default=db.func.now())

    # Relasi
    rombongan_pulang = db.relationship('Rombongan', foreign_keys=[rombongan_pulang_id], back_populates='pendaftar_pulang')
    rombongan_kembali = db.relationship('Rombongan', foreign_keys=[rombongan_kembali_id], back_populates='pendaftar_kembali')
    santri = db.relationship('Santri', back_populates='pendaftarans')
    bus_pulang = db.relationship('Bus', foreign_keys=[bus_pulang_id], back_populates='pendaftar_pulang')
    bus_kembali = db.relationship('Bus', foreign_keys=[bus_kembali_id], back_populates='pendaftar_kembali')
    absensi = db.relationship('Absen', backref='pendaftaran', lazy='dynamic', cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint('santri_id', 'edisi_id', name='uq_pendaftaran_santri_edisi'),
    )
    


class Absen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pendaftaran_id = db.Column(db.Integer, db.ForeignKey('pendaftaran.id'), nullable=False)
    nama_absen = db.Column(db.String(100), nullable=False) # Contoh: "Naik Bus Awal", "Rest Area KM 102"
    status = db.Column(db.String(20), nullable=False) # Contoh: "Hadir", "Tidak Hadir"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    dicatat_oleh_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    dicatat_oleh = db.relationship('User', backref='absen_dicatat')

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    action_type = db.Column(db.String(20), index=True) # Tambah, Edit, Hapus
    feature = db.Column(db.String(50), index=True) # Rombongan, Santri, Pendaftaran, dll.
    description = db.Column(db.Text)

    # Relasi untuk mengambil data user yang melakukan aksi
    user = db.relationship('User', backref='activities')

    def __repr__(self):
        return f'<Log: {self.user.username} - {self.action_type} - {self.feature}>'
    
class Wisuda(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Menggunakan NIS sebagai Foreign Key
    santri_nis = db.Column(db.String(30), db.ForeignKey('santri.nis'), nullable=False, unique=True)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    kategori_wisuda = db.Column(db.String(150), nullable=False)
    tanggal_penetapan = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi balik untuk akses mudah dari objek Edisi
    edisi = db.relationship('Edisi', backref=db.backref('wisudawan', lazy='dynamic'))
    

class Transaksi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edisi_id = db.Column(db.Integer, db.ForeignKey('edisi.id'), nullable=False)
    deskripsi = db.Column(db.String(255), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    tipe = db.Column(db.String(20), nullable=False) # 'PEMASUKAN' atau 'PENGELUaran'
    rekening = db.Column(db.String(50)) # 'REKENING_SAYA' atau 'REKENING_BUS'
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=True)


    user = db.relationship('User', backref='transaksi_dicatat')
    edisi = db.relationship('Edisi', backref='transaksi')
    rombongan = db.relationship('Rombongan', backref='transaksi_setoran')

    