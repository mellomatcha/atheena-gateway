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

## OPS-001 — Install 9Router fresh di CT 300

Selesai 28 September 2026. Detail operasional: `docs/ops/9router-ct300.md`.

### Yang dikerjakan
- Clone `decolua/9router` ke `/home/router/9router`, checkout tag `v0.5.91` (`f01fb90`), `npm install`, `npm run build` (puncak RSS ±2,0 GB, 43 detik, swap tidak terpakai).
- `.env` mode 600: `PORT`, `HOSTNAME`, `NEXT_PUBLIC_BASE_URL`, `BASE_URL`, `DATA_DIR`, `INITIAL_PASSWORD` (diisi dari `~/.9router-initial-password` di sisi server, tidak pernah ditampilkan).
- pm2: `pm2 start npm --name 9router -- start -- --port 20128`, lalu `pm2 save`.
- Prosedur backup online SQLite lewat `node:sqlite` diuji (`integrity_check: ok`). Lockfile diarsipkan di `~/9router-locks/`.
- Dokumen ops ditulis; PRD §9.2, §12, dan R11 diperbarui.
- Tidak ada provider, akun, atau key yang ditambahkan. Tidak ada perubahan di luar `/home/router`.

### Keputusan yang diambil (disetujui pemilik)
- **Tag v0.5.91**, bukan v0.5.35. v0.5.35 adalah GitHub Release "latest", tapi tag terbarunya v0.5.91.
- **`npm install`, bukan `npm ci`**, karena upstream tidak menyertakan `package-lock.json` (ada di `.gitignore` mereka). Lockfile hasil install disimpan.
- **`-- --port 20128`**: script `start` memaksa `--port 20127`, sehingga `PORT` di env diabaikan (terbukti listen di 20127 pada percobaan pertama).
- `BASE_URL` diisi selain `NEXT_PUBLIC_BASE_URL`, karena runtime server memprioritaskan `BASE_URL`.

### Temuan
- `HOSTNAME=0.0.0.0` tidak berpengaruh. Server bind ke `*:20128` (IPv4 dan IPv6), jadi firewall CT 300 harus memfilter keduanya.
- CT 300 tidak punya `sqlite3`, `make`, dan `g++`. `better-sqlite3` tetap jalan memakai prebuilt binary; backup memakai `node:sqlite`.
- `~/.9router` awalnya tidak ada (bukan sekadar kosong). Folder itu dibuat oleh 9Router saat start.
- `machine-id` tertanam di API key 9Router, jadi wajib ikut di-backup.
- Observability 9Router (`requestDetails`, menyimpan potongan request/response) default mati. Harus tetap mati (PRD §4.3).
- `data.sqlite` dan direktori `~/.9router/db` dibuat 9Router dengan izin 644/775 (umask default user `router`).

### Ditunda / perlu tindakan pemilik
- **Root**: `sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u router --hp /home/router` agar pm2 hidup lagi setelah reboot.
- Firewall CT 300 (PRD §11): tutup lagi akses sementara, izinkan hanya CT 301 dan admin, termasuk IPv6.
- Pertimbangkan `chmod 700 ~/.9router` dan `chmod 600 ~/.9router/db/data.sqlite` (di luar scope, belum dilakukan).
- Jadwal backup otomatis (cron) dan penyalinan ke disk lain: tahap ops/runbook.
- CLAUDE.md dan PRD §14 masih menyebut upstream development `10.10.10.13:3000` dan "CT 300 tidak boleh diakses". Perlu diperbarui saat cutover.
- Isi provider dan akun di dashboard, uji CodeBuddy (R11), lalu cutover dari CT 110.

