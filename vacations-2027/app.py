"""Планирование отпусков на 2027 год. Flask + SQLite, без внешних API."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, Response, current_app, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

YEAR = 2027
HOLIDAYS = {date(YEAR, 1, d) for d in range(1, 9)} | {
    date(YEAR, 2, 23), date(YEAR, 3, 8), date(YEAR, 5, 1),
    date(YEAR, 5, 9), date(YEAR, 6, 12), date(YEAR, 11, 4),
}
NEW_YEAR_WORK_START = date(2026, 12, 31)
NEW_YEAR_WORK_END = date(2027, 1, 10)
NEW_YEAR_WORK_DATES = {
    (NEW_YEAR_WORK_START + timedelta(days=offset)).isoformat()
    for offset in range((NEW_YEAR_WORK_END - NEW_YEAR_WORK_START).days + 1)
}


def normalize_name(value):
    return re.sub(r"\s+", " ", str(value).strip()).casefold().replace("ё", "е")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _employee(row):
    return {key: row[key] for key in ("id", "full_name", "surname", "allowance_days")}


def _summary(periods):
    counts = []
    calendar = 0
    for period in periods:
        start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
        span = (end - start).days + 1
        calendar += span
        counts.append(sum(start + timedelta(days=d) not in HOLIDAYS for d in range(span)))
    return {"calendar_days": calendar, "leave_days": sum(counts), "has_long_period": any(n >= 14 for n in counts)}


def _plan(employee_id):
    row = get_db().execute("SELECT * FROM plans WHERE employee_id=?", (employee_id,)).fetchone()
    if row is None:
        return {"periods": [], "holiday": {"choice": "undecided", "dates": [], "comment": ""}, "submitted": False, "updated_at": None}
    return {"periods": json.loads(row["periods_json"]), "holiday": json.loads(row["holiday_json"]), "submitted": bool(row["submitted"]), "updated_at": row["updated_at"]}


def _plan_response(employee):
    plan = _plan(employee["id"])
    return {"employee": _employee(employee), "plan": plan, "summary": _summary(plan["periods"])}


def create_app(config=None):
    instance = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "instance"))
    app = Flask(__name__, instance_path=str(instance.resolve()))
    app.config.from_mapping(
        DATABASE=str(instance / "vacations.sqlite3"),
        SECRET_KEY=os.environ.get("APP_SECRET_KEY"),
        ADMIN_LOGIN=os.environ.get("ADMIN_LOGIN", "admin01"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin01"),
        MAX_CONTENT_LENGTH=22 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        RATELIMIT_ENABLED=True,
        SEED_ROSTER=True,
    )
    if config:
        app.config.update(config)
    database = Path(app.config["DATABASE"])
    database.parent.mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        keyfile = database.parent / ".session-key"
        try:
            fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as stream:
                stream.write(secrets.token_hex(32))
        app.config["SECRET_KEY"] = keyfile.read_text().strip()
    admin_password_hash = generate_password_hash(app.config["ADMIN_PASSWORD"])

    @app.before_request
    def prepare_request():
        g._database_path = app.config["DATABASE"]
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            token = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(token, session["csrf_token"]):
                return jsonify(error="Сессия устарела. Обновите страницу и повторите действие."), 403

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.teardown_appcontext
    def close_db(_exception):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            messages = {413: "Слишком большие файлы. Максимальный размер каждого — 10 МБ.", 404: "Запись не найдена.", 405: "Метод не поддерживается."}
            return jsonify(error=messages.get(error.code, error.description)), error.code
        return error

    @app.errorhandler(ValueError)
    def validation_error(error):
        return jsonify(error=str(error)), 400

    def require_role(role):
        def decorator(function):
            @wraps(function)
            def wrapper(*args, **kwargs):
                if session.get("role") != role:
                    return jsonify(error="Войдите в соответствующий раздел."), 401
                if role == "employee" and current_employee() is None:
                    session.pop("role", None)
                    return jsonify(error="Сотрудник не найден. Обратитесь в отдел кадров."), 401
                return function(*args, **kwargs)
            return wrapper
        return decorator

    def current_employee():
        return get_db().execute("SELECT * FROM employees WHERE id=?", (session.get("employee_id"),)).fetchone()

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Ожидается объект JSON.")
        return data

    def rate_limited(kind):
        if not app.config["RATELIMIT_ENABLED"]:
            return False
        now = time.time()
        key = hashlib.sha256(f"{kind}:{request.remote_addr}".encode()).hexdigest()
        db = get_db()
        db.execute("DELETE FROM login_attempts WHERE occurred_at<?", (now - 900,))
        count = db.execute("SELECT count(*) FROM login_attempts WHERE identity=?", (key,)).fetchone()[0]
        db.execute("INSERT INTO login_attempts(identity,occurred_at) VALUES (?,?)", (key, now))
        db.commit()
        return count >= (30 if kind == "admin" else 200)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/healthz")
    def health():
        get_db().execute("SELECT 1 FROM employees LIMIT 1")
        return jsonify(status="ok", year=YEAR)

    @app.get("/api/session")
    def session_info():
        result = {"role": session.get("role"), "csrf_token": session["csrf_token"], "year": YEAR}
        if result["role"] == "employee":
            employee = current_employee()
            if employee:
                result["employee"] = _employee(employee)
            else:
                result["role"] = None
        return jsonify(result)

    @app.post("/api/login/employee")
    def employee_login():
        if rate_limited("employee"):
            return jsonify(error="Слишком много попыток входа. Попробуйте через 15 минут."), 429
        data = payload()
        surname = data.get("surname")
        if not isinstance(surname, str) or not 1 <= len(surname.strip()) <= 100:
            raise ValueError("Введите свою фамилию.")
        rows = get_db().execute("SELECT * FROM employees WHERE surname_key=? ORDER BY full_name", (normalize_name(surname),)).fetchall()
        if not rows:
            return jsonify(error="Фамилия не найдена в списке. Проверьте написание или обратитесь в отдел кадров."), 404
        if len(rows) > 1:
            selected = [row for row in rows if str(row["id"]) == str(data.get("employee_id", ""))]
            if not selected:
                return jsonify(error="Выберите своё полное ФИО.", code="ambiguous_surname", employees=[{"id": r["id"], "full_name": r["full_name"]} for r in rows]), 409
            employee = selected[0]
        else:
            employee = rows[0]
        csrf = session["csrf_token"]
        session.clear()
        session.update(role="employee", employee_id=employee["id"], csrf_token=csrf)
        session.permanent = True
        return jsonify(role="employee", employee=_employee(employee))

    @app.post("/api/login/admin")
    def admin_login():
        if rate_limited("admin"):
            return jsonify(error="Слишком много попыток входа. Попробуйте через 15 минут."), 429
        data = payload()
        if not isinstance(data.get("login"), str) or not isinstance(data.get("password"), str):
            raise ValueError("Введите логин и пароль.")
        login_ok = hmac.compare_digest(data["login"].encode(), app.config["ADMIN_LOGIN"].encode())
        password_ok = check_password_hash(admin_password_hash, data["password"])
        if not login_ok or not password_ok:
            return jsonify(error="Неверный логин или пароль."), 401
        csrf = session["csrf_token"]
        session.clear()
        session.update(role="admin", csrf_token=csrf)
        session.permanent = True
        return jsonify(role="admin")

    @app.post("/api/logout")
    def logout():
        csrf = session["csrf_token"]
        session.clear()
        session["csrf_token"] = csrf
        return jsonify(ok=True)

    @app.get("/api/employee/plan")
    @require_role("employee")
    def employee_plan():
        return jsonify(_plan_response(current_employee()))

    @app.put("/api/employee/plan")
    @require_role("employee")
    def save_plan():
        data = payload()
        employee = current_employee()
        periods = data.get("periods")
        if not isinstance(periods, list) or len(periods) > 24:
            raise ValueError("Укажите не более 24 периодов отпуска.")
        cleaned = []
        for period in periods:
            if not isinstance(period, dict):
                raise ValueError("Некорректный период отпуска.")
            try:
                start = date.fromisoformat(period.get("start", ""))
                end = date.fromisoformat(period.get("end", ""))
            except (ValueError, TypeError):
                raise ValueError("Укажите начало и конец каждого периода.") from None
            if start.year != YEAR or end.year != YEAR:
                raise ValueError("Все даты отпуска должны относиться к 2027 году.")
            if end < start:
                raise ValueError("Конец отпуска не может быть раньше начала.")
            cleaned.append({"start": start.isoformat(), "end": end.isoformat()})
        cleaned.sort(key=lambda p: p["start"])
        for earlier, later in zip(cleaned, cleaned[1:]):
            if earlier["end"] >= later["start"]:
                raise ValueError("Периоды отпуска не должны пересекаться.")
        holiday = data.get("holiday", {})
        if not isinstance(holiday, dict) or holiday.get("choice") not in ("undecided", "not_working", "selected_dates"):
            raise ValueError("Выберите ответ о работе в новогодние праздники.")
        dates = holiday.get("dates", [])
        if not isinstance(dates, list) or any(not isinstance(d, str) or d not in NEW_YEAR_WORK_DATES for d in dates):
            raise ValueError("Для работы в праздники выберите даты с 31 декабря 2026 по 10 января 2027 года.")
        if holiday["choice"] == "selected_dates" and not dates:
            raise ValueError("Выберите хотя бы один день работы в праздники.")
        if holiday["choice"] != "selected_dates":
            dates = []
        comment = holiday.get("comment", "")
        if not isinstance(comment, str) or len(comment) > 1000:
            raise ValueError("Комментарий должен содержать не более 1000 символов.")
        holiday = {"choice": holiday["choice"], "dates": sorted(set(dates)), "comment": comment.strip()}
        submitted = data.get("submitted", False)
        if not isinstance(submitted, bool):
            raise ValueError("Некорректный статус анкеты.")
        summary = _summary(cleaned)
        if summary["leave_days"] > employee["allowance_days"]:
            raise ValueError(f"Запланировано больше доступных дней ({employee['allowance_days']}). Для изменения лимита обратитесь в отдел кадров.")
        if submitted and not cleaned:
            raise ValueError("Добавьте хотя бы один период отпуска.")
        if submitted and not summary["has_long_period"]:
            raise ValueError("Один из периодов должен включать минимум 14 дней отпуска без учёта нерабочих праздничных дней.")
        get_db().execute(
            "INSERT INTO plans(employee_id,periods_json,holiday_json,submitted,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(employee_id) DO UPDATE SET periods_json=excluded.periods_json,holiday_json=excluded.holiday_json,submitted=excluded.submitted,updated_at=excluded.updated_at",
            (employee["id"], json.dumps(cleaned), json.dumps(holiday, ensure_ascii=False), int(submitted), _now()),
        )
        get_db().commit()
        return jsonify(_plan_response(employee))

    @app.get("/api/admin/dashboard")
    @require_role("admin")
    def dashboard():
        employees = [_plan_response(row) for row in get_db().execute("SELECT * FROM employees ORDER BY full_name")]
        employees = [{**r["employee"], "plan": r["plan"], "summary": r["summary"]} for r in employees]
        submitted = sum(r["plan"]["submitted"] for r in employees)
        drafts = sum(bool(r["plan"]["updated_at"]) and not r["plan"]["submitted"] for r in employees)
        return jsonify(year=YEAR, employees=employees, stats={"total": len(employees), "submitted": submitted, "drafts": drafts, "missing": len(employees) - submitted - drafts})

    def valid_employee_input(data, existing=None):
        full_name = data.get("full_name", existing["full_name"] if existing else "")
        if not isinstance(full_name, str) or not 3 <= len(full_name.strip()) <= 200 or len(full_name.split()) < 2:
            raise ValueError("Укажите полное ФИО сотрудника (минимум фамилию и имя).")
        full_name = " ".join(full_name.split())
        if not re.fullmatch(r"[А-Яа-яЁёA-Za-z\s.’'\-]+", full_name):
            raise ValueError("ФИО может содержать только буквы, пробелы, дефисы и апострофы.")
        allowance = data.get("allowance_days", existing["allowance_days"] if existing else 28)
        if isinstance(allowance, bool) or not isinstance(allowance, int) or not 14 <= allowance <= 366:
            raise ValueError("Лимит отпуска должен быть целым числом от 14 до 366 дней.")
        return full_name, allowance

    @app.post("/api/admin/employees")
    @require_role("admin")
    def add_employee():
        name, allowance = valid_employee_input(payload())
        try:
            cursor = get_db().execute("INSERT INTO employees(full_name,full_name_key,surname,surname_key,allowance_days) VALUES (?,?,?,?,?)", (name, normalize_name(name), name.split()[0], normalize_name(name.split()[0]), allowance))
            get_db().commit()
        except sqlite3.IntegrityError:
            return jsonify(error="Сотрудник с таким ФИО уже есть в списке."), 409
        row = get_db().execute("SELECT * FROM employees WHERE id=?", (cursor.lastrowid,)).fetchone()
        return jsonify(employee=_employee(row)), 201

    @app.patch("/api/admin/employees/<int:employee_id>")
    @require_role("admin")
    def update_employee(employee_id):
        employee = get_db().execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
        if not employee:
            return jsonify(error="Сотрудник не найден."), 404
        name, allowance = valid_employee_input(payload(), employee)
        if _summary(_plan(employee_id)["periods"])["leave_days"] > allowance:
            raise ValueError("Сначала скорректируйте отпуск: его продолжительность превышает новый лимит.")
        try:
            get_db().execute("UPDATE employees SET full_name=?,full_name_key=?,surname=?,surname_key=?,allowance_days=? WHERE id=?", (name, normalize_name(name), name.split()[0], normalize_name(name.split()[0]), allowance, employee_id))
            get_db().commit()
        except sqlite3.IntegrityError:
            return jsonify(error="Сотрудник с таким ФИО уже есть в списке."), 409
        return jsonify(employee=_employee(get_db().execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()))

    @app.post("/api/admin/import/preview")
    @require_role("admin")
    def import_preview():
        from importer import preview_import
        allowed = {".xlsx", ".csv", ".txt", ".docx", ".pdf"}
        with tempfile.TemporaryDirectory(prefix="vacations-import-") as folder:
            paths = []
            for field in ("vacations_file", "names_file"):
                file = request.files.get(field)
                if not file or not file.filename:
                    raise ValueError("Загрузите оба документа: список для отпусков и документ с полными ФИО.")
                suffix = Path(file.filename).suffix.lower()
                if suffix not in allowed:
                    raise ValueError("Поддерживаются XLSX, CSV, TXT, DOCX и PDF с текстом.")
                path = Path(folder) / f"{field}{suffix}"
                file.save(path)
                if path.stat().st_size > 10 * 1024 * 1024:
                    raise ValueError("Размер каждого документа не должен превышать 10 МБ.")
                paths.append(path)
            try:
                result = preview_import(*paths)
            except ValueError:
                raise
            except Exception:
                app.logger.warning("Document import rejected: unreadable or unsupported content")
                raise ValueError("Не удалось прочитать документ. Проверьте формат и отсутствие пароля.") from None
        token = secrets.token_urlsafe(32)
        db = get_db()
        db.execute("DELETE FROM import_previews WHERE created_at<?", (time.time() - 3600,))
        db.execute("INSERT INTO import_previews(token,session_key,payload_json,created_at) VALUES (?,?,?,?)", (token, session["csrf_token"], json.dumps(result, ensure_ascii=False), time.time()))
        db.commit()
        return jsonify(token=token, **result)

    @app.post("/api/admin/import/confirm")
    @require_role("admin")
    def import_confirm():
        token = payload().get("token")
        if not isinstance(token, str):
            raise ValueError("Сначала загрузите документы для предварительной проверки.")
        row = get_db().execute("SELECT payload_json FROM import_previews WHERE token=? AND session_key=? AND created_at>?", (token, session["csrf_token"], time.time() - 3600)).fetchone()
        if not row:
            raise ValueError("Предварительная проверка устарела. Загрузите документы повторно.")
        result = json.loads(row["payload_json"])
        added = 0
        for employee in result["matched"]:
            name = employee["full_name"]
            cursor = get_db().execute("INSERT OR IGNORE INTO employees(full_name,full_name_key,surname,surname_key) VALUES (?,?,?,?)", (name, normalize_name(name), employee["surname"], normalize_name(employee["surname"])))
            added += cursor.rowcount
        get_db().commit()
        return jsonify(added=added, existing=len(result["matched"]) - added, total=get_db().execute("SELECT count(*) FROM employees").fetchone()[0])

    @app.get("/api/admin/import/report")
    @require_role("admin")
    def initial_import_report():
        row = get_db().execute("SELECT value FROM metadata WHERE key='initial_import_report'").fetchone()
        return jsonify(json.loads(row[0]) if row else {})

    @app.get("/api/admin/export.csv")
    @require_role("admin")
    def export_csv():
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["ФИО", "Статус", "Лимит дней", "Дней отпуска", "Периоды отпуска 2027", "Работа в новогодние праздники", "Даты работы", "Комментарий", "Обновлено (UTC)"])
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        for employee in get_db().execute("SELECT * FROM employees ORDER BY full_name"):
            plan = _plan(employee["id"])
            status = "Отправлено" if plan["submitted"] else "Черновик" if plan["updated_at"] else "Не заполнено"
            holiday = plan["holiday"]
            writer.writerow([safe(employee["full_name"]), status, employee["allowance_days"], _summary(plan["periods"])["leave_days"], " | ".join(f"{p['start']} — {p['end']}" for p in plan["periods"]), {"undecided": "Пока не знаю", "not_working": "Не планирую", "selected_dates": "В выбранные дни"}[holiday["choice"]], ", ".join(holiday["dates"]), safe(holiday["comment"]), plan["updated_at"] or ""])
        return Response("\ufeff" + stream.getvalue(), content_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="vacations-2027.csv"'})

    with app.app_context():
        g._database_path = app.config["DATABASE"]
        db = get_db()
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                full_name_key TEXT NOT NULL UNIQUE,
                surname TEXT NOT NULL,
                surname_key TEXT NOT NULL,
                allowance_days INTEGER NOT NULL DEFAULT 28
            );
            CREATE INDEX IF NOT EXISTS employees_surname ON employees(surname_key);
            CREATE TABLE IF NOT EXISTS plans (
                employee_id INTEGER PRIMARY KEY REFERENCES employees(id),
                periods_json TEXT NOT NULL,
                holiday_json TEXT NOT NULL,
                submitted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS import_previews (
                token TEXT PRIMARY KEY, session_key TEXT NOT NULL,
                payload_json TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                identity TEXT NOT NULL, occurred_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS attempts_identity ON login_attempts(identity,occurred_at);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        seed = database.parent / "initial-roster.json"
        if not seed.exists():
            seed = Path(__file__).parent / "private" / "initial-roster.json"
        if app.config["SEED_ROSTER"] and seed.exists():
            result = json.loads(seed.read_text(encoding="utf-8-sig"))
            version = result.get("version")
            version = version if isinstance(version, str) and version else None
            previous = db.execute("SELECT value FROM metadata WHERE key='roster_version'").fetchone()
            empty = db.execute("SELECT count(*) FROM employees").fetchone()[0] == 0
            if empty or (version and (previous is None or previous["value"] != version)):
                # A versioned roster update adds people once, retaining saved plans,
                # HR edits and IDs. An unversioned custom seed keeps its old behavior.
                # Explicit additions also preserve names HR changed before upgrading.
                employees = result["matched"] if empty else result.get("additions", result["matched"])
                for employee in employees:
                    name = employee["full_name"]
                    surname = employee["surname"]
                    db.execute("INSERT OR IGNORE INTO employees(full_name,full_name_key,surname,surname_key) VALUES (?,?,?,?)", (name, normalize_name(name), surname, normalize_name(surname)))
                db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES ('initial_import_report',?)", (json.dumps(result, ensure_ascii=False),))
                if version:
                    db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES ('roster_version',?)", (version,))
        db.commit()
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
