FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r /app/requirements.txt

# --- tool eksternal untuk panel Tools (P3) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl perl unzip traceroute \
        libnet-ssleay-perl libio-socket-ssl-perl \
    && rm -rf /var/lib/apt/lists/*

# nikto (perl)
RUN curl -fsSL https://github.com/sullo/nikto/archive/refs/tags/2.5.0.tar.gz -o /tmp/nikto.tgz \
    && tar -xzf /tmp/nikto.tgz -C /opt \
    && chmod +x /opt/nikto-2.5.0/program/nikto.pl \
    && ln -s /opt/nikto-2.5.0/program/nikto.pl /usr/local/bin/nikto

# subfinder (biner Go) - arsitektur mengikuti image (amd64/arm64)
ARG SUBFINDER_VER=2.6.7
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL "https://github.com/projectdiscovery/subfinder/releases/download/v${SUBFINDER_VER}/subfinder_${SUBFINDER_VER}_linux_${ARCH}.zip" -o /tmp/sf.zip \
    && unzip -o /tmp/sf.zip -d /tmp/sf \
    && install -m 0755 /tmp/sf/subfinder /usr/local/bin/subfinder \
    && rm -rf /tmp/sf /tmp/sf.zip /tmp/nikto.tgz

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GALARDO_BIND=0.0.0.0

EXPOSE 8090 8095 8899

HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
  CMD python3 -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/v1/health').status==200 else 1)"

CMD ["python3", "backend/run_local.py"]