### Bukti selesai (28 September 2026)
- `ssh ct300 'ss -ltnp | grep 20128'` → `LISTEN 0 511 *:20128 *:* users:(("next-server (v1",pid=16725,fd=21))`
- Dari VM 999: `/` → `307` (→ `/dashboard` → `307` → `/login`), `/v1/models` → `401`.
- `pm2 restart 9router` → `online`, ↺ 1, tetap `*:20128`; `/` → `307`, `/v1/models` → `401`.
- `pm2 save` → dump berisi `9router /usr/bin/npm ["start","--","--port","20128"] /home/router/9router`.
- `stat .env` → `600 router`; key: `PORT HOSTNAME NEXT_PUBLIC_BASE_URL BASE_URL DATA_DIR INITIAL_PASSWORD`.
- Log pm2: `Driver: better-sqlite3`; `PRAGMA journal_mode` → `wal`.

### Cara reproduksi
```bash
ssh ct300 'pm2 ls; ss -ltnp | grep 20128'
curl -s -o /dev/null -w '%{http_code}\n' http://10.10.10.30:20128/
curl -s -o /dev/null -w '%{http_code}\n' http://10.10.10.30:20128/v1/models
ssh ct300 'pm2 restart 9router && sleep 10 && ss -ltnp | grep 20128'
```

## TASK-001 — Proxy inti dan pencatatan pemakaian

Selesai 28 September 2026. Satu bagian tertunda: verifikasi manual 3–4 terhadap 9Router sungguhan. Alasannya ada di bawah.

### Yang dikerjakan
- `backend/app/gateway/`: endpoint `GET /v1/models`, `POST /v1/chat/completions`, `POST /v1/messages`.
  - `keys.py`: format `sk-ath-` + 40 base62, hash SHA-256, cache Redis 60 detik, `invalidate_keys` / `invalidate_user_keys` untuk revoke instan.
  - `routes.py`: pemeriksaan berurutan FR-3.3 s.d. 3.10, lalu penerusan.
  - `relay.py`: response class ASGI sendiri. Heartbeat `: ping` untuk stream dan spasi di depan JSON untuk non-stream. Error sebelum commit memakai status HTTP yang benar; setelah commit dikirim di dalam body. Field `model` ditulis ulang ke nama publik, dan event yang tidak dikenali dibuang. Pencatatan tetap jalan walau klien memutus (`asyncio.shield`).
  - `usage.py`: parser usage OpenAI/Anthropic (termasuk cache write/read), estimasi, biaya Rupiah dengan `Decimal` dan pembulatan ke atas.
  - `billing.py`: satu transaksi `SELECT ... FOR UPDATE` → `users.balance_idr` + `ledger_entries` + `requests`.
  - `limits.py`: rate limit per key/user dan slot stream bersamaan, di Redis via Lua (atomik, aman untuk banyak replika).
- `make create-key EMAIL=... NAME=...` (`app/cli.py`).
- Fake upstream (`tests/fake_upstream/`) dijalankan dengan uvicorn sungguhan di thread, supaya streaming, TTFT lambat, dan disconnect terjadi nyata.
- 69 test baru (98 total).

### Keputusan yang diambil
- **Urutan pemeriksaan**: 413 (ukuran body) dicek tepat setelah 401, bukan setelah 429. Nama model ada di dalam body, jadi body harus dibaca dulu. Urutan lain sesuai FR-3.3 s.d. 3.10.
- **Error upstream tidak pernah diteruskan.** CT 110 mengembalikan pesan seperti `[codebuddy/gemini-3.1-flash-lite] ...` yang membocorkan ID dan provider (FR-4.0), dan bisa mengutip prompt. Pemetaannya: upstream 400 → 400, 413 → 413, 429 → 429 (`Retry-After: 30`), lainnya → 502. Pesan diganti teks tetap berbahasa Indonesia. Error inline dari upstream di tengah stream juga diganti.
- **Request berbiaya Rp 0 tidak membuat entri ledger.** Token tetap tercatat di `requests`. Tujuannya menghindari jutaan entri nol selama harga default Rp 0 (Q1).
- **Usage OpenAI**: `prompt_tokens` sudah termasuk `cached_tokens`, jadi `input_tokens = prompt − cached − cache_write` supaya token cache tidak ditagih dua kali.
- **Estimasi (FR-3.19)** hanya bila upstream sudah menerima request (200): klien memutus, stream terputus, atau usage tidak ada. Estimasinya ±4 karakter per token. Error upstream sebelum ada output dicatat dengan usage 0 (FR-3.22).
- **Heartbeat** hanya sebelum byte pertama (sesuai FR-3.15). Klien yang memutus dicatat dengan status 499 dan `error_type = client_disconnected`.
- **Batas harian** di-reset pukul 00:00 WIB (UTC+7).
- `last_used_at` key diperbarui paling sering sekali per menit, supaya key yang ramai tidak memicu tulis per request.
- `GET /v1/models` memakai format Anthropic bila ada header `anthropic-version`, dan format OpenAI selain itu.
- **Di luar scope, belum dibuat**: `/v1/messages/count_tokens` (Claude Code tetap jalan tanpanya, lihat bukti di bawah).

