#!/bin/bash
# Sumber ini sebelum menjalankan python yang perlu HTTPS:
#   source tools/ca_env.sh
CA="$(python3 -c "import sys; sys.path.insert(0, '/Users/eghi/Documents/REPO/Galardo/Galardo-main/backend'); import netssl; print(netssl.ca_file() or '')" 2>/dev/null)"
if [ -n "$CA" ]; then
  export SSL_CERT_FILE="$CA"
  echo "SSL_CERT_FILE=$CA"
else
  echo "CA bundle tidak ditemukan - jalankan: python3 tools/tls_doctor.py"
fi
