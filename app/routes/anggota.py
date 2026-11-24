"""Anggota management routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ..models import get_db

bp = Blueprint('anggota', __name__, url_prefix='/anggota')

def _is_superadmin():
    return current_user.is_authenticated and current_user.username == 'superadmin'

@bp.route('/')
@login_required
def index():
    # Blok anggota dari daftar anggota: anggota hanya melihat profil sendiri
    if current_user.role != 'admin':
        flash('Anda hanya dapat melihat profil Anda sendiri', 'error')
        if current_user.anggota_id:
            return redirect(url_for('anggota.detail', id=current_user.anggota_id))
        return redirect(url_for('dashboard.index'))

    db = get_db()
    scope = '' if current_user.role == 'admin' else ' WHERE id = ?'
    params = () if current_user.role == 'admin' else (current_user.anggota_id,)
    anggota = db.execute('SELECT * FROM anggota' + scope + ' ORDER BY tanggal_bergabung DESC', params).fetchall()
    stats = db.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'aktif' THEN 1 ELSE 0 END) AS aktif,
               SUM(CASE WHEN status != 'aktif' THEN 1 ELSE 0 END) AS non_aktif
        FROM anggota
    """ + ('' if current_user.role == 'admin' else ' WHERE id = ?'), params).fetchone()
    return render_template('anggota/index.html', anggota=anggota, stats=stats)

