from app import db
from app.models import Role, User

def seed_data():
    """Fungsi untuk membuat data awal (roles dan user admin)."""
    
    # Cek apakah role sudah ada, jika belum maka buat semua
    if not Role.query.first():
        print("Membuat roles...")
        role_korpus = Role(name='Korpus')
        role_korwil = Role(name='Korwil')
        role_korda = Role(name='Korda')
        role_keamanan = Role(name='Keamanan')
        role_pj_acara = Role(name='PJ Acara')
        db.session.add_all([role_korpus, role_korwil, role_korda, role_keamanan, role_pj_acara])
        db.session.commit()
        print("-> Semua role berhasil dibuat.")
    else:
        print("Roles sudah ada.")

    # Cek apakah user 'korpus' sudah ada, jika belum maka buat
    if not User.query.filter_by(username='korpus').first():
        print("Membuat user admin 'korpus'...")
        role_korpus = Role.query.filter_by(name='Korpus').first()
        
        admin_user = User(username='korpus', role=role_korpus)
        admin_user.set_password('mabar') # Ganti dengan password yang Anda inginkan
        
        db.session.add(admin_user)
        db.session.commit()
        print("-> User 'korpus' berhasil dibuat.")
    else:
        print("User 'korpus' sudah ada.")