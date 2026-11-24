"""Authentication routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import re
from ..models import authenticate_user, get_db, User

bp = Blueprint('auth', __name__)

@bp.route('/')
def index():
    return redirect(url_for('auth.login_anggota'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = authenticate_user(username, password)
        if user:
            login_user(user)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Username atau password salah', 'error')
    
    return render_template('login.html')

@bp.route('/login-anggota', methods=['GET', 'POST'])
def login_anggota():
    if request.method == 'POST':
        nik = request.form.get('nik')
        password = request.form.get('password')
        
        if not nik:
            flash('NIK wajib diisi', 'error')
            return render_template('login-anggota.html')
        
        db = get_db()
        anggota = db.execute('SELECT * FROM anggota WHERE nik = ?', (nik,)).fetchone()
        if anggota and anggota['user_id']:
            user = db.execute('SELECT * FROM users WHERE id = ?', (anggota['user_id'],)).fetchone()
            if user and check_password_hash(user['password'], password):
                user_obj = User(user['id'], user['username'], user['role'], anggota['id'])
                login_user(user_obj)
                return redirect(url_for('dashboard.index'))
        
        flash('NIK atau password salah', 'error')
    
    return render_template('login-anggota.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    """Halaman profil bersama untuk admin dan anggota."""
    db = get_db()
    user = db.execute('SELECT id, username, role, created_at FROM users WHERE id = ?', (current_user.id,)).fetchone()
    anggota = db.execute('SELECT * FROM anggota WHERE user_id = ?', (current_user.id,)).fetchone()

    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not old_password or not new_password or not confirm_password:
            flash('Semua field password wajib diisi', 'error')
        elif not check_password_hash(db.execute('SELECT password FROM users WHERE id = ?', (current_user.id,)).fetchone()['password'], old_password):
            flash('Kata sandi lama salah', 'error')
        elif len(new_password) < 6:
            flash('Kata sandi minimal 6 karakter', 'error')
        elif new_password != confirm_password:
            flash('Kata sandi baru dan konfirmasi tidak cocok', 'error')
        else:
            db.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(new_password), current_user.id))
            db.commit()
            flash('Kata sandi berhasil diubah', 'success')
            return redirect(url_for('auth.profil'))

    anggota_list = []
    if current_user.role == 'admin':
        anggota_list = db.execute('''
            SELECT a.id, a.nama, a.no_anggota, a.nik, a.status, u.username
            FROM anggota a LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.nama COLLATE NOCASE
        ''').fetchall()
    return render_template('profil.html', user=user, anggota=anggota, anggota_list=anggota_list)

@bp.route('/admin/ubah-password/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_ubah_password(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
    if not user:
        flash('User tidak ditemukan', 'error')
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password or not confirm_password:
            flash('Semua field wajib diisi', 'error')
            return render_template('admin/ubah_password.html', user=user)
        if new_password != confirm_password:
            flash('Kata sandi baru dan konfirmasi tidak cocok', 'error')
            return render_template('admin/ubah_password.html', user=user)
        if len(new_password) < 6:
            flash('Kata sandi minimal 6 karakter', 'error')
            return render_template('admin/ubah_password.html', user=user)
        db.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(new_password), id))
        db.commit()
        flash('Password berhasil direset', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('admin/ubah_password.html', user=user)

@bp.route('/admin/reset-password-anggota/<int:id>', methods=['POST'])
@login_required
def admin_reset_password_anggota(id):
    """Reset password akun anggota ke default operasional 123456."""
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    db = get_db()
    anggota = db.execute('SELECT id, nama, user_id FROM anggota WHERE id = ?', (id,)).fetchone()
    if not anggota or not anggota['user_id']:
        flash('Akun anggota tidak ditemukan', 'error')
        return redirect(url_for('auth.profil'))
    db.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash('123456'), anggota['user_id']))
    db.commit()
    flash(f'Password {anggota["nama"]} direset ke 123456', 'success')
    return redirect(url_for('auth.profil'))


@bp.route('/pengaturan/simpanan', methods=['GET', 'POST'])
@login_required
def pengaturan_simpanan():
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    db = get_db()
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()[:80]
        if len(nama) < 2:
            flash('Nama jenis simpanan wajib diisi', 'error')
            return redirect(url_for('auth.pengaturan_simpanan'))
        duplicate = db.execute('SELECT id FROM jenis_simpanan WHERE lower(nama) = lower(?)', (nama,)).fetchone()
        if duplicate:
            flash('Jenis simpanan tersebut sudah ada', 'error')
            return redirect(url_for('auth.pengaturan_simpanan'))
        base = re.sub(r'[^a-z0-9]+', '_', nama.lower()).strip('_') or 'simpanan'
        kode = base
        suffix = 2
        while db.execute('SELECT 1 FROM jenis_simpanan WHERE kode = ?', (kode,)).fetchone():
            kode = f'{base}_{suffix}'
            suffix += 1
        next_order = db.execute('SELECT COALESCE(MAX(urutan), 0) + 10 AS value FROM jenis_simpanan').fetchone()['value']
        db.execute('INSERT INTO jenis_simpanan (kode, nama, aktif, urutan) VALUES (?, ?, 1, ?)', (kode, nama, next_order))
        db.commit()
        flash('Jenis simpanan berhasil ditambahkan', 'success')
        return redirect(url_for('auth.pengaturan_simpanan'))
    jenis_simpanan = db.execute('SELECT * FROM jenis_simpanan ORDER BY urutan, id').fetchall()
    return render_template('admin/jenis-simpanan.html', jenis_simpanan=jenis_simpanan)

@bp.route('/pengaturan/simpanan/<int:id>/ubah', methods=['POST'])
@login_required
def ubah_jenis_simpanan(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    nama = request.form.get('nama', '').strip()[:80]
    db = get_db()
    item = db.execute('SELECT * FROM jenis_simpanan WHERE id = ?', (id,)).fetchone()
    if not item:
        flash('Jenis simpanan tidak ditemukan', 'error')
    elif len(nama) < 2:
        flash('Nama jenis simpanan wajib diisi', 'error')
    elif db.execute('SELECT id FROM jenis_simpanan WHERE lower(nama) = lower(?) AND id != ?', (nama, id)).fetchone():
        flash('Nama jenis simpanan tersebut sudah dipakai', 'error')
    else:
        db.execute('UPDATE jenis_simpanan SET nama = ? WHERE id = ?', (nama, id))
        db.commit()
        flash('Jenis simpanan berhasil diubah', 'success')
    return redirect(url_for('auth.pengaturan_simpanan'))

@bp.route('/pengaturan/simpanan/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_jenis_simpanan(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    db = get_db()
    item = db.execute('SELECT * FROM jenis_simpanan WHERE id = ?', (id,)).fetchone()
    if not item:
        flash('Jenis simpanan tidak ditemukan', 'error')
    elif item['aktif'] and db.execute('SELECT COUNT(*) AS total FROM jenis_simpanan WHERE aktif = 1').fetchone()['total'] <= 1:
        flash('Minimal satu jenis simpanan harus tetap aktif', 'error')
    else:
        db.execute('UPDATE jenis_simpanan SET aktif = ? WHERE id = ?', (0 if item['aktif'] else 1, id))
        db.commit()
        flash('Status jenis simpanan berhasil diubah', 'success')
    return redirect(url_for('auth.pengaturan_simpanan'))


@bp.route('/pengaturan/pinjaman', methods=['GET', 'POST'])
@login_required
def pengaturan_pinjaman():
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    db = get_db()
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()[:80]
        if len(nama) < 2:
            flash('Nama jenis pinjaman wajib diisi', 'error')
            return redirect(url_for('auth.pengaturan_pinjaman'))
        duplicate = db.execute('SELECT id FROM jenis_pinjaman WHERE lower(nama) = lower(?)', (nama,)).fetchone()
        if duplicate:
            flash('Jenis pinjaman tersebut sudah ada', 'error')
            return redirect(url_for('auth.pengaturan_pinjaman'))
        base = re.sub(r'[^a-z0-9]+', '_', nama.lower()).strip('_') or 'pinjaman'
        kode = base
        suffix = 2
        while db.execute('SELECT 1 FROM jenis_pinjaman WHERE kode = ?', (kode,)).fetchone():
            kode = f'{base}_{suffix}'
            suffix += 1
        next_order = db.execute('SELECT COALESCE(MAX(urutan), 0) + 10 AS value FROM jenis_pinjaman').fetchone()['value']
        db.execute('INSERT INTO jenis_pinjaman (kode, nama, aktif, urutan) VALUES (?, ?, 1, ?)', (kode, nama, next_order))
        db.commit()
        flash('Jenis pinjaman berhasil ditambahkan', 'success')
        return redirect(url_for('auth.pengaturan_pinjaman'))
    jenis_pinjaman = db.execute('SELECT * FROM jenis_pinjaman ORDER BY urutan, id').fetchall()
    return render_template('admin/jenis-pinjaman.html', jenis_pinjaman=jenis_pinjaman)

@bp.route('/pengaturan/pinjaman/<int:id>/ubah', methods=['POST'])
@login_required
def ubah_jenis_pinjaman(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    nama = request.form.get('nama', '').strip()[:80]
    db = get_db()
    item = db.execute('SELECT * FROM jenis_pinjaman WHERE id = ?', (id,)).fetchone()
    if not item:
        flash('Jenis pinjaman tidak ditemukan', 'error')
    elif len(nama) < 2:
        flash('Nama jenis pinjaman wajib diisi', 'error')
    elif db.execute('SELECT id FROM jenis_pinjaman WHERE lower(nama) = lower(?) AND id != ?', (nama, id)).fetchone():
        flash('Nama jenis pinjaman tersebut sudah dipakai', 'error')
    else:
        db.execute('UPDATE jenis_pinjaman SET nama = ? WHERE id = ?', (nama, id))
        db.commit()
        flash('Jenis pinjaman berhasil diubah', 'success')
    return redirect(url_for('auth.pengaturan_pinjaman'))

@bp.route('/pengaturan/pinjaman/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_jenis_pinjaman(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    db = get_db()
    item = db.execute('SELECT * FROM jenis_pinjaman WHERE id = ?', (id,)).fetchone()
    if not item:
        flash('Jenis pinjaman tidak ditemukan', 'error')
    elif item['aktif'] and db.execute('SELECT COUNT(*) AS total FROM jenis_pinjaman WHERE aktif = 1').fetchone()['total'] <= 1:
        flash('Minimal satu jenis pinjaman harus tetap aktif', 'error')
    else:
        db.execute('UPDATE jenis_pinjaman SET aktif = ? WHERE id = ?', (0 if item['aktif'] else 1, id))
        db.commit()
        flash('Status jenis pinjaman berhasil diubah', 'success')
    return redirect(url_for('auth.pengaturan_pinjaman'))


@bp.route('/profil-koperasi')
@login_required
def profil_koperasi():
    if current_user.role != 'admin':
        flash('Profil Koperasi hanya dapat diakses admin', 'error')
        return redirect(url_for('dashboard.index'))
    from ..models import get_koperasi_profile
    return render_template('profil-koperasi.html', koperasi=get_koperasi_profile())

@bp.route('/pengaturan/koperasi', methods=['GET', 'POST'])
@login_required
def pengaturan_koperasi():
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('auth.profil_koperasi'))
    from ..models import get_koperasi_profile
    db = get_db()
    if request.method == 'POST':
        nama = request.form.get('nama_koperasi', '').strip()
        if len(nama) < 2 or len(nama) > 120:
            flash('Nama koperasi wajib diisi dan maksimal 120 karakter', 'error')
            return render_template('admin/profil-koperasi.html', koperasi=get_koperasi_profile())
        fields = {
            'nama_koperasi': nama,
            'tagline_koperasi': request.form.get('tagline_koperasi', '').strip()[:160],
            'alamat_koperasi': request.form.get('alamat_koperasi', '').strip()[:240],
            'kota_koperasi': request.form.get('kota_koperasi', '').strip()[:120],
            'telepon_koperasi': request.form.get('telepon_koperasi', '').strip()[:40],
            'email_koperasi': request.form.get('email_koperasi', '').strip()[:120],
            'website_koperasi': request.form.get('website_koperasi', '').strip()[:200],
        }
        upload = request.files.get('logo_koperasi')
        if upload and upload.filename:
            allowed = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
            extension = upload.filename.rsplit('.', 1)[-1].lower() if '.' in upload.filename else ''
            if extension not in allowed:
                flash('Logo harus berupa PNG, JPG, WEBP, atau SVG', 'error')
                return render_template('admin/profil-koperasi.html', koperasi=get_koperasi_profile())
            if not secure_filename(upload.filename):
                flash('Nama file logo tidak valid', 'error')
                return render_template('admin/profil-koperasi.html', koperasi=get_koperasi_profile())
            upload_dir = os.path.join(current_app.static_folder, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            stored_name = f"koperasi-logo-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.{extension}"
            upload.save(os.path.join(upload_dir, stored_name))
            fields['logo_koperasi'] = f'uploads/{stored_name}'
        for key, value in fields.items():
            db.execute("""INSERT INTO pengaturan (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, value))
        db.commit()
        flash('Profil koperasi berhasil disimpan', 'success')
        return redirect(url_for('auth.profil_koperasi'))
    return render_template('admin/profil-koperasi.html', koperasi=get_koperasi_profile())