@bp.route('/tambah', methods=['GET', 'POST'])
@login_required
def tambah():
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('anggota.index'))
    
    if request.method == 'POST':
        db = get_db()
        
        last = db.execute('SELECT no_anggota FROM anggota ORDER BY id DESC LIMIT 1').fetchone()
        if last:
            last_num = int(last['no_anggota'].split('-')[1])
            no_anggota = f'ANG-{last_num + 1:05d}'
        else:
            no_anggota = 'ANG-00001'
        
        try:
            cursor = db.execute('''
                INSERT INTO anggota (no_anggota, nama, nik, tempat_lahir, tanggal_lahir, 
                                    jenis_kelamin, alamat, telepon, email, pekerjaan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (no_anggota, request.form.get('nama'), request.form.get('nik'),
                  request.form.get('tempat_lahir'), request.form.get('tanggal_lahir'),
                  request.form.get('jenis_kelamin'), request.form.get('alamat'),
                  request.form.get('telepon'), request.form.get('email'), request.form.get('pekerjaan')))
            
            anggota_id = cursor.lastrowid
            username = no_anggota.lower()
            
            user_cursor = db.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                      (username, generate_password_hash('123456'), 'anggota'))
            user_id = user_cursor.lastrowid
            db.execute('UPDATE anggota SET user_id = ? WHERE id = ?', (user_id, anggota_id))
            
            active_types = db.execute('SELECT kode FROM jenis_simpanan WHERE aktif = 1 ORDER BY urutan, id').fetchall()
            if not active_types:
                raise ValueError('Belum ada jenis simpanan aktif. Atur minimal satu jenis simpanan terlebih dahulu.')
            simpanan_pokok = db.execute('SELECT value FROM pengaturan WHERE key="simpanan_pokok"').fetchone()
            pokok_amount = float(simpanan_pokok['value']) if simpanan_pokok else 0
            for savings_type in active_types:
                saldo_awal = pokok_amount if savings_type['kode'] == 'pokok' else 0
                db.execute('INSERT INTO simpanan (anggota_id, jenis, saldo) VALUES (?, ?, ?)',
                           (anggota_id, savings_type['kode'], saldo_awal))
            
            db.commit()
            flash(f'Anggota berhasil ditambahkan. Username: {username}, Password: 123456', 'success')
            return redirect(url_for('anggota.index'))
        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('anggota/tambah.html')

@bp.route('/<int:id>')
@login_required
def detail(id):
    db = get_db()
    if current_user.role != 'admin' and current_user.anggota_id != id:
        flash('Anda hanya dapat melihat data sendiri', 'error')
        return redirect(url_for('anggota.detail', id=current_user.anggota_id)) if current_user.anggota_id else redirect(url_for('dashboard.index'))
    anggota = db.execute('SELECT * FROM anggota WHERE id = ?', (id,)).fetchone()
    if not anggota:
        flash('Anggota tidak ditemukan', 'error')
        return redirect(url_for('anggota.index'))
    
    simpanan = db.execute('''SELECT s.*, COALESCE(j.nama, s.jenis) AS jenis_nama
                             FROM simpanan s LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
                             WHERE s.anggota_id = ? ORDER BY s.jenis''', (id,)).fetchall()
    pinjaman = db.execute('SELECT * FROM pinjaman WHERE anggota_id = ? ORDER BY tanggal_pengajuan DESC', (id,)).fetchall()
    
    return render_template('anggota/detail.html', anggota=anggota, simpanan=simpanan, pinjaman=pinjaman)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('anggota.index'))
    
    db = get_db()
    anggota = db.execute('SELECT * FROM anggota WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        try:
            db.execute('''
                UPDATE anggota SET nama=?, nik=?, tempat_lahir=?, tanggal_lahir=?,
                                  jenis_kelamin=?, alamat=?, telepon=?, email=?, pekerjaan=?, status=?
                WHERE id=?
            ''', (request.form.get('nama'), request.form.get('nik'), request.form.get('tempat_lahir'),
                  request.form.get('tanggal_lahir'), request.form.get('jenis_kelamin'),
                  request.form.get('alamat'), request.form.get('telepon'), request.form.get('email'),
                  request.form.get('pekerjaan'), request.form.get('status'), id))
            db.commit()
            flash('Data anggota berhasil diperbarui', 'success')
            return redirect(url_for('anggota.detail', id=id))
        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('anggota/edit.html', anggota=anggota)

@bp.route('/<int:id>/ubah-password', methods=['GET', 'POST'])
@login_required
def ubah_password(id):
    # Hanya anggota pemilik akun atau admin
    if current_user.role != 'admin' and current_user.anggota_id != id:
        flash('Akses ditolak', 'error')
        return redirect(url_for('anggota.detail', id=current_user.anggota_id)) if current_user.anggota_id else redirect(url_for('dashboard.index'))

    db = get_db()
    anggota = db.execute('SELECT * FROM anggota WHERE id = ?', (id,)).fetchone()
    if not anggota:
        flash('Anggota tidak ditemukan', 'error')
        return redirect(url_for('anggota.index'))

    user = db.execute('SELECT * FROM users WHERE id = ?', (anggota['user_id'],)).fetchone()
    if not user:
        flash('Akun pengguna tidak ditemukan', 'error')
        return redirect(url_for('anggota.detail', id=id))

    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            flash('Semua field wajib diisi', 'error')
            return render_template('anggota/ubah_password.html', anggota=anggota)

        if not check_password_hash(user['password'], old_password):
            flash('Kata sandi lama salah', 'error')
            return render_template('anggota/ubah_password.html', anggota=anggota)

        if new_password != confirm_password:
            flash('Kata sandi baru tidak cocok', 'error')
            return render_template('anggota/ubah_password.html', anggota=anggota)

        if len(new_password) < 6:
            flash('Kata sandi minimal 6 karakter', 'error')
            return render_template('anggota/ubah_password.html', anggota=anggota)

        db.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(new_password), user['id']))
        db.commit()
        flash('Kata sandi Berhasil diubah', 'success')
        return redirect(url_for('anggota.detail', id=id))

    return render_template('anggota/ubah_password.html', anggota=anggota)


@bp.route('/<int:id>/status', methods=['POST'])
@login_required
def ubah_status(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    status = request.form.get('status', '')
    if status not in ('aktif', 'non-aktif'):
        flash('Status anggota tidak valid', 'error')
        return redirect(url_for('anggota.detail', id=id))
    db = get_db()
    anggota = db.execute('SELECT id, nama, status FROM anggota WHERE id = ?', (id,)).fetchone()
    if not anggota:
        flash('Anggota tidak ditemukan', 'error')
        return redirect(url_for('anggota.index'))
    db.execute('UPDATE anggota SET status = ? WHERE id = ?', (status, id))
    db.commit()
    label = 'diaktifkan kembali' if status == 'aktif' else 'dinonaktifkan'
    flash(f'Anggota {anggota["nama"]} berhasil {label}', 'success')
    return redirect(url_for('anggota.detail', id=id))

@bp.route('/<int:id>/hapus', methods=['POST'])
@login_required
def hapus(id):
    if not _is_superadmin():
        flash('Hanya superadmin yang dapat menghapus anggota', 'error')
        return redirect(url_for('anggota.detail', id=id))
    db = get_db()
    anggota = db.execute('SELECT id, nama, user_id, status FROM anggota WHERE id = ?', (id,)).fetchone()
    if not anggota:
        flash('Anggota tidak ditemukan', 'error')
        return redirect(url_for('anggota.index'))
    if anggota['status'] != 'non-aktif':
        flash('Anggota harus dinonaktifkan sebelum dihapus', 'error')
        return redirect(url_for('anggota.detail', id=id))
    related = db.execute("""
        SELECT
          (SELECT COUNT(*) FROM simpanan WHERE anggota_id = ?) +
          (SELECT COUNT(*) FROM pinjaman WHERE anggota_id = ?)
    """, (id, id)).fetchone()[0]
    if related:
        flash('Anggota memiliki riwayat simpanan atau pinjaman dan tidak dapat dihapus', 'error')
        return redirect(url_for('anggota.detail', id=id))
    db.execute('DELETE FROM anggota WHERE id = ?', (id,))
    if anggota['user_id']:
        db.execute('DELETE FROM users WHERE id = ?', (anggota['user_id'],))
    db.commit()
    flash(f'Anggota {anggota["nama"]} dihapus', 'success')
    return redirect(url_for('anggota.index'))
