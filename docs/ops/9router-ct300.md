# 9Router di CT 300

Instalasi 9Router dari source resmi, berjalan headless lewat pm2. Dikerjakan di OPS-001 (28 September 2026).

## Ringkasan

| Item | Nilai |
|---|---|
| Host | CT 300, `10.10.10.30`, user `router` (tanpa sudo). Akses: `ssh ct300` |
| Source | https://github.com/decolua/9router, tag **v0.5.91** (commit `f01fb90`, 26 September 2026) |
| Direktori aplikasi | `/home/router/9router` (checkout tag, detached HEAD) |
| Data (`DATA_DIR`) | `/home/router/.9router` |
| Database | `/home/router/.9router/db/data.sqlite`: SQLite mode WAL, driver `better-sqlite3` |
| Runtime | Node 22.23.3, npm 10.9.9, pm2 7.0.4, Next.js 16.3.6 |
| Port | `20128` (bind `*`, yaitu semua interface IPv4 dan IPv6) |
| Dashboard | `http://10.10.10.30:20128/dashboard` |
| API OpenAI-compatible | `http://10.10.10.30:20128/v1` |
| Proses | pm2, nama `9router` |
| Lockfile | `~/9router/package-lock.json` (di-gitignore upstream), arsip di `~/9router-locks/package-lock.<tag>.json` |

Isi `~/.9router`:

```
.9router/
├── db/
│   ├── data.sqlite     # database utama (provider, akun, API key, combo, setting, usage)
│   └── backups/        # backup otomatis 9Router, hanya dibuat sebelum migrasi skema (maks. 3)
├── jwt-secret          # secret session dashboard
├── machine-id          # tertanam di API key 9Router (sk-{machineId}-{keyId}-{crc})
└── logs/
```

`machine-id` **wajib ikut di-backup**: API key yang sudah dibagikan memuat machine-id dan CRC-nya. Kalau file ini hilang, key lama tidak valid lagi. `jwt-secret` juga ikut di-backup; kalau hilang, efeknya hanya semua sesi dashboard logout.

## Perbedaan dengan README v0.5.91

1. **`npm ci` tidak bisa dipakai** karena upstream tidak menyertakan `package-lock.json` (file itu ada di `.gitignore`). Kita memakai `npm install` sesuai README, lalu menyimpan lockfile hasilnya.
2. **`PORT` di env diabaikan.** Script `start` isinya `node custom-server.js --port 20127`, lalu diteruskan ke `next start --port 20127`, dan flag CLI menang atas env. README menyuruh `PORT=20128 ... npm run start`, tapi hasilnya tetap listen di 20127 (sudah dibuktikan). Solusinya: tambahkan flag `-- --port 20128`.
3. **`HOSTNAME=0.0.0.0` tidak berpengaruh** pada `next start`. Server bind ke `*` (dual-stack), jadi port juga terbuka di IPv6. Firewall CT 300 (PRD §11) harus memfilter IPv4 **dan** IPv6.
4. README production memakai `sudo fallocate` untuk swap sementara 2 GB. Langkah ini tidak diperlukan: build dengan RAM 4 GB memakai puncak ±2,0 GB RSS, selesai dalam 43 detik, dan swap tidak terpakai.
5. Sebagian README dan tabel env masih menyebut `db.json`. Sejak v0.5.x datanya ada di `DATA_DIR/db/data.sqlite` (lihat `DOCKER.md` dan `src/lib/db/`).
6. README menyebut runtime server memprioritaskan `BASE_URL` di atas `NEXT_PUBLIC_BASE_URL`, jadi keduanya diisi.
7. Saat `start`, Next memberi peringatan `"next start" does not work with "output: standalone"`. Aplikasi tetap berjalan normal karena memang begini alur resmi `custom-server.js` untuk checkout repo.

## Instalasi (yang dijalankan)

```bash
ssh ct300
cd ~
git clone https://github.com/decolua/9router.git 9router
cd 9router
git checkout v0.5.91
npm install --no-audit --no-fund          # better-sqlite3 memakai prebuilt binary (tidak ada make/g++)
npm run build
mkdir -p ~/9router-locks && cp package-lock.json ~/9router-locks/package-lock.v0.5.91.json
```

`.env` (mode 600, di-gitignore upstream). Password diambil dari file tanpa ditampilkan:

```bash
cd ~/9router
umask 077
{
  printf 'PORT=20128\nHOSTNAME=0.0.0.0\n'
  printf 'NEXT_PUBLIC_BASE_URL=http://10.10.10.30:20128\nBASE_URL=http://10.10.10.30:20128\n'
  printf 'DATA_DIR=/home/router/.9router\n'
  printf 'INITIAL_PASSWORD=%s\n' "$(cat ~/.9router-initial-password)"
} > .env
chmod 600 .env
cut -d= -f1 .env      # tampilkan nama key saja
```

Catatan: Next memproses `.env` dengan dotenv-expand, jadi password tidak boleh mengandung `$`, `#`, kutip, atau spasi. Password saat ini sudah dicek aman.

pm2:

```bash
cd ~/9router
pm2 start npm --name 9router -- start -- --port 20128
pm2 save
pm2 startup systemd      # hanya mencetak perintah; tidak dijalankan oleh user router
```

Perintah yang harus dijalankan **root** oleh pemilik agar pm2 hidup lagi setelah reboot:

```bash
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u router --hp /home/router
```

Instalasi ini tidak menambahkan provider, akun, maupun API key. Semua itu diisi pemilik lewat dashboard.

## Verifikasi

