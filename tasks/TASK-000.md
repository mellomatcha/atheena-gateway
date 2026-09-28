# TASK-000 — Fondasi repo dan lingkungan development

Referensi PRD: §4.3, §7, §9.1, §14 Tahap 0A.

## Tujuan
Repo siap dikembangkan: struktur monorepo, stack development berjalan di VM 999, skema database lengkap, test dan CI jalan. **Belum ada logika proxy** (itu TASK-001).

## Prasyarat (sudah disiapkan pemilik)
- Docker rootless aktif untuk user `agent`.
- Repo GitHub privat `atheena-gateway`, bisa di-push oleh `agent` lewat deploy key.
- `PRD.md`, `RINGKASAN.md`, `CLAUDE.md`, dan `tasks/` sudah ada di root repo.
- API key 9Router untuk development diisi manual oleh pemilik ke `.env` (tidak pernah di-commit).

## Scope
1. **Struktur repo**
   ```
   backend/                FastAPI app, Alembic, tests
   frontend/               Vite + React + TS (skeleton kosong)
   deploy/                 docker-compose.yml produksi + Caddyfile (placeholder, diberi TODO)
   docs/progress.md
   tasks/
   docker-compose.dev.yml  Postgres 16 + Redis 7 untuk development
   Makefile
   .env.example
   ```
2. **Backend skeleton**
   - Konfigurasi lewat environment (pydantic-settings): `DATABASE_URL`, `REDIS_URL`, `UPSTREAM_BASE_URL` (default `http://10.10.10.13:3000/v1`), `UPSTREAM_API_KEY`, `APP_ENV`, `SEED_ADMIN_EMAIL`.
   - `GET /healthz` → 200 selama proses hidup.
   - `GET /readyz` → cek Postgres, Redis, dan upstream (`GET {UPSTREAM_BASE_URL}/models` dengan key upstream); status per komponen, 503 jika ada yang gagal.
   - Logging JSON terstruktur dengan `request_id`.
3. **Database**
   - Model SQLAlchemy 2 dan migrasi Alembic awal untuk **semua tabel PRD §7**, termasuk indeks minimum. Tabel `requests` dipartisi per bulan (atau ditandai TODO yang jelas beserta alasannya).
   - Trigger database yang menolak UPDATE/DELETE pada `ledger_entries`.
   - Seed script (`make seed`): admin dari `SEED_ADMIN_EMAIL`, satu member contoh, project `helios` (`official_only = true`), settings default PRD §15, dan 2-3 model murah dari 9Router sebagai katalog awal (harga Rp 0, nama publik tanpa prefix provider sesuai FR-4.0).
4. **Kualitas**
   - pytest + pytest-asyncio; test memakai database terpisah.
   - ruff (lint + format), mypy untuk `backend/`.
   - `Makefile`: `dev`, `down`, `migrate`, `seed`, `test`, `lint`, `run`.
   - GitHub Actions: lint + test dengan Postgres dan Redis sebagai service container.
5. **Frontend**: hanya skeleton Vite (React + TS) yang bisa `npm run build`. Belum ada halaman.

## Di luar scope
Proxy, autentikasi Cloudflare, API key user, dashboard, deployment ke CT 301.

## Selesai jika (bukti wajib dilampirkan)
- `make dev && make migrate && make seed` berhasil dari clone bersih.
- `make test` lulus, termasuk test untuk `/healthz`, `/readyz` (juga saat upstream mati), dan trigger penolak UPDATE/DELETE ledger.
- `make lint` bersih.
- `curl localhost:8000/readyz` menunjukkan Postgres, Redis, dan 9Router sungguhan **sehat**.
- CI hijau di GitHub.
- `git grep -n -i -E "sk-[a-z0-9]|password="` hanya menemukan contoh palsu di `.env.example`.
- `docs/progress.md` terisi.
