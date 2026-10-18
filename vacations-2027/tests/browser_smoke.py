"""End-to-end smoke test with synthetic people and a disposable server/database.

Run: .venv/bin/python tests/browser_smoke.py
Uses system Chromium or BROWSER_EXECUTABLE; screenshots go to test-results/.
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test-results"


def run(local=False):
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vacations-browser-") as folder:
        data_dir = Path(folder)
        seed = {"matched": [
            {"full_name": "Тестов Иван Петрович", "surname": "Тестов"},
            {"full_name": "Проверкин Иван Иванович", "surname": "Проверкин"},
            {"full_name": "Проверкин Пётр Петрович", "surname": "Проверкин"},
        ]}
        (data_dir / "initial-roster.json").write_text(json.dumps(seed, ensure_ascii=False))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        address = f"http://127.0.0.1:{port}"
        environment = {**os.environ, "DATA_DIR": folder, "COOKIE_SECURE": "0", "ADMIN_LOGIN": "admin01", "ADMIN_PASSWORD": "admin01"}
        with (data_dir / "server.log").open("w") as log:
            command = [sys.executable, "-I", str(ROOT / "run_local.py"), "--data-dir", folder, "--port", str(port), "--no-browser"] if local else [str(Path(sys.executable).parent / "gunicorn"), "--bind", f"127.0.0.1:{port}", "--workers", "1", "--threads", "2", "app:create_app()"]
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log)
            try:
                for _ in range(50):
                    try:
                        urllib.request.urlopen(address + "/healthz", timeout=1).close()
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError((data_dir / "server.log").read_text())
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE") or shutil.which("chromium") or None, args=["--no-sandbox"])
                    context = browser.new_context(viewport={"width": 1440, "height": 1040}, locale="ru-RU", timezone_id="Europe/Moscow")
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    def console_message(message):
                        if message.type != "error":
                            return
                        # The deliberate surname-ambiguity check returns HTTP409.
                        if "status of 409" in message.text and message.location.get("url", "").endswith("/api/login/employee"):
                            return
                        errors.append(message.text)
                    page.on("console", console_message)
                    page.goto(address)
                    expect(page.locator("#surname")).to_be_visible()
                    page.screenshot(path=str(OUTPUT / "login-desktop.png"), full_page=True)
                    page.locator("#surname").fill("проверкин")
                    page.locator("#login-form button[type=submit]").click()
                    expect(page.locator("#employee-id")).to_be_visible()
                    expect(page.locator("#employee-id option")).to_have_count(3)
                    # Switch to the unique synthetic employee without creating a plan for a real person.
                    page.locator("#surname").fill("Тестов")
                    page.locator("#login-form button[type=submit]").click()
                    expect(page.locator("#period-start-0")).to_be_visible()
                    page.locator("#period-start-0").fill("2027-07-05")
                    page.locator("#period-end-0").fill("2027-07-18")
                    expect(page.locator("#used-days")).to_have_text("14")
                    page.locator('[data-action="holiday-date"][data-date="2027-01-02"]').click()
                    page.locator("#holiday-comment").fill("Могу работать утром. <b>Это текст.</b>")
                    page.locator('[data-action="save-draft"]').click()
                    expect(page.locator("#plan-badge")).to_contain_text("Черновик")
                    page.reload()
                    expect(page.locator("#period-start-0")).to_have_value("2027-07-05")
                    expect(page.locator("#holiday-comment")).to_have_value("Могу работать утром. <b>Это текст.</b>")
                    page.locator('[data-action="submit-plan"]').click()
                    expect(page.locator("#plan-badge")).to_contain_text("Отправлено")
                    page.screenshot(path=str(OUTPUT / "employee-desktop.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Employee page overflows mobile viewport"
                    page.screenshot(path=str(OUTPUT / "employee-mobile.png"), full_page=True)
                    page.locator('[data-action="logout"]').click()
                    page.locator('#tab-admin').click()
                    page.locator('#admin-login').fill('admin01')
                    page.locator('#admin-password').fill('admin01')
                    page.locator('#login-form button[type=submit]').click()
                    expect(page.locator('h1')).to_have_text('Отпуска команды')
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Admin page overflows mobile viewport"
                    page.set_viewport_size({"width": 1440, "height": 1040})
                    page.locator('#staff-search').fill('Тестов')
                    expect(page.locator('tr[data-action="employee-detail"]')).to_have_count(1)
                    page.locator('tr[data-action="employee-detail"]').click()
                    expect(page.locator('.modal')).to_contain_text('05.07.2027')
                    expect(page.locator('.detail-comment')).to_have_text('Могу работать утром. <b>Это текст.</b>')
                    assert page.locator('.detail-comment b').count() == 0, "Comment rendered as HTML"
                    page.locator('[data-action="edit-employee"]').click()
                    page.locator('#employee-allowance').fill('35')
                    page.locator('#employee-form button[type=submit]').click()
                    expect(page.locator('.modal')).to_have_count(0)
                    response = page.request.get(address + '/api/admin/dashboard')
                    dashboard = response.json()
                    assert dashboard['stats'] == {'total': 3, 'submitted': 1, 'drafts': 0, 'missing': 2}
                    employee = next(e for e in dashboard['employees'] if e['surname'] == 'Тестов')
                    assert employee['allowance_days'] == 35
                    assert employee['plan']['holiday']['dates'] == ['2027-01-02']
                    page.locator('#staff-search').fill('')
                    page.screenshot(path=str(OUTPUT / 'admin-desktop.png'), full_page=True)
                    page.locator('[data-action="view"][data-view="calendar"]').click()
                    expect(page.locator('[data-action="calendar-day"]').first).to_be_visible()
                    # Import a new synthetic person through the complete upload wizard.
                    (data_dir / 'selected.txt').write_text('Фамилия\nПримеров', encoding='utf-8')
                    (data_dir / 'names.txt').write_text('ФИО\nПримеров Сергей Иванович', encoding='utf-8')
                    page.locator('[data-action="import"]').click()
                    page.locator('input[name="vacations_file"]').set_input_files(data_dir / 'selected.txt')
                    page.locator('input[name="names_file"]').set_input_files(data_dir / 'names.txt')
                    page.locator('#import-form button[type=submit]').click()
                    expect(page.locator('.preview-person')).to_have_text('Примеров Сергей Иванович')
                    page.locator('[data-action="confirm-import"]').click()
                    expect(page.locator('.modal')).to_have_count(0)
                    assert page.request.get(address + '/api/admin/dashboard').json()['stats']['total'] == 4
                    export = page.request.get(address + '/api/admin/export.csv')
                    assert export.ok and 'Тестов Иван Петрович' in export.text()
                    assert not errors, errors
                    browser.close()
                print(('Local Waitress' if local else 'Cloud Gunicorn') + ' browser smoke passed: surname/ambiguity, draft/reload/submit, holidays, HR/detail/allowance, import/export, mobile, no console errors.')
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='Проверить локальный запуск через Waitress')
    run(local=parser.parse_args().local)
