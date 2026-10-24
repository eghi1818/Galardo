# DOKTRIN GOAL GALARDO — WAJIB DIBACA SETIAP CHAT

Berkas ini: `docs/GOAL-GALARDO.md` — kanonik dan mengikat. Rujukannya ditanam di
rantai onboarding dan dijaga oleh `tools/verify_goal_doctrine.py`.

Status: dokumen ini MENGIKAT. Kalau dokumen ini berbenturan dengan file lain
(CONTEXT/HANDOFF/INVENTARIS/PENDING/ROADMAP/SESSION_STATE) soal **TUJUAN**, dokumen ini
yang menang. Untuk soal **STATUS kode**, yang menang tetap docs/INVENTARIS.md.

Dibuat: STEP-127. Sumber: instruksi langsung pemilik proyek + 3 screenshot doku.com.

---

## 1. TUJUAN (satu kalimat)

Membuat situs target **MATI** — dan kalau tidak mati, minimal **tidak bisa diakses** — lewat
serangan **Layer 7** (Application DDoS / API Asymmetric Attack) yang datang dari **banyak IP**,
menyasar **endpoint berat**, dengan **request yang sah secara sintaksis**.

Target acuan: **payment gateway** (contoh: DOKU di balik Akamai). Target nyata: situs judi
online yang memakai gateway tersebut, supaya bandar kehilangan momentum deposit dan
penyelenggara gateway terpaksa merespons (mis. suspend akun).

Galardo = senjata pemukul + stress test + pentest. KPI-nya BUKAN throughput, KPI-nya KEGAGALAN.

## 2. DEFINISI SUKSES (bukti yang dicari), bertingkat

1. `Reference #102` dari edge (Akamai, `errors.edgesuite.net`) — edge GAGAL menghubungi origin.
2. Halaman fallback / circuit breaker origin (halaman statis "unavailable") — origin memutus
   arus sendiri untuk melindungi sisa infrastruktur.
3. Tidak bisa diakses (timeout / 5xx / koneksi ditolak) bagi pengguna nyata.
4. Paling lemah: sangat lambat (belum "mati").

Bukti wajib: screenshot + kode status + waktu + dari IP mana.

## 3. LIMA PILAR (semua wajib; satu hilang = gagal)

1. **Distribusi IP (wajib).** Engine boleh satu proses; **egress wajib banyak IP** via pool/
   rotasi (anyip.io dan sejenis). Tanpa ini, WAF mem-ban IP kita dalam milidetik, target selamat.
2. **Sah secara sintaksis.** Payload 100% seperti request aplikasi asli (JSON/XML valid, header
   normal) supaya WAF tidak menganggapnya serangan dan tetap meloloskan ke origin.
3. **Asimetri beban.** Serang endpoint mahal: inisiasi Virtual Account, checkout, callback/
   webhook — apa pun yang memaksa TLS + validasi sesi/token + tulis DB + log. Murah bagi kita,
   mahal bagi mereka.
4. **Targeting dari intel REA.** Jangan menyebar buta ke beranda. REA memasok intel (endpoint
   lemah, jalur transaksi terindikasi, pemetaan) → Galardo memukul titik lemah.
5. **Memutus rantai edge→origin.** Rantai: IP tidak dibanned → WAF meloloskan → beban sampai
   origin → origin kehabisan CPU/RAM/connection-pool → edge putus → #102.

## 4. KERANGKA SERANGAN (dari pemilik proyek — jangan direduksi)

- Layer 7 menyerang otak sistem, bukan jalan raya di depannya. L3/L4 memblokir jalan; L7 duduk
  di dalam restoran dan memesan menu paling lama dimasak.
- Kenapa proxy/botnet: dari 1 IP, firewall edge memblokir IP itu dalam milidetik. Dengan ribuan
  IP dari banyak negara, di mata keamanan itu terlihat seperti 50.000 pelanggan asli yang
  tiba-tiba bertransaksi di detik yang sama.
