from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, DateTimeLocalField, FieldList, FormField, SubmitField, Form, HiddenField
from wtforms.validators import DataRequired, Optional
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms import SelectField
from app.models import Rombongan


# Fee Pondok adalah nilai tetap, kita definisikan di sini
FEE_PONDOK = 10000

class TarifForm(Form):
    """Sub-form untuk satu baris tarif. Tidak pakai FlaskForm."""
    titik_turun = StringField('Titik Turun', validators=[DataRequired()])
    harga_bus = IntegerField('Harga Bus', validators=[DataRequired()])
    fee_korda = IntegerField('Fee Korda', default=0, validators=[Optional()])

class RombonganForm(FlaskForm):
    """Form utama untuk menambah/edit rombongan."""
    nama_rombongan = StringField('Nama Rombongan', validators=[DataRequired()])
    penanggung_jawab = StringField('Penanggung Jawab', validators=[DataRequired()])
    kontak_person = StringField('Kontak Person (WA)', validators=[DataRequired()])
    nomor_rekening = StringField('Nomor Rekening', validators=[DataRequired()])
    jadwal_keberangkatan = DateTimeLocalField(
        'Jadwal Keberangkatan', 
        format='%Y-%m-%dT%H:%M', 
        validators=[DataRequired()]
    )
    titik_kumpul = StringField('Titik Kumpul', validators=[DataRequired()])
    nama_armada = StringField('Nama Armada', validators=[Optional()])
    keterangan_armada = TextAreaField('Keterangan Armada', validators=[Optional()])
    cakupan_wilayah = HiddenField('Cakupan Wilayah')


    # Bagian dinamis untuk tarif
    tarifs = FieldList(
        FormField(TarifForm),
        min_entries=1,
        label='Tarif Berdasarkan Titik Turun'
    )

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