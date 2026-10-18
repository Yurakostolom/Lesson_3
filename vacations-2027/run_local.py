"""Local desktop launcher. The browser is the UI; all data stays on this PC."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import signal
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# -I isolates the bundled interpreter from user/site environment variables.
# Include only this application's own directory for local application modules.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

APP_ID = "medsonar-vacations-local-2027"
LOCAL_VERSION = "1.0.2"


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Medsonar" / "Vacations2027"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Medsonar" / "Vacations2027"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "medsonar-vacations-2027"


def data_identity(data_dir: Path) -> str:
    return hashlib.sha256(str(data_dir.resolve()).encode("utf-8")).hexdigest()


def create_local_app(data_dir: Path):
    from app import create_app

    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    application = create_app({
        "DATABASE": str(data_dir / "vacations.sqlite3"),
        "SECRET_KEY": None,
        "SESSION_COOKIE_SECURE": False,
        "ADMIN_LOGIN": "admin01",
        "ADMIN_PASSWORD": "admin01",
        "SEED_ROSTER": True,
    })

    @application.get("/_local/status")
    def local_status():
        return {"app": APP_ID, "data": data_identity(data_dir), "year": 2027}

    return application


def existing_server(data_dir: Path) -> str | None:
    """Reuse only an instance of this program with the same local database."""
    try:
        marker = json.loads((data_dir / ".local-server.json").read_text(encoding="utf-8"))
        port = marker["port"]
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            return None
        address = f"http://127.0.0.1:{port}"
        # A localhost request must never go through machine-wide network proxies.
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with client.open(address + "/_local/status", timeout=0.8) as response:
            status = json.load(response)
        if status == {"app": APP_ID, "data": data_identity(data_dir), "year": 2027}:
            return address
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        pass
    return None


def open_browser(address: str):
    try:
        if not webbrowser.open(address, new=2):
            print(f"Откройте этот адрес в браузере: {address}", flush=True)
    except Exception:
        print(f"Откройте этот адрес в браузере: {address}", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Отпуска сотрудников на 2027 год — локальная программа")
    parser.add_argument("--data-dir", type=Path, default=None, help="Каталог базы данных (по умолчанию — папка текущего пользователя)")
    parser.add_argument("--port", type=int, default=None, help="Порт от 1024 до 65535; по умолчанию автоматически 8765–8784")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер автоматически")
    options = parser.parse_args(argv)
    if options.port is not None and not 1024 <= options.port <= 65535:
        parser.error("Порт должен быть от 1024 до 65535.")
    data_dir = (options.data_dir or default_data_dir()).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    active = existing_server(data_dir)
    if active:
        print(f"Программа уже запущена: {active}", flush=True)
        if not options.no_browser:
            open_browser(active)
        return 0

    from waitress import create_server

    application = create_local_app(data_dir)
    ports = [options.port] if options.port else range(8765, 8785)
    server = None
    port = None
    for candidate in ports:
        try:
            server = create_server(application, host="127.0.0.1", port=candidate, threads=4, expose_tracebacks=False)
        except OSError as error:
            if error.errno not in (errno.EADDRINUSE, 10048) and getattr(error, "winerror", None) != 10048:
                raise
        else:
            port = candidate
            break
    if server is None:
        print("Не удалось открыть локальный порт. Закройте другую копию программы или запустите с параметром --port 8786.", file=sys.stderr)
        return 1

    address = f"http://127.0.0.1:{port}"
    marker = data_dir / ".local-server.json"
    marker.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
    print(f"\nОтпуска сотрудников · 2027 · версия {LOCAL_VERSION}", flush=True)
    print(f"Адрес программы: {address}", flush=True)
    print(f"Данные: {data_dir}", flush=True)
    print("Оставьте это окно открытым, пока работаете с программой.", flush=True)
    print("Для завершения закройте это окно или нажмите Ctrl+C.\n", flush=True)
    if not options.no_browser:
        timer = threading.Timer(0.7, open_browser, args=(address,))
        timer.daemon = True
        timer.start()

    def terminate(_signum, _frame):
        raise KeyboardInterrupt

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, terminate)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nПрограмма остановлена. Данные сохранены.", flush=True)
    finally:
        server.close()
        try:
            saved = json.loads(marker.read_text(encoding="utf-8"))
            if saved.get("pid") == os.getpid():
                marker.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        print("Не удалось запустить программу. Сведения об ошибке:", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
