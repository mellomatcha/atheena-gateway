# PRD — Atheena AI Gateway

| | |
|---|---|
| Versi | 0.2 |
| Tanggal | 28 September 2026 |
| Pemilik | Dafin Dafwatul Yudha |
| Status | Siap dikerjakan, mulai dari Tahap 0 |
| Target skala | 25 pengguna saat awal, dirancang hingga 50 (fase ini) |
| Domain dev | `atheena.online` (produksi nanti: `dafin.id`) |

**Perubahan v0.2**: satu base URL + satu key untuk semua tool (§5.3), nama model publik tanpa prefix provider (§5.4), top-up MVP lewat WhatsApp + input saldo manual oleh admin (§5.5), nomor CT baru (CT 300 = 9Router, CT 301 = portal, VM 999 = lingkungan development), spesifikasi CT 301 diturunkan untuk 25 user (§9.2), keputusan terbuka diberi nilai default (§15).

> Dokumen ini adalah acuan utama untuk semua pekerjaan implementasi. Agent (Claude Code / OpenCode) wajib membaca dokumen ini sebelum mengerjakan task apa pun. Jika ada konflik antara instruksi task dan dokumen ini, dokumen ini yang berlaku, kecuali task secara eksplisit menyatakan mengubah PRD.

---

## 0. Ringkasan eksekutif

Atheena AI Gateway adalah satu pintu akses API model AI (Anthropic, CodeBuddy, dan provider lain) untuk tim internal, dengan pencatatan pemakaian per orang dalam token dan Rupiah.

Setiap anggota punya akun, API key sendiri, dan saldo Rupiah. Saldo diisi lewat top-up QRIS yang di-approve admin. Setiap request dicatat (metadata saja, bukan isi prompt), biayanya dihitung dari tabel harga yang bisa diedit admin, lalu saldo dipotong.

Arsitekturnya dibuat untuk 50 pengguna sekarang, tetapi dirancang agar bisa naik ke 100-300 pengguna tanpa ditulis ulang: portal stateless, state di Postgres/Redis, dan router di belakangnya bisa diganti.

---

## 1. Latar belakang

- Tim menggunakan banyak provider AI (Anthropic API dari dana kantor, akun CodeBuddy untuk eksperimen, dan provider lain) lewat satu router self-hosted (9Router) di Proxmox.
- Saat ini tidak ada pencatatan pemakaian per orang, tidak ada kontrol biaya, dan key router dibagi manual.
- Eksperimen ini mendapat dana per orang. Setiap anggota perlu melihat berapa yang sudah ia pakai dan berapa sisa saldonya.
- Jika eksperimen berhasil, sistem ini berpotensi menjadi gateway AI untuk seluruh kantor (100-300 orang).

## 2. Tujuan dan non-goals

### Tujuan (fase ini)
1. Setiap anggota bisa memakai model AI dari tool favoritnya (OpenCode, Claude Code, Cursor, SDK) dengan API key pribadi.
2. Setiap request tercatat: siapa, model apa, token berapa, biaya berapa (Rupiah), berhasil/gagal, proyek apa.
3. Anggota bisa melihat pemakaiannya sendiri dengan filter periode, model, key, dan proyek, dalam satuan token atau Rupiah.
4. Admin bisa mengelola user, top-up, harga model, dan melihat seluruh pemakaian.
5. Request ditolak otomatis jika saldo habis atau batas terlampaui.
6. Leaderboard internal untuk transparansi dan mendorong pemakaian yang efisien.

### Non-goals (tidak dikerjakan di fase ini)
- Payment gateway otomatis (top-up tetap manual via QRIS + approval).
- Penentuan harga final (tabel harga ada, angkanya diputuskan kemudian).
- Mata uang selain Rupiah.
- Multi-instance / load balancer (disiapkan arsitekturnya, tidak dipasang).
- Menyimpan isi prompt atau response.
- Aplikasi mobile.
- Fitur untuk publik di luar kantor.

## 3. Pengguna dan peran

| Peran | Siapa | Bisa melakukan |
|---|---|---|
| Member | Anggota tim | Kelola key sendiri, lihat pemakaian sendiri, ajukan top-up, lihat leaderboard |
| Admin | Dafin | Semua fitur member + kelola user, approve top-up, edit harga dan katalog model, lihat semua pemakaian, ekspor laporan, akses dashboard 9Router |

Aturan akses:
- Login hanya lewat Cloudflare Access dengan Google sebagai identity provider.
- Email harus ada di allowlist Cloudflare Access **dan** terdaftar sebagai user aktif di database portal. Lolos Access saja tidak cukup.
- Peran ditentukan di database portal, bukan di Cloudflare.

---

## 4. Arsitektur

### 4.1 Gambaran

```
                        Internet
                           │
                 ┌─────────▼──────────┐
                 │     Cloudflare     │
                 │ Tunnel · Access ·  │
                 │ WAF rate limit     │
                 └──┬──────┬──────┬───┘
      ai.atheena    │      │      │   router.atheena
  (Access: allowlist)      │      │   (Access: admin saja)
                    │   api.atheena     │
                    │  (bypass Access,  │
                    │   API key)        │
┌───────────────────▼──────▼──────┐    │
│ CT 301 — Portal                 │    │
│  Caddy (reverse proxy internal) │    │
│  ├─ Web (frontend statis)       │    │
│  └─ API app (FastAPI)           │    │
│      ├─ /v1/*  → proxy gateway  │    │
│      └─ /app/* → API dashboard  │    │
│  Postgres 16 · Redis 7          │    │
└───────────────┬─────────────────┘    │
                │ HTTP internal        │
                │ (hanya dari CT 301)  │
┌───────────────▼──────────────────────▼┐
│ CT 300 — 9Router (1 instance)         │
│  Menyimpan semua key provider         │
└───────────────┬───────────────────────┘
                │
   Anthropic API · CodeBuddy · provider lain
```