### Tertunda
- **Verifikasi manual 3–4 terhadap 9Router sungguhan** (selisih token 0 untuk 10–20 request, `cache_read_tokens > 0` pada prompt berulang). Upstream dev CT 110 sedang tidak bisa inference: probe 28 September memberi `429 Credits exhausted`, lalu semua model murah (`cb/gemini-3.1-flash-lite`, `cb/glm-4.6`, `cb/claude-haiku-4.5`, `cb/default-model-lite`, `cb/gemini-2.5-flash`) mengembalikan `400 service info not found`. Akan diulang setelah CT 110 pulih atau setelah cutover "CT 300 siap".
- Uji 524 lewat Cloudflare sungguhan: setelah tunnel ada (TASK-006). Perilakunya sudah diuji dengan fake upstream.
- Job pembuatan partisi `requests` bulanan: bersama worker di TASK-004.

### Bukti selesai (28 September 2026, VM 999)
- `make test` → **98 passed** (13,6 detik). `make lint` → ruff, format, mypy (41 file) bersih; oxlint frontend bersih.
- Test wajib TASK-001 dan lokasinya:
  - Token dan biaya empat kombinasi: `test_gateway_billing.py::test_usage_and_cost_recorded_for_each_format`.
  - Cache Anthropic: `::test_anthropic_cache_write_and_read_billed_separately`.
  - Heartbeat stream/non-stream: `test_gateway_stream.py::test_stream_heartbeat_before_first_byte`, `::test_nonstream_heartbeat_is_leading_whitespace`.
  - Konkurensi 20 paralel (saldo akhir tepat, 20 entri ledger, `balance_after` turun berurutan): `::test_twenty_parallel_requests_debit_balance_exactly`.
  - 402 / 403 tier / 403 helios / 429 + `Retry-After`: `test_gateway_checks.py`.
  - ID upstream tidak bocor: `assert_no_upstream_leak` dipanggil di semua test stream, `/v1/models`, dan error.
  - Log tanpa prompt/response: `::test_prompt_and_response_never_logged`.
- **Klien sungguhan ke portal** (uvicorn di `:18000`, DB `atheena_test`, fake upstream di `:18081`):
  - OpenCode 1.18.32, satu provider `atheena` (`@ai-sdk/openai-compatible`), `opencode run -m atheena/demo-sonnet "katakan halo"` → jawaban tampil, exit 0. Log portal: `/v1/chat/completions stream=True status=200 input=120 output=30 cost_idr=1`.
  - Claude Code, `ANTHROPIC_BASE_URL=http://localhost:18000` + `ANTHROPIC_AUTH_TOKEN=<key portal>`, `claude -p "katakan halo" --model demo-sonnet` → jawaban tampil, exit 0. Log portal: `/v1/messages stream=True status=200 input=120 output=30 cache_read=80`.
  - Bonus: saat fake upstream belum mengirim `finish_reason`, OpenCode mengulang terus dan dipotong 429 portal di request ke-61 (rate limit 60/menit terbukti terhadap klien sungguhan).
