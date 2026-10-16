# AUDIT DASHBOARD — catatan awal

Dibuat otomatis STEP-37. Isi: struktur, jumlah file, entry point.

## Struktur
```
dashboard/index.html
```

## Jumlah per ekstensi
```
   1 html
```

## Disajikan oleh
```
1:"""GALARDO - REST API + dashboard static server (stdlib only, ThreadingHTTPServer).
30:DASH_DIR = os.path.normpath(os.path.join(BASE, "..", "dashboard"))
301:    def _static(self, path):
305:        root = os.path.normpath(DASH_DIR)
309:        if not fp.startswith(DASH_DIR) or not os.path.isfile(fp):
352:                return self._static(path)
1298:    print(f"[galardo-api] listening on http://{host}:{port}  (dashboard: http://{host}:{port}/)")
```