```bash
ssh ct300 'ss -ltnp | grep 20128'                                         # LISTEN *:20128
curl -s -o /dev/null -w '%{http_code}\n' http://10.10.10.30:20128/          # 307 -> /dashboard -> /login
curl -s -o /dev/null -w '%{http_code}\n' http://10.10.10.30:20128/v1/models # 401 (belum ada key)
ssh ct300 'pm2 restart 9router && sleep 10 && pm2 ls && ss -ltnp | grep 20128'
```

## Update ke rilis baru

1. **Backup dulu** (lihat bagian berikut), termasuk `machine-id` dan `jwt-secret`.
2. Cek tag baru dan perubahannya:
   ```bash
   cd ~/9router
   git fetch --tags
   git tag --sort=-v:refname | head -5
   git diff v0.5.91 <tag-baru> -- README.md .env.example package.json custom-server.js
   ```
   Perhatikan: script `start` (apakah port masih di-hardcode), env baru, dan versi Node yang dibutuhkan. Baca juga `CHANGELOG.md`.
3. Checkout, install, build (proses lama tetap melayani selama build):
   ```bash
   git checkout <tag-baru>
   npm install --no-audit --no-fund
   npm run build 2>&1 | tee ~/9router-build.log
   cp package-lock.json ~/9router-locks/package-lock.<tag-baru>.json
   ```
   Kalau build gagal, **jangan restart**. Kembalikan dengan `git checkout v0.5.91`, lalu `cp ~/9router-locks/package-lock.v0.5.91.json package-lock.json && npm ci && npm run build`.
4. `pm2 restart 9router`, lalu jalankan verifikasi di atas. 9Router otomatis menjalankan migrasi skema saat start, dan sebelumnya menyimpan backup di `~/.9router/db/backups/`.
5. Rollback setelah restart: checkout tag lama, `npm ci` dengan lockfile arsip, build, `pm2 stop 9router`, restore database dari backup sebelum update (karena skema mungkin sudah bermigrasi), lalu `pm2 start 9router`.
6. Perbarui tag di dokumen ini.

## Backup SQLite

Database memakai WAL, jadi data terbaru bisa masih ada di `data.sqlite-wal` dan belum masuk ke `data.sqlite`. **Jangan `cp data.sqlite` saat 9Router berjalan.** Salinan seperti itu bisa tidak konsisten atau kehilangan transaksi terakhir. Gunakan online backup API SQLite: API ini membaca snapshot yang konsisten (termasuk isi WAL) tanpa menghentikan aplikasi.

CLI `sqlite3` **tidak terpasang** di CT 300 (dan tidak bisa dipasang tanpa sudo), jadi backup memakai `node:sqlite` bawaan Node 22:

```bash
ssh ct300
mkdir -p ~/backups/9router && chmod 700 ~/backups ~/backups/9router
TS=$(date +%Y%m%d-%H%M%S); OUT=~/backups/9router/$TS; mkdir -m 700 "$OUT"
node --no-warnings -e '
const { DatabaseSync, backup } = require("node:sqlite");
const [src, dst] = process.argv.slice(1);
const db = new DatabaseSync(src, { readOnly: true });
backup(db, dst).then(() => {
  const b = new DatabaseSync(dst, { readOnly: true });
  const r = b.prepare("PRAGMA integrity_check").get().integrity_check;
  console.log("integrity_check:", r);
  if (r !== "ok") process.exit(1);
});' /home/router/.9router/db/data.sqlite "$OUT/data.sqlite"
cp -p ~/.9router/machine-id ~/.9router/jwt-secret "$OUT/"
chmod 600 "$OUT"/*
```

Alternatif yang setara jika `sqlite3` tersedia (misalnya di mesin lain):
`sqlite3 /home/router/.9router/db/data.sqlite ".backup '/path/data.sqlite'"`, atau `VACUUM INTO '/path/data.sqlite'`.

Prosedur ini sudah diuji di OPS-001: `integrity_check: ok`, 12 tabel.

Catatan keamanan:
- Backup berisi token OAuth dan API key provider. Simpan dengan izin 600/700, salin ke disk lain (PRD §12), dan jangan pernah commit.
- `vzdump` mingguan CT 300 (PRD §12) tetap jalan sebagai lapisan kedua. Backup file di atas untuk restore cepat dan sebelum update.
- Folder `db/backups/` milik 9Router hanya dibuat sebelum migrasi dan sengaja tidak memuat tabel `requestDetails`. Folder itu bukan pengganti backup ini.
- Observability 9Router (`requestDetails`, menyimpan potongan request/response) default **mati** (`enableObservability: false`). Biarkan mati agar isi prompt tidak tersimpan di CT 300 maupun di backup (sejalan dengan PRD §4.3 poin 4).

## Restore

```bash
ssh ct300
BK=~/backups/9router/<timestamp>
pm2 stop 9router
cd ~/.9router/db
PRE=~/backups/9router/pre-restore-$(date +%Y%m%d-%H%M%S); mkdir -m 700 -p "$PRE"
mv data.sqlite data.sqlite-wal data.sqlite-shm "$PRE"/ 2>/dev/null
cp "$BK/data.sqlite" data.sqlite
cp -p "$BK/machine-id" "$BK/jwt-secret" ~/.9router/
pm2 start 9router
```

Wajib: file `-wal` dan `-shm` lama dipindahkan atau dihapus sebelum start. WAL milik database lama yang tertinggal bisa merusak database hasil restore. Setelah start, jalankan verifikasi di atas dan login ke dashboard untuk mengecek provider dan key.