- **Portal → 9Router CT 110 sungguhan** (model `gemini-3.1-flash-lite` → `cb/gemini-3.1-flash-lite`):
  - non-stream → `HTTP 400 {"error":{"message":"Provider model menolak request ini.",...,"code":"upstream_rejected"}}`
  - stream → `HTTP 429 ... "upstream_rate_limited"`
  - `/v1/messages` → `HTTP 429 {"type":"error","error":{"type":"rate_limit_error",...}}`
  - Tidak ada `codebuddy` / `cb/` di response. `/readyz` → semua `ok`.

### Cara reproduksi
```bash
make test && make lint
make seed && make create-key EMAIL=<email-admin> NAME=laptop   # key tampil sekali
make run
curl -s localhost:8000/v1/models -H "Authorization: Bearer <key>"
curl -sN localhost:8000/v1/chat/completions -H "Authorization: Bearer <key>" \
  -H 'content-type: application/json' \
  -d '{"model":"<nama-publik>","stream":true,"messages":[{"role":"user","content":"hi"}]}'
```

## TASK-002 — Auth portal dan manajemen API key

Selesai 28 September 2026. Rencana: `tasks/TASK-002.md`.

### Yang dikerjakan
- **Validasi Cloudflare Access** (`app/portal/access.py`):
  - JWT `Cf-Access-Jwt-Assertion` (atau cookie `CF_Authorization`) diverifikasi RS256 terhadap JWKS `https://<team>/cdn-cgi/access/certs`, dengan cek `aud`, `iss`, `exp`.
  - Email diambil dari klaim. Bila header `Cf-Access-Authenticated-User-Email` ada, isinya harus cocok.
  - JWKS di-cache di proses (cache publik, boleh dibangun ulang tiap replika) dan diambil ulang saat ada `kid` baru (maks. sekali/menit) atau setiap jam.
- **Dependency** (`app/portal/deps.py`):
  - `current_user`: user harus ada dan `active`, selain itu 403 `account_inactive` "Akun belum aktif, hubungi admin." (FR-1.3).
  - `require_admin`: cek peran di server.
  - `csrf_protect`: mutasi wajib membawa header `X-Atheena-CSRF: 1` dan `Origin` dengan host yang sama.
  - Format error dashboard: `{"error": {"code", "message"}}`.