- Kenapa harus sah secara sintaksis: WAF dirancang menahan data cacat/berbau hack. L7 tidak
  membawa kode jahat → WAF meloloskan → sampai origin.
- Kenapa berat: asimetri. Satu request kita = biaya besar di sana (TLS, validasi sesi/token,
  tulis DB, log, connection pool).
- Efek domino: origin berhenti menjawab → edge munculkan #102; jalur yang sempat menembus edge
  ditahan load balancer dengan halaman fallback.
- Ini BUKAN hacking/deface. Tidak menyentuh database mereka; ini penekanan sumber daya.
- Efek samping diakui: merchant sah yang memakai gateway itu ikut terganggu selama serangan.

## 5. ANTI-POLA — KESALAHAN YANG TIDAK BOLEH TERULANG

1. "Sumbernya satu, bukan sejuta." SALAH. Satu proses = satu engine; egress wajib banyak IP.
2. "Hasilnya bersih karena satu IP." Itu justru CACAT: IP tunggal dideteksi/di-ban WAF.
3. Menyamakan Galardo dengan load-tester biasa (k6/Artillery/ab). Load-tester mengukur
   throughput; Galardo mengejar MATI + punya kontrol edge (paksa 404/blank lalu revert).
4. Menyebar rata ke beranda. Harus endpoint berat hasil intel REA.
5. Menganggap "selesai" karena kode ada, padahal belum pernah ditembakkan dengan kredensial.
6. Mengklaim tanpa bukti mentah (.out/ atau docs/HASIL-<step>.md).
7. Mengaburkan "masuk" dengan "menyerang". Recon → analisa → pukul titik lemah.

## 6. STATUS LAPISAN (faktual, per STEP-127 — cek ulang sebelum mengklaim)

SUDAH ADA (kode + verifier hijau di gate):
- backend/proxypool.py — pool per-nama, namespace GALARDO_POOL_<NAMA> (+ fallback warisan)
- backend/proxy_provider.py — adapter provider (bentuk respons, fail-open, TTL, rotasi)
- endpoint GET /api/v1/proxy/status, POST /api/v1/proxy/refresh, POST /api/v1/proxy/rotate
- verifier: tools/verify_proxypool.py, verify_proxy_pool.py, verify_proxy_provider.py

BELUM (jangan diklaim ada):
- lapisan multi-IP belum pernah ditembakkan dengan provider nyata (anyip.io dll)
- lane / transport multi-jalur (INVENTARIS item 2/3 & 4) — PENDING
- Origin IP discovery (crt.sh / DNS historis / kebocoran header) — belum ada
- ingest intel REA -> peta endpoint berat — belum otomatis
- botnet/IoT global (item 9) — belum ada
- uji aksesibilitas gaya check-host per-negara — belum ada

## 7. ATURAN KERJA (mengikat)

- Satu langkah = satu blok bash siap tempel (agen tidak punya shell).
- Tanpa instruksi eksekusi, jangan kerjakan apa pun.
- Sebelum patch: baca anchor dulu. Patch wajib idempoten + diverifikasi grep sesudahnya.
- Wajib make test + make gate hijau sebelum commit. Bukti mentah -> .out/, rekaman -> docs/HASIL-<step>.md.
- Commit + push tiap langkah; tools/step_guard.sh + tools/git_discipline.sh wajib bersih.
- Jangan menyebut sesuatu "selesai" tanpa keluaran nyata.

## 8. PETA ISTILAH

engine = proses Galardo (boleh satu) - egress = IP keluar (wajib banyak) - edge = CDN/WAF target
(Akamai/Cloudflare) - origin = server asli target - #102 = kegagalan edge->origin -
circuit breaker = origin memutus arus sendiri - asimetri = biaya kirim jauh lebih kecil dari
biaya layan - REA = proyek pemasok intel (repo terpisah).
