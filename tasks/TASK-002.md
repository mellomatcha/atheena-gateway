# TASK-002 — Auth portal dan manajemen API key

Referensi PRD: §3, §5.1 (FR-1.1 s.d. FR-1.5), §5.2 (FR-2.1 s.d. FR-2.7), §8, §11 (Aplikasi), §14 Tahap 2.
Prasyarat: TASK-001 selesai.

## Tujuan
Dashboard API (`/app/api/*`) mengenali pengguna dari Cloudflare Access dengan validasi JWT, hanya melayani user aktif, dan member bisa mengelola API key sendiri. Key yang dibuat langsung bisa dipakai di `/v1/*`, dan revoke berlaku instan.

## Scope
1. **Konfigurasi** (env): `CF_ACCESS_TEAM_DOMAIN` (misal `atheena.cloudflareaccess.com`), `CF_ACCESS_AUD` (Application Audience tag), `DEV_AUTH_EMAIL`. `APP_ENV` menerima `dev`/`prod` sebagai alias `development`/`production`.
2. **Validasi Cloudflare Access** (FR-1.1, FR-1.2):
   - JWT `Cf-Access-Jwt-Assertion` (header, atau cookie `CF_Authorization`) diverifikasi RS256 terhadap JWKS tim (`https://<team>/cdn-cgi/access/certs`).
   - Klaim yang dicek: `aud`, `iss`, `exp`/`nbf`.
   - Email diambil dari klaim JWT. Bila header `Cf-Access-Authenticated-User-Email` ada, isinya harus sama.
   - JWKS di-cache di proses (hanya cache, bukan state) dan diambil ulang bila `kid` tidak dikenal.
3. **Bypass dev**: hanya bila `APP_ENV=development` dan `DEV_AUTH_EMAIL` diisi; request dianggap datang dari email itu.
   - Di `production`, bypass tidak pernah dipakai, dan aplikasi **menolak start** bila `DEV_AUTH_EMAIL` terisi atau `CF_ACCESS_*` kosong.
   - Di `test`, bypass juga mati.
   - Semua dibuktikan dengan test.
4. **Status akun** (FR-1.3):
   - Email yang lolos Access tapi tidak ada di `users`, atau statusnya bukan `active` → `403` dengan `code = account_inactive` dan pesan "Akun belum aktif, hubungi admin." (halaman UI di TASK-004).
   - Peran dari database (§3).
   - Dependency `require_admin` untuk endpoint admin (§11).
5. **CSRF** (§11): request `POST/PATCH/PUT/DELETE` ke `/app/api/*` wajib membawa header `X-Atheena-CSRF: 1`. Header kustom memaksa preflight CORS, dan portal tidak mengizinkan CORS lintas origin, jadi situs lain tidak bisa memalsukannya. Bila header `Origin` ada, host-nya harus sama.
6. **Endpoint member** (§8):
   - `GET /app/api/me`, `PATCH /app/api/me` (nama tampilan, ambang saldo, opt-out leaderboard).
   - `GET /app/api/keys`: nama, prefix, status, dibuat, terakhir dipakai, total pemakaian (request, token, Rp) — FR-2.6.
   - `POST /app/api/keys`: nama, opsional `daily_cap_idr` dan `model_allowlist` (FR-2.7). Key penuh ditampilkan sekali (FR-2.2). Batas key aktif dari settings (FR-2.5).
   - `DELETE /app/api/keys/{id}`: revoke + hapus cache Redis (FR-2.4).
   - `GET /app/api/models`: katalog yang boleh dipakai user, tanpa ID upstream dan provider (FR-4.0).
7. **Suspend user** (FR-1.5): helper `invalidate_user_keys` sudah ada (TASK-001). Endpoint admin untuk suspend ada di TASK-005 dan wajib memanggilnya.

## Di luar scope
UI (TASK-004), endpoint admin kelola user (TASK-005), top-up (TASK-003), otomatisasi allowlist Cloudflare.

## Rencana implementasi
- **File baru**:
  - `backend/app/portal/__init__.py`
  - `backend/app/portal/access.py`: JWKS + verifikasi JWT
  - `backend/app/portal/deps.py`: `current_user`, `require_admin`, CSRF
  - `backend/app/portal/me.py`, `backend/app/portal/keys.py`, `backend/app/portal/catalog.py`, `backend/app/portal/router.py`
  - `backend/app/services/api_keys.py`: pembuatan key dipakai bersama CLI dan dashboard
- **File diubah**: `app/config.py` (field + validasi produksi), `app/main.py`, `app/cli.py`, `pyproject.toml` + `requirements.lock` (`pyjwt[crypto]`), `.env.example`.
- **Test** (`tests/test_portal_auth.py`, `tests/test_portal_keys.py`):
  - Pasangan RSA dibuat saat test; JWKS di-mock dengan respx.
  - JWT valid, `aud` salah, `iss` salah, kedaluwarsa, tanda tangan salah, `kid` tidak dikenal, dan email header yang tidak cocok.
  - Bypass jalan di `development`, mati di `test` dan `production`; start `production` gagal bila `DEV_AUTH_EMAIL` terisi.
  - User tidak terdaftar/suspended → 403 `account_inactive`; CSRF ditolak tanpa header.
  - Key: batas 5, tampil sekali, prefix 12 karakter, revoke langsung 401 di `/v1/*` (tanpa menunggu TTL cache), user lain tidak bisa revoke key orang lain.
- **Verifikasi manual**: `APP_ENV=development DEV_AUTH_EMAIL=<admin> make run` → buat key via `curl` ke `/app/api/keys` → pakai key di `/v1/models` → revoke → langsung 401.

## Selesai jika
`make test` dan `make lint` hijau, verifikasi manual tercatat di `docs/progress.md`. Login Google sungguhan lewat Cloudflare diuji setelah tunnel ada (TASK-006).
