from app import db
from app.models import Role, User

def seed_data():
    """Fungsi untuk membuat data awal (roles dan user admin)."""
    
    # Daftar semua peran yang seharusnya ada di sistem
    required_roles = [
        'Korpus', 'Korwil', 'Korda', 'Keamanan', 
        'PJ Acara', 'Korlapda', 'Bendahara Pusat', 'Sekretaris', 'Korpuspi'
    ]
    
    # Ambil semua nama peran yang sudah ada di database
    existing_roles = {role.name for role in Role.query.all()}
    
    # Loop melalui peran yang dibutuhkan dan tambahkan jika belum ada
    new_roles_added = False
    for role_name in required_roles:
        if role_name not in existing_roles:
            print(f"Membuat role baru: {role_name}...")
            new_role = Role(name=role_name)
            db.session.add(new_role)
            new_roles_added = True

    if new_roles_added:
        db.session.commit()
        print("-> Role baru berhasil ditambahkan.")
    else:
        print("Semua role yang dibutuhkan sudah ada.")

    # Cek apakah user 'korpus' sudah ada (logika ini tetap sama)
    if not User.query.filter_by(username='korpus').first():
        print("Membuat user admin 'korpus'...")
        role_korpus = Role.query.filter_by(name='Korpus').first()
        
        if role_korpus:
            admin_user = User(username='korpus', role=role_korpus)
            admin_user.set_password('mabar') # Ganti dengan password yang Anda inginkan
            
            db.session.add(admin_user)
            db.session.commit()
            print("-> User 'korpus' berhasil dibuat.")
        else:
            print("-> GAGAL: Role 'Korpus' tidak ditemukan untuk membuat user admin.")
    else:
        print("User 'korpus' sudah ada.")