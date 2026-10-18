FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/var/data PORT=8000
WORKDIR /app
COPY requirements.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --require-hashes -r requirements.lock
COPY . .
RUN mkdir -p /var/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8000')+'/healthz',timeout=3)"
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 60 'app:create_app()'"]
