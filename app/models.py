"""Database models dan schema"""
import sqlite3
from flask import current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    import os
    os.makedirs(os.path.dirname(current_app.config['DATABASE']), exist_ok=True)
    
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'anggota')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS anggota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            no_anggota TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            nik TEXT UNIQUE NOT NULL,
            tempat_lahir TEXT,
            tanggal_lahir DATE,
            jenis_kelamin TEXT CHECK(jenis_kelamin IN ('L', 'P')),
            alamat TEXT,
            telepon TEXT,
            email TEXT,
            pekerjaan TEXT,
            status TEXT DEFAULT 'aktif' CHECK(status IN ('aktif', 'non-aktif')),
            tanggal_bergabung DATE DEFAULT (date('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS simpanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anggota_id INTEGER NOT NULL,
            jenis TEXT NOT NULL,
            saldo REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anggota_id) REFERENCES anggota(id),
            UNIQUE(anggota_id, jenis)
        );

        CREATE TABLE IF NOT EXISTS jenis_simpanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT UNIQUE NOT NULL,
            nama TEXT UNIQUE NOT NULL,
            aktif INTEGER NOT NULL DEFAULT 1 CHECK(aktif IN (0, 1)),
            urutan INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS transaksi_simpanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simpanan_id INTEGER NOT NULL,
            jenis_transaksi TEXT NOT NULL CHECK(jenis_transaksi IN ('setor', 'tarik')),
            jumlah REAL NOT NULL,
            keterangan TEXT,
            tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            petugas_id INTEGER,
            FOREIGN KEY (simpanan_id) REFERENCES simpanan(id),
            FOREIGN KEY (petugas_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS pinjaman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anggota_id INTEGER NOT NULL,
            no_pinjaman TEXT UNIQUE NOT NULL,
            jumlah_pinjaman REAL NOT NULL,
            suku_bunga REAL NOT NULL,
            jangka_waktu INTEGER NOT NULL,
            jumlah_cicilan REAL NOT NULL,
            sisa_pinjaman REAL NOT NULL,
            status TEXT DEFAULT 'diajukan' CHECK(status IN ('diajukan', 'disetujui', 'ditolak', 'lunas')),
            tanggal_pengajuan TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tanggal_persetujuan TIMESTAMP,
            petugas_id INTEGER,
            FOREIGN KEY (anggota_id) REFERENCES anggota(id),
            FOREIGN KEY (petugas_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS cicilan_pinjaman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pinjaman_id INTEGER NOT NULL,
            cicilan_ke INTEGER NOT NULL,
            jumlah_cicilan REAL NOT NULL,
            tanggal_jatuh_tempo DATE NOT NULL,
            tanggal_bayar TIMESTAMP,
            jumlah_bayar REAL DEFAULT 0,
            denda REAL DEFAULT 0,
            status TEXT DEFAULT 'belum' CHECK(status IN ('belum', 'lunas')),
            petugas_id INTEGER,
            FOREIGN KEY (pinjaman_id) REFERENCES pinjaman(id),
            FOREIGN KEY (petugas_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS pengaturan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jenis_pinjaman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT UNIQUE NOT NULL,
            nama TEXT UNIQUE NOT NULL,
            aktif INTEGER NOT NULL DEFAULT 1 CHECK(aktif IN (0, 1)),
            urutan INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_anggota_no ON anggota(no_anggota);
        CREATE INDEX IF NOT EXISTS idx_pinjaman_no ON pinjaman(no_pinjaman);
        CREATE INDEX IF NOT EXISTS idx_pinjaman_status ON pinjaman(status);
    ''')

    # Migration: pinjaman tidak punya kolom jenis_pinjaman_id di versi lama.
    pinjaman_columns = [r[1] for r in db.execute('PRAGMA table_info(pinjaman)')]
    if 'jenis_pinjaman_id' not in pinjaman_columns:
        db.execute('ALTER TABLE pinjaman ADD COLUMN jenis_pinjaman_id INTEGER')

    # Migration: hapus constraint CHECK lama tanpa menulis saldo/pinjaman lama.
    pinjaman_schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pinjaman'").fetchone()['sql'] or ''
    # (constraint CHECK status sudah aman; tidak perlu migrasi di sini)

    # Legacy simpanan types: hanya Simpanan Wajib yang aktif.
    legacy_types = [('pokok', 'Simpanan Pokok', 0, 10), ('wajib', 'Simpanan Wajib', 1, 20), ('sukarela', 'Simpanan Sukarela', 0, 30)]
    for kode, nama, aktif, urutan in legacy_types:
        db.execute('INSERT OR IGNORE INTO jenis_simpanan (kode, nama, aktif, urutan) VALUES (?, ?, ?, ?)',
                   (kode, nama, aktif, urutan))
    
    cursor = db.execute('SELECT COUNT(*) as count FROM users')
    if cursor.fetchone()['count'] == 0:
        db.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                  ('admin', generate_password_hash('admin123'), 'admin'))
        
        db.execute('''INSERT INTO pengaturan (key, value) VALUES
            ('nama_koperasi', 'Koperasi Sejahtera'),
            ('suku_bunga_pinjaman', '12'),
            ('biaya_admin', '50000'),
            ('simpanan_pokok', '100000'),
            ('simpanan_wajib', '50000')
        ''')
    
    profile_defaults = {
        'nama_koperasi': 'Koperasi Sejahtera',
        'tagline_koperasi': '',
        'alamat_koperasi': '',
        'kota_koperasi': '',
        'telepon_koperasi': '',
        'email_koperasi': '',
        'website_koperasi': '',
        'logo_koperasi': '',
    }
    for setting_key, setting_value in profile_defaults.items():
        db.execute('INSERT OR IGNORE INTO pengaturan (key, value) VALUES (?, ?)', (setting_key, setting_value))
    db.commit()

class User(UserMixin):
    def __init__(self, id, username, role, anggota_id=None):
        self.id = id
        self.username = username
        self.role = role
        self.anggota_id = anggota_id

def get_koperasi_profile():
    rows = get_db().execute("SELECT key, value FROM pengaturan WHERE key LIKE '%_koperasi'").fetchall()
    values = {row['key']: row['value'] for row in rows}
    return {
        'nama': values.get('nama_koperasi') or 'Koperasi Sejahtera',
        'tagline': values.get('tagline_koperasi') or '',
        'alamat': values.get('alamat_koperasi') or '',
        'kota': values.get('kota_koperasi') or '',
        'telepon': values.get('telepon_koperasi') or '',
        'email': values.get('email_koperasi') or '',
        'website': values.get('website_koperasi') or '',
        'logo': values.get('logo_koperasi') or '',
    }

def get_user_by_id(user_id):
    db = get_db()
    user = db.execute('''
        SELECT u.*, a.id AS anggota_id
        FROM users u LEFT JOIN anggota a ON a.user_id = u.id
        WHERE u.id = ?
    ''', (user_id,)).fetchone()
    if user:
        return User(user['id'], user['username'], user['role'], user['anggota_id'])
    return None

def authenticate_user(username, password):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if user and check_password_hash(user['password'], password):
        anggota = db.execute('SELECT id FROM anggota WHERE user_id = ?', (user['id'],)).fetchone()
        return User(user['id'], user['username'], user['role'], anggota['id'] if anggota else None)
    return None
