import os
import click # <-- Tambahkan import ini di bagian atas
from app import create_app
from seed import seed_data # <-- 1. Import fungsi seed_data
from app.models import Pendaftaran, Izin, Wisuda, Santri, Absen, Partisipan
from app import db


# Ambil nama config dari environment variable 'FLASK_ENV'.
# Jika tidak ada, default ke 'development'.
config_name = os.getenv('FLASK_ENV', 'development')

app = create_app(config_name)
app.config['SQLALCHEMY_ECHO'] = True


@app.cli.command("seed")
def seed():
    """Membuat data awal untuk database."""
    seed_data()

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])

@app.cli.command("clear-santri")
def clear_santri():
    """Menghapus semua data santri dan data terkait (Pendaftaran, Izin, Wisuda)."""
    if click.confirm('PERINGATAN: Anda akan menghapus SEMUA data santri, pendaftaran, izin, dan wisuda secara permanen. Lanjutkan?'):
        try:
            # Hapus data dari tabel anak terlebih dahulu untuk menghindari error foreign key
            print("Menghapus data Absen...")
            db.session.query(Absen).delete()

            print("Menghapus data Pendaftaran...")
            db.session.query(Pendaftaran).delete()
            
            print("Menghapus data Izin...")
            db.session.query(Izin).delete()

            print("Menghapus data Wisuda...")
            db.session.query(Wisuda).delete()

            print("Menghapus data Partisipan...")
            db.session.query(Partisipan).delete()
            
            # Setelah semua data terkait dihapus, baru hapus data santri
            print("Menghapus data Santri...")
            num_rows_deleted = db.session.query(Santri).delete()
            
            db.session.commit()
            
            print("-" * 30)
            print(f"BERHASIL! Sebanyak {num_rows_deleted} baris data santri dan semua data terkait telah dihapus.")
            print("-" * 30)

        except Exception as e:
            db.session.rollback()
            print(f"Error: Proses gagal dan semua perubahan dibatalkan. Detail: {e}")