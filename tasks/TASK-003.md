# TASK-003 — Ledger dan top-up MVP

Referensi PRD: §4.3 poin 6, §5.5 (FR-5.1 s.d. FR-5.5), §5.7 (FR-7.1, FR-7.2, FR-7.7), §7, §8, §10, §11.
Prasyarat: TASK-002 selesai.

## Tujuan
Member bisa top-up lewat QRIS + konfirmasi WhatsApp, admin menambah saldo dan membuat adjustment dari dashboard, dan setiap perubahan saldo punya entri ledger serta audit log.

## Scope
1. **Service ledger** (`app/services/ledger.py`): satu pintu untuk semua perubahan saldo.
   - Kunci baris user (`FOR UPDATE`), hitung `balance_after`, insert `ledger_entries`, update `users.balance_idr`, semuanya dalam transaksi pemanggil (FR-5.1).
   - Proxy (`billing.py`) ikut memakai service ini.
2. **Audit log** (`app/services/audit.py`): `audit_logs` dengan nilai sebelum/sesudah, pelaku, dan hash IP (FR-7.7).
3. **API member**:
   - `GET /app/api/ledger?page&kind=all|credits`: riwayat ledger sendiri, 50 per halaman; `credits` = top-up, adjustment, refund (FR-6.6).
   - `GET /app/api/topup-info`: nomor WhatsApp admin dan path gambar QRIS, supaya keduanya bisa diganti tanpa build ulang frontend.
4. **API admin** (`/app/api/admin`, wajib admin):
   - `GET /users?q`: daftar ringkas user + saldo (untuk memilih user; manajemen lengkap di TASK-005).
   - `POST /users/{id}/adjustments`: `{type: "topup" | "adjustment", amount_idr, note}`.
     - `topup`: nominal positif, catatan opsional.
     - `adjustment`: kredit/debit, catatan wajib (FR-5.2).
     - Pelaku admin dicatat di `ledger_entries.created_by` dan di `audit_logs`.
   - `GET /users/{id}/ledger?page&kind`: riwayat per user (FR-7.2).
5. **Frontend** (fondasi dashboard, arah desain PRD §10):
   - React Router, klien API dengan header CSRF, format Rupiah dan tanggal WIB.
   - Shell: rail navigasi + saldo; halaman "Akun belum aktif" (FR-1.3) dan "Sesi berakhir".
   - **Halaman Top-up**: gambar QRIS statis (`/assets/qris.png`, bisa diganti tanpa build ulang lewat volume di deploy), langkah bayar → isi nominal → konfirmasi. Tombol "Konfirmasi via WhatsApp" membuka `https://wa.me/6282312202002?text=...` berisi nama, email, dan nominal. Riwayat ledger ada di halaman yang sama.
   - **Halaman admin Saldo**: cari user, tambah saldo atau adjustment dengan konfirmasi, lalu riwayat ledger user tersebut.
   - Dev server Vite mem-proxy `/app/api` dan `/v1` ke `localhost:8000`.

## Di luar scope
Upload bukti dan antrean approval (FR-5.4, ditunda sesuai PRD), manajemen user lengkap (TASK-005), dashboard pemakaian (TASK-004), banner saldo rendah FR-5.5 (TASK-004 bersama ringkasan).

## Rencana implementasi
- **File baru**:
  - Backend: `app/services/ledger.py`, `app/services/audit.py`, `app/portal/ledger.py`, `app/portal/admin/__init__.py`, `app/portal/admin/balances.py`.
  - Frontend: `frontend/src/{api.ts,format.ts,styles.css,App.tsx,...}`, `frontend/src/pages/{TopUp,AdminBalance,Inactive}.tsx`, `frontend/public/assets/qris.png` (placeholder bertanda "contoh").
- **File diubah**: `app/gateway/billing.py` (pakai service ledger), `app/portal/router.py`, `app/config.py` (`TOPUP_WHATSAPP_NUMBER`, `TOPUP_QRIS_PATH`), `frontend/vite.config.ts`, `frontend/package.json`.
- **Test**:
  - Service ledger: saldo = jumlah ledger; topup/adjustment/refund; adjustment tanpa catatan ditolak.
  - **Konkurensi**: 10 top-up admin + 10 request berbayar paralel → saldo akhir tepat dan 20 entri.
  - API admin: member ditolak 403, audit log terisi dengan sebelum/sesudah, nominal tidak valid ditolak.
  - Ledger member: hanya milik sendiri, paginasi, filter `credits`.
- **Verifikasi manual**: build frontend, jalankan portal (bypass dev), buka halaman top-up dan admin, tambah saldo, cek ledger dan audit log di DB. Screenshot halaman bila browser headless tersedia.

## Selesai jika
`make test` dan `make lint` hijau (termasuk `npm run build` dan oxlint frontend), dan bukti manual tercatat di `docs/progress.md`.