- **Endpoint** `/app/api`: `GET/PATCH /me`, `GET/POST /keys`, `DELETE /keys/{id}`, `GET /models`.
- `app/services/api_keys.py` dan `app/services/catalog.py` dipakai bersama oleh CLI, dashboard, dan gateway.
- Konfigurasi baru: `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `DEV_AUTH_EMAIL`, `IP_HASH_SECRET`; `APP_ENV` menerima `dev`/`prod`.
- 29 test baru (127 total).

### Keputusan yang diambil
- **Bypass dev** hanya aktif bila `APP_ENV=development` dan `DEV_AUTH_EMAIL` terisi. Di `test` juga mati.
  - Di `production`, aplikasi **menolak start** bila `DEV_AUTH_EMAIL` terisi atau `CF_ACCESS_*` kosong (validasi `Settings`).
  - Jadi bypass tidak mungkin aktif di produksi, termasuk karena salah konfigurasi.
- **CSRF** memakai header kustom, bukan token: situs lain tidak bisa mengirim header kustom lintas origin tanpa preflight CORS, dan portal tidak mengaktifkan CORS. Frontend (TASK-004) wajib mengirim `X-Atheena-CSRF: 1` di setiap mutasi.
- **Batas key aktif** (FR-2.5): saat membuat key, baris user dikunci (`FOR UPDATE`), supaya dua request paralel tidak bisa melewati batas. Melewati batas → 409 `key_limit`.
- **`model_allowlist`** hanya boleh berisi model yang memang diizinkan tier user (FR-2.7), selain itu 400.
- **Daftar key** menampilkan key aktif dan yang dicabut. Total pemakaian per key dihitung langsung dari `requests` (nanti bisa pindah ke `usage_daily` bila berat).
- **`GET /app/api/models`** tidak pernah mengembalikan `upstream_id` atau `provider` (FR-4.0). Kategori (resmi/eksperimen) dan harga ditampilkan.
- **Suspend user** (FR-1.5): gateway sudah menolak user non-aktif. Supaya instan (tanpa menunggu TTL cache 60 detik), endpoint suspend di TASK-005 wajib memanggil `invalidate_user_keys`.

### Tertunda
- Login Google sungguhan lewat Cloudflare Access: setelah tunnel dan aplikasi Access dibuat pemilik (TASK-006 menyiapkan template `.env`).
- Halaman key dan halaman "Akun belum aktif" di UI: TASK-004.
- Endpoint admin tambah/suspend user (FR-1.4): TASK-005.

### Bukti selesai (28 September 2026, VM 999)
- `make test` → **127 passed**. `make lint` → bersih.
- Test utama:
  - `test_portal_auth.py`: token valid via header dan cookie; token ditolak untuk `aud`/`iss` salah, kedaluwarsa, tanda tangan salah, `kid` tak dikenal, HS256, malformed, tanpa email; header email tanpa JWT ditolak; rotasi kunci; 403 `account_inactive` untuk suspended/pending/tidak terdaftar.
  - Bypass per environment: `test_dev_bypass_works_only_in_development`, `test_dev_bypass_is_off_in_production` (termasuk `APP_ENV=prod` + `DEV_AUTH_EMAIL` → `ValidationError`); CSRF.
  - `test_portal_keys.py`: key tampil sekali dan hanya hash yang disimpan; revoke instan walau cache sudah hangat; batas 5; tidak bisa mencabut key orang lain; total pemakaian; allowlist + batas harian; PATCH `/me` tidak bisa mengubah role.
- **Verifikasi manual** (DB dev, `APP_ENV=dev DEV_AUTH_EMAIL=<admin seed>`, port 18002):
  ```
  GET  /app/api/me                     → role=admin tier=advanced status=active
  POST /app/api/keys (tanpa CSRF)      → 403
  POST /app/api/keys                   → status=active prefix=sk-ath-k8G1O, key 47 karakter
  GET  /v1/models (key baru)           → 200 [claude-haiku-4.5-exp, gemini-3.1-flash-lite, glm-4.6]
  DELETE /app/api/keys/{id}            → 200
  GET  /v1/models (key sama)           → 401 (langsung)
  GET  /app/api/models                 → 3 model, tanpa upstream_id / "cb/"
  APP_ENV=prod DEV_AUTH_EMAIL=... create_app() → ValidationError "DEV_AUTH_EMAIL must not be set when APP_ENV=production"
  ```

### Cara reproduksi
```bash
make test && make lint
APP_ENV=dev DEV_AUTH_EMAIL=<email-admin> make run
curl -s localhost:8000/app/api/me
curl -s -X POST localhost:8000/app/api/keys -H 'X-Atheena-CSRF: 1' \
  -H 'content-type: application/json' -d '{"name":"laptop"}'
