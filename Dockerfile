FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GALARDO_BIND=0.0.0.0

EXPOSE 8090 8095 8899

HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
  CMD python3 -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/v1/health').status==200 else 1)"

CMD ["python3", "backend/run_local.py"]
