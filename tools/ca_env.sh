#!/bin/bash
# Sumber ini sebelum menjalankan python yang perlu HTTPS:
#   source tools/ca_env.sh
[ -n "" ] && export SSL_CERT_FILE="$/etc/ssl/cert.pem"
