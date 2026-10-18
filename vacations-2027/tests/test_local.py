"""Local launcher integration checks; all saved data is confined to tmp_path."""

from pathlib import Path

import pytest

from app import get_db
import run_local
from run_local import create_local_app


@pytest.fixture(autouse=True)
def isolate_session_secret(monkeypatch):
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)


def csrf(client):
    return {"X-CSRF-Token": client.get("/api/session").get_json()["csrf_token"]}


def login_employee(client, surname="Николаенко"):
    response = client.post(
        "/api/login/employee", json={"surname": surname}, headers=csrf(client)
    )
    assert response.status_code == 200
    return response.get_json()["employee"]


def login_admin(client):
    response = client.post(
        "/api/login/admin",
        json={"login": "admin01", "password": "admin01"},
        headers=csrf(client),
    )
    assert response.status_code == 200


def test_first_local_launch_creates_selected_roster_in_external_data_directory(tmp_path):
    data_dir = tmp_path / "user-data" / "vacations"
    application = create_local_app(data_dir)
    assert Path(application.config["DATABASE"]).resolve() == data_dir / "vacations.sqlite3"
    assert (data_dir / "vacations.sqlite3").is_file()
    with application.app_context():
        employees = get_db().execute("SELECT surname,full_name FROM employees").fetchall()
    assert len(employees) == 30
    assert [row["full_name"] for row in employees if row["surname"] == "Николаенко"] == [
        "Николаенко Оксана Владимировна"
    ]
    assert not {"Корсакова", "Растрыгина", "Соломонов"}.intersection(
        row["surname"] for row in employees
    )
    assert (data_dir / ".session-key").is_file()
    assert login_employee(application.test_client())["full_name"] == "Николаенко Оксана Владимировна"


