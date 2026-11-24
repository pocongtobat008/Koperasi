"""Simpanan routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import get_db

bp = Blueprint('simpanan', __name__, url_prefix='/simpanan')

@bp.route('/')
@login_required
def index():
    db = get_db()
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    simpanan = db.execute('''
        SELECT s.*, a.no_anggota, a.nama, COALESCE(j.nama, s.jenis) AS jenis_nama
        FROM simpanan s
        JOIN anggota a ON s.anggota_id = a.id
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        {where}
        ORDER BY a.no_anggota, s.jenis
    '''.format(where='WHERE s.anggota_id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    stats = db.execute("""
        SELECT COUNT(*) AS total,
               COALESCE(SUM(saldo), 0) AS saldo,
               COALESCE(SUM(CASE WHEN jenis = 'pokok' THEN saldo ELSE 0 END), 0) AS pokok,
               COALESCE(SUM(CASE WHEN jenis = 'wajib' THEN saldo ELSE 0 END), 0) AS wajib,
               COALESCE(SUM(CASE WHEN jenis = 'sukarela' THEN saldo ELSE 0 END), 0) AS sukarela
        FROM simpanan
    """ + (" WHERE anggota_id = ?" if member_only else ""), (member_id,) if member_only else ()).fetchone()
    return render_template('simpanan/index.html', simpanan=simpanan, stats=stats)

@bp.route('/setor', methods=['GET', 'POST'])
@login_required
def setor():
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('simpanan.index'))
    if request.method == 'POST':
        db = get_db()
        try:
            simpanan_id = request.form.get('simpanan_id')
            jumlah = float(request.form.get('jumlah'))
            keterangan = request.form.get('keterangan')
            
            db.execute('''
                INSERT INTO transaksi_simpanan (simpanan_id, jenis_transaksi, jumlah, keterangan, petugas_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (simpanan_id, 'setor', jumlah, keterangan, current_user.id))
            
            db.execute('UPDATE simpanan SET saldo = saldo + ? WHERE id = ?', (jumlah, simpanan_id))
            
            db.commit()
            flash('Setoran berhasil dicatat', 'success')
            return redirect(url_for('simpanan.index'))
        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    db = get_db()
    anggota = db.execute('''
        SELECT s.id, s.jenis, s.saldo, COALESCE(j.nama, s.jenis) AS jenis_nama, a.no_anggota, a.nama
        FROM simpanan s JOIN anggota a ON a.id = s.anggota_id
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        WHERE a.status = 'aktif'
        ORDER BY a.nama, s.jenis
    ''').fetchall()
    return render_template('simpanan/setor.html', anggota=anggota)

@bp.route('/tarik', methods=['GET', 'POST'])
@login_required
def tarik():
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('simpanan.index'))
    if request.method == 'POST':
        db = get_db()
        try:
            simpanan_id = request.form.get('simpanan_id')
            jumlah = float(request.form.get('jumlah'))
            keterangan = request.form.get('keterangan')
            
            simpanan = db.execute('SELECT * FROM simpanan WHERE id = ?', (simpanan_id,)).fetchone()
            if simpanan['saldo'] < jumlah:
                flash('Saldo tidak mencukupi', 'error')
                return redirect(url_for('simpanan.tarik'))
            
            db.execute('''
                INSERT INTO transaksi_simpanan (simpanan_id, jenis_transaksi, jumlah, keterangan, petugas_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (simpanan_id, 'tarik', jumlah, keterangan, current_user.id))
            
            db.execute('UPDATE simpanan SET saldo = saldo - ? WHERE id = ?', (jumlah, simpanan_id))
            
            db.commit()
            flash('Penarikan berhasil dicatat', 'success')
            return redirect(url_for('simpanan.index'))
        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    db = get_db()
    anggota = db.execute('''
        SELECT s.id, s.jenis, s.saldo, COALESCE(j.nama, s.jenis) AS jenis_nama, a.no_anggota, a.nama
        FROM simpanan s JOIN anggota a ON a.id = s.anggota_id
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        WHERE a.status = 'aktif'
        ORDER BY a.nama, s.jenis
    ''').fetchall()
    return render_template('simpanan/tarik.html', anggota=anggota)

@bp.route('/riwayat/<int:id>')
@login_required
def riwayat(id):
    db = get_db()
    simpanan = db.execute('''
        SELECT s.*, a.no_anggota, a.nama, COALESCE(j.nama, s.jenis) AS jenis_nama
        FROM simpanan s
        JOIN anggota a ON s.anggota_id = a.id
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        WHERE s.id = ?
    ''', (id,)).fetchone()
    
    if not simpanan or (current_user.role != 'admin' and simpanan['anggota_id'] != current_user.anggota_id):
        flash('Akses ditolak', 'error')
        return redirect(url_for('simpanan.index'))

    transaksi = db.execute('''
        SELECT ts.*, u.username as petugas
        FROM transaksi_simpanan ts
        LEFT JOIN users u ON ts.petugas_id = u.id
        WHERE ts.simpanan_id = ?
        ORDER BY ts.tanggal DESC
    ''', (id,)).fetchall()
    
    return render_template('simpanan/riwayat.html', simpanan=simpanan, transaksi=transaksi)
