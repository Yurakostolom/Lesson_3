#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p instance
if [[ -f instance/gunicorn.pid ]]; then
  server_pid=$(cat instance/gunicorn.pid)
  if ! kill -0 "$server_pid" 2>/dev/null; then
    rm instance/gunicorn.pid
  fi
fi
if [[ ! -f instance/gunicorn.pid ]]; then
  .venv/bin/gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 \
    --daemon --pid instance/gunicorn.pid \
    --access-logfile instance/access.log --error-logfile instance/server.log \
    'app:create_app()'
fi
.venv/bin/python - <<'PY'
import json
import time
import urllib.error
import urllib.request
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2) as response:
            result = json.load(response)
        if result == {'status': 'ok', 'year': 2027}:
            print('Сервер отпусков 2027 готов.')
            break
    except (OSError, urllib.error.URLError):
        pass
    time.sleep(1)
else:
    raise SystemExit('Сервер не ответил. Проверьте instance/server.log.')
PY
