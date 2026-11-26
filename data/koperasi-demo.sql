BEGIN TRANSACTION;
CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','anggota')), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
INSERT INTO users(id,username,password,role) VALUES (1,'admin','scrypt:32768:8:1$demo$REPLACE_AFTER_IMPORT','admin');
INSERT INTO users(id,username,password,role) VALUES (2,'superadmin','scrypt:32768:8:1$demo$REPLACE_AFTER_IMPORT','admin');
COMMIT;