### 4.2 Subdomain

| Subdomain | Isi | Proteksi |
|---|---|---|
| `ai.atheena.online` | Landing page, dashboard user, dashboard admin | Cloudflare Access (Google, allowlist email) |
| `api.atheena.online` | Endpoint API untuk tool (`/v1/*`) | Bypass Access; API key portal + WAF rate limit |
| `router.atheena.online` | Dashboard bawaan 9Router | Cloudflare Access, hanya email admin |

### 4.3 Prinsip arsitektur (wajib dipatuhi)

1. **Portal stateless.** Tidak ada state penting di memori proses. Semua disimpan di Postgres (data permanen) atau Redis (rate limit, hitungan stream, cache). Tujuannya agar nanti bisa dijalankan beberapa replika di belakang load balancer tanpa perubahan kode.
2. **Router bisa diganti.** Portal hanya bergantung pada kontrak API OpenAI-compatible dan Anthropic-compatible dari upstream. Alamat upstream adalah satu variabel konfigurasi. 9Router bisa diganti (misalnya ke gateway multi-instance) tanpa mengubah logika billing.
3. **Portal adalah sumber kebenaran pemakaian.** Semua token dan biaya dihitung dan dicatat oleh portal, bukan dibaca dari fitur usage 9Router.
4. **Metadata saja.** Isi prompt dan response tidak pernah disimpan ke database atau log.
5. **Rupiah saja, dengan snapshot harga.** Biaya dihitung dalam Rupiah. Harga per model yang berlaku saat request disalin ke baris request, sehingga perubahan harga tidak mengubah histori.
6. **Ledger append-only.** Saldo tidak pernah di-update langsung tanpa entri ledger. Koreksi dilakukan dengan entri baru, bukan edit/hapus.
7. **Streaming end-to-end.** Proxy meneruskan stream byte-per-byte, tidak menunggu response selesai.

---

## 5. Kebutuhan fungsional

Penomoran FR dipakai untuk referensi di task.

### 5.1 Autentikasi dan akses

- **FR-1.1** Portal membaca identitas dari header `Cf-Access-Authenticated-User-Email`. Header ini hanya dipercaya jika request datang lewat Cloudflare Tunnel (portal tidak boleh bisa diakses langsung dari jaringan lain tanpa lewat tunnel).
- **FR-1.2** Portal memvalidasi JWT `Cf-Access-Jwt-Assertion` terhadap public key tim Cloudflare Access (bukan hanya percaya header email).
- **FR-1.3** Jika email lolos Access tetapi tidak ada di tabel `users` atau statusnya bukan `active`, tampilkan halaman "Akun belum aktif, hubungi admin".
- **FR-1.4** Admin bisa menambahkan user (email, nama tampilan, tier), menonaktifkan, dan mengaktifkan kembali. Menambah user baru juga butuh menambahkan email ke allowlist Cloudflare Access (dicatat di runbook; otomatisasi via Cloudflare API opsional di fase berikutnya).
- **FR-1.5** User yang di-suspend: semua API key-nya langsung ditolak.

### 5.2 Manajemen API key

- **FR-2.1** Member bisa membuat key dengan nama (misal "laptop-kantor", "opencode-helios").
- **FR-2.2** Format key: `sk-ath-` + 40 karakter acak (base62). Key ditampilkan penuh **satu kali** saat dibuat. Prefix tidak memengaruhi performa; fungsinya agar key mudah dikenali (oleh manusia dan secret scanner) dan tidak tertukar dengan key 9Router. Key 9Router tidak pernah diberikan ke pengguna; hanya portal yang memegangnya.
- **FR-2.3** Database hanya menyimpan hash SHA-256 key + prefix 12 karakter untuk identifikasi visual.
- **FR-2.4** Member bisa revoke key. Revoke berlaku instan (cache di Redis ikut dihapus).
- **FR-2.5** Batas maksimal 5 key aktif per user (bisa diubah di settings).
- **FR-2.6** Setiap key menampilkan: nama, prefix, dibuat kapan, terakhir dipakai kapan, total pemakaian.
- **FR-2.7** Opsional per key: batas biaya harian (Rp) dan allowlist model yang lebih sempit dari tier user.

### 5.3 Proxy gateway (inti sistem)

**Prinsip "satu pintu"**
- **FR-3.0** Pengguna hanya butuh **satu base URL** (`https://api.atheena.online/v1`) dan **satu API key**. Semua model, dari provider mana pun, diakses lewat base URL dan key yang sama. Tidak ada variabel atau provider tambahan per model di sisi pengguna.
  - OpenCode, Cursor, dan SDK OpenAI cukup satu provider OpenAI-compatible.
  - Claude Code memakai base URL dan key yang sama; portal otomatis melayani format Anthropic di `/v1/messages` (Claude Code tidak bisa memakai format OpenAI).
  - Pengguna tidak perlu tahu provider asli sebuah model.

**Endpoint yang didukung**

| Endpoint | Format | Dipakai oleh |
|---|---|---|
| `POST /v1/chat/completions` | OpenAI | OpenCode (openai-compatible), Cursor, SDK OpenAI |
| `POST /v1/messages` | Anthropic | Claude Code, OpenCode (`@ai-sdk/anthropic`), SDK Anthropic |
| `GET /v1/models` | OpenAI | Semua tool untuk daftar model |

