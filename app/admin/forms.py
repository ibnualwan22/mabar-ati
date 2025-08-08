from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, DateTimeLocalField, FieldList, FormField, SubmitField, Form, HiddenField, SelectField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Optional, EqualTo, Length
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from app.models import Rombongan, Santri, Role
from wtforms.fields import DateField
from wtforms.widgets import ListWidget, CheckboxInput




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
    santri = HiddenField('Pilih Santri', validators=[DataRequired()])
    
    # Detail Perjalanan Pulang
    status_pulang = SelectField('Status Pembayaran Pulang', choices=[('Belum Bayar', 'Belum Bayar'), ('Lunas', 'Lunas'), ('Tidak Ikut', 'Tidak Ikut')], default='Belum Bayar', validators=[DataRequired()])
    metode_pembayaran_pulang = SelectField('Metode Pembayaran (Pulang)', choices=[('', '-'), ('Cash', 'Cash'), ('Transfer', 'Transfer')], validators=[Optional()])
    bus_pulang = SelectField('Bus Pulang', validators=[Optional()])
    titik_turun = SelectField('Pilih Titik Turun', choices=[], validators=[DataRequired()])

    # Detail Perjalanan Kembali
    status_kembali = SelectField('Status Pembayaran Kembali', choices=[('Belum Bayar', 'Belum Bayar'), ('Lunas', 'Lunas'), ('Tidak Ikut', 'Tidak Ikut')], default='Belum Bayar', validators=[DataRequired()])
    metode_pembayaran_kembali = SelectField('Metode Pembayaran (Kembali)', choices=[('', '-'), ('Cash', 'Cash'), ('Transfer', 'Transfer')], validators=[Optional()])
    bus_kembali = SelectField('Bus Kembali', validators=[Optional()])
    
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

class IzinForm(FlaskForm):
    santri = HiddenField('Pilih Santri', validators=[DataRequired()])
    tanggal_berakhir = DateField('Izin Sampai Tanggal', format='%Y-%m-%d', validators=[DataRequired()])
    keterangan = TextAreaField('Keterangan Keperluan', validators=[DataRequired()])
    submit = SubmitField('Simpan Izin')

def santri_bisa_jadi_partisipan_query():
    return Santri.query.filter(
        Santri.status_santri == 'Aktif', 
        Santri.izin == None, 
        Santri.partisipan == None
    ).order_by(Santri.nama).all()

class PartisipanForm(FlaskForm):
    santri = HiddenField('Pilih Santri', validators=[DataRequired()])
    kategori = StringField('Kategori Partisipan', validators=[DataRequired()], description="Contoh: Panitia, Peserta Lomba, Khotmil Qur'an")
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
    submit = SubmitField('Simpan Edisi')

class BusForm(FlaskForm):
    nama_armada = StringField('Nama Armada (PO)', validators=[DataRequired()])
    nomor_lambung = StringField('Nomor Lambung/Bus', validators=[Optional()])
    plat_nomor = StringField('Plat Nomor', validators=[Optional()])
    kuota = IntegerField('Kuota Kursi', default=50, validators=[DataRequired()])
    keterangan = TextAreaField('Keterangan', validators=[Optional()])
    submit = SubmitField('Simpan Bus')

class KorlapdaForm(FlaskForm):
    username = StringField('Username Korlapda', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Konfirmasi Password', validators=[DataRequired(), EqualTo('password')])
    
    # Dropdown untuk memilih bus, pilihannya akan kita isi secara dinamis di route
    bus = SelectField('Tugaskan ke Bus', validators=[DataRequired()])

    submit = SubmitField('Simpan User Korlapda')


