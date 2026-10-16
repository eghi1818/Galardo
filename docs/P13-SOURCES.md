# P1.3 — Registry Sumber & Kapabilitas residential (STEP-53)

## Rujukan 'residential' di repo
```
backend/identity_sim.py:10:- no third-party/residential proxies, no IP rotation services
backend/transport.py:37:SUPPORTED_ENCODINGS = ("residential", "identity", "gzip", "base64", "base64+gzip")
backend/srccap.py:40:    "udp", "spoof_src", "residential", "datacenter", "high_concurrency",
backend/srccap.py:43:KINDS = ("local", "vps", "worker", "proxy", "residential")
tools/galardo_srccap.py:38:    for need in (["http1", "tls13"], ["http1", "udp"], ["http1", "spoof_src", "residential"]):
tools/verify_proxy_pool.py:73:    norm = parse(base + "proxy_pool: 'residential'\n")
tools/verify_proxy_pool.py:82:          norm.get("proxy_pool") == ["residential"],
tests/tests_integration.py:130:    check("proxy_pool diterima (jalur probe residential)",
tests/tests_integration.py:399:    st, pk2 = req("POST", "/sources/pick", {"required": ["http1", "residential"]})
tests/tests_integration.py:401:          st == 409 and "residential" in json.dumps(pk2), str(pk2)[:200])
tests/tests_integration.py:489:FIX_WITH_PROXY = FIX_VALID + "proxy_pool: 'residential'\n"
```

## Handler /sources
```
1011:            if api_path == "/sources/matrix" and method == "GET":
1014:            if api_path == "/sources/pick" and method == "POST":
1022:            if api_path == "/sources" and method == "GET":
1029:            if api_path == "/sources" and method == "POST":
1048:            m = _match(api_path, "/sources/*/probe")
1057:            m = _match(api_path, "/sources/*/udp")
1076:            m = _match(api_path, "/sources/*/remove")
1083:            m = _match(api_path, "/sources/*")
```

## Langkah berikut

- Resolver nama pool -> endpoint proxy (host, port, user, pass).
- Sambungkan ke jalur probe (transport.set_tunnel) supaya probe tidak lagi dari satu IP.
- Tanpa kredensial: pool 'residential' boleh kosong, probe jatuh ke koneksi langsung.
