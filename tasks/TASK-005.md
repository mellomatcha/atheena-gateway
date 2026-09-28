# TASK-005 — Dashboard admin dan leaderboard

Referensi PRD: §3, §5.4 (FR-4.1 s.d. FR-4.5), §5.7 (FR-7.1 s.d. FR-7.9), §5.8 (FR-8.1 s.d. FR-8.4), §8 (admin), §11, §14 Tahap 5, §15 Q6.
Prasyarat: TASK-004 selesai.

## Tujuan
Admin bisa mengelola user, top-up, harga dan katalog model, pengaturan, dan proyek; melihat pemakaian global; mengekspor laporan bulanan per proyek dan per user; membaca audit log; dan memantau status sistem. Member melihat leaderboard.

## Scope
1. **User** (FR-1.4, FR-1.5, FR-7.1):
   - `GET/POST /admin/users`, `PATCH /admin/users/{id}` (nama, tier, peran, status, batas harian).
   - Suspend → semua cache key user dihapus (revoke instan).
   - Admin tidak bisa men-suspend atau menurunkan peran dirinya sendiri (mencegah terkunci).
   - Riwayat top-up per user = `GET /admin/users/{id}/ledger?kind=credits` (sudah ada, FR-7.2).
2. **Pemakaian global** (FR-7.3), memakai ulang `app/services/usage.py` dengan filter `user`:
   - `GET /admin/usage/{summary,timeseries,requests,export.csv}`.
   - Ringkasan per user, per model, per proyek, per provider.
3. **Laporan bulanan** (FR-7.4): `GET /admin/reports/monthly?month=YYYY-MM&by=project|user` dan versi `.csv`.
4. **Katalog model** (FR-4.1 s.d. 4.5, FR-7.5):
   - `GET/POST /admin/models`, `PATCH /admin/models/{id}`.
   - Setiap perubahan (termasuk harga lama → baru) masuk audit log (FR-4.3).
   - Nama publik divalidasi tanpa prefix provider (FR-4.0).
   - `POST /admin/models/sync`: daftar ID upstream yang belum ada di katalog; tidak menambah otomatis (FR-4.5).
5. **Pengaturan dan proyek** (FR-7.6): `GET/PATCH /admin/settings` (saldo minimum, rate limit, batas stream, batas key, batas harian default, ukuran body), `GET/POST/PATCH /admin/projects`. Semua perubahan diaudit.
6. **Audit log** (FR-7.7): `GET /admin/audit-logs?page&action`.
7. **Status sistem** (FR-7.8, FR-7.9): `GET /admin/health`: kesehatan 9Router, stream aktif (Redis), error rate dan latensi rata-rata/p95 1 jam terakhir, tautan `router.atheena.online`.
8. **Leaderboard** (FR-8.1 s.d. 8.4): `GET /app/api/leaderboard?period=week|month&metric=tokens|requests|cost|efficiency`.
   - Sumber data `usage_daily` (hasil worker).
   - Minggu = Senin–Minggu WIB; bulan = bulan kalender WIB.
   - Efisiensi = cache read ÷ (input + cache write + cache read), minimal 100 request.
   - Tampil nama tampilan saja; user yang opt-out dan user nonaktif tidak ditampilkan.
9. **Frontend** (PRD §10, gaya yang sama dengan dashboard member):
   - Halaman admin: Pengguna, Pemakaian global + laporan bulanan, Model, Pengaturan + proyek, Audit log, Status sistem.
   - Halaman Leaderboard untuk semua user.

## Rencana implementasi
- **Backend baru**:
  - `app/portal/admin/{users,usage,models,settings,audit,health}.py`, `app/portal/leaderboard.py`
  - `app/services/reports.py`, `app/services/leaderboard.py`
- **Frontend baru**: `pages/admin/{Users,Usage,Models,Settings,Audit,Status}.tsx`, `pages/Leaderboard.tsx`.
- **Test**:
  - Semua endpoint admin menolak member (403).
  - Suspend langsung memutus key walau cache hangat; admin tidak bisa mengunci dirinya sendiri.
  - Audit log berisi nilai lama/baru untuk harga, pengaturan, user, dan proyek.
  - Validasi nama model; sync hanya mengembalikan ID baru (fake upstream `/models`).
  - Laporan bulanan = jumlah `requests` per proyek/user, dan CSV-nya.
  - Health menghitung stream aktif dan error rate.
  - Leaderboard: urutan, opt-out, minimal 100 request untuk efisiensi, batas minggu/bulan WIB.
- **Verifikasi manual**: halaman admin dibuka di Chromium headless (desktop + HP) dengan data demo; ubah harga → audit tampil; suspend user → key-nya langsung 401.

## Selesai jika
`make test` dan `make lint` hijau, build frontend sukses, dan bukti tercatat di `docs/progress.md`. Sesuai acceptance Tahap 5: admin bisa mengelola user, top-up, dan harga, serta mengekspor laporan bulanan per proyek.
