# Ringkasan — Atheena AI Gateway

Satu halaman untuk dibaca cepat. Detail lengkap ada di `PRD.md`.

## Apa ini
Satu pintu API AI untuk tim (target ≤ 50 orang). Setiap anggota punya akun, API key, dan saldo Rupiah. Setiap request dicatat token dan biayanya. Dirancang agar bisa naik ke 100-300 orang tanpa ditulis ulang.

## Keputusan yang sudah dikunci
- **Login**: Cloudflare Access + Google. Email harus di allowlist dan terdaftar aktif di portal.
- **Mata uang**: Rupiah saja. Harga per model diedit admin; snapshot harga disimpan per request.
- **Satu pintu**: satu base URL + satu key untuk semua model dan semua tool. Nama model bersih (`atheena/claude-sonnet-4.6`); provider asli hanya admin yang tahu.
- **Top-up (MVP)**: QRIS statis → konfirmasi via WhatsApp (wa.me/6282312202002) → admin tambah saldo manual dari dashboard. Tanpa payment gateway.
- **Pencatatan**: metadata saja (token, biaya, model, proyek, latency). Isi prompt tidak pernah disimpan.
- **Router**: 9Router upstream, 1 instance di CT 300 (menggantikan CT 110). Bisa diganti kapan saja.
- **Development**: Claude Code di VM 999 (agent-hub), user `agent`.
- **Pricing final**: ditunda. Tabel harga boleh 0 dulu.

## Arsitektur
```
Tool (OpenCode/Claude Code) → Cloudflare → CT 301 Portal (proxy + dashboard + Postgres + Redis) → CT 300 9Router → Anthropic / CodeBuddy / lainnya
```
- `ai.` dashboard (Access), `api.` endpoint tool (API key), `router.` dashboard 9Router (admin saja).
- Portal **stateless**: semua state di Postgres/Redis, supaya nanti tinggal tambah replika + load balancer.

## Spesifikasi
| | vCPU | RAM | Disk |
|---|---|---|---|
| CT 300 — 9Router | 2 | 2 GB | 20 GB |
| CT 301 — Portal + DB + Redis | 2 | 4 GB | 50 GB |

Cukup untuk 25 user; CT 301 dinaikkan ke 4 vCPU / 8 GB saat mendekati 50 user. Load balancer **belum perlu**.

## Stack
FastAPI + httpx async · Postgres 16 · Redis 7 · React/Vite · Caddy · Docker Compose · cloudflared · Uptime Kuma.

## Lima hal yang paling penting
1. **Proxy dan pencatatan token harus akurat dulu.** Semua fitur billing bergantung padanya.
2. **Request Claude diteruskan native** (`/v1/messages`) supaya prompt caching tidak hilang.
3. **Heartbeat SSE tiap 15 detik** untuk mencegah timeout Cloudflare (error 524) di model reasoning.
4. **Potong saldo dalam transaksi + row lock**, supaya request paralel tidak menghitung ganda.
5. **Pindah node Proxmox ke kabel LAN + UPS** sebelum tim mulai pakai.

## Concern terbesar
- Homelab = single point of failure (satu host, satu ISP, satu maintainer).
- Akun CodeBuddy rawan ban dan tidak cocok untuk data sensitif → proyek sensitif (misal `helios`) dikunci ke provider resmi.
- Cloudflare Access gratis maksimal **50 user**. Di atas itu berbayar.
- Biaya portal perlu direkonsiliasi bulanan dengan tagihan provider.

## Urutan kerja
0. Fondasi: repo + dev stack di VM 999 (Claude Code) · CT 300/301, firewall, tunnel, Access (Dafin)
1. **Proxy inti + pencatatan** ← paling kritis, dikerjakan Claude Code
2. Auth, user, API key
3. Ledger + top-up manual via WhatsApp
4. Dashboard member ← **MVP selesai di sini**
5. Dashboard admin + leaderboard
6. Hardening, backup teruji, runbook
7. Landing page (chrome/biru, gritty neo-Y2K)

## Default yang dipakai (bisa diubah kapan saja)
Harga Rp 0 dulu · tier `basic` = semua kecuali Opus · proyek `helios` = hanya provider resmi · saldo minimum Rp 1.000 · domain tetap atheena.online.
