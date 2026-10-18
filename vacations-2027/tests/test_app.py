"""End-to-end API checks using a temporary database and synthetic employees."""

import json
from io import BytesIO

import pytest
from openpyxl import Workbook

from app import create_app, get_db, normalize_name


EMPLOYEE_LOGIN = "/api/login/employee"
ADMIN_LOGIN = "/api/login/admin"


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "vacations.sqlite3"),
            "SECRET_KEY": "synthetic-test-secret",
            "ADMIN_LOGIN": "admin01",
            "ADMIN_PASSWORD": "admin01",
            "SEED_ROSTER": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    with application.app_context():
        connection = get_db()
        employees = [
                (1, "Иванов", "Иванов Иван Иванович", 28),
                (2, "Петрова", "Петрова Анна Сергеевна", 28),
                (3, "Смирнов", "Смирнов Алексей Петрович", 28),
                (4, "Смирнов", "Смирнов Сергей Николаевич", 28),
        ]
        connection.executemany(
            "INSERT INTO employees (id, surname, full_name, allowance_days, surname_key, full_name_key) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(*employee, normalize_name(employee[1]), normalize_name(employee[2])) for employee in employees],
        )
        connection.commit()
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client):
    response = client.get("/api/session")
    assert response.status_code == 200
    token = response.get_json()["csrf_token"]
    assert token
    return {"X-CSRF-Token": token}


def employee_login(client, surname="Иванов", employee_id=None):
    payload = {"surname": surname}
    if employee_id is not None:
        payload["employee_id"] = employee_id
    return client.post(EMPLOYEE_LOGIN, json=payload, headers=csrf(client))


def admin_login(client):
    return client.post(
        ADMIN_LOGIN,
        json={"login": "admin01", "password": "admin01"},
        headers=csrf(client),
    )


def plan(periods=None, *, submitted=False, holiday=None):
    return {
        "periods": periods if periods is not None else [{"start": "2027-07-05", "end": "2027-07-18"}],
        "holiday": holiday or {"choice": "undecided", "dates": [], "comment": ""},
        "submitted": submitted,
    }


def save_plan(client, payload):
    return client.put("/api/employee/plan", json=payload, headers=csrf(client))


def test_health_checks_the_database(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "year": 2027}


def test_anonymous_requests_cannot_read_plans_or_export_roster(client):
    for endpoint in ("/api/employee/plan", "/api/admin/dashboard", "/api/admin/export.csv"):
        assert client.get(endpoint).status_code in (401, 403)
    session = client.get("/api/session").get_json()
    assert "Иванов" not in str(session)
    assert "Иванов Иван Иванович" not in str(session)


def test_mutations_require_the_current_session_csrf_token(client):
    assert client.post(EMPLOYEE_LOGIN, json={"surname": "Иванов"}).status_code in (400, 403)
    assert client.post(
        EMPLOYEE_LOGIN, json={"surname": "Иванов"}, headers={"X-CSRF-Token": "invalid"}
    ).status_code in (400, 403)
    headers = csrf(client)
    assert client.post(EMPLOYEE_LOGIN, json={"surname": "Иванов"}, headers=headers).status_code == 200
    assert client.put("/api/employee/plan", json=plan()).status_code in (400, 403)
    assert client.put("/api/employee/plan", json=plan(), headers=headers).status_code == 200
    assert client.post("/api/logout", headers=headers).status_code == 200
    assert client.put("/api/employee/plan", json=plan(), headers=headers).status_code in (401, 403)


def test_surname_login_disambiguates_names_and_cannot_select_unrelated_employee(client):
    assert employee_login(client, "Неизвестный").status_code in (400, 401, 404)
    response = employee_login(client, "Смирнов")
    assert response.status_code == 409
    assert "Смирнов Алексей Петрович" in str(response.get_json())
    assert "Смирнов Сергей Николаевич" in str(response.get_json())
    unrelated = employee_login(client, "Иванов", employee_id=2)
    if unrelated.status_code == 200:
        assert client.get("/api/employee/plan").get_json()["employee"]["id"] == 1
    else:
        assert unrelated.status_code in (400, 401, 403, 404)
    assert employee_login(client, "Смирнов", employee_id=4).status_code == 200
    assert client.get("/api/employee/plan").status_code == 200


