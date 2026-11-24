"""Pinjaman routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import get_db
from datetime import datetime
from dateutil.relativedelta import relativedelta

bp = Blueprint('pinjaman', __name__, url_prefix='/pinjaman')

@bp.route('/')
@login_required
def index():
    db = get_db()
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    pinjaman = db.execute('''
        SELECT p.*, a.no_anggota, a.nama, j.nama as jenis_nama
        FROM pinjaman p LEFT JOIN jenis_pinjaman j ON j.id = p.jenis_pinjaman_id
        JOIN anggota a ON p.anggota_id = a.id
        {where}
        ORDER BY p.tanggal_pengajuan DESC
    '''.format(where='WHERE p.anggota_id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    stats = db.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'disetujui' THEN 1 ELSE 0 END) AS aktif,
               SUM(CASE WHEN status = 'diajukan' THEN 1 ELSE 0 END) AS menunggu,
               COALESCE(SUM(CASE WHEN status = 'disetujui' THEN sisa_pinjaman ELSE 0 END), 0) AS sisa
        FROM pinjaman
    """ + (" WHERE anggota_id = ?" if member_only else ""), (member_id,) if member_only else ()).fetchone()
    return render_template('pinjaman/index.html', pinjaman=pinjaman, stats=stats)

@bp.route('/ajukan', methods=['GET', 'POST'])
@login_required
def ajukan():
    if current_user.role != 'admin':
        flash('Pengajuan pinjaman anggota belum tersedia', 'error')
        return redirect(url_for('pinjaman.index'))
    db = get_db()
    # Ambil jenis pinjaman aktif untuk dropdown
    aktif_pinjaman = db.execute('SELECT * FROM jenis_pinjaman WHERE aktif = 1 ORDER BY urutan, id').fetchall()
    default_pinjaman_id = aktif_pinjaman[0]['id'] if aktif_pinjaman else None
    
    if request.method == 'POST':
        try:
            anggota_id = request.form.get('anggota_id')
            jumlah_pinjaman = float(request.form.get('jumlah_pinjaman'))
            jangka_waktu = int(request.form.get('jangka_waktu'))
            jenis_pinjaman_id = int(request.form.get('jenis_pinjaman_id'))
            
            suku_bunga = float(db.execute('SELECT value FROM pengaturan WHERE key="suku_bunga_pinjaman"').fetchone()['value'])
            
            bunga_total = (jumlah_pinjaman * suku_bunga / 100 * jangka_waktu) / 12
            total_pinjaman = jumlah_pinjaman + bunga_total
            jumlah_cicilan = total_pinjaman / jangka_waktu
            
            last = db.execute('SELECT no_pinjaman FROM pinjaman ORDER BY id DESC LIMIT 1').fetchone()
            if last:
                last_num = int(last['no_pinjaman'].split('-')[1])
                no_pinjaman = f'PJM-{last_num + 1:05d}'
            else:
                no_pinjaman = 'PJM-00001'
            
            cursor = db.execute('''
                INSERT INTO pinjaman (anggota_id, no_pinjaman, jumlah_pinjaman, suku_bunga, 
                                     jangka_waktu, jumlah_cicilan, sisa_pinjaman, status, jenis_pinjaman_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (anggota_id, no_pinjaman, jumlah_pinjaman, suku_bunga, jangka_waktu, 
                  jumlah_cicilan, total_pinjaman, 'diajukan', jenis_pinjaman_id))
            
            db.commit()
            flash('Pengajuan pinjaman berhasil', 'success')
            return redirect(url_for('pinjaman.index'))
        except Exception as e:
            db.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    db = get_db()
    anggota = db.execute('SELECT * FROM anggota WHERE status="aktif" ORDER BY nama').fetchall()
    pengaturan = db.execute('SELECT * FROM pengaturan WHERE key IN ("suku_bunga_pinjaman", "biaya_admin")').fetchall()
    return render_template('pinjaman/ajukan.html', anggota=anggota, pengaturan={p['key']: p['value'] for p in pengaturan}, 
                           aktif_pinjaman=aktif_pinjaman, default_pinjaman_id=default_pinjaman_id)

@bp.route('/<int:id>/setujui', methods=['POST'])
@login_required
def setujui(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('pinjaman.index'))
    
    db = get_db()
    try:
        pinjaman = db.execute('SELECT * FROM pinjaman WHERE id = ?', (id,)).fetchone()
        
        db.execute('''
            UPDATE pinjaman SET status = ?, tanggal_persetujuan = ?, petugas_id = ?
            WHERE id = ?
        ''', ('disetujui', datetime.now(), current_user.id, id))
        
        tanggal_mulai = datetime.now()
        for i in range(pinjaman['jangka_waktu']):
            tanggal_jatuh_tempo = tanggal_mulai + relativedelta(months=i+1)
            db.execute('''
                INSERT INTO cicilan_pinjaman (pinjaman_id, cicilan_ke, jumlah_cicilan, tanggal_jatuh_tempo)
                VALUES (?, ?, ?, ?)
            ''', (id, i+1, pinjaman['jumlah_cicilan'], tanggal_jatuh_tempo.date()))
        
        db.commit()
        flash('Pinjaman disetujui', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('pinjaman.detail', id=id))

@bp.route('/<int:id>/tolak', methods=['POST'])
@login_required
def tolak(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('pinjaman.index'))
    
    db = get_db()
    db.execute('UPDATE pinjaman SET status = ?, petugas_id = ? WHERE id = ?', ('ditolak', current_user.id, id))
    db.commit()
    flash('Pinjaman ditolak', 'success')
    return redirect(url_for('pinjaman.detail', id=id))

@bp.route('/<int:id>')
@login_required
def detail(id):
    db = get_db()
    pinjaman = db.execute('''
        SELECT p.*, a.no_anggota, a.nama, j.nama as jenis_nama, u.username as petugas
        FROM pinjaman p LEFT JOIN jenis_pinjaman j ON j.id = p.jenis_pinjaman_id
        JOIN anggota a ON p.anggota_id = a.id
        LEFT JOIN users u ON p.petugas_id = u.id
        WHERE p.id = ?
    ''', (id,)).fetchone()
    if not pinjaman or (current_user.role != 'admin' and pinjaman['anggota_id'] != current_user.anggota_id):
        flash('Akses ditolak', 'error')
        return redirect(url_for('pinjaman.index'))
    
    cicilan = db.execute('''
        SELECT cp.*, u.username as petugas
        FROM cicilan_pinjaman cp
        LEFT JOIN users u ON cp.petugas_id = u.id
        WHERE cp.pinjaman_id = ?
        ORDER BY cp.cicilan_ke
    ''', (id,)).fetchall()
    
    return render_template('pinjaman/detail.html', pinjaman=pinjaman, cicilan=cicilan)

@bp.route('/cicilan/<int:id>/bayar', methods=['POST'])
@login_required
def bayar_cicilan(id):
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('pinjaman.index'))
    db = get_db()
    try:
        cicilan = db.execute('SELECT * FROM cicilan_pinjaman WHERE id = ?', (id,)).fetchone()
        jumlah_bayar = float(request.form.get('jumlah_bayar', cicilan['jumlah_cicilan']))
        denda = float(request.form.get('denda', 0))
        
        db.execute('''
            UPDATE cicilan_pinjaman 
            SET tanggal_bayar = ?, jumlah_bayar = ?, denda = ?, status = ?, petugas_id = ?
            WHERE id = ?
        ''', (datetime.now(), jumlah_bayar, denda, 'lunas', current_user.id, id))
        
        db.execute('UPDATE pinjaman SET sisa_pinjaman = sisa_pinjaman - ? WHERE id = ?', 
                  (jumlah_bayar, cicilan['pinjaman_id']))
        
        pinjaman = db.execute('SELECT * FROM pinjaman WHERE id = ?', (cicilan['pinjaman_id'],)).fetchone()
        if pinjaman['sisa_pinjaman'] <= 0:
            db.execute('UPDATE pinjaman SET status = ? WHERE id = ?', ('lunas', cicilan['pinjaman_id']))
        
        db.commit()
        flash('Pembayaran cicilan berhasil', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('pinjaman.detail', id=cicilan['pinjaman_id']))