"""Transaksi routes"""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from ..models import get_db

bp = Blueprint('transaksi', __name__, url_prefix='/transaksi')

@bp.route('/')
@login_required
def index():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    
    transaksi = db.execute('''
        SELECT ts.*, s.jenis, COALESCE(j.nama, s.jenis) AS jenis_nama, a.no_anggota, a.nama, u.username as petugas
        FROM transaksi_simpanan ts
        JOIN simpanan s ON ts.simpanan_id = s.id
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        JOIN anggota a ON s.anggota_id = a.id
        LEFT JOIN users u ON ts.petugas_id = u.id
        {where}
        ORDER BY ts.tanggal DESC
        LIMIT ? OFFSET ?
    '''.format(where='WHERE a.id = ?' if member_only else ''), ((member_id, per_page, offset) if member_only else (per_page, offset))).fetchall()
    
    total = db.execute('''
        SELECT COUNT(*) as count
        FROM transaksi_simpanan ts JOIN simpanan s ON s.id=ts.simpanan_id
    ''' + (' WHERE s.anggota_id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchone()['count']
    stats = db.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN jenis_transaksi = 'setor' THEN 1 ELSE 0 END) AS setor,
               SUM(CASE WHEN jenis_transaksi = 'tarik' THEN 1 ELSE 0 END) AS tarik,
               COALESCE(SUM(CASE WHEN jenis_transaksi = 'setor' THEN jumlah ELSE 0 END), 0) AS nominal_setor,
               COALESCE(SUM(CASE WHEN jenis_transaksi = 'tarik' THEN jumlah ELSE 0 END), 0) AS nominal_tarik
        FROM transaksi_simpanan ts JOIN simpanan s ON s.id=ts.simpanan_id
    """ + (" WHERE s.anggota_id = ?" if member_only else ""), (member_id,) if member_only else ()).fetchone()
    
    return render_template('transaksi/index.html', transaksi=transaksi, page=page, 
                          total_pages=(total + per_page - 1) // per_page, stats=stats)
