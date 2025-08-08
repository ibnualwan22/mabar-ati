from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from collections import defaultdict
from sqlalchemy.orm import joinedload

from . import lapangan_bp
from app import db
from app.models import User, Bus, Pendaftaran, Absen, Role, Rombongan
from app.admin.forms import LoginForm
from app.admin.routes import get_active_edisi

@lapangan_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.role.name == 'Korlapda':
        return redirect(url_for('lapangan.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.role.name == 'Korlapda':
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('lapangan.dashboard'))
        else:
            flash('Username atau password salah, atau Anda bukan Korlapda.', 'danger')
            
    return render_template('login_lapangan.html', form=form)

@lapangan_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('lapangan.login'))

@lapangan_bp.route('/')
@login_required
def dashboard():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)

    bus = Bus.query.get_or_404(current_user.bus_id)
    active_edisi = get_active_edisi()
    
    peserta_pulang = []
    peserta_kembali = []
    grouped_pulang = defaultdict(list)
    grouped_kembali = defaultdict(list)
    absen_map = {}
    checkpoints_pulang = []
    checkpoints_kembali = []

    if active_edisi and bus.rombongan.edisi_id == active_edisi.id:
        peserta_pulang = Pendaftaran.query.options(joinedload(Pendaftaran.santri)).filter_by(bus_pulang_id=bus.id).all()
        peserta_kembali = Pendaftaran.query.options(joinedload(Pendaftaran.santri)).filter_by(bus_kembali_id=bus.id).all()

        for p in peserta_pulang:
            grouped_pulang[p.titik_turun].append(p)
            
        for p in peserta_kembali:
            grouped_kembali[p.santri.kabupaten].append(p)

        pendaftar_ids = [p.id for p in peserta_pulang] + [p.id for p in peserta_kembali]
        absen_tercatat = Absen.query.filter(Absen.pendaftaran_id.in_(pendaftar_ids)).all()
        absen_map = {f"{absen.pendaftaran_id}-{absen.nama_absen}": absen.status for absen in absen_tercatat}
        
        checkpoints_pulang = [c[0] for c in db.session.query(Absen.nama_absen).filter(Absen.pendaftaran_id.in_(pendaftar_ids), Absen.nama_absen.like('%(Pulang)%')).distinct().all()]
        checkpoints_kembali = [c[0] for c in db.session.query(Absen.nama_absen).filter(Absen.pendaftaran_id.in_(pendaftar_ids), Absen.nama_absen.like('%(Kembali)%')).distinct().all()]
    else:
        flash("Saat ini tidak ada edisi perpulangan yang aktif untuk bus Anda.", "info")

    return render_template('dashboard_lapangan.html',
                           bus=bus,
                           grouped_pulang=grouped_pulang,
                           grouped_kembali=grouped_kembali,
                           absen_map=absen_map,
                           checkpoints_pulang=checkpoints_pulang,
                           checkpoints_kembali=checkpoints_kembali)

@lapangan_bp.route('/tambah-checkpoint', methods=['POST'])
@login_required
def tambah_checkpoint_absen():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)
    
    nama_absen_baru = request.form.get('nama_absen_baru')
    arah = request.form.get('arah_perjalanan')
    
    if not nama_absen_baru or not arah:
        flash("Nama checkpoint tidak boleh kosong.", "danger")
        return redirect(url_for('lapangan.dashboard'))

    pendaftar_ids = []
    if arah == 'Pulang':
        pendaftar_ids = [p.id for p in Pendaftaran.query.filter_by(bus_pulang_id=current_user.bus_id).all()]
    else: # Kembali
        pendaftar_ids = [p.id for p in Pendaftaran.query.filter_by(bus_kembali_id=current_user.bus_id).all()]

    nama_absen_final = f"{nama_absen_baru} ({arah})"

    for p_id in pendaftar_ids:
        new_absen = Absen(
            pendaftaran_id=p_id,
            nama_absen=nama_absen_final,
            status="Tidak Hadir",
            dicatat_oleh_id=current_user.id
        )
        db.session.add(new_absen)
    
    db.session.commit()
    flash(f'Checkpoint absen "{nama_absen_baru}" berhasil dibuat.', 'success')
    return redirect(url_for('lapangan.dashboard'))

@lapangan_bp.route('/simpan-absen', methods=['POST'])
@login_required
def simpan_absen():
    if current_user.role.name != 'Korlapda' or not current_user.bus_id:
        abort(403)

    form_data = request.form.to_dict(flat=False)
    
    for key, pendaftar_ids_hadir in form_data.items():
        if key.startswith('hadir-'):
            nama_absen = key.replace('hadir-', '')
            
            manifest_ids = []
            if 'Pulang' in nama_absen:
                 manifest_ids = [p.id for p in Pendaftaran.query.filter_by(bus_pulang_id=current_user.bus_id).all()]
            else: # Kembali
                 manifest_ids = [p.id for p in Pendaftaran.query.filter_by(bus_kembali_id=current_user.bus_id).all()]

            for p_id in manifest_ids:
                Absen.query.filter_by(pendaftaran_id=p_id, nama_absen=nama_absen).delete()
                status = "Hadir" if str(p_id) in pendaftar_ids_hadir else "Tidak Hadir"
                new_absen = Absen(pendaftaran_id=p_id, nama_absen=nama_absen, status=status, dicatat_oleh_id=current_user.id)
                db.session.add(new_absen)
    
    db.session.commit()
    flash('Data absensi berhasil disimpan.', 'success')
    return redirect(url_for('lapangan.dashboard'))