# CLAUDE.md — Atheena AI Gateway

## Wajib dibaca sebelum bekerja
1. `PRD.md` — acuan utama. Semua keputusan arsitektur dan kebutuhan (FR-x.x) ada di sana.
2. File task yang sedang dikerjakan di `tasks/`.

Jika instruksi task bertentangan dengan PRD, PRD yang berlaku, kecuali task secara eksplisit menyatakan mengubah PRD. Jika PRD ambigu atau diam, pakai default PRD §15 bila ada dan catat di `docs/progress.md`; jika tidak ada default dan keputusannya berisiko bertentangan dengan PRD, tanya dulu. Jangan mengarang.

## Cara bekerja
- Kerjakan task **satu per satu, berurutan**. Jangan menambah fitur di luar scope task, sekecil apa pun.
- Kerjakan secara **otonom**. Tulis rencana singkat tiap task di `tasks/TASK-xxx.md` (file yang dibuat/diubah, urutan kerja, cara verifikasi), lalu langsung eksekusi.
- Berhenti dan tanya **hanya** jika: butuh secret atau kredensial yang tidak ada, keputusan bertentangan dengan PRD, atau aksi tak bisa dibatalkan di luar repo.
- Keputusan terbuka: pakai default PRD §15 dan catat di `docs/progress.md`.
- Gerbang kualitas tiap task (wajib sebelum lanjut ke task berikutnya): `make test` dan `make lint` hijau, commit kecil-kecil, push.
- Commit kecil dan sering. Pesan commit dalam bahasa Inggris, format `type(scope): ringkasan` (misal `feat(proxy): stream passthrough`).
- Task dianggap selesai hanya dengan **bukti**: output test yang lulus + langkah reproduksi manual. Laporan "sudah selesai" tanpa bukti tidak diterima.
- Di akhir task, tulis ringkasan ke `docs/progress.md`: apa yang dikerjakan, keputusan yang diambil, dan hal yang ditunda.

## Bahasa
- Komunikasi dengan pemilik: Bahasa Indonesia.
- Kode, komentar, nama variabel, pesan commit: bahasa Inggris.
- Teks yang tampil ke pengguna di UI: Bahasa Indonesia.

## Aturan keras
- **Jangan pernah** mencatat isi prompt atau response model ke database, log, maupun pesan error (PRD §4.3 poin 4).
- **Jangan pernah** commit secret. Semua secret lewat `.env` (di-gitignore); contoh di `.env.example` dengan nilai palsu.
- Setiap logika yang menyentuh uang (hitung biaya, potong saldo, ledger) **wajib** punya test, termasuk test konkurensi.
- Ledger append-only: tidak ada UPDATE/DELETE pada `ledger_entries`.
- Portal harus stateless: state bersama di Postgres/Redis, bukan di memori proses.
- Test tidak boleh memanggil provider AI sungguhan; gunakan fake upstream. Pemanggilan ke 9Router sungguhan hanya untuk verifikasi manual yang disebut eksplisit di task, dan hanya dengan model murah.

## Lingkungan
- Development berjalan di VM 999 (agent-hub) sebagai user `agent` tanpa sudo.
- Docker berjalan dalam mode rootless (`DOCKER_HOST=unix:///run/user/<uid>/docker.sock`).
- Satu-satunya alamat jaringan internal yang bisa dijangkau: 9Router di `http://10.10.10.13:3000` (upstream development). Alamat internal lain memang diblokir firewall; jangan mencoba mengakalinya.
- Internet tersedia (GitHub, Docker Hub, npm, PyPI).
- Postgres 16 dan Redis 7 berjalan native (systemd) di VM 999, bukan Docker. Database `atheena` dan `atheena_test` milik user `agent`, koneksi unix socket tanpa password: `postgresql+asyncpg://agent@/atheena?host=/var/run/postgresql`. Redis di `127.0.0.1:6379`. Tidak ada Docker di VM ini; `docker-compose.dev.yml` tetap dibuat untuk CI dan server, tapi `make dev` di VM ini cukup mengecek kedua service.
- Server deploy: CT 301 (`ssh ct301`, user `deploy`, Docker tersedia, direktori /opt/atheena). Hanya dipakai saat task meminta deploy. CT 300 (9Router) tidak boleh diakses.


## Stack (PRD §9.1)
Python 3.12 · FastAPI · uvicorn · httpx (async) · SQLAlchemy 2 + Alembic · PostgreSQL 16 · Redis 7 · React + Vite + TypeScript · Caddy · Docker Compose.

## Skill
`frontend-design`, `ui-ux-pro-max`, `web-design-guidelines`, dan `r3f-*` tersedia. Gunakan hanya saat mengerjakan UI (Tahap 4 ke atas). Arah desain ada di PRD §10. Jangan jalankan script skill yang butuh API key pihak ketiga (Gemini, Google Fonts) atau yang mengunduh aset dari internet tanpa izin.
