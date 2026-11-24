"""Laporan routes"""
from flask import Blueprint, render_template, request, make_response, redirect, url_for
from flask_login import login_required, current_user
from ..models import get_db
from datetime import datetime
import csv
from io import StringIO, BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

bp = Blueprint('laporan', __name__, url_prefix='/laporan')

@bp.route('/')
@login_required
def index():
    return render_template('laporan/index.html', milik_sendiri=current_user.role != 'admin')

@bp.route('/keuangan')
@login_required
def keuangan():
    db = get_db()
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    
    simpanan = db.execute('''
        SELECT s.jenis, COALESCE(j.nama, s.jenis) AS jenis_nama, SUM(s.saldo) as total
        FROM simpanan s
        LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        {where}
        GROUP BY s.jenis
    '''.format(where='WHERE s.anggota_id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    
    pinjaman_summary = db.execute('''
        SELECT 
            SUM(CASE WHEN status = 'disetujui' THEN sisa_pinjaman ELSE 0 END) as pinjaman_aktif,
            SUM(CASE WHEN status = 'lunas' THEN jumlah_pinjaman ELSE 0 END) as pinjaman_lunas,
            COUNT(CASE WHEN status = 'diajukan' THEN 1 END) as pinjaman_menunggu
        FROM pinjaman
    ''' + (" WHERE anggota_id = ?" if member_only else ""), (member_id,) if member_only else ()).fetchone()
    
    transaksi_bulan_ini = db.execute('''
        SELECT 
            ts.jenis_transaksi,
            COUNT(*) as jumlah_transaksi,
            SUM(ts.jumlah) as total_nominal
        FROM transaksi_simpanan ts
        JOIN simpanan s ON s.id = ts.simpanan_id
        WHERE strftime('%Y-%m', ts.tanggal) = strftime('%Y-%m', 'now')
        {where}
        GROUP BY jenis_transaksi
    '''.format(where='AND s.anggota_id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    
    return render_template('laporan/keuangan.html', 
                          simpanan=simpanan, 
                          pinjaman=pinjaman_summary,
                          transaksi=transaksi_bulan_ini)

@bp.route('/anggota')
@login_required
def anggota():
    db = get_db()
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    
    stats = db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'aktif' THEN 1 ELSE 0 END) as aktif,
            SUM(CASE WHEN status = 'non-aktif' THEN 1 ELSE 0 END) as non_aktif
        FROM anggota
    ''' + (" WHERE id = ?" if member_only else ""), (member_id,) if member_only else ()).fetchone()
    
    anggota_baru = db.execute('''
        SELECT * FROM anggota
        WHERE strftime('%Y-%m', tanggal_bergabung) = strftime('%Y-%m', 'now')
        {where}
        ORDER BY tanggal_bergabung DESC
    '''.format(where='AND id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    
    return render_template('laporan/anggota.html', stats=stats, anggota_baru=anggota_baru)

@bp.route('/pinjaman')
@login_required
def pinjaman():
    db = get_db()
    member_only = current_user.role != 'admin'
    member_id = current_user.anggota_id
    
    status_summary = db.execute('''
        SELECT status, COUNT(*) as jumlah, SUM(jumlah_pinjaman) as total
        FROM pinjaman
        {where}
        GROUP BY status
    '''.format(where='WHERE anggota_id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    
    cicilan_jatuh_tempo = db.execute('''
        SELECT cp.*, p.no_pinjaman, a.nama, a.no_anggota
        FROM cicilan_pinjaman cp
        JOIN pinjaman p ON cp.pinjaman_id = p.id
        JOIN anggota a ON p.anggota_id = a.id
        WHERE cp.status = 'belum'
        {where}
        ORDER BY cp.tanggal_jatuh_tempo ASC
    '''.format(where='AND a.id = ?' if member_only else ''), (member_id,) if member_only else ()).fetchall()
    
    return render_template('laporan/pinjaman.html', 
                          status_summary=status_summary,
                          cicilan=cicilan_jatuh_tempo)

def _export_csv(db, jenis):
    si = StringIO()
    writer = csv.writer(si)
    
    if jenis == 'anggota':
        writer.writerow(['No Anggota', 'Nama', 'NIK', 'Telepon', 'Email', 'Status', 'Tanggal Bergabung'])
        rows = db.execute('SELECT no_anggota, nama, nik, telepon, email, status, tanggal_bergabung FROM anggota').fetchall()
        for row in rows:
            writer.writerow(row)
    
    elif jenis == 'simpanan':
        writer.writerow(['No Anggota', 'Nama', 'Jenis', 'Saldo'])
        rows = db.execute('''
            SELECT a.no_anggota, a.nama, COALESCE(j.nama, s.jenis) AS jenis_nama, s.saldo
            FROM simpanan s
            JOIN anggota a ON s.anggota_id = a.id
            LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        ''').fetchall()
        for row in rows:
            writer.writerow(row)
    
    elif jenis == 'pinjaman':
        writer.writerow(['No Pinjaman', 'No Anggota', 'Nama', 'Jumlah', 'Sisa', 'Status', 'Tanggal'])
        rows = db.execute('''
            SELECT p.no_pinjaman, a.no_anggota, a.nama, p.jumlah_pinjaman, p.sisa_pinjaman, p.status, p.tanggal_pengajuan
            FROM pinjaman p
            JOIN anggota a ON p.anggota_id = a.id
        ''').fetchall()
        for row in rows:
            writer.writerow(row)
    
    return si.getvalue()

def _export_excel(db, jenis):
    wb = Workbook()
    ws = wb.active
    ws.title = jenis.title()
    
    header_font = Font(bold=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    if jenis == 'anggota':
        ws.append(['No Anggota', 'Nama', 'NIK', 'Telepon', 'Email', 'Status', 'Tanggal Bergabung'])
        rows = db.execute('SELECT no_anggota, nama, nik, telepon, email, status, tanggal_bergabung FROM anggota').fetchall()
        for row in rows:
            ws.append(list(row))
    
    elif jenis == 'simpanan':
        ws.append(['No Anggota', 'Nama', 'Jenis', 'Saldo'])
        rows = db.execute('''
            SELECT a.no_anggota, a.nama, COALESCE(j.nama, s.jenis) AS jenis_nama, s.saldo
            FROM simpanan s
            JOIN anggota a ON s.anggota_id = a.id
            LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
        ''').fetchall()
        for row in rows:
            ws.append(list(row))
    
    elif jenis == 'pinjaman':
        ws.append(['No Pinjaman', 'No Anggota', 'Nama', 'Jumlah', 'Sisa', 'Status', 'Tanggal'])
        rows = db.execute('''
            SELECT p.no_pinjaman, a.no_anggota, a.nama, p.jumlah_pinjaman, p.sisa_pinjaman, p.status, p.tanggal_pengajuan
            FROM pinjaman p
            JOIN anggota a ON p.anggota_id = a.id
        ''').fetchall()
        for row in rows:
            ws.append(list(row))
    
    # Style header
    for cell in ws[1]:
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center')
    
    # Style data cells
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = thin_border
    
    # Adjust column widths
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 40)
        ws.column_dimensions[col_letter].width = adjusted_width
    
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()

@bp.route('/export/<jenis>')
@login_required
def export(jenis):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard.index'))
    
    db = get_db()
    csv_data = _export_csv(db, jenis)
    output = make_response(csv_data)
    output.headers["Content-Disposition"] = f"attachment; filename=laporan_{jenis}_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@bp.route('/export/excel/all')
@login_required
def export_excel_all():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard.index'))
    db = get_db()
    wb = Workbook()

    header_font = Font(bold=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    sheets = [
        ('Anggota', [
            ['No Anggota', 'Nama', 'NIK', 'Telepon', 'Email', 'Status', 'Tanggal Bergabung'],
            db.execute("SELECT no_anggota, nama, nik, telepon, email, status, tanggal_bergabung FROM anggota").fetchall()
        ]),
        ('Simpanan', [
            ['No Anggota', 'Nama', 'Jenis', 'Saldo'],
            db.execute("""SELECT a.no_anggota, a.nama, COALESCE(j.nama, s.jenis) AS jenis_nama, s.saldo
                FROM simpanan s
                JOIN anggota a ON s.anggota_id = a.id
                LEFT JOIN jenis_simpanan j ON j.kode = s.jenis""").fetchall()
        ]),
        ('Pinjaman', [
            ['No Pinjaman', 'No Anggota', 'Nama', 'Jumlah', 'Sisa', 'Status', 'Tanggal'],
            db.execute("""SELECT p.no_pinjaman, a.no_anggota, a.nama, p.jumlah_pinjaman, p.sisa_pinjaman, p.status, p.tanggal_pengajuan
                FROM pinjaman p
                JOIN anggota a ON p.anggota_id = a.id""").fetchall()
        ]),
        ('Transaksi', [
            ['Tanggal', 'Jenis', 'Anggota', 'No Anggota', 'No Simpanan', 'Jumlah', 'Keterangan'],
            db.execute("""SELECT ts.tanggal, ts.jenis_transaksi, a.nama, a.no_anggota, ts.jumlah, ts.keterangan
                FROM transaksi_simpanan ts
                JOIN simpanan s ON ts.simpanan_id = s.id
                JOIN anggota a ON s.anggota_id = a.id""").fetchall()
        ]),
    ]

    for idx, (title, (headers, rows)) in enumerate(sheets):
        if idx == 0:
            ws = wb.active
            ws.title = title
        else:
            ws = wb.create_sheet(title=title)
        ws.append(headers)
        for row in rows:
            ws.append(list(row))
        # Style header
        for cell in ws[1]:
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
        # Style data cells
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.border = thin_border
        # Adjust column widths
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = min(max_length + 2, 40)
            ws.column_dimensions[col_letter].width = adjusted_width

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return make_response(bio.getvalue(),
        {'Content-Disposition': f'attachment; filename=laporan_keseluruhan_{datetime.now().strftime("%Y%m%d")}.xlsx',
         'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})

@bp.route('/export/excel/<jenis>')
@login_required
def export_excel(jenis):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard.index'))
    
    db = get_db()
    xlsx_data = _export_excel(db, jenis)
    output = make_response(xlsx_data)
    output.headers["Content-Disposition"] = f"attachment; filename=laporan_{jenis}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    output.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return output

"""Route handler untuk sync Google Sheets"""
import os
import json
from flask import request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..models import get_db

CREDS_PATH = '/opt/koperasi/data/google_service_account.json'

@bp.route('/sync/google-sheets', methods=['POST'])
@login_required
def sync_google_sheets():
    """Sync data koperasi ke Google Sheets menggunakan service account."""
    if current_user.role != 'admin':
        flash('Akses ditolak', 'error')
        return redirect(url_for('dashboard.index'))
    
    sheets_url = request.form.get('sheets_url', '').strip()
    if not sheets_url:
        flash('URL Google Sheets wajib diisi', 'error')
        return redirect(url_for('laporan.index'))
    
    # Extract spreadsheet ID from URL
    import re
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheets_url)
    if not match:
        flash('Format URL Google Sheets tidak valid', 'error')
        return redirect(url_for('laporan.index'))
    
    spreadsheet_id = match.group(1)
    
    # Save uploaded service account JSON if provided
    if 'service_json' in request.files:
        file = request.files['service_json']
        if file and file.filename and file.filename.endswith('.json'):
            try:
                content = file.read()
                data = json.loads(content)
                if 'type' not in data or data['type'] != 'service_account':
                    flash('File JSON bukan service account yang valid', 'error')
                    return redirect(url_for('laporan.index'))
                with open(CREDS_PATH, 'wb') as f:
                    f.write(content)
                os.chmod(CREDS_PATH, 0o600)
                flash('Kredensial service account berhasil disimpan', 'success')
            except Exception as e:
                flash(f'Gagal menyimpan kredensial: {str(e)}', 'error')
                return redirect(url_for('laporan.index'))
    
    # Check if credentials exist
    if not os.path.exists(CREDS_PATH):
        flash('Kredensial service account belum diunggah', 'error')
        return redirect(url_for('laporan.index'))
    
    # Perform sync (requires gspread + oauth2client or google-auth)
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open spreadsheet
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        db = get_db()
        
        # Sheet 1: Anggota
        try:
            sheet_anggota = spreadsheet.worksheet('Anggota')
        except:
            sheet_anggota = spreadsheet.add_worksheet('Anggota', 1000, 10)
        
        anggota_data = db.execute('''
            SELECT a.no_anggota, a.nama, a.nik, a.tempat_lahir, a.tanggal_lahir,
                   a.alamat, a.telepon, a.email, a.status, a.tanggal_bergabung
            FROM anggota a ORDER BY a.no_anggota
        ''').fetchall()
        
        anggota_rows = [['No Anggota', 'Nama', 'NIK', 'Tempat Lahir', 'Tanggal Lahir',
                        'Alamat', 'Telepon', 'Email', 'Status', 'Tanggal Bergabung']]
        for row in anggota_data:
            anggota_rows.append(list(row))
        
        sheet_anggota.clear()
        sheet_anggota.update('A1', anggota_rows)
        
        # Sheet 2: Simpanan
        try:
            sheet_simpanan = spreadsheet.worksheet('Simpanan')
        except:
            sheet_simpanan = spreadsheet.add_worksheet('Simpanan', 1000, 6)
        
        simpanan_data = db.execute('''
            SELECT a.no_anggota, a.nama, COALESCE(j.nama, s.jenis) AS jenis_simpanan,
                   s.saldo, s.created_at
            FROM simpanan s
            JOIN anggota a ON a.id = s.anggota_id
            LEFT JOIN jenis_simpanan j ON j.kode = s.jenis
            ORDER BY a.no_anggota, s.jenis
        ''').fetchall()
        
        simpanan_rows = [['No Anggota', 'Nama', 'Jenis Simpanan', 'Saldo', 'Dibuat']]
        for row in simpanan_data:
            simpanan_rows.append(list(row))
        
        sheet_simpanan.clear()
        sheet_simpanan.update('A1', simpanan_rows)
        
        # Sheet 3: Pinjaman
        try:
            sheet_pinjaman = spreadsheet.worksheet('Pinjaman')
        except:
            sheet_pinjaman = spreadsheet.add_worksheet('Pinjaman', 1000, 10)
        
        pinjaman_data = db.execute('''
            SELECT p.no_pinjaman, a.no_anggota, a.nama,
                   COALESCE(j.nama, 'Umum') AS jenis_pinjaman,
                   p.jumlah_pinjaman, p.suku_bunga, p.jangka_waktu,
                   p.jumlah_cicilan, p.sisa_pinjaman, p.status,
                   p.tanggal_pengajuan, p.tanggal_persetujuan
            FROM pinjaman p
            JOIN anggota a ON a.id = p.anggota_id
            LEFT JOIN jenis_pinjaman j ON j.id = p.jenis_pinjaman_id
            ORDER BY p.tanggal_pengajuan DESC
        ''').fetchall()
        
        pinjaman_rows = [['No Pinjaman', 'No Anggota', 'Nama', 'Jenis Pinjaman',
                         'Jumlah', 'Bunga %', 'Jangka Waktu', 'Cicilan', 'Sisa',
                         'Status', 'Tanggal Pengajuan', 'Tanggal Persetujuan']]
        for row in pinjaman_data:
            pinjaman_rows.append(list(row))
        
        sheet_pinjaman.clear()
        sheet_pinjaman.update('A1', pinjaman_rows)
        
        flash(f'Data berhasil disinkronkan ke Google Sheets: {len(anggota_data)} anggota, {len(simpanan_data)} simpanan, {len(pinjaman_data)} pinjaman', 'success')
        
    except ImportError:
        flash('Library gspread atau google-auth belum terinstal. Jalankan: pip install gspread google-auth', 'error')
    except Exception as e:
        flash(f'Gagal sync: {str(e)}', 'error')
    
    return redirect(url_for('laporan.index'))
