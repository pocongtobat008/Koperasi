# Konfigurasi dan import database

Aplikasi memakai SQLite pada `data/koperasi.db`.

## Demo login

Database demo kosong dari data anggota dan transaksi. Akun awal:

- `admin` / `123456`
- `superadmin` / `123456`

Segera ganti password setelah login. Password disimpan sebagai hash Werkzeug.

## Import

```bash
mkdir -p data
cp data/koperasi.db data/koperasi.db.backup.$(date +%Y%m%d-%H%M%S) 2>/dev/null || true
sqlite3 data/koperasi.db < data/koperasi-demo.sql
python - <<'PY'
import sqlite3
con = sqlite3.connect('data/koperasi.db')
print(con.execute('PRAGMA integrity_check').fetchone()[0])
PY
```

Output harus `ok`. Jangan commit database produksi, backup, `.env`, log, session, atau kredensial.
