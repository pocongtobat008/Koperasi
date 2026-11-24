"""Dashboard routes"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..models import get_db
from datetime import datetime

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    db = get_db()
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    
    stats = {}
    if member_only:
        stats['total_anggota'] = db.execute('SELECT COUNT(*) as count FROM anggota WHERE id=? AND status="aktif"', (member_id,)).fetchone()['count']
        stats['total_simpanan'] = db.execute('SELECT COALESCE(SUM(saldo), 0) as total FROM simpanan WHERE anggota_id=?', (member_id,)).fetchone()['total']
        stats['total_pinjaman_aktif'] = db.execute('SELECT COALESCE(SUM(sisa_pinjaman), 0) as total FROM pinjaman WHERE anggota_id=? AND status="disetujui"', (member_id,)).fetchone()['total']
        stats['pinjaman_diajukan'] = db.execute('SELECT COUNT(*) as count FROM pinjaman WHERE anggota_id=? AND status="diajukan"', (member_id,)).fetchone()['count']
    else:
        stats['total_anggota'] = db.execute('SELECT COUNT(*) as count FROM anggota WHERE status="aktif"').fetchone()['count']
        stats['total_simpanan'] = db.execute('SELECT COALESCE(SUM(saldo), 0) as total FROM simpanan').fetchone()['total']
        stats['total_pinjaman_aktif'] = db.execute('SELECT COALESCE(SUM(sisa_pinjaman), 0) as total FROM pinjaman WHERE status="disetujui"').fetchone()['total']
        stats['pinjaman_diajukan'] = db.execute('SELECT COUNT(*) as count FROM pinjaman WHERE status="diajukan"').fetchone()['count']
    
    transaksi_sql = '''
        SELECT ts.*, s.jenis, COALESCE(j.nama, s.jenis) AS jenis_nama, a.nama, a.no_anggota
        FROM transaksi_simpanan ts
        JOIN simpanan s ON ts.simpanan_id = s.id
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        JOIN anggota a ON s.anggota_id = a.id
        {where}
        ORDER BY ts.tanggal DESC LIMIT 10
    '''.format(where='WHERE a.id = ?' if member_only else '')
    transaksi_terakhir = db.execute(transaksi_sql, (member_id,) if member_only else ()).fetchall()
    
    cicilan_sql = '''
        SELECT cp.*, p.no_pinjaman, a.nama, a.no_anggota
        FROM cicilan_pinjaman cp
        JOIN pinjaman p ON cp.pinjaman_id = p.id
        JOIN anggota a ON p.anggota_id = a.id
        WHERE cp.status = "belum" AND cp.tanggal_jatuh_tempo <= date('now', '+7 days')
        {where}
        ORDER BY cp.tanggal_jatuh_tempo ASC LIMIT 10
    '''.format(where='AND a.id = ?' if member_only else '')
    cicilan_jatuh_tempo = db.execute(cicilan_sql, (member_id,) if member_only else ()).fetchall()
    
    trend_sql = """
        WITH RECURSIVE months(month) AS (
            SELECT strftime('%Y-%m', 'now', 'start of month', '-5 months')
            UNION ALL
            SELECT strftime('%Y-%m', month || '-01', '+1 month')
            FROM months WHERE month < strftime('%Y-%m', 'now')
        )
        SELECT months.month,
               COALESCE((SELECT SUM(CASE WHEN jenis_transaksi = 'setor' THEN jumlah ELSE -jumlah END)
                         FROM transaksi_simpanan ts JOIN simpanan ss ON ts.simpanan_id=ss.id
                         WHERE strftime('%Y-%m', ts.tanggal) = months.month {member_tx}), 0) AS simpanan,
               COALESCE((SELECT SUM(jumlah_pinjaman) FROM pinjaman
                         WHERE strftime('%Y-%m', tanggal_pengajuan) = months.month {member_loan}), 0) AS pinjaman
        FROM months ORDER BY months.month
    """.format(member_tx='AND ss.anggota_id = ?' if member_only else '', member_loan='AND anggota_id = ?' if member_only else '')
    trend_params = (member_id, member_id) if member_only else ()
    trend_rows = db.execute(trend_sql, trend_params).fetchall()
    max_value = max(1, max([max(abs(float(row['simpanan'])), float(row['pinjaman'])) for row in trend_rows] or [0]))
    trend = []
    for row in trend_rows:
        trend.append({'label': datetime.strptime(row['month'], '%Y-%m').strftime('%b'),
                      'simpanan': float(row['simpanan']), 'pinjaman': float(row['pinjaman']),
                      'simpanan_pct': round(abs(float(row['simpanan'])) / max_value * 100, 1),
                      'pinjaman_pct': round(float(row['pinjaman']) / max_value * 100, 1)})
    return render_template('dashboard.html', stats=stats, transaksi=transaksi_terakhir,
                           cicilan=cicilan_jatuh_tempo, trend=trend)
