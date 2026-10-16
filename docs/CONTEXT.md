# KONTEKS MUTLAK — Galardo

## REPOSITORY KANONIK (TERKUNCI)
- Path: /Users/eghi/Documents/REPO/Galardo/Galardo-main
- Remote: git@github.com:eghi1818/Galardo.git
- WAJIB: setiap perintah kerja diawali `cd /Users/eghi/Documents/REPO/Galardo/Galardo-main`
  lalu diverifikasi dengan `pwd -P`
- /Users/eghi/Galardo = bekas lokasi .git -> diarsipkan, JANGAN dipakai

## Salinan lain (jangan dipakai kerja)
| Path | Catatan |
|---|---|
| /Users/eghi/Galardo_ARSIP_home | arsip; .git sudah diadopsi ke kanonik |
| ~/.openclaw-autoclaw/agents/eghi/workspace/galardo | salinan AutoClaw, punya .git sendiri |
| ~/Documents/Venice/Galardo | bukan repo; backup chat + db/ |

## Aturan output
- Output STEP -> <repo>/.out/   (BUKAN Desktop)
- STEP hijau -> langsung commit + push origin main
- Satu langkah -> satu patch -> satu verifikasi -> satu commit
- Tes merah -> STOP, rollback ke checkpoint

## JEBAKAN SHELL (zsh)
- `path` adalah variabel khusus terikat ke PATH. Jangan pakai sebagai nama
  variabel loop: `while read -r path` akan MENGHANCURKAN PATH.
  Pakai `rel`, `f`, atau `line`.
- zsh TIDAK memecah variabel tak dikutip: `cmd $LIST` = satu argumen.

## Core goals (tidak boleh dilanggar)
1. Mode Aktif: mesin eksekusi terverifikasi, bukan dashboard pasif
2. Goal 2: spike wajib pakai cache-buster `?__gb=<nonce>` menembus CDN ke origin,
   divalidasi siklus UP -> SUSPECT -> DOWN -> RECOVERING -> RECOVERED + time_to_recover
3. Goal 3: 404/blank hanya lewat Tier sah (T1 hosts, T2 shim lokal, T3 Cloudflare Edge Rule)
4. Fail-closed: GATE 0 kepemilikan, GATE 1 canary, GATE 2 toleransi fase 70/30
5. Proxy pihak ketiga HANYA untuk jalur probe, bukan beban utama

## Titik aman
git reset --hard checkpoint/galardo-v1.1-mulai

## Catatan integrasi (dari audit kode)
- backend/proxy.py TIDAK ADA dan tidak perlu: transport.py sudah punya proxy + set_tunnel
- Hook residential: field `proxy_pool` (kini ditolak sebagai field asing)
- Registry /sources sudah memodelkan `residential` sebagai capability hilang
