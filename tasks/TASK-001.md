# TASK-001 — Proxy inti dan pencatatan pemakaian

Referensi PRD: §4.3, §5.3 (FR-3.0 s.d. FR-3.24), §5.4 (FR-4.0, FR-4.4), §5.5 (FR-5.1), §14 Tahap 1.
Prasyarat: TASK-000 selesai dan disetujui.

## Tujuan
Bagian paling kritis: tool (OpenCode, Claude Code) memakai **satu base URL dan satu key portal**, request diteruskan ke 9Router, lalu setiap request tercatat token dan biayanya dengan akurat dan saldo dipotong dengan benar.

## Scope
1. **Endpoint** (FR-3.0): `GET /v1/models`, `POST /v1/chat/completions` (OpenAI), `POST /v1/messages` (Anthropic).
2. **Autentikasi key** (FR-3.1, 3.2): `Authorization: Bearer` atau `x-api-key`; hash SHA-256 dengan perbandingan constant-time; cache Redis TTL 60 detik; revoke menghapus cache. Key dibuat lewat CLI (`make create-key EMAIL=... NAME=...`), belum ada UI.
3. **Pemeriksaan berurutan** (FR-3.3 s.d. 3.10) dengan kode status dan format error sesuai endpoint (FR-3.24).
4. **Penerusan** (FR-3.11 s.d. 3.17):
   - Terjemahkan nama publik ke ID upstream. ID upstream dan provider asli tidak boleh bocor ke klien (FR-4.0).
   - `/v1/messages` diteruskan native ke endpoint Anthropic upstream tanpa konversi format.
   - Suntikkan `stream_options.include_usage` untuk stream OpenAI.
   - Streaming tanpa buffering.
   - **Heartbeat**: untuk stream, kirim `: ping\n\n` tiap 15 detik selama belum ada byte dari upstream. Untuk non-stream, setelah 30 detik tanpa response kirim spasi di depan body JSON tiap 15 detik (whitespace sebelum JSON tetap valid). Karena status 200 sudah terkirim, error upstream setelah heartbeat dikirim sebagai error di dalam body/stream sesuai format endpoint.
5. **Pencatatan** (FR-3.18 s.d. 3.23):
   - Usage dari format OpenAI dan Anthropic, termasuk cache write/read.
   - Estimasi jika usage tidak ada (`usage_estimated = true`).
   - Biaya Rupiah dengan snapshot harga, dibulatkan ke atas.
   - Insert `requests` + `ledger_entries` + update `users.balance_idr` dalam **satu transaksi** dengan `SELECT ... FOR UPDATE`.
   - Klien memutus di tengah stream: tetap catat usage yang sudah diterima.
6. **Rate limit dan batas stream** di Redis (FR-3.7, 3.8), supaya tetap benar saat portal nanti berjalan beberapa replika.

## Strategi test
- **Fake upstream** (ASGI app di `backend/tests/fake_upstream/`) yang bisa mensimulasikan: response OpenAI dan Anthropic, stream dan non-stream, usage lengkap/tanpa usage, TTFT lambat (durasi bisa dipercepat lewat parameter), error 4xx/5xx, dan putus di tengah stream.
- Test wajib:
  - Token dan biaya tepat untuk keempat kombinasi (OpenAI/Anthropic × stream/non-stream).
  - Cache write/read Anthropic tercatat terpisah dengan biaya benar.
  - Heartbeat terkirim saat TTFT lambat (stream dan non-stream).
  - **Konkurensi**: 20 request paralel dari satu user → saldo akhir = saldo awal − total biaya, dan tepat 20 entri ledger.
  - Saldo di bawah minimum → 402; model di luar tier → 403; project `helios` + model eksperimen → 403; rate limit → 429 dengan `Retry-After`.
  - ID upstream tidak muncul di response mana pun (termasuk `/v1/models` dan pesan error).
  - Isi prompt/response tidak muncul di log (tangkap log saat test).

## Verifikasi manual terhadap 9Router sungguhan (model murah saja)
1. OpenCode dengan satu provider `atheena` (OpenAI-compatible) ke `http://localhost:8000/v1`: satu percakapan stream.
2. Claude Code ke portal (`ANTHROPIC_BASE_URL=http://localhost:8000`, `ANTHROPIC_AUTH_TOKEN=<key portal>`): satu prompt singkat dengan model murah di katalog.
3. Bandingkan token di tabel `requests` dengan usage dari upstream untuk 10 request. Selisih harus 0 untuk request non-estimasi.
4. Prompt yang sama dua kali ke model format Anthropic: `cache_read_tokens > 0` di request kedua (jika model mendukung caching).

## Di luar scope
UI, Cloudflare Access, manajemen key dari dashboard, agregasi harian, leaderboard.

## Selesai jika
Semua test lulus, verifikasi manual 1-4 terdokumentasi (perintah + output ringkas) di `docs/progress.md`, dan checklist PRD §14 Tahap 1 terpenuhi. Uji timeout Cloudflare dilakukan dengan fake upstream; uji lewat Cloudflare sungguhan menyusul setelah tunnel ada.