```

## TASK-003 — Ledger dan top-up MVP

Selesai 28 September 2026. Rencana: `tasks/TASK-003.md`.

### Yang dikerjakan
- **Backend**:
  - `app/services/ledger.py` (`post_entry`): satu-satunya jalur perubahan saldo. Baris user dikunci (`FOR UPDATE`), lalu `ledger_entries` dan `users.balance_idr` ditulis dalam transaksi yang sama. Proxy (`billing.py`) ikut memakainya.
  - `app/services/audit.py`: pencatatan audit log.
  - `app/net.py`: hash IP bersama.
- **API**:
  - Member: `GET /app/api/ledger?page&kind=all|credits`, `GET /app/api/topup-info`.
  - Admin: `GET /app/api/admin/users?q`, `POST /app/api/admin/users/{id}/adjustments` (top-up atau penyesuaian), `GET /app/api/admin/users/{id}/ledger`.
- **Frontend** (fondasi dashboard untuk TASK-004 dan 005):
  - React Router, klien API (header CSRF otomatis), format Rupiah dan WIB.
  - Shell dengan readout saldo, halaman "Akun belum aktif" dan "Sesi berakhir".
  - Halaman **Top-up** (`/app/topup`) dan halaman admin **Saldo pengguna** (`/app/admin/saldo`).
- Konfigurasi baru: `TOPUP_WHATSAPP_NUMBER` (default `6282312202002`), `TOPUP_QRIS_PATH` (default `/assets/qris.png`).
- 15 test baru (142 total).

### Keputusan yang diambil
- **Nominal**: top-up wajib positif dan catatannya opsional. Penyesuaian boleh kredit atau debit dengan alasan wajib (FR-5.2). Batas per entri Rp 100.000.000 untuk mencegah salah ketik nol.
  - Penyesuaian debit boleh membuat saldo negatif (koreksi admin), konsisten dengan FR-3.23.
- **QRIS** adalah file statis `frontend/public/assets/qris.png`. File saat ini **placeholder bertanda "CONTOH, bukan QRIS asli"**; pemilik wajib menggantinya dengan QRIS asli. Path-nya diambil dari API (`/topup-info`), jadi di deploy bisa diganti lewat volume tanpa build ulang (TASK-006).
- **Pesan WhatsApp** otomatis: "Halo Admin Atheena, saya ingin konfirmasi top-up saldo." + nama + email + nominal + pengingat melampirkan bukti. Tombol nonaktif sampai nominal diisi.
- **Admin wajib mengonfirmasi** sebelum menyimpan ("Tambah Rp X ke saldo Y?"), dan tombol dikunci selama request berjalan, untuk mencegah klik ganda.
- **Desain** (PRD §10, skill `frontend-design`):
  - Palet persis PRD. Biru elektrik hanya untuk aksi utama. Border 1px Gunmetal, tanpa shadow.
  - Font self-hosted dari npm: Schibsted Grotesk (UI) dan Martian Mono (semua angka, semi-condensed, tabular). Tanpa CDN Google Fonts.
  - Satu elemen menonjol: readout saldo di rail. Readout berwarna peringatan saat saldo di bawah ambang. Efek chrome hanya di wordmark.
  - Penomoran hanya di langkah top-up karena memang berurutan.
  - Di HP, rail menjadi header dengan tab, dan tabel ledger menjadi baris bertumpuk.
- **Proxy dev Vite** memakai `changeOrigin: false`, supaya header `Host` sampai utuh ke API dan cek CSRF `Origin` lolos. Di produksi, Caddy dan Cloudflare Tunnel juga mempertahankan `Host`.

### Tertunda
- Upload bukti dan antrean approval (FR-5.4): ditunda sesuai PRD. Tabel `topup_requests` sudah ada.
- Banner saldo rendah (FR-5.5) dan halaman ringkasan: TASK-004.
- Manajemen user lengkap (tambah, ubah tier, suspend): TASK-005.
- **Pemilik**: kirim/unggah gambar QRIS asli untuk menggantikan placeholder.

### Bukti selesai (28 September 2026, VM 999)
- `make test` → **142 passed**. `make lint` → ruff, format, mypy, dan oxlint bersih (0 warning). `npm run build` (tsc + vite) sukses.
- Test utama (`test_ledger_topup.py`):
  - Saldo = jumlah ledger; entri tidak valid ditolak.
  - Top-up admin tercatat dengan `created_by` + audit sebelum/sesudah + hash IP (IP mentah tidak disimpan).
  - Penyesuaian wajib alasan; member ditolak 403.
  - **Konkurensi**: 10 top-up admin + 10 request berbayar paralel → saldo akhir tepat Rp 50.000, 21 entri, rantai `balance_after` utuh dalam urutan lock (dijalankan 5× berturut-turut, stabil).
  - Ledger member privat, terpaginasi, bisa difilter.
  - Pencarian admin aman dari wildcard `%`.
- **Uji manual end-to-end** di DB dev (API `:8000` bypass sebagai admin seed, `vite preview` `:4173`, Chromium headless via Playwright):
  - Halaman top-up: nominal 150.000 → link `https://wa.me/6282312202002?text=...` berisi `Nama: Admin | Email: <email admin> | Nominal: Rp 150.000`.
  - Halaman admin: pilih user → Tambah saldo → konfirmasi → "Tersimpan. Saldo Admin sekarang Rp 150.000."
  - HP 390 px: tidak ada scroll horizontal (`scrollWidth > innerWidth` = false).
  - Skrip dijalankan 4×, jadi saldo uji Rp 600.000 **dikoreksi dengan entri penyesuaian** −600.000 ("Membatalkan top-up uji manual TASK-003"), tanpa menghapus baris. Isi DB setelahnya: 4 × `topup` + 1 × `adjustment`; `users.balance_idr` = jumlah ledger = 0; 5 baris `audit_logs` (`balance.topup` ×4, `balance.adjustment`) dengan sebelum/sesudah dan `ip_hash`.

