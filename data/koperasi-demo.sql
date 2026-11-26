BEGIN TRANSACTION;
CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','anggota')), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
INSERT INTO users(id,username,password,role) VALUES (1,'admin','scrypt:32768:8:1$PNB9p9sbowpCthwx$ce6dd08e8534a3d97b1de9ad23f53d33e83ad4d2162b07ec04524dbf23e56e0c0f94819457ec18f81579b6dddb6140a30aa737b2922b041dd41a9ffc7ff60721','admin');
INSERT INTO users(id,username,password,role) VALUES (2,'superadmin','scrypt:32768:8:1$PNB9p9sbowpCthwx$ce6dd08e8534a3d97b1de9ad23f53d33e83ad4d2162b07ec04524dbf23e56e0c0f94819457ec18f81579b6dddb6140a30aa737b2922b041dd41a9ffc7ff60721','admin');
COMMIT;