**Autentikasi request**
- **FR-3.1** Menerima key dari `Authorization: Bearer <key>` atau `x-api-key: <key>` (Claude Code dan SDK Anthropic memakai salah satunya).
- **FR-3.2** Validasi key via cache Redis (TTL 60 detik), fallback ke Postgres.

**Pemeriksaan sebelum diteruskan** (urutan, berhenti di pengecekan pertama yang gagal)
- **FR-3.3** Key valid dan aktif, user aktif → jika tidak: `401`.
- **FR-3.4** Model ada di katalog, aktif, dan diizinkan untuk tier user (dan allowlist key jika ada) → jika tidak: `403` dengan pesan model yang diizinkan.
- **FR-3.5** Saldo user ≥ saldo minimum (default Rp 1.000, bisa diatur) → jika tidak: `402` "Saldo habis, silakan top-up".
- **FR-3.6** Batas biaya harian per key/user belum terlampaui → jika tidak: `429`.
- **FR-3.7** Rate limit per key (default 60 request/menit) dan per user belum terlampaui → jika tidak: `429` dengan header `Retry-After`.
- **FR-3.8** Jumlah stream bersamaan per user < batas (default 8) → jika tidak: `429`.
- **FR-3.9** Ukuran body ≤ batas (default 20 MB) → jika tidak: `413`.
- **FR-3.10** Aturan proyek: jika header `X-Project` bernilai proyek yang ditandai "hanya provider resmi" (misal `helios`), model non-resmi (CodeBuddy dll) ditolak dengan `403`.

**Penerusan**
- **FR-3.11** Nama model publik diterjemahkan ke ID model upstream sesuai katalog (misal `claude-sonnet-4.6` → `anthropic/claude-sonnet-4-6` di 9Router).
- **FR-3.12** Request `/v1/messages` diteruskan ke endpoint Anthropic-native upstream **tanpa konversi format**, agar `cache_control` (prompt caching) tetap utuh.
- **FR-3.13** Untuk request OpenAI streaming, proxy menyuntikkan `stream_options: {"include_usage": true}` agar chunk terakhir berisi data usage.
- **FR-3.14** Stream diteruskan ke klien tanpa buffering.
- **FR-3.15** Selama belum ada byte dari upstream, proxy mengirim heartbeat SSE (`: ping\n\n`) setiap 15 detik ke klien. Tujuannya menghindari timeout ±100 detik Cloudflare (error 524) saat model reasoning lama sebelum token pertama.
- **FR-3.16** Header internal (`X-Project`, dll) tidak diteruskan ke upstream. Key portal tidak pernah diteruskan; proxy memakai kredensial 9Router sendiri.
- **FR-3.17** Setiap request diberi `request_id` (UUID v7), dikembalikan ke klien lewat header `X-Request-Id`.

**Pencatatan pemakaian**
- **FR-3.18** Ambil usage dari response:
  - Format OpenAI: objek `usage` (`prompt_tokens`, `completion_tokens`, `prompt_tokens_details.cached_tokens`) di response non-stream atau chunk terakhir stream.
  - Format Anthropic: `usage` di event `message_start` (input, `cache_creation_input_tokens`, `cache_read_input_tokens`) dan `message_delta` (output kumulatif).
- **FR-3.19** Jika upstream tidak mengirim usage (error, klien memutus di tengah stream), token diestimasi dari panjang teks dan baris ditandai `usage_estimated = true`.
- **FR-3.20** Hitung biaya Rupiah:
  `biaya = (input × harga_input + output × harga_output + cache_write × harga_cache_write + cache_read × harga_cache_read) / 1.000.000`
  Pembulatan ke atas ke Rupiah terdekat per request.
- **FR-3.21** Simpan baris `requests` dan entri `ledger_entries` (debit) dalam **satu transaksi database**, dengan lock baris saldo user (`SELECT ... FOR UPDATE`) agar request paralel tidak menghitung ganda.
- **FR-3.22** Request yang gagal sebelum sampai upstream (401/402/403/429/413) dicatat dengan biaya 0. Request yang gagal di upstream dicatat dengan usage yang tersedia (sering 0).
- **FR-3.23** Saldo boleh menjadi sedikit negatif akibat request terakhir yang lolos pemeriksaan minimum. Request berikutnya otomatis ditolak oleh FR-3.5. (Alternatif "reserve worst-case" seperti gateway komersial ditunda; lihat §13.)

**Error**
- **FR-3.24** Semua error dari proxy memakai format error yang sesuai endpoint (format OpenAI untuk `/v1/chat/completions`, format Anthropic untuk `/v1/messages`) agar tool klien menampilkan pesan dengan benar.

### 5.4 Katalog model dan harga

- **FR-4.0** Nama model publik bersih, tanpa prefix provider asli: `claude-sonnet-4.6`, `deepseek-v4.1-flash`, `glm-5.3`. Di OpenCode, provider dinamai `atheena`, sehingga model tampil sebagai `atheena/claude-sonnet-4.6`. ID upstream (`anthropic/...`, `cb/...`) dan provider asli **hanya terlihat oleh admin**; tidak pernah muncul di `/v1/models`, pesan error, maupun dashboard member. Model yang sama dari dua sumber (misal Claude dari Anthropic dan dari CodeBuddy) harus diberi nama publik berbeda, misal `claude-sonnet-4.6` dan `claude-sonnet-4.6-exp`.
- **FR-4.1** Tabel `models` bisa dikelola admin dari dashboard: nama publik, ID upstream, format (openai/anthropic/keduanya), provider, kategori (`resmi` / `eksperimen`), tier minimum, status aktif, konteks maksimum (informasi), dan 4 harga Rupiah per 1 juta token (input, output, cache write, cache read).
- **FR-4.2** Harga boleh 0 (misal model eksperimen yang belum ditentukan harganya). Biaya tetap dicatat 0, token tetap tercatat.
- **FR-4.3** Setiap perubahan harga tercatat di audit log (nilai lama dan baru).
- **FR-4.4** `GET /v1/models` hanya mengembalikan model yang aktif dan diizinkan untuk key tersebut.
- **FR-4.5** Tombol "Sinkronkan dari 9Router": ambil daftar model upstream, tampilkan yang belum ada di katalog untuk ditambahkan admin (tidak otomatis aktif).

