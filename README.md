# Koperasi - Sistem Manajemen Koperasi

Sistem manajemen koperasi berbasis web dengan Flask, mendukung pengelolaan anggota, simpanan, pinjaman, dan laporan keuangan.

## Fitur

- **Manajemen Anggota**: Pendaftaran, edit profil, status keanggotaan
- **Simpanan**: Jenis simpanan kustom (wajib, pokok, sukarela), setor/tarik
- **Pinjaman**: Jenis pinjaman kustom (pembelian barang, emergency, pendidikan), pengajuan, persetujuan, dan cicilan
- **Laporan**: Export CSV/Excel per kategori dan multi-sheet, dashboard keuangan
- **Role-based Access**: Admin dan Anggota dengan permission berbeda
- **Responsive UI**: Mobile-first design dengan Tailwind CSS

## Tech Stack

- **Backend**: Flask (Python 3)
- **Database**: SQLite
- **Frontend**: Tailwind CSS, Alpine.js
- **Export**: CSV, Excel (openpyxl)

## Struktur Direktori

```
.
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # Database models & schema
│   └── routes/              # Route blueprints
│       ├── anggota.py       # Member management
│       ├── auth.py          # Login, settings, loan/savings types
│       ├── dashboard.py     # Dashboard
│       ├── laporan.py       # Reports & exports
│       ├── pinjaman.py      # Loan management
│       ├── simpanan.py      # Savings management
│       └── transaksi.py     # Transactions
├── static/
│   ├── css/                 # Custom CSS
│   ├── js/                  # Frontend JS
│   └── uploads/             # User uploads
├── templates/               # Jinja2 templates
├── requirements.txt         # Python dependencies
└── server.py                # Entry point
```

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python3 -c "from app import create_app; app = create_app(); app.app_context().push(); from app.models import init_db; init_db()"
```

Database akan dibuat di `data/koperasi.db` dengan:
- Tabel: `anggota`, `simpanan`, `pinjaman`, `angsuran`, `transaksi_simpanan`, `jenis_simpanan`, `jenis_pinjaman`, `profil_koperasi`
- Admin default: `admin` / `123456`
- Jenis simpanan default: Wajib, Pokok, Sukarela
- Jenis pinjaman default: Pembelian barang, Emergency, Dana pendidikan

### 3. Run Server

```bash
# Development
python3 server.py

# Production (recommended: gunicorn)
gunicorn -w 4 -b 0.0.0.0:8290 "app:create_app()"
```

Aplikasi berjalan di `http://localhost:8290`

## Deployment

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name koperasi.yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8290;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Systemd Service

```ini
[Unit]
Description=Sistem Koperasi
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/koperasi
Environment="PATH=/opt/koperasi/venv/bin"
ExecStart=/opt/koperasi/venv/bin/python3 /opt/koperasi/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Keamanan

Jangan commit database produksi, file environment, kredensial, token, atau file upload yang bersifat privat. Buat akun administrator dan password yang kuat saat instalasi, lalu ganti kredensial default sebelum aplikasi digunakan di production.

## License

MIT

## Contributing

Pull requests welcome. Untuk perubahan besar, buka issue terlebih dahulu.