def test_employee_cannot_access_hr_endpoints(client):
    assert employee_login(client).status_code == 200
    assert client.get("/api/admin/dashboard").status_code in (401, 403)
    assert client.get("/api/admin/export.csv").status_code in (401, 403)
    assert client.post("/api/admin/import/preview", headers=csrf(client)).status_code in (401, 403)
    assert client.post("/api/admin/import/confirm", json={"token": "fake"}, headers=csrf(client)).status_code in (401, 403)


def test_plan_persists_across_sessions_and_is_isolated_by_employee(app, client):
    assert employee_login(client).status_code == 200
    payload = plan(
        [
            {"start": "2027-07-05", "end": "2027-07-18"},
            {"start": "2027-08-02", "end": "2027-08-08"},
        ],
        submitted=True,
        holiday={"choice": "selected_dates", "dates": ["2027-01-01", "2027-01-06"], "comment": "Утром"},
    )
    assert save_plan(client, payload).status_code == 200
    second_session = app.test_client()
    assert employee_login(second_session).status_code == 200
    stored = second_session.get("/api/employee/plan").get_json()
    stored_plan = stored.get("plan", stored)
    assert stored_plan["periods"] == payload["periods"]
    assert stored_plan["holiday"] == payload["holiday"]
    assert stored_plan["submitted"] is True
    third_session = app.test_client()
    assert employee_login(third_session, "Петрова").status_code == 200
    other = third_session.get("/api/employee/plan").get_json()
    assert other.get("plan", other)["periods"] == []


@pytest.mark.parametrize(
    "periods",
    [
        [{"start": "2026-12-30", "end": "2027-01-05"}],
        [{"start": "2027-12-30", "end": "2028-01-05"}],
        [{"start": "2027-07-18", "end": "2027-07-05"}],
        [{"start": "2027-02-29", "end": "2027-03-05"}],
        [
            {"start": "2027-07-01", "end": "2027-07-14"},
            {"start": "2027-07-14", "end": "2027-07-20"},
        ],
        [{"start": "2027-07-01", "end": "2027-07-29"}],
    ],
)
def test_invalid_or_excessive_leave_is_rejected_without_overwriting_draft(client, periods):
    assert employee_login(client).status_code == 200
    original = plan()
    assert save_plan(client, original).status_code == 200
    assert save_plan(client, plan(periods)).status_code in (400, 422)
    response = client.get("/api/employee/plan").get_json()
    assert response.get("plan", response)["periods"] == original["periods"]


def test_submission_requires_a_fourteen_day_period_but_drafts_can_be_empty(client):
    assert employee_login(client).status_code == 200
    assert save_plan(client, plan([])).status_code == 200
    assert save_plan(client, plan([], submitted=True)).status_code in (400, 422)
    two_short_periods = [
        {"start": "2027-07-01", "end": "2027-07-07"},
        {"start": "2027-08-01", "end": "2027-08-07"},
    ]
    assert save_plan(client, plan(two_short_periods)).status_code == 200
    assert save_plan(client, plan(two_short_periods, submitted=True)).status_code in (400, 422)


def test_january_public_holidays_do_not_consume_leave_allowance(client):
    assert employee_login(client).status_code == 200
    exactly_twenty_eight = [
        {"start": "2027-01-01", "end": "2027-01-22"},
        {"start": "2027-07-01", "end": "2027-07-14"},
    ]
    assert save_plan(client, plan(exactly_twenty_eight, submitted=True)).status_code == 200
    too_many = [dict(period) for period in exactly_twenty_eight]
    too_many[1]["end"] = "2027-07-15"
    assert save_plan(client, plan(too_many, submitted=True)).status_code in (400, 422)
    # January 1–21 contains only thirteen leave days.
    assert save_plan(
        client, plan([{"start": "2027-01-01", "end": "2027-01-21"}], submitted=True)
    ).status_code in (400, 422)


@pytest.mark.parametrize(
    "start,end",
    [
        ("2027-02-16", "2027-03-02"),
        ("2027-03-01", "2027-03-15"),
        ("2027-04-24", "2027-05-08"),
        ("2027-05-02", "2027-05-16"),
        ("2027-06-05", "2027-06-19"),
        ("2027-11-01", "2027-11-15"),
    ],
)
def test_other_public_holidays_are_excluded_from_leave_day_count(client, start, end):
    assert employee_login(client).status_code == 200
    response = save_plan(client, plan([{"start": start, "end": end}], submitted=True))
    assert response.status_code == 200
    assert response.get_json()["summary"]["calendar_days"] == 15
    assert response.get_json()["summary"]["leave_days"] == 14