### 5.5 Saldo dan top-up

- **FR-5.1** Saldo user = jumlah semua entri ledger. Untuk performa, kolom `users.balance_idr` diperbarui dalam transaksi yang sama dengan setiap entri ledger.
- **FR-5.2** Jenis entri ledger: `topup` (kredit), `usage` (debit), `adjustment` (kredit/debit oleh admin, wajib alasan), `refund` (kredit).
- **FR-5.3** Alur top-up (MVP):
  1. Member membuka halaman top-up, melihat QRIS statis dan instruksi.
  2. Tombol "Konfirmasi via WhatsApp" membuka `https://wa.me/6282312202002?text=...` dengan pesan terisi otomatis: nama, email, dan nominal yang diketik member.
  3. Member mengirim bukti bayar lewat WhatsApp.
  4. Admin menambah saldo secara manual dari dashboard admin (FR-7.1): pilih user, isi nominal dan catatan, simpan. Tercatat sebagai entri ledger `topup` beserta admin pelakunya, dan masuk audit log.
- **FR-5.4** (Ditunda setelah MVP) Upload bukti bayar di portal dengan antrean approval. Tabel `topup_requests` tetap dibuat sejak awal agar tidak perlu migrasi besar nanti.
- **FR-5.5** Peringatan saldo: banner di dashboard saat saldo < ambang (default Rp 10.000, bisa diatur user).

### 5.6 Dashboard member

