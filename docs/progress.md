# Progress

## TASK-000 — Fondasi repo dan lingkungan development

**Status: selesai** (bukti di bagian "Bukti selesai").
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
- **Seed** (`make seed`, idempoten, tidak menimpa perubahan admin): admin dari `SEED_ADMIN_EMAIL` (role admin, tier advanced, aktif), `member.contoh@example.com` (basic, aktif), project `helios` (`official_only = true`), settings default §15 (ditambah rate limit per user 120/menit), dan katalog development 3 model (lihat Keputusan).
- **Kualitas**: pytest + pytest-asyncio (DB `atheena_test`, Redis db 15, upstream palsu via respx), ruff (lint + format), mypy strict. 27 test.
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
- **Python tooling**: venv + pip, versi dipin persis. `backend/requirements.lock` berisi seluruh dependensi (langsung + transitif). Makefile memakai `python3.12 -m venv` standar (sekarang `python3.12-venv` terpasang di VM 999); jalur cadangan (venv tanpa pip + pip sistem) tetap ada untuk mesin tanpa paket itu.
- **Frontend**: versi npm dipin persis (`.npmrc save-exact`); template Vite sekarang memakai oxlint, bukan ESLint.
- **`make dev` di VM 999** hanya mengecek Postgres dan Redis native. `make dev USE_DOCKER=1` menyalakan `docker-compose.dev.yml` untuk mesin lain.
- **Katalog development** (disetujui pemilik): semua model di 9Router CT 110 adalah CodeBuddy (`cb/`), jadi ketiganya `experimental`, provider `codebuddy`, tier `basic`, aktif, harga Rp 0, `context_window` null (tidak diberikan upstream).

  | Nama publik | ID upstream |
  |---|---|
  | `claude-haiku-4.5-exp` | `cb/claude-haiku-4.5` |
  | `gemini-3.1-flash-lite` | `cb/gemini-3.1-flash-lite` |
  | `glm-4.6` | `cb/glm-4.6` |

  Claude diberi akhiran `-exp` agar nama tanpa akhiran tersedia untuk sumber Anthropic resmi (FR-4.0). `api_format = both` untuk ketiganya karena 9Router menerjemahkan format; kebenarannya dibuktikan di verifikasi manual TASK-001. Karena semuanya `experimental`, project `helios` akan menolak ketiganya (sesuai FR-3.10). Katalog produksi diisi setelah 9Router CT 300 siap.
- **Rate limit per user**: 120 request/menit (2x per key), diputuskan pemilik, disimpan di settings `rate_limit_per_user_per_minute`.
- **Git author** untuk repo ini diset ke email pemilik (config lokal repo), karena `user.email` global berisi placeholder.

### Ditunda (di luar scope TASK-000)
- Job `worker`: pembuatan partisi `requests` bulanan dan agregasi `usage_daily`.
- `pip-audit` / `npm audit` di CI (Tahap 6).
- Katalog produksi dan model OpenAgentic: setelah 9Router CT 300 siap.
- Verifikasi `api_format = both` untuk model `cb/`: manual di TASK-001.

### Bukti selesai (28 September 2026, VM 999)
- `rm -rf backend/.venv && make dev`: venv standar dibuat, `postgres: ok`, `redis: ok`.
- `make migrate`: DB dev `atheena` di revisi `0001 (head)`. Migrasi dari nol sudah dibuktikan di clone bersih sebelumnya, dan `test_downgrade_and_upgrade_roundtrip` menjalankan downgrade → upgrade → `alembic check` di setiap `make test`.
- `make seed` dijalankan dua kali: `Seed complete: admin <SEED_ADMIN_EMAIL>, 3 catalog models`. Isi DB: 2 user, project `helios` (`official_only = t`), 3 model, 8 settings. Tidak ada duplikat.
- `make test`: 27 passed. `make lint`: ruff, format, dan mypy (24 file) bersih.
- `curl localhost:8000/readyz` → HTTP 200:
  `{"status":"ok","checks":{"postgres":{"ok":true,...},"redis":{"ok":true,...},"upstream":{"ok":true,...}}}`
  Log akses JSON memuat `request_id` yang sama dengan header `X-Request-Id`; tidak ada body maupun key di log.
- CI GitHub hijau (run #3, `d304053`, dikonfirmasi pemilik).
- `git grep -n -i -E "sk-[a-z0-9]|password="`: hanya false positive (`ta`**`sk-0`**`00` di nama task, format `sk-ath-` di PRD). Tidak ada secret; `.env` di-gitignore.

### Cara reproduksi
```bash
git clone git@github.com:mellomatcha/atheena-gateway.git && cd atheena-gateway
cp .env.example .env   # isi UPSTREAM_API_KEY dan SEED_ADMIN_EMAIL
make dev && make migrate && make seed
make test && make lint
make run   # terminal lain: curl -s localhost:8000/readyz
```