@pytest.mark.parametrize(
    "holiday",
    [
        {"choice": "selected_dates", "dates": [], "comment": ""},
        {"choice": "selected_dates", "dates": ["2027-01-09"], "comment": ""},
        {"choice": "selected_dates", "dates": ["2026-01-01"], "comment": ""},
        {"choice": "selected_dates", "dates": ["invalid"], "comment": ""},
        {"choice": "invalid", "dates": [], "comment": ""},
    ],
)
def test_invalid_new_year_work_choices_are_rejected(client, holiday):
    assert employee_login(client).status_code == 200
    assert save_plan(client, plan(holiday=holiday)).status_code in (400, 422)


def test_hr_stats_and_utf8_csv_reflect_saved_plan(app, client):
    employee = app.test_client()
    assert employee_login(employee).status_code == 200
    payload = plan(
        submitted=True,
        holiday={"choice": "selected_dates", "dates": ["2027-01-03"], "comment": "Дежурство"},
    )
    assert save_plan(employee, payload).status_code == 200
    draft_employee = app.test_client()
    assert employee_login(draft_employee, "Петрова").status_code == 200
    assert save_plan(draft_employee, plan([])).status_code == 200
    assert client.post(
        ADMIN_LOGIN, json={"login": "admin01", "password": "wrong"}, headers=csrf(client)
    ).status_code in (400, 401, 403)
    assert admin_login(client).status_code == 200
    dashboard = client.get("/api/admin/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.get_json()["stats"] == {"total": 4, "submitted": 1, "drafts": 1, "missing": 2}
    assert len(dashboard.get_json()["employees"]) == 4
    export = client.get("/api/admin/export.csv")
    assert export.status_code == 200
    assert "csv" in export.content_type
    assert export.data.startswith(b"\xef\xbb\xbf")
    csv = export.data.decode("utf-8-sig")
    for expected in ("Иванов Иван Иванович", "2027-07-05", "2027-07-18", "2027-01-03", "Дежурство"):
        assert expected in csv


def test_hr_can_extend_allowance_but_cannot_reduce_it_below_saved_leave(app, client):
    employee = app.test_client()
    assert employee_login(employee).status_code == 200
    longer_leave = plan([{"start": "2027-07-01", "end": "2027-08-04"}], submitted=True)
    assert save_plan(employee, longer_leave).status_code in (400, 422)
    assert employee.patch(
        "/api/admin/employees/1", json={"allowance_days": 42}, headers=csrf(employee)
    ).status_code in (401, 403)
    assert admin_login(client).status_code == 200
    assert client.patch(
        "/api/admin/employees/1", json={"allowance_days": 42}, headers=csrf(client)
    ).status_code == 200
    assert save_plan(employee, longer_leave).status_code == 200
    assert client.patch(
        "/api/admin/employees/1", json={"allowance_days": 28}, headers=csrf(client)
    ).status_code in (400, 422)
    stored = employee.get("/api/employee/plan").get_json()
    assert stored["employee"]["allowance_days"] == 42
    assert stored["summary"]["leave_days"] == 35
    assert stored["plan"]["submitted"] is True


def _xlsx(surnames):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["№", "Фамилия", "Отпуск 2027"])
    for index, surname in enumerate(surnames, 1):
        sheet.append([index, surname, ""])
    result = BytesIO()
    workbook.save(result)
    result.seek(0)
    return result


def _pdf(lines):
    """Build a small Unicode PDF without adding a PDF writer dependency."""
    characters = sorted(set("".join(lines)))
    codes = {character: index + 32 for index, character in enumerate(characters)}
    mappings = "\n".join(f"<{code:02X}> <{ord(character):04X}>" for character, code in codes.items())
    cmap = (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /SyntheticUnicode def /CMapType 2 def\n"
        "1 begincodespacerange <00> <FF> endcodespacerange\n"
        f"{len(codes)} beginbfchar\n{mappings}\nendbfchar\n"
        "endcmap CMapName currentdict /CMap defineresource pop end end"
    ).encode("ascii")
    encoded = ["".join(f"{codes[character]:02X}" for character in line) for line in lines]
    content = ("BT /F1 12 Tf 40 780 Td " + " 0 -20 Td ".join(f"<{line}> Tj" for line in encoded) + " ET").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /ToUnicode 6 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        f"<< /Length {len(cmap)} >>\nstream\n".encode() + cmap + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    startxref = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF".encode())
    return BytesIO(document)


