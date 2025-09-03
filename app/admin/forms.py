from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, StringField, TextAreaField, IntegerField, DateTimeLocalField, FieldList, FormField, SubmitField, Form, HiddenField, SelectField, PasswordField, BooleanField, DateTimeLocalField, ValidationError
from wtforms.validators import DataRequired, Optional, EqualTo, Length, URL, NumberRange
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from app.models import Rombongan, Santri, Role
from wtforms.fields import DateField
from wtforms.widgets import ListWidget, CheckboxInput
from flask_wtf.file import FileField, FileRequired, FileAllowed




# Fee Pondok adalah nilai tetap, kita definisikan di sini
FEE_PONDOK = 10000

class TarifForm(Form):
    """Sub-form untuk satu baris tarif. Tidak pakai FlaskForm."""
    titik_turun = StringField('Titik Turun', validators=[DataRequired()])
    harga_bus = IntegerField('Harga Bus', validators=[DataRequired()])
    fee_korda = IntegerField('Fee Korda', default=0, validators=[Optional()])

class RombonganForm(FlaskForm):
    nama_rombongan = StringField('Nama Rombongan', validators=[DataRequired()])
    penanggung_jawab_putra = StringField('PJ Putra', validators=[Optional()])
    kontak_person_putra = StringField('Kontak PJ Putra (WA)', validators=[Optional()])
    penanggung_jawab_putri = StringField('PJ Putri', validators=[Optional()])
    kontak_person_putri = StringField('Kontak PJ Putri (WA)', validators=[Optional()])
    nomor_rekening = StringField('Nomor Rekening', validators=[Optional()])
    cakupan_wilayah = HiddenField('Cakupan Wilayah')
    jadwal_pulang = DateTimeLocalField('Jadwal Pulang (dari Pondok)', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    batas_pembayaran_pulang = DateField('Batas Bayar Pulang', format='%Y-%m-%d', validators=[Optional()])
    jadwal_berangkat = DateTimeLocalField('Jadwal Berangkat (kembali ke Pondok)', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    batas_pembayaran_berangkat = DateField('Batas Bayar Berangkat', format='%Y-%m-%d', validators=[Optional()])
    titik_jemput_berangkat = StringField('Titik Kumpul Berangkat (di Daerah)', validators=[Optional()])
    tarifs = FieldList(FormField(TarifForm), min_entries=1, label='Detail Harga Titik Turun/Jemput')
    submit = SubmitField('Simpan Rombongan')

def rombongan_query():
    return Rombongan.query.order_by(Rombongan.nama_rombongan).all()

class SantriEditForm(FlaskForm):
    # Field untuk mendaftarkan santri ke rombongan.
    # QuerySelectField akan otomatis membuat dropdown dari data Rombongan.
    rombongan = QuerySelectField(
        'Daftarkan ke Rombongan',
        query_factory=rombongan_query,
        get_label='nama_rombongan',
        allow_blank=True,
        blank_text='-- Tidak Terdaftar di Rombongan --',
        validators=[Optional()]
    )
    
    # Dropdown untuk Status Rombongan
    status_rombongan = SelectField(
        'Status Partisipasi',
        choices=[
            ('Ikut Rombongan', 'Ikut Rombongan'),
            ('Tidak Ikut Rombongan', 'Tidak Ikut Rombongan'),
            ('Izin', 'Izin'),
            ('Partisipan', 'Partisipan'),
            ('Wisuda', 'Wisuda')
        ],
        validators=[DataRequired()]
    )
    
    # Dropdown untuk Status Pembayaran
    status_pembayaran = SelectField(
        'Status Pembayaran',
        choices=[('Belum Lunas', 'Belum Lunas'), ('Lunas', 'Lunas')],
        validators=[DataRequired()]
    )
    
    submit = SubmitField('Simpan Perubahan')

def rombongan_query():
    return Rombongan.query.order_by(Rombongan.nama_rombongan).all()

def santri_query():
    # Hanya tampilkan santri yang statusnya 'Aktif' dan belum terdaftar
    return Santri.query.filter(Santri.status_santri == 'Aktif', Santri.pendaftaran == None).order_by(Santri.nama).all()

class PendaftaranForm(FlaskForm):
    rombongan = SelectField('Pilih Rombongan', validators=[DataRequired()])
    santri_list = HiddenField('Pilih Santri (bisa lebih dari satu)', validators=[DataRequired()])
    
    # Detail Perjalanan Pulang
    status_pulang = SelectField('Status Pembayaran Pulang', choices=[('Belum Bayar', 'Belum Bayar'), ('Lunas', 'Lunas'), ('Tidak Ikut', 'Tidak Ikut')], default='Belum Bayar', validators=[DataRequired()])
    metode_pembayaran_pulang = SelectField('Metode Pembayaran (Pulang)', choices=[('', '-'), ('Cash', 'Cash'), ('Transfer', 'Transfer')], validators=[Optional()])
    titik_turun = SelectField('Pilih Titik Turun', choices=[], validators=[DataRequired()])

    # Detail Perjalanan Kembali
    status_kembali = SelectField('Status Pembayaran Kembali', choices=[('Belum Bayar', 'Belum Bayar'), ('Lunas', 'Lunas'), ('Tidak Ikut', 'Tidak Ikut')], default='Belum Bayar', validators=[DataRequired()])
    metode_pembayaran_kembali = SelectField('Metode Pembayaran (Kembali)', choices=[('', '-'), ('Cash', 'Cash'), ('Transfer', 'Transfer')], validators=[Optional()])
    
    submit = SubmitField('Daftarkan Santri')

class PendaftaranEditForm(FlaskForm):
    rombongan_pulang_nama = StringField('Rombongan Pulang', render_kw={'readonly': True})

    # Field Rombongan Kembali (bisa diubah)
    rombongan_kembali = QuerySelectField(
        'Rombongan Kembali',
        query_factory=rombongan_query, # Menggunakan query semua rombongan
        get_label='nama_rombongan',
        allow_blank=True,
        blank_text='-- Sama dengan Rombongan Pulang --'
    )
    # Field untuk Perjalanan Pulang
    status_pulang = SelectField(
        'Status Perjalanan Pulang',
        choices=[('Belum Bayar', 'Belum Bayar'), ('Lunas', 'Lunas'), ('Tidak Ikut', 'Tidak Ikut')],
        validators=[DataRequired()]
    )
    metode_pembayaran_pulang = SelectField('Metode Pembayaran (Pulang)', choices=[('', '-'), ('Cash', 'Cash'), ('Transfer', 'Transfer')], validators=[Optional()])
    titik_turun = SelectField('Titik Turun', validators=[DataRequired()])
    bus_pulang = SelectField('Bus Pulang', validators=[Optional()])
    titik_turun = SelectField('Titik Turun', validators=[DataRequired()])

    # Field untuk Perjalanan Kembali
    status_kembali = SelectField(
        'Status Perjalanan Kembali',
        choices=[('Belum Bayar', 'Belum Bayar'), ('Lunas', 'Lunas'), ('Tidak Ikut', 'Tidak Ikut')],
        validators=[DataRequired()]
    )
    titik_jemput_kembali = SelectField('Titik Jemput Kembali', choices=[], validators=[Optional()])

    metode_pembayaran_kembali = SelectField('Metode Pembayaran (Kembali)', choices=[('', '-'), ('Cash', 'Cash'), ('Transfer', 'Transfer')], validators=[Optional()])
    bus_kembali = SelectField('Bus Kembali', validators=[Optional()])
    
    submit = SubmitField('Simpan Perubahan')

def santri_aktif_query():
    return Santri.query.filter_by(status_santri='Aktif', izin=None).order_by(Santri.nama).all()

# Di dalam file app/admin/forms.py

class IzinForm(FlaskForm):
    santri = HiddenField('Pilih Santri', validators=[DataRequired()])
    
    # Field baru untuk memilih status
    status_izin = SelectField('Status Pengajuan Izin', choices=[
        ('Diterima', 'Diterima (Santri akan berstatus Izin)'), 
        ('Ditolak', 'Ditolak (Santri tetap berstatus Aktif)')
    ], validators=[DataRequired()])

    tanggal_pengajuan = DateField('Izin Diajukan Pada Tanggal', format='%Y-%m-%d', validators=[DataRequired()])
    tanggal_berakhir = DateField('Izin Diterima Sampai Tanggal (kosongi jika ditolak)', format='%Y-%m-%d', validators=[Optional()])
    
    keterangan = TextAreaField('Keterangan Keperluan', validators=[DataRequired()])
    submit = SubmitField('Simpan Izin')

class EditIzinForm(FlaskForm):
    status_izin = SelectField('Status Pengajuan Izin', choices=[
        ('Aktif', 'Diterima (Santri akan berstatus Izin)'), 
        ('Ditolak', 'Ditolak (Santri tetap berstatus Aktif)')
    ], validators=[DataRequired()])
    
    tanggal_pengajuan = DateField('Izin Diajukan Pada Tanggal', format='%Y-%m-%d', validators=[DataRequired()])
    tanggal_berakhir = DateField('Izin Diterima Sampai Tanggal (kosongi jika ditolak)', format='%Y-%m-%d', validators=[Optional()])
    keterangan = TextAreaField('Keterangan Keperluan', validators=[DataRequired()])
    submit = SubmitField('Update Izin')

def santri_bisa_jadi_partisipan_query():
    return Santri.query.filter(
        Santri.status_santri == 'Aktif', 
        Santri.izin == None, 
        Santri.partisipan == None
    ).order_by(Santri.nama).all()

class PartisipanForm(FlaskForm):
    # validate_choice=False supaya WTForms tidak memaksa nilai harus ada di choices
    santri_ids = SelectMultipleField(
        'Pilih Santri',
        coerce=int,
        choices=[],
        validate_choice=False
    )
    kategori = StringField(
        'Kategori Partisipan',
        validators=[DataRequired()],
        description="Contoh: Marching band, Kecak, Demonstrasi, dll."
    )
    submit = SubmitField('Simpan Status Partisipan')

class PartisipanEditForm(FlaskForm):
    kategori = StringField('Ubah Kategori Partisipan', validators=[DataRequired()])
    submit = SubmitField('Simpan Perubahan')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Ingat Saya')
    submit = SubmitField('Login')

def role_query():
    return Role.query.order_by(Role.name).all()

def rombongan_query():
    return Rombongan.query.order_by(Rombongan.nama_rombongan).all()

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    role = QuerySelectField('Peran (Role)', query_factory=role_query, get_label='name', allow_blank=False)
    
    # --- UBAH FIELD INI ---
    managed_rombongan_multi = QuerySelectMultipleField(
        'Rombongan yang Dikelola (Korwil)',
        query_factory=rombongan_query,
        get_label='nama_rombongan',
        widget=ListWidget(prefix_label=False),      # Gunakan list widget
        option_widget=CheckboxInput(),              # Render setiap opsi sebagai checkbox
        validators=[Optional()]
    )
    # Field BARU untuk Korda (hanya bisa pilih satu)
    managed_rombongan_single = QuerySelectField(
        'Rombongan yang Dikelola (Korda)',
        query_factory=rombongan_query,
        get_label='nama_rombongan',
        allow_blank=True,
        blank_text='-- Pilih Satu Rombongan --',
        validators=[Optional()]
    )

    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Konfirmasi Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Simpan User')

class UserEditForm(UserForm):
    password = PasswordField('Password Baru (kosongi jika tidak ingin diubah)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Konfirmasi Password Baru', validators=[EqualTo('password')])

class EdisiForm(FlaskForm):
    nama = StringField('Nama Edisi', validators=[DataRequired()], description="Contoh: Ramadhan 1448 H")
    tahun = IntegerField('Tahun Hijriah', validators=[DataRequired()], description="Contoh: 1448")
    is_active = BooleanField('Jadikan Edisi Aktif?')
    
    # --- TAMBAHKAN DUA FIELD INI ---
    countdown_title = StringField('Judul Hitung Mundur', validators=[Optional()], description="Contoh: Hitung Mundur Perpulangan")
    countdown_target_date = DateTimeLocalField('Tanggal Target Hitung Mundur', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    # -----------------------------
    
    submit = SubmitField('Simpan Edisi')

class BusForm(FlaskForm):
    nama_armada = StringField('Nama Armada (PO)', validators=[DataRequired()])
    nomor_lambung = StringField('Nomor Lambung/Bus', validators=[Optional()])
    plat_nomor = StringField('Plat Nomor', validators=[Optional()])
    kuota = IntegerField('Kuota Kursi', default=50, validators=[DataRequired()])
    keterangan = TextAreaField('Keterangan', validators=[Optional()])
    submit = SubmitField('Simpan Bus')

# Ganti KorlapdaForm dengan ini
class PetugasLapanganForm(FlaskForm):
    username = StringField('Username Petugas', validators=[DataRequired(), Length(min=4, max=25)])

    # Dropdown baru untuk memilih peran
    role = SelectField('Peran Petugas', coerce=int, validators=[DataRequired()])

    # Field bus sekarang opsional, karena Sarpras tidak terikat pada bus
    bus = SelectField('Tugaskan ke Bus (khusus Korlapda)', coerce=int, validators=[Optional()])

    # Field baru untuk Sarpras, agar terikat pada rombongan Korda
    managed_rombongan = SelectField('Tugaskan ke Rombongan (khusus Sarpras)', coerce=int, validators=[Optional()])

    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Konfirmasi Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Simpan Akun Petugas')

class LokasiBusForm(FlaskForm):
    gmaps_share_url = StringField('URL Google Maps Share Location', validators=[DataRequired(), URL()])
    submit = SubmitField('Update Lokasi Bus')

class HubungkanPerangkatForm(FlaskForm):
    traccar_device_id = StringField(
        'ID Perangkat Traccar',
        validators=[DataRequired(message="ID Perangkat tidak boleh kosong.")],
        description="Masukkan ID unik dari aplikasi Traccar Client di HP Anda."
    )
    submit = SubmitField('Hubungkan & Mulai Pelacakan')

class WisudaForm(FlaskForm):
    """Form untuk menambahkan wisudawan satu per satu."""
    santri = HiddenField('Santri', validators=[DataRequired()])
    kategori_wisuda = StringField('Kategori Wisuda', 
                                  validators=[DataRequired()], 
                                  description="Contoh: Wisuda Amtsilati, Wisuda Al-Qur'an")
    submit = SubmitField('Simpan Status Wisuda')

class ImportWisudaForm(FlaskForm):
    """Form untuk impor data wisudawan dari file Excel."""
    file = FileField('Pilih File Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Hanya file .xlsx yang diizinkan!')
    ])
    kategori_wisuda = StringField('Kategori Wisuda untuk Semua Data', 
                                  validators=[DataRequired()],
                                  description="Kategori ini akan diterapkan ke semua santri di dalam file.")
    submit = SubmitField('Impor Data')

class TransaksiForm(FlaskForm):
    deskripsi = StringField('Deskripsi Pengeluaran', validators=[DataRequired()])
    jumlah = IntegerField('Jumlah (Rp)', validators=[DataRequired()])
    submit = SubmitField('Catat Pengeluaran')

class PengeluaranBusForm(FlaskForm):
    deskripsi = StringField('Deskripsi Pengeluaran', validators=[DataRequired()])
    jumlah = IntegerField('Jumlah (Rp)', validators=[DataRequired()])
    # Dropdown untuk memilih sumber dana bus
    rekening = SelectField('Ambil Dana dari Rekening', choices=[
        ('REKENING_BUS_PULANG', 'Rekening Bus Pulang'),
        ('REKENING_BUS_KEMBALI', 'Rekening Bus Kembali')
    ], validators=[DataRequired()])
    submit = SubmitField('Catat Pengeluaran Bus')

class KonfirmasiSetoranForm(FlaskForm):
    jumlah_disetor = IntegerField('Nominal yang Disetor', 
                                  validators=[DataRequired(), NumberRange(min=1, message="Jumlah harus lebih dari 0")])
    submit = SubmitField('Konfirmasi')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Password Saat Ini', validators=[DataRequired()])
    new_password = PasswordField('Password Baru', validators=[
        DataRequired(),
        Length(min=6, message='Password minimal harus 6 karakter.')
    ])
    confirm_password = PasswordField('Konfirmasi Password Baru', validators=[
        DataRequired(),
        EqualTo('new_password', message='Konfirmasi password tidak cocok dengan password baru.')
    ])
    submit = SubmitField('Ganti Password')

# Di dalam file app/admin/forms.py

class SantriManualForm(FlaskForm):
    nama = StringField(
        'Nama Lengkap Santri', 
        validators=[
            DataRequired(message='Nama harus diisi'),
            Length(min=2, max=100, message='Nama harus 2-100 karakter')
        ]
    )
    
    # SelectField dengan validasi yang lebih fleksibel untuk dynamic choices
    provinsi = StringField(  # Ganti ke StringField untuk menghindari validasi choices
        'Provinsi', 
        validators=[DataRequired(message='Provinsi harus dipilih')]
    )
    
    kabupaten = StringField(  # Ganti ke StringField untuk menghindari validasi choices
        'Kabupaten/Kota', 
        validators=[DataRequired(message='Kabupaten harus dipilih')]
    )
    
    jenis_kelamin = SelectField(
        'Jenis Kelamin', 
        choices=[('', '-- Pilih Jenis Kelamin --'), ('PUTRA', 'Putra'), ('PUTRI', 'Putri')],
        validators=[DataRequired(message='Jenis kelamin harus dipilih')]
    )
    
    status_santri = SelectField(
        'Status Santri', 
        choices=[
            ('', '-- Pilih Status --'),
            ('Aktif', 'Aktif'), 
            ('Izin', 'Izin'), 
            ('Partisipan', 'Partisipan'), 
            ('Wisuda', 'Wisuda')
        ],
        default='Aktif',
        validators=[DataRequired(message='Status santri harus dipilih')]
    )
    
    asrama = StringField(
        'Asrama', 
        validators=[
            Optional(),
            Length(max=50, message='Nama asrama maksimal 50 karakter')
        ]
    )
    
    no_hp_wali = StringField(
        'No. HP Wali', 
        validators=[
            Optional(),
            Length(min=10, max=15, message='Nomor HP harus 10-15 karakter')
        ]
    )
    
    kelas_formal = StringField(
        'Kelas Formal', 
        validators=[
            Optional(),
            Length(max=20, message='Kelas formal maksimal 20 karakter')
        ]
    )
    
    kelas_ngaji = StringField(
        'Kelas Ngaji', 
        validators=[
            Optional(),
            Length(max=20, message='Kelas ngaji maksimal 20 karakter')
        ]
    )
    
    submit = SubmitField('Simpan Data Santri')
    
    def validate_no_hp_wali(self, field):
        """Custom validation untuk nomor HP"""
        if field.data:
            import re
            if not re.match(r'^[0-9+\-\s]+$', field.data):
                raise ValidationError('Nomor HP hanya boleh mengandung angka, +, -, dan spasi')
    
    def validate_provinsi(self, field):
        """Custom validation untuk provinsi - bisa ditambahkan validasi tambahan jika diperlukan"""
        if field.data and field.data.strip() == '':
            raise ValidationError('Provinsi harus dipilih')
    
    def validate_kabupaten(self, field):
        """Custom validation untuk kabupaten - bisa ditambahkan validasi tambahan jika diperlukan"""
        if field.data and field.data.strip() == '':
            raise ValidationError('Kabupaten harus dipilih')
    
    def validate(self, extra_validators=None):
        """Custom validation tambahan"""
        if not super().validate(extra_validators):
            return False
            
        # Validasi nama tidak boleh hanya spasi
        if self.nama.data and not self.nama.data.strip():
            self.nama.errors.append('Nama tidak boleh kosong')
            return False
        
        # Validasi provinsi tidak boleh placeholder
        if self.provinsi.data in ['-- Pilih Provinsi --', '']:
            self.provinsi.errors.append('Provinsi harus dipilih')
            return False
            
        # Validasi kabupaten tidak boleh placeholder
        if self.kabupaten.data in ['-- Pilih Kabupaten/Kota --', '-- Pilih Provinsi Dulu --', '']:
            self.kabupaten.errors.append('Kabupaten harus dipilih')
            return False
            
        return True


class BarangForm(FlaskForm):
    jumlah_koli = IntegerField('Jumlah Koli/Barang', validators=[DataRequired()])
    foto_barang = FileField('Foto Barang', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Hanya gambar (JPG, PNG) yang diizinkan!')
    ])
    submit = SubmitField('Simpan Data Barang')

class ImportPartisipanForm(FlaskForm):
    """Form untuk impor data partisipan dari file Excel."""
    file = FileField('Pilih File Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Hanya file .xlsx yang diizinkan!')
    ])
    kategori = StringField('Kategori Partisipan untuk Semua Data', 
                                  validators=[DataRequired()],
                                  description="Kategori ini akan diterapkan ke semua santri di dalam file.")
    submit = SubmitField('Impor Data Partisipan')


