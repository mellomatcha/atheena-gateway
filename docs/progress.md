# Progress

## TASK-000 — Fondasi repo dan lingkungan development

**Status: sebagian besar selesai; menunggu 3 hal dari pemilik (lihat "Belum selesai").**
Tanggal: 28 September 2026.

### Yang dikerjakan
- **Repo**: git lokal (`main`) terhubung ke `git@github.com:mellomatcha/atheena-gateway.git`, struktur monorepo `backend/`, `frontend/`, `deploy/`, `docs/`, `tasks/`.
- **Backend** (`backend/app/`):
  - Konfigurasi via pydantic-settings: `DATABASE_URL`, `REDIS_URL`, `UPSTREAM_BASE_URL` (default `http://10.10.10.13:3000/v1`), `UPSTREAM_API_KEY`, `APP_ENV`, `SEED_ADMIN_EMAIL`. File `.env` dibaca dari root repo.
  - `GET /healthz` → 200.
  - `GET /readyz` → cek Postgres (`SELECT 1`), Redis (`PING`), upstream (`GET {UPSTREAM_BASE_URL}/models` dengan key upstream), paralel, timeout 5 detik per cek; 503 jika ada yang gagal. Pesan error hanya berisi tipe exception atau kode HTTP, tidak pernah body upstream.
  - Logging JSON ke stdout, satu baris akses per request, dengan `request_id` UUID v7 yang juga dikembalikan di header `X-Request-Id`. Tidak ada body yang dilog.
- **Database**: model SQLAlchemy 2 dan migrasi Alembic `0001` untuk semua tabel PRD §7, termasuk `usage_daily`.
  - Indeks minimum §7 lengkap.
  - `requests` dipartisi per bulan (batas UTC); fungsi SQL `create_requests_partition(date)`; migrasi membuat bulan ini + 3 bulan ke depan + partisi `requests_default`.
  - Trigger `ledger_entries`: menolak UPDATE, DELETE (per baris) dan TRUNCATE (per statement).
  - Constraint uang: tanda `amount_idr` sesuai jenis (topup/refund > 0, usage ≤ 0), adjustment wajib catatan, harga model ≥ 0.
- **Seed** (`make seed`, idempoten, tidak menimpa perubahan admin): admin dari `SEED_ADMIN_EMAIL` (role admin, tier advanced, aktif), `member.contoh@example.com` (basic, aktif), project `helios` (`official_only = true`), settings default §15.
- **Kualitas**: pytest + pytest-asyncio (DB `atheena_test`, Redis db 15, upstream palsu via respx), ruff (lint + format), mypy strict. 26 test.
- **Makefile**: `dev`, `down`, `migrate`, `seed`, `test`, `lint`, `run`, plus `install`, `fmt`, `frontend`, `lock`.
- **CI** (`.github/workflows/ci.yml`): job backend (service postgres:16 + redis:7 → lint + test) dan job frontend (npm ci → lint → build).
- **Frontend**: skeleton Vite + React + TS (tanpa halaman), build dan lint bersih.
- **Deploy**: `deploy/docker-compose.yml` dan `deploy/Caddyfile` sebagai placeholder dengan TODO.

### Keputusan yang diambil
- **Tidak ada FK `ledger_entries.request_id` → `requests`** (disetujui pemilik). Postgres mewajibkan setiap unique key/PK pada tabel berpartisi memuat kolom partisi (`started_at`), sehingga FK harus berupa `(request_id, started_at)`. Menambah `started_at` ke ledger hanya demi FK dinilai tidak sepadan. Kolom tetap UUID berindeks; konsistensi dijaga oleh transaksi tunggal di FR-3.21 (TASK-001).
- **PK `requests` = `(id, started_at)`** dan unique `(request_id, started_at)`, karena alasan yang sama.
- **`requests.user_id` dan `api_key_id` nullable**: FR-3.22 mewajibkan request 401 tetap dicatat, padahal saat itu user/key belum diketahui. `model_id` juga nullable untuk model yang tidak dikenal.
- **Partisi**: migrasi hanya membuat 4 bulan. `requests_default` menampung sisanya. Job `worker` wajib membuat partisi bulan berikutnya sebelum bulan itu tiba (TODO di migrasi), karena partisi baru tidak bisa dibuat selama `requests_default` berisi baris pada rentang itu.
- **Status/peran/tipe sebagai `TEXT` + `CHECK`**, bukan enum Postgres, agar mudah diubah lewat migrasi.
- **`ledger_entries.updated_at` tetap ada** (disetujui); nilainya selalu sama dengan `created_at` karena trigger.
- **Email user disimpan lowercase** (CHECK `email = lower(email)`).
- **Python tooling**: venv + pip, versi dipin persis. `backend/requirements.lock` berisi seluruh dependensi (langsung + transitif). VM 999 tidak punya `python3.12-venv` dan tidak ada sudo, jadi Makefile otomatis membuat venv tanpa pip lalu memasang pip lewat pip sistem.
- **Frontend**: versi npm dipin persis (`.npmrc save-exact`); template Vite sekarang memakai oxlint, bukan ESLint.
- **`make dev` di VM 999** hanya mengecek Postgres dan Redis native. `make dev USE_DOCKER=1` menyalakan `docker-compose.dev.yml` untuk mesin lain.
- **Git author** untuk repo ini diset ke email pemilik (config lokal repo), karena `user.email` global berisi placeholder.

### Belum selesai / ditunda
1. **Katalog model di seed**: `SEED_MODELS` masih kosong. Menunggu `.env` berisi `UPSTREAM_API_KEY` agar daftar model 9Router bisa diambil, lalu pilihan 2-3 model ditunjukkan ke pemilik sebelum dimasukkan.
2. **`/readyz` terhadap 9Router sungguhan**: saat ini Postgres dan Redis sehat, upstream gagal karena `UPSTREAM_API_KEY` belum diisi (503 `UPSTREAM_API_KEY is not set`).
3. **CI hijau**: terkonfirmasi pemilik (run #3, commit d304053).
4. **`make seed` penuh** belum dijalankan ke DB dev, karena `SEED_ADMIN_EMAIL` ada di `.env` yang belum dibuat.
5. **Rate limit per user**: diputuskan pemilik 120 request/menit (2x per key), disimpan di settings `rate_limit_per_user_per_minute`.
6. Di luar scope: `pip-audit`/`npm audit` di CI (Tahap 6), job worker untuk partisi dan agregasi.

### Cara reproduksi
```bash
git clone git@github.com:mellomatcha/atheena-gateway.git && cd atheena-gateway
cp .env.example .env   # isi UPSTREAM_API_KEY dan SEED_ADMIN_EMAIL
make dev && make migrate && make seed
make test && make lint
make run   # terminal lain: curl -s localhost:8000/readyz
```