def _preview(client):
    return client.post(
        "/api/admin/import/preview",
        data={
            "vacations_file": (_xlsx(["Иванов", "Кузнецова"]), "vacations.xlsx"),
            "names_file": (_pdf(["Иванов Иван Иванович", "Кузнецова Мария Алексеевна"]), "employees.pdf"),
        },
        headers=csrf(client),
        content_type="multipart/form-data",
    )


def test_hr_import_preview_confirm_is_idempotent_and_preserves_existing_plans(app, client):
    employee = app.test_client()
    assert employee_login(employee).status_code == 200
    assert save_plan(employee, plan(submitted=True)).status_code == 200
    assert admin_login(client).status_code == 200
    assert client.post("/api/admin/import/preview", headers=csrf(client)).status_code in (400, 422)
    preview = _preview(client)
    assert preview.status_code == 200, preview.get_data(as_text=True)
    token = preview.get_json()["token"]
    assert token
    assert client.post(
        "/api/admin/import/confirm", json={"token": "invalid"}, headers=csrf(client)
    ).status_code in (400, 404, 409, 422)
    confirmed = client.post("/api/admin/import/confirm", json={"token": token}, headers=csrf(client))
    assert confirmed.status_code == 200, confirmed.get_data(as_text=True)
    assert confirmed.get_json()["added"] == 1
    assert confirmed.get_json()["existing"] == 1
    # Re-preview the same source roster: it must not reset employee plans or add duplicates.
    token = _preview(client).get_json()["token"]
    repeat = client.post("/api/admin/import/confirm", json={"token": token}, headers=csrf(client))
    assert repeat.status_code == 200
    assert repeat.get_json()["added"] == 0
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 5
        assert get_db().execute("SELECT submitted FROM plans WHERE employee_id = 1").fetchone()[0] == 1


def test_import_requires_csrf_and_preview_belongs_to_its_hr_session(app, client):
    assert admin_login(client).status_code == 200
    rejected = client.post(
        "/api/admin/import/preview",
        data={
            "vacations_file": (_xlsx(["Иванов"]), "vacations.xlsx"),
            "names_file": (_pdf(["Иванов Иван Иванович"]), "employees.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert rejected.status_code in (400, 403)
    preview = _preview(client)
    assert preview.status_code == 200
    token = preview.get_json()["token"]
    second_hr_session = app.test_client()
    assert admin_login(second_hr_session).status_code == 200
    assert second_hr_session.post(
        "/api/admin/import/confirm", json={"token": token}, headers=csrf(second_hr_session)
    ).status_code in (400, 403, 404, 422)
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 4
    # A preview performs no roster writes; its original session can still confirm it.
    assert client.post(
        "/api/admin/import/confirm", json={"token": token}, headers=csrf(client)
    ).status_code == 200


def test_initial_seed_imports_only_matched_people_and_restart_preserves_plans(app, tmp_path):
    database = tmp_path / "seeded" / "vacations.sqlite3"
    database.parent.mkdir()
    (database.parent / "initial-roster.json").write_text(
        json.dumps(
            {
                "matched": [{"surname": "Иванов", "full_name": "Иванов Иван Иванович"}],
                "unmatched": ["Неизвестный"],
                "ambiguous": [{"surname": "Смирнов", "candidates": ["Смирнов Алексей Петрович", "Смирнов Сергей Николаевич"]}],
                "warnings": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config = {**app.config, "DATABASE": str(database), "SEED_ROSTER": True}
    seeded_app = create_app(config)
    employee = seeded_app.test_client()
    assert employee_login(employee).status_code == 200
    assert save_plan(employee, plan(submitted=True)).status_code == 200
    restarted_app = create_app(config)
    restarted_client = restarted_app.test_client()
    assert employee_login(restarted_client).status_code == 200
    assert restarted_client.get("/api/employee/plan").get_json()["plan"]["submitted"] is True
    with restarted_app.app_context():
        rows = get_db().execute("SELECT full_name FROM employees").fetchall()
        assert [row[0] for row in rows] == ["Иванов Иван Иванович"]