def test_local_http_login_uses_local_defaults_despite_cloud_environment(tmp_path, monkeypatch):
    cloud_data = tmp_path / "cloud-data"
    monkeypatch.setenv("DATA_DIR", str(cloud_data))
    monkeypatch.setenv("COOKIE_SECURE", "1")
    monkeypatch.setenv("ADMIN_LOGIN", "cloud-only-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "cloud-only-password")
    data_dir = tmp_path / "local-data"
    application = create_local_app(data_dir)
    assert application.config["SESSION_COOKIE_SECURE"] is False
    assert application.config["ADMIN_LOGIN"] == "admin01"
    client = application.test_client()
    response = client.get("/api/session", base_url="http://127.0.0.1")
    cookie = response.headers["Set-Cookie"]
    assert "Secure" not in cookie
    assert "HttpOnly" in cookie
    login_admin(client)
    assert client.get("/api/admin/dashboard").get_json()["stats"]["total"] == 30
    assert not (cloud_data / "vacations.sqlite3").exists()


def test_saved_plan_hr_changes_and_session_key_survive_local_restart(tmp_path):
    data_dir = tmp_path / "local-data"
    first_app = create_local_app(data_dir)
    first_client = first_app.test_client()
    employee = login_employee(first_client)
    payload = {
        "periods": [{"start": "2027-07-05", "end": "2027-07-18"}],
        "holiday": {
            "choice": "selected_dates",
            "dates": ["2027-01-02", "2027-01-06"],
            "comment": "Утренние смены",
        },
        "submitted": True,
    }
    response = first_client.put("/api/employee/plan", json=payload, headers=csrf(first_client))
    assert response.status_code == 200
    admin_client = first_app.test_client()
    login_admin(admin_client)
    response = admin_client.patch(
        f"/api/admin/employees/{employee['id']}",
        json={"allowance_days": 35},
        headers=csrf(admin_client),
    )
    assert response.status_code == 200
    response = admin_client.post(
        "/api/admin/employees",
        json={"full_name": "Тестов Иван Петрович"},
        headers=csrf(admin_client),
    )
    assert response.status_code == 201
    session_key = (data_dir / ".session-key").read_bytes()

    second_app = create_local_app(data_dir)
    assert (data_dir / ".session-key").read_bytes() == session_key
    second_client = second_app.test_client()
    assert login_employee(second_client)["id"] == employee["id"]
    stored = second_client.get("/api/employee/plan").get_json()
    assert stored["plan"]["periods"] == payload["periods"]
    assert stored["plan"]["holiday"] == payload["holiday"]
    assert stored["plan"]["submitted"] is True
    assert stored["employee"]["allowance_days"] == 35
    login_admin(second_app.test_client())
    with second_app.app_context():
        assert get_db().execute("SELECT count(*) FROM employees").fetchone()[0] == 31


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_default_storage_uses_user_data_folder_outside_program(tmp_path, monkeypatch, platform):
    home = tmp_path / "user home"
    windows_profile = tmp_path / "LocalAppData"
    xdg_data = tmp_path / "XDG data"
    monkeypatch.setattr(run_local.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("LOCALAPPDATA", str(windows_profile))
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    expected = {
        "win32": windows_profile / "Medsonar" / "Vacations2027",
        "darwin": home / "Library" / "Application Support" / "Medsonar" / "Vacations2027",
        "linux": xdg_data / "medsonar-vacations-2027",
    }
    assert run_local.default_data_dir() == expected[platform]


def test_server_reuse_status_identifies_its_own_data_directory(tmp_path):
    first = create_local_app(tmp_path / "first").test_client().get("/_local/status")
    second = create_local_app(tmp_path / "second").test_client().get("/_local/status")
    first_status, second_status = first.get_json(), second.get_json()
    assert first_status["app"] == second_status["app"] == run_local.APP_ID
    assert first_status["year"] == second_status["year"] == 2027
    assert first_status["data"] != second_status["data"]
    assert str(tmp_path) not in first.get_data(as_text=True)


@pytest.mark.parametrize("seed_encoding", ["utf-8", "utf-8-sig"])
@pytest.mark.parametrize("after_failed_startup", [False, True])
def test_cyrillic_roster_starts_and_survives_restart_with_windows_code_page(
    tmp_path, monkeypatch, seed_encoding, after_failed_startup
):
    import json

    data_dir = tmp_path / "local-data"
    data_dir.mkdir()
    seed = data_dir / "initial-roster.json"
    full_name = "Иванов Иван Игоревич"
    seed.write_text(
        json.dumps(
            {"matched": [{"surname": "Иванов", "full_name": full_name}]},
            ensure_ascii=False,
        ),
        encoding=seed_encoding,
    )
    # The UTF-8 bytes of И include 0x98, which is undefined in Windows-1251.
    # Reproduce the reported first-launch failure even on a UTF-8 Linux host.
    with pytest.raises(UnicodeDecodeError):
        seed.read_bytes().decode("cp1251")

    original_read_text = Path.read_text

    if after_failed_startup:
        def legacy_read_text(path, encoding=None, errors=None, **kwargs):
            return original_read_text(
                path, encoding="cp1251" if path == seed else encoding,
                errors=errors, **kwargs
            )

        with monkeypatch.context() as legacy:
            legacy.setattr(Path, "read_text", legacy_read_text)
            with pytest.raises(UnicodeDecodeError):
                create_local_app(data_dir)
        database_before_retry = (data_dir / "vacations.sqlite3").stat()
        session_key_before_retry = (data_dir / ".session-key").read_bytes()

    def windows_read_text(path, encoding=None, errors=None, **kwargs):
        if path == seed and encoding is None:
            encoding = "cp1251"
        return original_read_text(path, encoding=encoding, errors=errors, **kwargs)

    monkeypatch.setattr(Path, "read_text", windows_read_text)

    first_app = create_local_app(data_dir)
    if after_failed_startup:
        assert (data_dir / "vacations.sqlite3").stat().st_ino == database_before_retry.st_ino
        assert (data_dir / ".session-key").read_bytes() == session_key_before_retry
    employee = login_employee(first_app.test_client(), surname="Иванов")
    assert employee["full_name"] == full_name

    restarted_app = create_local_app(data_dir)
    saved_employee = login_employee(restarted_app.test_client(), surname="Иванов")
    assert saved_employee["id"] == employee["id"]
    assert saved_employee["full_name"] == full_name
    with restarted_app.app_context():
        names = get_db().execute("SELECT full_name FROM employees").fetchall()
    assert [row["full_name"] for row in names] == [full_name]
