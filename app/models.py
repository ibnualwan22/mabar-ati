from . import db

# Tabel Jembatan untuk Pendaftaran
class Pendaftaran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Kunci Asing (Foreign Key)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    
    # Detail Spesifik Pendaftaran
    titik_turun = db.Column(db.String(100), nullable=False)
    jenis_perjalanan = db.Column(db.String(20), default='Pulang Saja') # Pulang Saja atau Pulang Pergi
    nomor_bus = db.Column(db.String(20))
    status_pembayaran = db.Column(db.String(20), default='Belum Lunas')
    metode_pembayaran = db.Column(db.String(20)) # Isinya bisa 'Cash' atau 'Transfer'
    total_biaya = db.Column(db.Integer, nullable=False)
    tanggal_pendaftaran = db.Column(db.DateTime, server_default=db.func.now())

    # Relasi balik untuk akses mudah
    santri = db.relationship('Santri', backref=db.backref('pendaftaran', uselist=False))
    rombongan = db.relationship('Rombongan', backref='pendaftar')

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
    cakupan_wilayah = db.Column(db.JSON)

    tarifs = db.relationship('Tarif', backref='rombongan', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Rombongan {self.nama_rombongan}>'

class Tarif(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titik_turun = db.Column(db.String(100), nullable=False)
    harga_bus = db.Column(db.Integer, nullable=False)
    fee_korda = db.Column(db.Integer, default=0)
    rombongan_id = db.Column(db.Integer, db.ForeignKey('rombongan.id'), nullable=False)
    
    def __repr__(self):
        return f'<Tarif {self.titik_turun}>'

class Izin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    santri_id = db.Column(db.Integer, db.ForeignKey('santri.id'), nullable=False, unique=True)
    tanggal_berakhir = db.Column(db.Date, nullable=False)
    keterangan = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Izin untuk {self.santri.nama}>'

class Santri(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    api_student_id = db.Column(db.String(50), unique=True, nullable=False)
    nis = db.Column(db.String(30), nullable=False)
    nama = db.Column(db.String(150), nullable=False)
    kabupaten = db.Column(db.String(100))
    asrama = db.Column(db.String(50))
    no_hp_wali = db.Column(db.String(20))
    jenis_kelamin = db.Column(db.String(10), default='Putra')

    # --- PERUBAHAN DI SINI ---
    # Status utama santri
    status_santri = db.Column(db.String(20), default='Aktif') # Aktif, Izin, Wisuda, Partisipan
    izin = db.relationship('Izin', backref='santri', uselist=False, cascade="all, delete-orphan")

    
    # Kita tidak lagi menyimpan rombongan_id atau status pembayaran di sini.
    # Semua detail pendaftaran akan disimpan di tabel Pendaftaran.

    def __repr__(self):
        return f'<Santri {self.nama}>'