### Cara reproduksi
```bash
make test && make lint && make frontend
APP_ENV=dev DEV_AUTH_EMAIL=<email-admin> make run   # terminal 1
cd frontend && npm run dev                          # terminal 2, buka http://localhost:5173/app/topup
```

## TASK-004 — Dashboard member dan agregasi harian

Selesai 28 September 2026. **MVP selesai di tahap ini.** Rencana: `tasks/TASK-004.md`.

### Yang dikerjakan
- **API member**: `GET /app/api/usage/summary`, `/usage/timeseries`, `/usage/requests`, `/usage/export.csv`, `/usage/facets`, `/config`.
  - Semua memakai tanggal WIB inklusif `from`/`to` (default 30 hari, maksimal 366).
  - Filter: model, key, proyek (`none` = tanpa proyek), status (`success`/`failed`).
- `app/services/usage.py`: query bersama dengan `user_id=None` untuk admin, jadi TASK-005 tinggal memakainya.
- **Worker** `app/worker.py` (`make worker`, `python -m app.worker --once --backfill-days N`):
  - Setiap 10 menit, `usage_daily` untuk hari ini dan kemarin dihitung ulang (upsert idempoten).
  - Partisi `requests` bulan ini + 3 bulan ke depan dibuat (menutup TODO migrasi 0001).
  - `pg_try_advisory_xact_lock`, jadi aman bila ada lebih dari satu replika.
- **Frontend**:
  - **Ringkasan** (`/app`): strip hari ini / 7 / 30 hari + model terbanyak, filter yang tersimpan di URL, bar chart harian dengan toggle Rupiah/Token, log request, ekspor CSV.
  - **API key** (`/app/keys`): buat (key tampil sekali + tombol salin), batasan opsional (batas harian, allowlist model), cabut dengan konfirmasi.
  - **Mulai** (`/app/mulai`): snippet OpenCode, Claude Code, Cursor, curl, plus tabel model yang bisa dipakai.
  - **Pengaturan** (`/app/profil`): nama tampilan, ambang saldo rendah, opt-out leaderboard.
  - Banner saldo rendah (FR-5.5), skip link, code splitting per halaman.
- 10 test baru (152 total).

### Keputusan yang diambil
- **Dashboard member membaca langsung dari `requests`, bukan dari `usage_daily`.**
  - Alasan: angka grafik harus sama dengan tabel log (acceptance Tahap 4), dan filter key/status tidak ada di `usage_daily`.
  - Dengan indeks `(user_id, started_at)`, query per user untuk 30 hari tetap ringan pada skala 50 user.
  - `usage_daily` dipakai untuk laporan admin dan leaderboard (TASK-005) serta retensi 12 bulan nanti.