- **FR-6.1** Ringkasan: saldo, pemakaian hari ini / 7 hari / 30 hari, model paling sering dipakai.
- **FR-6.2** Grafik pemakaian per hari, dengan toggle satuan **token** atau **Rupiah**.
- **FR-6.3** Filter: rentang tanggal, model, key, proyek, status (sukses/gagal).
- **FR-6.4** Tabel log request (metadata): waktu, model, key, proyek, token input/output/cache, biaya, latency, status, tanda estimasi. Paginasi.
- **FR-6.5** Halaman key (FR-2).
- **FR-6.6** Halaman top-up dan riwayat ledger.
- **FR-6.7** Halaman quickstart: snippet siap-salin untuk OpenCode (`opencode.json` dengan **satu** provider `atheena` OpenAI-compatible), Claude Code (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`, base URL dan key yang sama), Cursor, dan `curl`. Key user otomatis terisi di snippet saat baru dibuat.
- **FR-6.8** Ekspor CSV pemakaian sendiri.

### 5.7 Dashboard admin

- **FR-7.1** Manajemen user: daftar, tambah, ubah tier, suspend/aktifkan, lihat saldo, **tambah saldo (top-up manual)** dan adjustment (kredit/debit dengan alasan wajib).
- **FR-7.2** Riwayat top-up per user. (Antrean approval menyusul bersama FR-5.4.)
- **FR-7.3** Pemakaian global: semua filter FR-6.3 ditambah filter per user; ringkasan per user, per model, per proyek, per provider.
- **FR-7.4** Laporan bulanan per proyek dan per user, ekspor CSV.
- **FR-7.5** Katalog model dan harga (FR-4).
- **FR-7.6** Pengaturan: saldo minimum, rate limit default, batas stream, batas key per user, proyek dengan aturan "hanya provider resmi".
- **FR-7.7** Audit log: semua aksi admin (tambah user, approve top-up, adjustment, ubah harga, ubah pengaturan).
- **FR-7.8** Status sistem: health 9Router, jumlah stream aktif, error rate 1 jam terakhir, rata-rata latency.
- **FR-7.9** Tautan ke `router.atheena.online`.

### 5.8 Leaderboard

- **FR-8.1** Periode: minggu ini, bulan ini.
- **FR-8.2** Kategori: total token, jumlah request, biaya, dan "paling efisien" (rasio cache read terhadap total input, minimal 100 request agar adil).
- **FR-8.3** Menampilkan nama tampilan, bukan email.
- **FR-8.4** Member bisa memilih keluar dari leaderboard (opt-out) di pengaturan profil.

### 5.9 Landing page

- **FR-9.1** Dikerjakan setelah MVP. Isi: nama gateway, daftar model yang tersedia, cara mulai, tombol masuk.
- **FR-9.2** Arah desain: lihat §10.

---

## 6. Kebutuhan non-fungsional

| Aspek | Target |
|---|---|
| Overhead proxy | p95 < 50 ms (di luar waktu upstream) |
| Kapasitas fase ini | 50 user, ±100 stream bersamaan pada 1 instance |
| Ketersediaan | Best effort, target 99% di jam kerja (homelab, tanpa HA) |
| Backup | RPO 24 jam, RTO 2 jam |
| Retensi log request | 12 bulan (metadata), lalu diagregasi per hari |
| Retensi bukti top-up | 12 bulan |
| Privasi | Tidak ada isi prompt/response di database, log, maupun error tracking |
| Browser | Chrome/Edge/Firefox terbaru, layar desktop dan HP |

---

## 7. Model data

Semua tabel memakai `id` UUID v7, `created_at` dan `updated_at` (timestamptz). Nominal Rupiah disimpan sebagai `BIGINT` (Rupiah utuh); harga per 1 juta token disimpan sebagai `NUMERIC(14,2)` agar harga kecil tidak hilang.

**users**
`email` (unik), `display_name`, `role` (`member`/`admin`), `tier` (`basic`/`advanced`), `status` (`active`/`suspended`/`pending`), `balance_idr` BIGINT, `low_balance_threshold_idr`, `daily_cap_idr` (nullable), `leaderboard_opt_out` bool.

**api_keys**
`user_id`, `name`, `key_hash` (unik), `key_prefix`, `status` (`active`/`revoked`), `last_used_at`, `daily_cap_idr` (nullable), `model_allowlist` (array, nullable), `revoked_at`.

**models**
`public_name` (unik), `upstream_id`, `api_format` (`openai`/`anthropic`/`both`), `provider`, `category` (`official`/`experimental`), `min_tier`, `is_active`, `context_window`, `price_input_per_m`, `price_output_per_m`, `price_cache_write_per_m`, `price_cache_read_per_m`.

**requests** (tabel terbesar; partisi per bulan disarankan sejak awal)
`request_id`, `user_id`, `api_key_id`, `model_id`, `model_public_name`, `project` (nullable), `endpoint`, `is_stream`, `status_code`, `error_type` (nullable), `input_tokens`, `output_tokens`, `cache_write_tokens`, `cache_read_tokens`, `usage_estimated` bool, `price_snapshot` JSONB (4 harga saat request), `cost_idr` BIGINT, `latency_ms`, `ttft_ms` (time to first token), `client_ip_hash`, `user_agent`, `started_at`, `finished_at`.

**ledger_entries** (append-only; tidak ada UPDATE/DELETE)
`user_id`, `type` (`topup`/`usage`/`adjustment`/`refund`), `amount_idr` (positif = kredit, negatif = debit), `balance_after_idr`, `request_id` (nullable), `topup_request_id` (nullable), `note`, `created_by` (user_id admin, nullable).

**topup_requests**
`user_id`, `amount_requested_idr`, `amount_approved_idr` (nullable), `proof_path`, `status` (`pending`/`approved`/`rejected`), `reviewed_by`, `reviewed_at`, `review_note`.

**projects**
`slug` (unik, misal `helios`), `name`, `official_only` bool.

**audit_logs**
`actor_user_id`, `action`, `target_type`, `target_id`, `before` JSONB, `after` JSONB, `ip_hash`.

**settings** (key-value)
`key`, `value` JSONB.

Indeks minimum: `requests(user_id, started_at)`, `requests(model_id, started_at)`, `requests(project, started_at)`, `ledger_entries(user_id, created_at)`, `api_keys(key_hash)`.

Agregasi harian (`usage_daily`: user, model, project, tanggal, total token, total biaya, jumlah request) dihitung oleh job terjadwal untuk mempercepat grafik dan leaderboard.

---

## 8. API internal portal (untuk frontend)

Semua di bawah `/app/api/*`, diautentikasi lewat header Cloudflare Access (FR-1.1/1.2).

**Member**
- `GET /me` — profil, saldo, tier
- `PATCH /me` — nama tampilan, ambang saldo, opt-out leaderboard
- `GET /keys`, `POST /keys`, `DELETE /keys/{id}`
- `GET /usage/summary?from&to`
- `GET /usage/timeseries?from&to&unit=token|idr&model&key&project`
- `GET /usage/requests?from&to&...&page`
- `GET /usage/export.csv?...`
- `GET /ledger?page`
- `GET /topups`, `POST /topups` (multipart: nominal + bukti)
- `GET /models` — katalog yang boleh dipakai user
- `GET /leaderboard?period=week|month&metric=...`

**Admin** (`/app/api/admin/*`, wajib role admin)
- `GET/POST/PATCH /users`, `POST /users/{id}/adjustments`
- `GET /topups?status`, `POST /topups/{id}/approve`, `POST /topups/{id}/reject`, `GET /topups/{id}/proof`
- `GET /usage/*` (sama seperti member, ditambah filter `user`)
- `GET/POST/PATCH /models`, `POST /models/sync`
- `GET/PATCH /settings`, `GET/POST/PATCH /projects`
- `GET /audit-logs`
- `GET /health`

**Operasional**
- `GET /healthz` — liveness (tanpa auth, tidak diekspos lewat tunnel)
- `GET /readyz` — cek Postgres, Redis, dan 9Router

---

## 9. Infrastruktur dan spesifikasi

### 9.1 Stack yang disarankan

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Backend + proxy | Python 3.12, FastAPI, uvicorn, httpx (async) | Async untuk streaming; sudah familiar (Pallas) |
| ORM + migrasi | SQLAlchemy 2 + Alembic | Skema berubah lewat file migrasi |
| Database | PostgreSQL 16 | Sumber kebenaran, transaksi untuk ledger |
| Cache / rate limit | Redis 7 | State bersama agar portal tetap stateless |
| Frontend | React + Vite + TypeScript, dibuild statis | Dilayani Caddy, tidak butuh server Node di produksi |
| Grafik | Recharts atau ECharts | |
| Reverse proxy internal | Caddy | Titik pasang load balancer di fase berikutnya |
| Orkestrasi | Docker Compose | Pindah server cukup `docker compose up` |
| Tunnel | cloudflared (container atau service di CT 301) | Tanpa port terbuka ke internet |
| Monitoring (opsional) | Uptime Kuma | Mengecek `/readyz` dan 9Router tiap menit, kirim notifikasi Telegram kalau mati. Tidak wajib untuk MVP |

Layanan Docker Compose di CT 301: `caddy`, `api`, `worker` (job agregasi harian + pembersihan), `postgres`, `redis`, `cloudflared`.

### 9.2 Spesifikasi

| Komponen | vCPU | RAM | Disk | Catatan |
|---|---|---|---|---|
| CT 300 — 9Router (install baru dari upstream, menggantikan CT 110) | 2 | 4 GB | 20 GB | 1 instance, port 20128, state di SQLite (`/home/router/.9router/db/data.sqlite`). Build Next.js butuh ±2 GB RAM. Detail: `docs/ops/9router-ct300.md` |
| CT 301 — Portal (api, worker, Postgres, Redis, Caddy) | 2 | 4 GB | 50 GB | Cukup untuk 25 user. Naikkan ke 4 vCPU / 8 GB saat mendekati 50 user atau RAM terpakai > 75% |
| VM 999 — agent-hub (sudah ada) | 4 | 8 GB | 80 GB | Lingkungan development (Claude Code, OpenCode). Bukan produksi |
| Uptime Kuma (opsional, CT terpisah) | 1 | 512 MB | 4 GB | Terpisah agar tetap jalan saat CT 301 bermasalah |

Host EVO-X2 (96 GB) jauh dari batas. CT 110 (9Router lama) tetap hidup sampai CT 300 terbukti berjalan, baru dimatikan. Pertumbuhan database dengan metadata saja: ±0,5 KB per request, sehingga 50 user × ±300 request/hari ≈ 7,5 MB/hari (±2,7 GB/tahun sebelum agregasi).

### 9.3 Jaringan (bottleneck sebenarnya)

- **Wajib pindah node Proxmox dari WiFi ke kabel LAN** sebelum dipakai tim. Saat ini node keluar internet lewat WiFi NAT; jika WiFi putus, semua pengguna terputus bersamaan.
- Estimasi upload saat puncak: 50 user aktif × ±6 request/menit × ±150 KB konteks per request ≈ 45 MB/menit ≈ **6 Mbps upload** berkelanjutan, dan bisa lebih tinggi saat burst. Pastikan paket ISP punya upload memadai (idealnya ≥ 20 Mbps).
- UPS untuk host dan router rumah.
- Opsional: koneksi internet cadangan (tethering/ISP kedua) untuk failover manual.

### 9.4 Cloudflare

- **Zero Trust (Access) paket gratis mendukung hingga 50 user.** Ini pas dengan target fase ini, tetapi naik di atas 50 user butuh paket berbayar. Masukkan ke perencanaan anggaran jika sistem di-acc kantor.
- Timeout ±100 detik menunggu byte pertama dari origin; ditangani oleh heartbeat (FR-3.15). Wajib dites dengan model reasoning dan konteks besar.
- WAF rate limiting rule di `api.` sebagai lapisan pertama sebelum rate limit aplikasi.

---

## 10. Arah desain

- Dasar hitam, aksen logam/silver, satu biru elektrik untuk aksi utama.
- Palet: Void `#0A0A0B` (background), Graphite `#17181B` (kartu), Gunmetal `#2A2D33` (border), Chrome `#C8CCD2` (teks utama/logo), Steel `#8A9099` (teks sekunder), Electric blue `#2E5BFF` (CTA), Ice blue `#9EC5FF` (hover/highlight).
- Karakter: gritty dan neo-Y2K di landing page (grain tipis, heading display condensed, efek chrome hanya di logo/hero). Dashboard tetap flat dan tenang; angka memakai font monospace.
- Hindari tampilan template generik (Inter/Roboto sebagai font utama, gradien ungu, layout shadcn default).
- Wajib responsif (dashboard bisa dibuka di HP).
- Gunakan skill `frontend-design` saat mengerjakan UI.

---

## 11. Keamanan dan hardening

### Jaringan
- Tidak ada port yang dibuka ke internet; semua lewat Cloudflare Tunnel.
- Firewall CT 300 (Proxmox firewall / nftables): port 9Router hanya menerima dari IP CT 301 dan Tailscale admin.
- Firewall CT 301: hanya menerima dari cloudflared (lokal) dan Tailscale admin.
- `router.` hanya untuk email admin. Password default dashboard 9Router wajib diganti.

### Aplikasi
- Key disimpan sebagai hash; perbandingan memakai constant-time compare.
- JWT Cloudflare Access divalidasi (FR-1.2), bukan hanya header email.
- Semua endpoint admin cek role di server, bukan hanya disembunyikan di UI.
- Upload bukti top-up: validasi tipe file dari isi (magic bytes), batas ukuran, nama file acak, disimpan di luar web root.
- CSRF protection untuk endpoint dashboard yang mengubah data.
- Header keamanan (CSP, HSTS, X-Content-Type-Options) diatur di Caddy.
- Isi prompt/response tidak pernah masuk log, termasuk saat error.
- Dependensi dipindai (`pip-audit`, `npm audit`) di CI.

### OS dan layanan
- LXC unprivileged, container Docker jalan sebagai non-root.
- SSH hanya key, password auth dimatikan.
- `unattended-upgrades` aktif untuk patch keamanan.
- Secret di file `.env` (`chmod 600`), tidak masuk git; contoh di `.env.example`.

### Operasional
- Audit log untuk semua aksi admin.
- Rotasi kredensial 9Router dan key provider terdokumentasi di runbook.
- Log akses proxy (metadata) bisa dikirim ke stack monitoring/SIEM.

---

## 12. Observability, backup, dan runbook

- **Log**: format JSON, berisi `request_id`, user_id, model, status, latency. Tanpa isi prompt.
- **Metrik** (endpoint `/metrics` internal, opsional di MVP): request per menit, stream aktif, error rate, latency p50/p95, TTFT.
- **Health check**: `/healthz`, `/readyz` dipantau Uptime Kuma, notifikasi ke Telegram/email.
- **Backup**:
  - `pg_dump` harian, disimpan di disk lain (bukan disk CT 301), retensi 14 hari.
  - `vzdump` mingguan CT 300 dan CT 301.
  - Data 9Router di CT 300 ada di SQLite mode WAL (`/home/router/.9router/db/data.sqlite`), bukan `db.json`. Backup memakai online backup API SQLite (`sqlite3 .backup` atau `node:sqlite` `backup()`), bukan `cp` file saat aplikasi jalan. `machine-id` dan `jwt-secret` di `/home/router/.9router` ikut di-backup. Prosedur: `docs/ops/9router-ct300.md`.
  - Backup bukti top-up bersama `pg_dump`.
  - **Tes restore minimal sekali sebelum go-live**, lalu sebulan sekali.
- **Runbook** (`RUNBOOK.md`, dibuat di tahap ops): restart layanan, rollback deploy, restore database, menambah user baru (termasuk Cloudflare Access), rotasi key, apa yang dilakukan jika 9Router down.

---

## 13. Risiko dan concern

| # | Risiko | Dampak | Mitigasi |
|---|---|---|---|
| R1 | Akun CodeBuddy (bulk) kena ban atau kredit hangus | Model eksperimen tiba-tiba tidak tersedia | Kategorikan sebagai `experimental`; fallback ke provider resmi; jangan dijadikan andalan |
| R2 | Data sensitif (klien, kantor) lewat akun pihak ketiga tanpa kontrak | Temuan audit, kebocoran data | Aturan proyek `official_only` (FR-3.10); edukasi tim; di skala kantor, keluarkan CodeBuddy dari gateway resmi |
| R3 | Homelab jadi single point of failure (satu host, satu ISP, satu maintainer) | Semua user berhenti saat ada masalah | Kabel LAN, UPS, runbook, backup teruji; di skala kantor pindah ke infrastruktur kantor/cloud |
| R4 | Timeout Cloudflare 524 pada model reasoning | Error acak, sulit dilacak | Heartbeat SSE (FR-3.15), tes eksplisit sebelum go-live |
| R5 | Batas 50 user Cloudflare Access gratis | Tidak bisa menambah user ke-51 | Anggarkan paket berbayar jika di-acc kantor |
| R6 | 9Router single instance dan state di file | Downtime saat 9Router bermasalah; tidak bisa di-scale horizontal | Snapshot + restore cepat; desain "router bisa diganti" (§4.3) |
| R7 | Usage tidak dikirim upstream / stream putus | Biaya tercatat kurang | Estimasi + tanda `usage_estimated`; laporan admin menampilkan persentase estimasi |
| R8 | Biaya di portal tidak cocok dengan tagihan provider | Laporan ke kantor tidak akurat | Rekonsiliasi bulanan: bandingkan total portal vs console Anthropic |
| R9 | Agent loop tak terkendali menghabiskan saldo/dana | Pemborosan dana eksperimen | Batas biaya harian per key/user, rate limit, batas stream |
| R10 | Key bocor (commit ke repo, dibagikan) | Pemakaian oleh pihak lain | Hash, revoke instan, rate limit, notifikasi pemakaian anomali (fase berikutnya) |
| R11 | 9Router upstream tidak mendukung provider CodeBuddy seperti fork wyx0 | Akun CB tidak terbaca di CT 300 | Uji di CT 300 sebelum cutover; CT 110 lama tetap hidup sebagai cadangan; backup `db.json` dari CT 110 (9Router lama). Di CT 300, data 9Router ada di SQLite (`/home/router/.9router/db/data.sqlite`), bukan `db.json` |
| R12 | Race condition saat request paralel memotong saldo | Saldo salah | Transaksi + row lock (FR-3.21), test konkurensi |
| R13 | Bus factor: hanya satu orang yang paham sistem | Sistem terbengkalai saat pemilik tidak tersedia | Runbook, PRD, dan kode terdokumentasi |

**Keputusan yang sengaja ditunda**
- Model "reserve worst-case lalu settle" (menahan saldo sebesar biaya maksimum sebelum request). Fase ini memakai saldo minimum + boleh sedikit negatif (FR-3.23), karena lebih sederhana dan cukup untuk skala internal.

---

## 14. Tahapan dan acceptance criteria

Setiap tahap dikerjakan di environment dev/staging dulu, baru produksi. Satu tahap = satu atau beberapa file `tasks/TASK-xxx.md`.

### Tahap 0 — Fondasi
Dibagi dua jalur yang bisa berjalan paralel:

**0A — Aplikasi (dikerjakan Claude Code di VM 999, user `agent`)**: `tasks/TASK-000.md`
- Repo git, struktur monorepo (`backend/`, `frontend/`, `deploy/`, `docs/`, `tasks/`).
- Docker Compose untuk development (Postgres, Redis), `.env.example`, Alembic dengan migrasi awal seluruh tabel §7.
- Skeleton FastAPI dengan `/healthz` dan `/readyz`, pytest, linting, CI.
- Upstream development: 9Router lama di `http://10.10.10.13:3000` (satu-satunya alamat internal yang diizinkan firewall VM 999).

**0B — Infrastruktur (dikerjakan Dafin, bukan agent)**
- CT 300: 9Router upstream baru, uji semua provider, lalu cutover dari CT 110.
- CT 301: Docker, firewall (CT 300 hanya menerima dari CT 301 dan admin).
- Node Proxmox dipindah ke kabel LAN.
- Cloudflare Tunnel + Access untuk `ai.`, `api.`, `router.` di `atheena.online`.

- **Selesai jika**: `make test` lulus di VM 999; `GET /readyz` di lingkungan dev melaporkan Postgres, Redis, dan 9Router sehat; `router.` hanya bisa dibuka admin.

### Tahap 1 — Proxy inti (paling kritis)
- FR-3.1 s.d. FR-3.24 dengan user, key, dan katalog model dibuat lewat seed script (belum ada UI).
- **Selesai jika**:
  - OpenCode (openai-compatible dan anthropic) dan Claude Code berhasil memakai key portal, streaming dan non-streaming.
  - Token yang tercatat cocok dengan usage yang dilaporkan upstream untuk 20 request sampel (selisih 0 untuk request non-estimasi).
  - Prompt caching Anthropic terbukti bekerja (ada `cache_read_tokens` > 0 pada request berulang).
  - Request dengan TTFT > 100 detik tidak kena 524.
  - Test konkurensi: 20 request paralel dari satu user memotong saldo dengan tepat.
  - Saldo di bawah minimum → 402; model di luar tier → 403.

### Tahap 2 — Auth, user, key
- FR-1.x, FR-2.x, halaman key di dashboard.
- **Selesai jika**: user baru bisa login via Google, membuat key, memakai key dari OpenCode, dan revoke berlaku instan.

### Tahap 3 — Ledger dan top-up
- FR-5.x.
- **Selesai jika**: alur top-up dari upload bukti sampai saldo bertambah berjalan; semua perubahan saldo punya entri ledger; audit log terisi.

### Tahap 4 — Dashboard member (MVP selesai di sini)
- FR-6.x, agregasi harian.
- **Selesai jika**: member bisa melihat pemakaian dengan filter dan toggle token/Rupiah; angka di grafik cocok dengan jumlah di tabel log.

### Tahap 5 — Dashboard admin + leaderboard
- FR-7.x, FR-8.x.
- **Selesai jika**: admin bisa mengelola user, top-up, harga, dan mengekspor laporan bulanan per proyek.

### Tahap 6 — Hardening dan operasional
- §11 dan §12 lengkap, `RUNBOOK.md`, backup teruji restore.
- **Selesai jika**: checklist hardening terpenuhi dan restore dari backup berhasil dites.

### Tahap 7 — Landing page
- FR-9.x dengan arah desain §10.

### Pembagian kerja agent
- **Claude Code**: tahap 1 (proxy, streaming, usage, transaksi saldo), desain skema, keamanan auth, review akhir tiap tahap.
- **OpenCode (model murah)**: recon codebase, boilerplate CRUD, halaman dashboard berbasis API yang sudah jadi, test tambahan, dokumentasi.
- Aturan: setiap tahap ditutup dengan bukti (hasil test + langkah reproduksi), bukan hanya laporan "selesai" dari agent.

---

## 15. Keputusan terbuka

Setiap keputusan diberi nilai default agar pekerjaan tidak terhambat. Semua nilai default bisa diubah dari dashboard admin atau seed, tanpa ubah kode.

| # | Pertanyaan | Default yang dipakai | Dibutuhkan sebelum |
|---|---|---|---|
| Q1 | Harga Rupiah per model | Rp 0 untuk semua model; token tetap tercatat | Tahap 4 |
| Q2 | Aturan tier | `basic`: semua model kecuali kelas Opus. `advanced`: semua model | Tahap 1 (seed) |
| Q3 | Proyek `official_only` | `helios` | Tahap 1 (seed) |
| Q4 | Saldo minimum dan batas harian | Saldo minimum Rp 1.000; batas harian per user tidak aktif (null) | Tahap 1 (seed) |
| Q5 | Domain final | Tetap `atheena.online` selama fase ini | Sebelum dipakai di luar tim |
| Q6 | Approval model mahal | Cukup lewat tier `advanced` | Tahap 5 |
| Q7 | Kanal notifikasi admin | Belum ada; top-up lewat WhatsApp langsung | Setelah MVP |

---

## 16. Jalur skala (setelah fase ini)

| Fase | Skala | Perubahan |
|---|---|---|
| 1 (dokumen ini) | ≤ 50 user | 1 instance portal, Postgres + Redis di CT 301, 9Router 1 instance |
| 2 | 100+ user | Portal 2-3 replika di belakang Caddy/Traefik; Postgres di CT sendiri; koneksi internet cadangan; Cloudflare Access berbayar |
| 3 | 300 user, layanan resmi kantor | Pindah ke infrastruktur kantor/cloud; login Google Workspace kantor; 9Router diganti gateway multi-instance berbasis database; CodeBuddy dikeluarkan; SLA dan on-call |

Karena prinsip §4.3 dipatuhi sejak awal, fase 2 dan 3 tidak membutuhkan penulisan ulang logika billing.

---

## 17. Glosarium

- **Proxy gateway**: bagian portal yang menerima request API dari tool, memeriksa, meneruskan ke 9Router, dan mencatat pemakaian.
- **Stateless**: aplikasi tidak menyimpan data penting di memorinya sendiri, sehingga beberapa salinan bisa berjalan bersamaan.
- **Ledger**: catatan transaksi saldo yang hanya bisa ditambah, tidak diubah.
- **TTFT**: time to first token, waktu dari request dikirim sampai token pertama diterima.
- **Prompt caching**: fitur provider yang membuat konteks berulang jauh lebih murah; dicatat sebagai cache write/read.
- **Heartbeat SSE**: baris komentar kosong yang dikirim berkala di stream agar koneksi tidak dianggap mati.
- **Tier**: tingkat akses model per user.
