# TASK-004 — Dashboard member dan agregasi harian

Referensi PRD: §5.5 (FR-5.5), §5.6 (FR-6.1 s.d. FR-6.8), §7 (`usage_daily`, partisi `requests`), §8, §9.1 (`worker`), §10, §14 Tahap 4.
Prasyarat: TASK-003 selesai (fondasi frontend ada).

## Tujuan
Member bisa melihat pemakaiannya sendiri: ringkasan, grafik harian dalam token atau Rupiah, filter, log request, ekspor CSV, kelola key, dan snippet quickstart. Worker menghitung `usage_daily` dan menyiapkan partisi bulanan. **MVP selesai di tahap ini.**

## Scope
1. **API pemakaian member** (`/app/api/usage/*`, §8). Semua memakai tanggal WIB inklusif (`from`, `to` = `YYYY-MM-DD`, default 30 hari terakhir, maksimal 366 hari).
   - `GET /usage/summary`: pemakaian hari ini / 7 hari / 30 hari (request, token, Rp) dan model yang paling sering dipakai 30 hari terakhir (FR-6.1).
   - `GET /usage/timeseries?unit=token|idr&model&key&project&status`: satu titik per hari, hari tanpa pemakaian diisi 0 (FR-6.2, FR-6.3).
   - `GET /usage/requests?...&page`: log metadata dengan paginasi (FR-6.4).
   - `GET /usage/export.csv?...`: ekspor CSV yang di-stream, aman dari CSV injection (FR-6.8).
   - `GET /usage/facets`: daftar model dan proyek yang pernah dipakai, untuk isi dropdown filter.
   - `GET /config`: base URL API publik untuk snippet quickstart (`PUBLIC_API_BASE_URL`).
2. **Sumber data**: dashboard member membaca langsung dari `requests` (indeks `user_id, started_at`), supaya angka grafik selalu sama dengan tabel log dan filter key/status (yang tidak ada di `usage_daily`) tetap bisa dipakai.
3. **Worker** (`python -m app.worker`, `make worker`):
   - Setiap 10 menit, hitung ulang `usage_daily` untuk hari ini dan kemarin (WIB). Idempoten lewat upsert; kemarin ikut dihitung ulang karena stream yang melewati tengah malam dicatat setelahnya.
   - Pastikan partisi `requests` bulan ini + 3 bulan ke depan ada (menutup TODO migrasi 0001).
   - `pg_advisory_lock` supaya aman bila ada lebih dari satu replika.
   - `--once` untuk sekali jalan, dan `--backfill-days N`.
4. **Frontend** (PRD §10, skill `frontend-design` + `ui-ux-pro-max`):
   - **Ringkasan** (`/app`): strip ringkasan, filter, bar chart harian dengan toggle Rupiah/Token (Recharts sesuai §9.1), tabel log berpaginasi, tombol ekspor CSV.
   - **Key** (`/app/keys`, FR-6.5): daftar, buat (key tampil sekali, dengan tombol salin dan tautan ke quickstart berisi key), cabut dengan konfirmasi.
   - **Mulai** (`/app/mulai`, FR-6.7): snippet OpenCode (satu provider `atheena`), Claude Code, Cursor, dan curl. Key terisi otomatis bila baru dibuat; key hanya disimpan di memori, tidak di URL maupun storage.
   - **Pengaturan** (`/app/profil`): nama tampilan, ambang saldo rendah (FR-5.5), opt-out leaderboard (FR-8.4).
   - Banner saldo rendah di semua halaman bila saldo < ambang (FR-5.5).

## Di luar scope
Dashboard admin dan leaderboard (TASK-005), job retensi 12 bulan (Tahap 6).

## Rencana implementasi
- **File baru**:
  - Backend: `app/services/usage.py` (query bersama, dipakai ulang admin di TASK-005), `app/portal/usage.py`, `app/worker.py`.
  - Frontend: `frontend/src/pages/{Overview,Keys,Quickstart,Profile}.tsx`, `frontend/src/components/{UsageChart,Filters,CopyButton}.tsx`.
- **File diubah**: `app/config.py`, `app/portal/router.py`, `Makefile` (`worker`), `frontend/src/App.tsx`, `Shell.tsx`, `styles.css`.
- **Test**:
  - Batas hari WIB (request 23.30 WIB masuk hari yang benar).
  - Total grafik = jumlah tabel log untuk filter yang sama.
  - Filter model/key/proyek/status; data user lain tidak pernah terlihat.
  - Paginasi; CSV (header, isi, escape formula `=`/`+`/`-`/`@`).
  - Worker: upsert idempoten, hasil sama dengan agregasi manual, partisi dibuat, dua worker paralel tidak bentrok.
- **Verifikasi manual**: data contoh dibuat lewat proxy (fake upstream), lalu dashboard dibuka di Chromium headless (desktop + HP); grafik dicocokkan dengan tabel log, dan CSV diunduh.

## Selesai jika
`make test` dan `make lint` hijau, build frontend sukses, dan bukti tercatat di `docs/progress.md`.
