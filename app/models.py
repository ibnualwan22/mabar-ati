from . import db # Import db dari __init__.py

class Rombongan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_rombongan = db.Column(db.String(100), nullable=False)
    penanggung_jawab = db.Column(db.String(100), nullable=False)
    kontak_person = db.Column(db.String(20), nullable=False)
    nomor_rekening = db.Column(db.String(50), nullable=False)
    jadwal_keberangkatan = db.Column(db.DateTime, nullable=False)
    titik_kumpul = db.Column(db.String(200), nullable=False)
    nama_armada = db.Column(db.String(100))
    keterangan_armada = db.Column(db.Text)
    cakupan_wilayah = db.Column(db.JSON) # PASTIKAN BARIS INI ADA

    
    # Relasi one-to-many ke model Tarif
    # cascade="all, delete-orphan" artinya jika Rombongan dihapus, semua Tarif terkait juga akan terhapus.
    tarifs = db.relationship('Tarif', backref='rombongan', lazy=True, cascade="all, delete-orphan")
    santris = db.relationship('Santri', backref='rombongan', lazy=True, cascade="all, delete-orphan")


    def __repr__(self):
        return f'<Rombongan {self.nama_rombongan}>'

class Tarif(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titik_turun = db.Column(db.String(100), nullable=False)
    harga_bus = db.Column(db.Integer, nullable=False)
    fee_korda = db.Column(db.Integer, default=0)
    
    # Foreign Key untuk menghubungkan ke tabel Rombongan
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    
    def __repr__(self):
        return f'<Tarif {self.titik_turun}>'

class Santri(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # --- Data dari Snapshot API ---
    api_student_id = db.Column(db.String(50), unique=True, nullable=False)
    nis = db.Column(db.String(30), nullable=False)
    nama = db.Column(db.String(150), nullable=False)
    kabupaten = db.Column(db.String(100))
    asrama = db.Column(db.String(50))
    no_hp_wali = db.Column(db.String(20))
    jenis_kelamin = db.Column(db.String(10), default='Putra')

    # --- Data Manajemen Lokal ---
    status_rombongan = db.Column(db.String(30), default='Tidak Ikut Rombongan')
    status_pembayaran = db.Column(db.String(20), default='Belum Lunas')
    
    # --- Relasi ke Rombongan ---
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=True) # <-- Ubah menjadi True
    def __repr__(self):
        return f'<Santri {self.nama}>'