- **Hari = tanggal WIB (UTC+7)**, sama dengan batas harian di proxy. Request pukul 23.30 WIB masuk hari itu walau di UTC masih siang.
- **Grafik bar**, bukan garis: datanya total harian yang dibandingkan antarhari. Tabel log di bawahnya menjadi alternatif aksesibel, dan grafik punya ringkasan teks untuk screen reader.
- **CSV**: di-stream (maksimal 200.000 baris per ekspor), ada BOM supaya Excel membaca UTF-8, dan sel teks yang diawali `=`, `+`, `-`, `@` diberi awalan `'` (anti CSV injection). Nama proyek berasal dari header `X-Project` pengguna, jadi ini wajib.
- **Key baru di quickstart** dibawa lewat state router saja, tidak lewat URL atau `localStorage`.
- `PUBLIC_API_BASE_URL` (default `https://api.atheena.online/v1`) dipakai untuk snippet. Claude Code memakai root tanpa `/v1`.
- **Performa**: Recharts (sesuai §9.1) hanya dimuat di halaman Ringkasan. Bundle awal 238 kB (gzip 76 kB), chunk Overview 368 kB (gzip 106 kB).
- **Label sumbu X** dihitung dari lebar grafik yang diukur (`ResizeObserver`). Mode otomatis Recharts tetap menumpuk label di HP.

### Tertunda
- Retensi 12 bulan + agregasi lama (§6): Tahap 6.
- Tanggal di `input type=date` mengikuti locale browser (di Chromium headless berbahasa Inggris tampil `08/30/2026`; di browser berbahasa Indonesia tampil `30/08/2026`).

### Bukti selesai (28 September 2026, VM 999)
- `make test` → **152 passed**. `make lint` → bersih (oxlint 0 warning). `npm run build` sukses.
- Test utama (`test_usage.py`):
  - Batas hari WIB (23.30 vs 00.30 WIB); hari kosong diisi 0.
  - **Total grafik = jumlah log** untuk 7 kombinasi filter.
  - Filter memilih baris yang benar; data user lain tidak pernah muncul.
  - Paginasi 50/halaman; ringkasan jendela waktu dan model terbanyak; rentang tidak valid → 400.
  - CSV hanya milik sendiri dan formula dinetralkan.
  - Rollup = agregasi `requests`, idempoten, request terlambat ikut terhitung.
  - Partisi dibuat; worker kedua dilewati saat lock dipegang.
- **Uji manual end-to-end** (DB `atheena_test`, fake upstream `:18081`, API bypass dev `:8000`, `vite preview` `:4173`, Chromium headless). Data: 145 request historis 29 hari + 6 request hari ini lewat proxy sungguhan.
  - Tanpa user terdaftar → halaman "Akun belum aktif".
  - Ringkasan: grafik "Rp 23.306 dari 151 request" = pager log "151 request".
  - Filter model `claude-sonnet-4.6` + satuan Token → URL `/app?from=2026-08-30&to=2026-09-28&model=claude-sonnet-4.6`, grafik "927.540 token dari 39 request", CSV terunduh `atheena-pemakaian-2026-08-30-2026-09-28.csv` berisi 39 baris.
  - Buat key → panel "hanya ditampilkan sekali" → "Pasang di OpenCode atau Claude Code" → snippet berisi key asli, URL tetap `/app/mulai` (key tidak ada di URL).
  - Batas 5 key aktif terbukti di UI (pembuatan key ke-6 ditolak sampai key lama dicabut).
  - `X-Project: helios` + model eksperimen lewat proxy → `403 project_official_only`.
  - HP 390 px: tanpa scroll horizontal; strip ringkasan 2 kolom, log bertumpuk.
  - `python -m app.worker --once --backfill-days 30` → "rollup done hari: 31 baris: 117"; `sum(usage_daily.cost_idr)` = `sum(requests.cost_idr)` = 23.306.

### Cara reproduksi
```bash
make test && make lint && make frontend
APP_ENV=dev DEV_AUTH_EMAIL=<email> make run   # terminal 1
make worker                                   # terminal 2 (rollup tiap 10 menit)
cd frontend && npm run dev                    # terminal 3, buka http://localhost:5173/app
```
