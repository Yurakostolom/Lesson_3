"use strict";

const YEAR = 2027;
const MONTHS = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];
const HOLIDAYS = new Set([
  "01-01",
  "01-02",
  "01-03",
  "01-04",
  "01-05",
  "01-06",
  "01-07",
  "01-08",
  "02-23",
  "03-08",
  "05-01",
  "05-09",
  "06-12",
  "11-04",
]);
const HOLIDAY_DATES = [
  "2026-12-31",
  ...Array.from(
    { length: 10 },
    (_, i) => `2027-01-${String(i + 1).padStart(2, "0")}`,
  ),
];
const ICONS = {
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2"/>',
  people:
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/>',
  shield:
    '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>',
  leaf: '<path d="M20 3c-8 0-15 3-15 10a6 6 0 0 0 6 6c7 0 9-8 9-16ZM4 21l10-10"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  logout:
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  save: '<path d="m19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2ZM17 21v-8H7v8M7 3v5h8V3"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7h.01"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  upload:
    '<path d="M12 16V3m-5 5 5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  download:
    '<path d="M12 3v13m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  document:
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6M8 13h8M8 17h6"/>',
  list: '<path d="M9 6h12M9 12h12M9 18h12M3 6h.01M3 12h.01M3 18h.01"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  edit: '<path d="m16 3 5 5L9 20l-6 1 1-6L16 3ZM13 6l5 5"/>',
};
const state = {
  session: null,
  roleTab: "employee",
  loginError: "",
  candidates: [],
  surname: "",
  plan: null,
  employee: null,
  dashboard: null,
  dirty: false,
  saving: false,
  search: "",
  filter: "all",
  view: "list",
  selectedDay: null,
  importFiles: { vacations: null, names: null },
  preview: null,
  modal: null,
};
const $ = (selector) => document.querySelector(selector);
const h = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const icon = (name) =>
  `<svg aria-hidden="true" viewBox="0 0 24 24">${ICONS[name] || ICONS.calendar}</svg>`;
const initials = (name) =>
  (name || "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
const dateLabel = (value) => {
  if (!value) return "—";
  const [y, m, d] = value.split("-");
  return `${d}.${m}.${y}`;
};
function holidayDateButton(date, selected) {
  const [year, month, day] = date.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  const weekdayNames = [
    "воскресенье", "понедельник", "вторник", "среда",
    "четверг", "пятница", "суббота",
  ];
  const weekdayShort = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  const monthName = month === 12 ? "декабря" : "января";
  const monthShort = month === 12 ? "дек" : "янв";
  return `<button class="holiday-date ${selected ? "selected" : ""}" aria-label="${day} ${monthName} ${year}, ${weekdayNames[weekday]}" aria-pressed="${selected}" data-action="holiday-date" data-date="${date}"><strong>${day}</strong><span>${monthShort} · ${weekdayShort[weekday]}</span></button>`;
}
const plural = (count, forms = ["день", "дня", "дней"]) =>
  forms[
    count % 10 === 1 && count % 100 !== 11
      ? 0
      : count % 10 >= 2 &&
          count % 10 <= 4 &&
          (count % 100 < 12 || count % 100 > 14)
        ? 1
        : 2
  ];
const status = (plan) =>
  plan?.submitted ? "submitted" : plan?.updated_at ? "draft" : "missing";
const statusLabel = (value) =>
  ({ submitted: "Отправлено", draft: "Черновик", missing: "Не заполнено" })[
    value
  ];
const badge = (plan) =>
  `<span class="badge ${status(plan)}">${icon(plan?.submitted ? "check" : "clock")}${statusLabel(status(plan))}</span>`;
const loading = (text) =>
  `<div class="loading-panel"><span class="spinner" aria-hidden="true"></span><p>${h(text)}</p></div>`;
let toastTimer;
let previousFocus;

async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body && !(options.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (options.method && !["GET", "HEAD"].includes(options.method))
    headers["X-CSRF-Token"] = state.session?.csrf_token || "";
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch (_) {
    throw new Error(
      "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.",
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      data.error || "Не удалось выполнить запрос. Попробуйте ещё раз.",
    );
    error.status = response.status;
    error.data = data;
    if (
      response.status === 401 &&
      state.session?.role &&
      !path.includes("/login/")
    ) {
      state.session = { ...state.session, role: null };
      state.plan = null;
      state.dashboard = null;
      closeModal();
      render();
    }
    throw error;
  }
  return data;
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  const element = $("#toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.hidden = false;
  toastTimer = setTimeout(
    () => {
      element.hidden = true;
    },
    error ? 8000 : 4500,
  );
}

function shell(content) {
  const role = state.session?.role;
  const active = role || state.roleTab;
  return `<div class="app-shell">
    <aside class="sidebar" aria-label="Основная навигация">
      <a class="brand" href="/" aria-label="Отпуска — главная"> <span class="brand-mark">${icon("calendar")}</span>Отпуска<sup>2027</sup></a>
      <div class="sidebar-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <nav class="side-nav">
        <button class="side-link ${active === "employee" ? "active" : ""}" data-action="role" data-role="employee" ${role && role !== "employee" ? 'title="Выйдите из текущего аккаунта, чтобы войти как сотрудник"' : ""}>${icon("user")}<span>Сотрудник</span></button>
        <button class="side-link ${active === "admin" ? "active" : ""}" data-action="role" data-role="admin" ${role && role !== "admin" ? 'title="Выйдите из текущего аккаунта, чтобы войти в отдел кадров"' : ""}>${icon("people")}<span>Отдел кадров</span></button>
      </nav>
      <div class="sidebar-bottom"><div class="sidebar-note">${icon("leaf")}<h3>Время для себя</h3><p>Планируйте отдых заранее — чтобы год прошёл в балансе.</p></div><div class="sidebar-footer"><span class="status-dot"></span>Планирование на 2027 год</div></div>
    </aside>
    <section class="workspace"><header class="topbar"><div class="breadcrumb"><span>Рабочее пространство</span>${icon("chevron")}<strong>${role === "admin" ? "Отдел кадров" : role === "employee" ? "Мой отпуск" : "Вход в систему"}</strong></div><div class="top-actions"><span class="year-chip">${icon("calendar")}2027 год</span>${role ? `<button class="logout-button" data-action="logout">${icon("logout")}Выйти</button>` : ""}</div></header>
    <main id="main" class="main-content">${content}<footer class="page-footer"><span>Отпуска · Планирование команды</span><span>${icon("shield")}Данные сохраняются в системе</span></footer></main></section></div>`;
}

function render() {
  if (!state.session) return;
  $("#app").innerHTML = shell(
    state.session.role === "employee"
      ? employeePage()
      : state.session.role === "admin"
        ? adminPage()
        : loginPage(),
  );
  updateSummary();
}

function loginPage() {
  const isEmployee = state.roleTab === "employee";
  return `<div class="login-layout"><section class="login-intro"><div class="intro-pill">${icon("sun")}ПЛАНЫ НА ХОРОШИЙ ГОД</div><h1>Рабочие планы.<br><span>Время для отдыха.</span></h1><p class="intro-copy">Спланируйте свой отпуск на 2027 год.<br>Всё в одном месте, без лишних формальностей.</p><div class="login-features"><div class="login-feature"><span class="feature-check">${icon("check")}</span>Выбирайте удобные даты отпуска</div><div class="login-feature"><span class="feature-check">${icon("check")}</span>Укажите планы на новогодние праздники</div><div class="login-feature"><span class="feature-check">${icon("check")}</span>Сохраняйте и возвращайтесь в любое время</div></div><div class="login-illustration" aria-hidden="true"><div class="mini-calendar"><div class="mini-calendar-title"><span>ИЮЛЬ 2027</span><span>‹ &nbsp; ›</span></div><div class="mini-calendar-grid">${["П", "В", "С", "Ч", "П", "С", "В"].map((d) => `<span class="off">${d}</span>`).join("")}${Array.from({ length: 3 }, () => "<span></span>").join("")}${Array.from({ length: 31 }, (_, i) => `<span class="${i >= 11 && i <= 24 ? "holiday" : ""}">${i + 1}</span>`).join("")}</div></div><div class="calendar-sticker">${icon("leaf")}<div><strong>Отдых — часть плана</strong>Пусть на всё хватит времени</div></div></div></section><section class="card login-card" aria-labelledby="login-title"><div class="role-tabs" role="tablist" aria-label="Способ входа"><button id="tab-employee" class="role-tab ${isEmployee ? "active" : ""}" role="tab" aria-selected="${isEmployee}" aria-controls="login-panel" data-action="role" data-role="employee">${icon("user")}Сотрудник</button><button id="tab-admin" class="role-tab ${!isEmployee ? "active" : ""}" role="tab" aria-selected="${!isEmployee}" aria-controls="login-panel" data-action="role" data-role="admin">${icon("shield")}Отдел кадров</button></div><div id="login-panel" role="tabpanel" aria-labelledby="tab-${state.roleTab}"><h2 id="login-title">${isEmployee ? "Начнём с вашей фамилии" : "Вход для отдела кадров"}</h2><p class="login-subtitle">${isEmployee ? "Пароль не нужен. Найдите себя в списке сотрудников и переходите к планированию." : "Войдите, чтобы управлять списком сотрудников и видеть общие планы команды."}</p>${state.loginError ? `<div class="error-box" role="alert">${h(state.loginError)}</div>` : ""}<form id="login-form">${isEmployee ? `<div class="field"><label for="surname">Ваша фамилия</label><input id="surname" name="surname" autocomplete="family-name" placeholder="Введите фамилию" value="${h(state.surname)}" required maxlength="100"><span class="field-hint">Укажите фамилию так, как она записана в документах.</span></div>${state.candidates.length ? `<div class="field"><label for="employee-id">Выберите своё полное ФИО</label><select id="employee-id" name="employee_id" required><option value="">Выберите сотрудника</option>${state.candidates.map((e) => `<option value="${h(e.id)}">${h(e.full_name)}</option>`).join("")}</select><span class="field-hint">В списке несколько сотрудников с такой фамилией.</span></div>` : ""}` : '<div class="field"><label for="admin-login">Логин</label><input id="admin-login" name="login" autocomplete="username" placeholder="Введите логин" required maxlength="100"></div><div class="field"><label for="admin-password">Пароль</label><input id="admin-password" name="password" type="password" autocomplete="current-password" placeholder="Введите пароль" required maxlength="256"></div>'}<button class="btn btn-primary" type="submit">${isEmployee ? "Перейти к моему отпуску" : "Войти в отдел кадров"}${icon("arrow")}</button></form><div class="login-footnote">${icon("lock")}${isEmployee ? "Доступ к вашей анкете по фамилии" : "Доступ только для сотрудника отдела кадров"}</div></div></section></div>`;
}

function emptyPlan() {
  return {
    periods: [],
    holiday: { choice: "undecided", dates: [], comment: "" },
    submitted: false,
    updated_at: null,
  };
}

function employeePage() {
  if (!state.plan) return loading("Загружаем ваш план отпусков…");
  const employee = state.employee;
  const plan = state.plan;
  return `<div class="page-heading"><div><div class="eyebrow">ЛИЧНЫЙ КАЛЕНДАРЬ</div><h1>Мой отпуск в 2027 году</h1><p>Выберите даты отдыха. Хороший год начинается с хорошего плана.</p></div></div><section class="profile-banner" aria-label="Ваш профиль"><div class="avatar">${h(initials(employee.full_name))}</div><div><div class="profile-name">${h(employee.full_name)}</div><div class="profile-label">Планирование ежегодного отпуска · 2027</div></div><span id="plan-badge">${badge(plan)}</span></section><div class="metrics"><div class="metric"><div class="metric-label">Доступно на год${icon("sun")}</div><div class="metric-value">${employee.allowance_days || 28}<small>${plural(employee.allowance_days || 28)}</small></div><div class="metric-note">Ежегодный отпуск</div></div><div class="metric"><div class="metric-label">Запланировано${icon("calendar")}</div><div class="metric-value"><span id="used-days">0</span><small>дней</small></div><progress id="leave-progress" class="leave-progress" value="0" max="28" aria-label="Доля запланированного отпуска"></progress></div><div class="metric"><div class="metric-label">Осталось выбрать${icon("leaf")}</div><div class="metric-value"><span id="remaining-days">28</span><small>дней</small></div><div id="remaining-note" class="metric-note">Для ваших будущих планов</div></div></div><div id="validation-notes" class="validation-notes" hidden></div><div class="employee-grid"><section class="card"><div class="card-header"><div class="section-title"><span class="card-icon">${icon("calendar")}</span><div><h2>Периоды отпуска</h2><p>Можно разделить отпуск на несколько частей</p></div></div><span class="step-number">ШАГ 01</span></div><div class="subtle-line"></div><div id="period-list" class="period-list">${plan.periods.map(periodRow).join("")}</div><div class="add-period-wrap"><button class="btn btn-secondary btn-small" data-action="add-period">${icon("plus")}Добавить период</button></div><div class="leave-note">${icon("info")}<span>Хотя бы одна часть отпуска — от 14 дней. Официальные нерабочие праздничные дни не расходуют отпуск. Перенесённые выходные отдельно не учитываются.</span></div></section><section class="card"><div class="card-header"><div class="section-title"><span class="card-icon">${icon("sun")}</span><div><h2>Новогодние праздники</h2><p>31 декабря 2026 — 10 января 2027</p></div></div><span class="step-number">ШАГ 02</span></div><div class="holiday-body"><p class="holiday-question">Когда вы планируете работать в новогодние праздники?</p><div class="holiday-options" role="group" aria-label="Планы на праздники">${[
    ["undecided", "Пока не решил(а)"],
    ["not_working", "Не планирую работать"],
    ["selected_dates", "Выбрать дни"],
  ]
    .map(
      ([value, label]) =>
        `<button class="choice-pill ${plan.holiday.choice === value ? "active" : ""}" aria-pressed="${plan.holiday.choice === value}" data-action="holiday-choice" data-choice="${value}">${label}</button>`,
    )
    .join(
      "",
    )}</div><div class="holiday-dates" role="group" aria-label="Рабочие дни в новогодние праздники">${HOLIDAY_DATES.map((date) => holidayDateButton(date, plan.holiday.dates.includes(date))).join("")}</div><p class="holiday-annotation">Нажмите на даты, в которые планируете работать. Это предварительные пожелания для отдела кадров.</p><div class="field"><label for="holiday-comment">Комментарий <span class="muted">· необязательно</span></label><textarea id="holiday-comment" maxlength="1000" placeholder="Например, удобное время или дополнительные пожелания">${h(plan.holiday.comment || "")}</textarea></div></div></section></div><section class="card save-bar" aria-label="Сохранение плана"><div id="save-status" class="save-status">${icon("shield")}<span>${saveStatusText()}</span></div><div class="save-actions"><button class="btn btn-secondary" data-action="save-draft">${icon("save")}Сохранить черновик</button><button class="btn btn-primary" data-action="submit-plan">Отправить в отдел кадров${icon("arrow")}</button></div></section>`;
}

function saveStatusText() {
  if (state.dirty) return "Есть несохранённые изменения";
  if (!state.plan?.updated_at) return "Заполните план и сохраните изменения";
  const date = new Date(state.plan.updated_at);
  return Number.isNaN(date.valueOf())
    ? "Все изменения сохранены"
    : `Сохранено ${date.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`;
}

function periodRow(period, index) {
  const summary = calculate([period]);
  return `<div class="period-row" data-index="${index}"><div class="period-row-heading"><strong>Период ${String(index + 1).padStart(2, "0")}</strong><button class="icon-btn" data-action="remove-period" data-index="${index}" aria-label="Удалить период ${index + 1}">${icon("trash")}</button></div><div class="period-fields"><div class="field"><label for="period-start-${index}">Начало отпуска</label><input id="period-start-${index}" class="period-input" type="date" name="start" data-index="${index}" min="2027-01-01" max="2027-12-31" value="${h(period.start)}" required></div><span class="date-separator">—</span><div class="field"><label for="period-end-${index}">Окончание отпуска</label><input id="period-end-${index}" class="period-input" type="date" name="end" data-index="${index}" min="2027-01-01" max="2027-12-31" value="${h(period.end)}" required></div></div><div class="period-days" id="period-days-${index}">${periodDaysText(period, summary)}</div></div>`;
}

function periodDaysText(period, summary) {
  if (!period.start || !period.end)
    return "<span>Выберите начало и окончание периода</span>";
  if (period.end < period.start)
    return '<span class="warning-text">Окончание должно быть не раньше начала</span>';
  return `<span>${summary.leave_days} ${plural(summary.leave_days)} отпуска</span><span>${summary.calendar_days} ${plural(summary.calendar_days)} по календарю</span>`;
}

function calculate(periods) {
  const used = new Set();
  let calendarDays = 0;
  let hasLong = false;
  for (const period of periods) {
    if (
      !/^2027-\d{2}-\d{2}$/.test(period.start) ||
      !/^2027-\d{2}-\d{2}$/.test(period.end) ||
      period.end < period.start
    )
      continue;
    const start = Date.parse(`${period.start}T00:00:00Z`),
      end = Date.parse(`${period.end}T00:00:00Z`);
    if (
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      end - start > 366 * 86400000
    )
      continue;
    let periodLeave = 0;
    for (let day = start; day <= end; day += 86400000) {
      const key = new Date(day).toISOString().slice(0, 10);
      calendarDays++;
      if (!HOLIDAYS.has(key.slice(5))) {
        used.add(key);
        periodLeave++;
      }
    }
    if (periodLeave >= 14) hasLong = true;
  }
  return {
    leave_days: used.size,
    calendar_days: calendarDays,
    has_long_period: hasLong,
  };
}

function updateSummary() {
  if (!state.plan || state.session?.role !== "employee" || !$("#used-days"))
    return;
  const summary = calculate(state.plan.periods),
    allowance = state.employee.allowance_days || 28;
  $("#used-days").textContent = summary.leave_days;
  $("#remaining-days").textContent = Math.max(
    0,
    allowance - summary.leave_days,
  );
  $("#leave-progress").max = allowance;
  $("#leave-progress").value = summary.leave_days;
  $("#remaining-note").textContent =
    summary.leave_days > allowance
      ? `Превышение на ${summary.leave_days - allowance} ${plural(summary.leave_days - allowance)}`
      : "Для ваших будущих планов";
  const notes = [];
  if (summary.leave_days > allowance)
    notes.push(
      `Вы выбрали ${summary.leave_days} дней при доступных ${allowance}. Скорректируйте периоды перед отправкой.`,
    );
  if (summary.leave_days && !summary.has_long_period)
    notes.push(
      "Для отправки добавьте хотя бы один непрерывный период от 14 дней отпуска.",
    );
  const valid = state.plan.periods
    .filter((p) => p.start && p.end && p.end >= p.start)
    .sort((a, b) => a.start.localeCompare(b.start));
  if (valid.some((p, i) => i > 0 && p.start <= valid[i - 1].end))
    notes.push(
      "Некоторые периоды пересекаются. Проверьте даты перед сохранением.",
    );
  $("#validation-notes").hidden = !notes.length;
  $("#validation-notes").innerHTML = notes
    .map((note) => `<p>${h(note)}</p>`)
    .join("");
  for (let i = 0; i < state.plan.periods.length; i++) {
    const el = $(`#period-days-${i}`);
    if (el)
      el.innerHTML = periodDaysText(
        state.plan.periods[i],
        calculate([state.plan.periods[i]]),
      );
  }
  if ($("#save-status"))
    $("#save-status").innerHTML =
      `${icon("shield")}<span>${saveStatusText()}</span>`;
  if (state.dirty && $("#plan-badge"))
    $("#plan-badge").innerHTML =
      '<span class="badge draft">Есть изменения</span>';
}

function markDirty() {
  state.dirty = true;
  updateSummary();
}

function adminPage() {
  if (!state.dashboard) return loading("Собираем планы команды…");
  const stats = state.dashboard.stats;
  return `<div class="page-heading"><div><div class="eyebrow">ОТДЕЛ КАДРОВ</div><h1>Отпуска команды</h1><p>Общая картина на 2027 год — от первого плана до готового графика.</p></div><div class="heading-tools"><button class="btn btn-secondary" data-action="add-employee">${icon("plus")}Сотрудник</button><button class="btn btn-secondary" data-action="import">${icon("upload")}Импорт списка</button><a class="btn btn-primary" href="/api/admin/export.csv" download>${icon("download")}Выгрузить CSV</a></div></div><div class="metrics admin-metrics">${[
    [stats.total, "Всего сотрудников", "В списке планирования", "people"],
    [stats.submitted, "Отправили план", "Готово к рассмотрению", "check"],
    [stats.drafts, "Черновики", "Продолжают заполнять", "edit"],
    [stats.missing, "Не заполнено", "Ожидаем планы", "clock"],
  ]
    .map(
      ([value, label, note, i]) =>
        `<div class="metric"><div class="metric-label">${label}${icon(i)}</div><div class="metric-value">${value || 0}</div><div class="metric-note">${note}</div></div>`,
    )
    .join("")}</div><section class="card" aria-label="Планы сотрудников">${
    !stats.total
      ? emptyRoster()
      : `<div class="admin-toolbar"><div class="search-wrap">${icon("search")}<input class="search-input" id="staff-search" type="search" aria-label="Найти сотрудника по ФИО" placeholder="Найти сотрудника по ФИО…" value="${h(state.search)}"></div><select class="status-select" id="staff-filter" aria-label="Фильтр по статусу">${[
          ["all", "Все статусы"],
          ["submitted", "Отправлено"],
          ["draft", "Черновики"],
          ["missing", "Не заполнено"],
        ]
          .map(
            ([v, t]) =>
              `<option value="${v}" ${state.filter === v ? "selected" : ""}>${t}</option>`,
          )
          .join(
            "",
          )}</select><div class="view-toggle" role="group" aria-label="Вид планов"><button class="${state.view === "list" ? "active" : ""}" data-action="view" data-view="list" aria-pressed="${state.view === "list"}">${icon("list")}Список</button><button class="${state.view === "calendar" ? "active" : ""}" data-action="view" data-view="calendar" aria-pressed="${state.view === "calendar"}">${icon("calendar")}Календарь</button></div></div><div id="admin-results">${adminResults()}</div>`
  }</section>`;
}

function emptyRoster() {
  return `<div class="empty-state"><div class="empty-icon">${icon("people")}</div><h2>Начнём со списка сотрудников</h2><p>Загрузите файл «Отпуска» со списком фамилий и второй документ с полными ФИО. Мы сопоставим данные и покажем результат перед добавлением.</p><button class="btn btn-primary" data-action="import">${icon("upload")}Загрузить два документа</button><small>XLSX, CSV, TXT, DOCX или PDF с текстовым слоем</small></div>`;
}

function filteredEmployees() {
  const search = state.search
    .trim()
    .toLocaleLowerCase("ru")
    .replaceAll("ё", "е");
  return (state.dashboard?.employees || []).filter(
    (e) =>
      (!search ||
        e.full_name
          .toLocaleLowerCase("ru")
          .replaceAll("ё", "е")
          .includes(search)) &&
      (state.filter === "all" || status(e.plan) === state.filter),
  );
}

function adminResults() {
  const employees = filteredEmployees();
  if (!employees.length)
    return '<div class="no-results">Сотрудники не найдены. Измените запрос или фильтр.</div>';
  if (state.view === "calendar") return calendarView(employees);
  return `<div class="table-wrap"><table class="staff-table"><thead><tr><th scope="col">Сотрудник</th><th scope="col">Статус</th><th scope="col">Отпуск</th><th scope="col">Новый год</th><th scope="col">Обновлено</th><th scope="col"><span class="visually-hidden">Подробности</span></th></tr></thead><tbody>${employees.map((e) => `<tr data-action="employee-detail" data-id="${h(e.id)}" tabindex="0" aria-label="Открыть план: ${h(e.full_name)}"><td><span class="staff-name"><span class="staff-avatar">${h(initials(e.full_name))}</span>${h(e.full_name)}</span></td><td>${badge(e.plan)}</td><td>${e.summary.leave_days} из ${e.allowance_days || 28} дн.</td><td>${holidayShort(e.plan.holiday)}</td><td>${e.plan.updated_at ? h(new Date(e.plan.updated_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })) : "—"}</td><td>${icon("chevron")}</td></tr>`).join("")}</tbody></table></div><div class="table-foot"><span>Показано: ${employees.length} из ${state.dashboard.employees.length}</span><span>Нажмите на сотрудника, чтобы открыть план</span></div>`;
}

function holidayShort(holiday) {
  if (holiday?.choice === "not_working") return "Не работает";
  if (holiday?.choice === "selected_dates")
    return `${holiday.dates.length} ${plural(holiday.dates.length)} работы`;
  return "Пока не решил(а)";
}

function dayEmployees(date, employees) {
  return employees.filter((e) =>
    e.plan.periods.some((p) => p.start <= date && p.end >= date),
  );
}

function calendarView(employees) {
  return `<div class="calendar-view"><div class="calendar-legend"><span><i class="legend-box"></i>Никого</span><span><i class="legend-box low"></i>1 сотрудник</span><span><i class="legend-box medium"></i>2–3</span><span><i class="legend-box high"></i>4 и более</span><span>Нажмите дату, чтобы увидеть пересечения</span></div>${state.selectedDay ? calendarDetail(state.selectedDay, employees) : ""}<div class="calendar-months">${MONTHS.map(
    (month, m) => {
      const first = new Date(Date.UTC(YEAR, m, 1));
      const offset = (first.getUTCDay() + 6) % 7;
      const days = new Date(Date.UTC(YEAR, m + 1, 0)).getUTCDate();
      return `<section><h3 class="month-name">${month}</h3><div class="month-grid">${["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((d) => `<span class="weekday">${d}</span>`).join("")}${Array.from({ length: offset }, () => '<span class="calendar-day empty"></span>').join("")}${Array.from(
        { length: days },
        (_, d) => {
          const date = `2027-${String(m + 1).padStart(2, "0")}-${String(d + 1).padStart(2, "0")}`;
          const people = dayEmployees(date, employees);
          return `<button class="calendar-day ${people.length >= 4 ? "high" : people.length >= 2 ? "medium" : people.length ? "low" : ""} ${(d + offset) % 7 >= 5 ? "weekend" : ""}" data-action="calendar-day" data-date="${date}" title="${d + 1} ${h(month.toLowerCase())}: ${people.length ? h(people.map((e) => e.full_name).join("; ")) : "отпусков нет"}" aria-label="${dateLabel(date)}, сотрудников в отпуске: ${people.length}">${d + 1}</button>`;
        },
      ).join("")}</div></section>`;
    },
  ).join(
    "",
  )}</div><div class="info-box calendar-note">${icon("info")}Календарь показывает все даты выбранных периодов, включая праздники, с учётом текущего фильтра. Совпадение дат — подсказка для планирования.</div></div>`;
}

function calendarDetail(date, employees) {
  const people = dayEmployees(date, employees);
  return `<div class="calendar-detail" role="status"><strong>${dateLabel(date)} · ${people.length ? `В отпуске: ${people.length}` : "Нет запланированных отпусков"}</strong>${people.map((e) => h(e.full_name)).join("<br>")}</div>`;
}

function updateAdminResults() {
  if ($("#admin-results")) $("#admin-results").innerHTML = adminResults();
}

function openModal(content, wide = false) {
  previousFocus = document.activeElement;
  $("#modal-root").innerHTML =
    `<div class="modal-backdrop"><section class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title">${content}</section></div>`;
  document.body.classList.add("modal-open");
  requestAnimationFrame(() => $(".modal button, .modal input")?.focus());
}

function closeModal() {
  $("#modal-root").innerHTML = "";
  document.body.classList.remove("modal-open");
  state.modal = null;
  if (previousFocus?.isConnected) previousFocus.focus();
}

function showEmployee(id) {
  const employee = state.dashboard.employees.find(
    (e) => String(e.id) === String(id),
  );
  if (!employee) return;
  state.modal = "detail";
  const plan = employee.plan,
    holiday = plan.holiday;
  openModal(
    `<header class="modal-header"><div><h2 id="modal-title">План сотрудника</h2><p>Отпуск и новогодние праздники · 2027</p></div><button class="icon-btn" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header><div class="modal-body"><div class="detail-person"><div class="avatar">${h(initials(employee.full_name))}</div><div><h3>${h(employee.full_name)}</h3>${badge(plan)}</div></div><div class="metrics detail-metrics"><div class="metric"><div class="metric-label">Доступно</div><div class="metric-value">${employee.allowance_days || 28}<small>дн.</small></div></div><div class="metric"><div class="metric-label">Выбрано</div><div class="metric-value">${employee.summary.leave_days}<small>дн.</small></div></div><div class="metric"><div class="metric-label">Периодов</div><div class="metric-value">${plan.periods.length}</div></div></div><section class="detail-section"><h3>Периоды отпуска</h3>${plan.periods.length ? plan.periods.map((p) => `<div class="detail-period"><span>${dateLabel(p.start)} — ${dateLabel(p.end)}</span><small>${calculate([p]).leave_days} ${plural(calculate([p]).leave_days)}</small></div>`).join("") : '<div class="detail-empty">Сотрудник пока не выбрал даты.</div>'}</section><section class="detail-section"><h3>Работа в новогодние праздники</h3><div class="detail-holiday">${holiday.choice === "selected_dates" ? `Планирует работать: ${holiday.dates.map(dateLabel).join(", ")}` : holiday.choice === "not_working" ? "Не планирует работать с 31 декабря 2026 по 10 января 2027 года." : "Пока не определился(ась) с планами."}</div>${holiday.comment ? `<div class="detail-comment">${h(holiday.comment)}</div>` : ""}</section><div class="field-hint detail-updated">${plan.updated_at ? `Последнее сохранение: ${h(new Date(plan.updated_at).toLocaleString("ru-RU"))}` : "Анкета ещё не сохранялась."}</div></div><footer class="modal-footer"><button class="btn btn-secondary btn-small" data-action="edit-employee" data-id="${h(employee.id)}">${icon("edit")}Данные сотрудника</button><button class="btn btn-primary btn-small" data-action="close-modal">Закрыть</button></footer>`,
  );
}

function showEmployeeForm(id = null) {
  const employee = id
    ? state.dashboard.employees.find((e) => String(e.id) === String(id))
    : null;
  state.modal = "employee-form";
  openModal(
    `<header class="modal-header"><div><h2 id="modal-title">${employee ? "Данные сотрудника" : "Добавить сотрудника"}</h2><p>${employee ? "Уточните ФИО или количество доступных дней." : "Введите полное ФИО из кадровых документов."}</p></div><button class="icon-btn" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header><form id="employee-form" data-id="${h(employee?.id || "")}"><div class="modal-body"><div id="employee-form-error"></div><div class="field"><label for="employee-full-name">Полное ФИО</label><input id="employee-full-name" name="full_name" value="${h(employee?.full_name || "")}" placeholder="Фамилия Имя Отчество" required maxlength="200"><span class="field-hint">Первое слово используется как фамилия для входа.</span></div><div class="field"><label for="employee-allowance">Дней отпуска на 2027 год</label><input id="employee-allowance" name="allowance_days" type="number" value="${employee?.allowance_days || 28}" min="14" max="366" required><span class="field-hint">По умолчанию — 28 календарных дней.</span></div></div><footer class="modal-footer"><button type="button" class="btn btn-secondary" data-action="close-modal">Отмена</button><button type="submit" class="btn btn-primary">${employee ? "Сохранить" : "Добавить сотрудника"}${icon("check")}</button></footer></form>`,
  );
}

function showImport(reset = true) {
  if (reset) {
    state.preview = null;
    state.importFiles = { vacations: null, names: null };
  }
  state.modal = "import";
  openModal(
    `<header class="modal-header"><div><h2 id="modal-title">Импорт сотрудников</h2><p>Два документа — один точный список для планирования.</p></div><button class="icon-btn" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header><form id="import-form"><div class="modal-body"><div class="upload-step"><b>1</b><span class="current">Документы</span>${icon("chevron")}<b>2</b><span>Проверка списка</span></div><div id="import-error"></div><div class="info-box">В файле «Отпуска» нужны фамилии тех, кто заполняет план. Во втором документе — полные ФИО. Существующие сотрудники и планы сохранятся.</div><div class="upload-grid">${[
      [
        "vacations",
        "vacations_file",
        "Файл «Отпуска»",
        "Список нужных фамилий",
      ],
      ["names", "names_file", "Документ с ФИО", "Полные имена сотрудников"],
    ]
      .map(
        ([key, name, label, caption]) =>
          `<label class="upload-zone ${state.importFiles[key] ? "has-file" : ""}" id="upload-${key}">${icon("upload")}<strong>${label}</strong><span id="filename-${key}">${h(state.importFiles[key]?.name || caption)}</span><input type="file" name="${name}" data-file-key="${key}" accept=".xlsx,.csv,.txt,.docx,.pdf" aria-label="${label}" ${state.importFiles[key] ? "" : "required"}></label>`,
      )
      .join(
        "",
      )}</div><p class="field-hint">Поддерживаются XLSX, CSV, TXT, DOCX и PDF с текстом. Изображения и сканы без текстового слоя не распознаются.</p></div><footer class="modal-footer"><button class="btn btn-secondary" type="button" data-action="close-modal">Отмена</button><button class="btn btn-primary" type="submit">Проверить список${icon("arrow")}</button></footer></form>`,
    true,
  );
}

function showPreview() {
  const preview = state.preview;
  state.modal = "preview";
  const unresolved = [
    ...(preview.unmatched || []).map((s) => `Не найдено полное ФИО: ${s}`),
    ...(preview.ambiguous || []).map(
      (a) =>
        `Несколько совпадений для «${a.surname}»: ${a.candidates.join("; ")}`,
    ),
    ...(preview.warnings || []),
  ];
  openModal(
    `<header class="modal-header"><div><h2 id="modal-title">Проверим список</h2><p>Добавим только сотрудников, для которых найдено однозначное полное ФИО.</p></div><button class="icon-btn" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header><div class="modal-body"><div class="upload-step"><b>1</b><span>Документы</span>${icon("chevron")}<b>2</b><span class="current">Проверка списка</span></div><div id="import-error"></div><div class="preview-counts"><div class="preview-count"><strong>${preview.counts.selected}</strong><span>Фамилий в списке</span></div><div class="preview-count"><strong>${preview.counts.matched}</strong><span>Готовы к добавлению</span></div><div class="preview-count"><strong>${preview.counts.unmatched + preview.counts.ambiguous}</strong><span>Нужно уточнить</span></div></div>${preview.matched.length ? `<div class="preview-label">Будут добавлены в список</div><div class="preview-list">${preview.matched.map((e) => `<div class="preview-person">${icon("check")}${h(e.full_name)}</div>`).join("")}</div>` : ""}${unresolved.length ? `<div class="preview-label">Требует внимания</div><div class="warning-list">${unresolved.map((text) => `<p>${h(text)}</p>`).join("")}</div><p class="field-hint preview-hint">Эти записи не добавятся автоматически. Уточните документы или добавьте сотрудников вручную после импорта.</p>` : ""}<div class="info-box preview-info">${icon("shield")}Повторный импорт не удаляет сотрудников и не изменяет заполненные планы.</div></div><footer class="modal-footer"><button class="btn btn-secondary" data-action="import-back">Назад к документам</button><button class="btn btn-primary" data-action="confirm-import" ${!preview.matched.length ? "disabled" : ""}>Добавить ${preview.matched.length} ${plural(preview.matched.length, ["сотрудника", "сотрудников", "сотрудников"])}${icon("check")}</button></footer>`,
    true,
  );
}

async function loadRole() {
  render();
  try {
    if (state.session.role === "employee") {
      const data = await api("/api/employee/plan");
      state.employee = data.employee;
      state.plan = data.plan || emptyPlan();
      state.plan.holiday ||= emptyPlan().holiday;
      if (!state.plan.periods.length)
        state.plan.periods.push({ start: "", end: "" });
      state.dirty = false;
    } else if (state.session.role === "admin")
      state.dashboard = await api("/api/admin/dashboard");
    render();
  } catch (error) {
    toast(error.message, true);
  }
}

async function login(form) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = "Входим…";
  const data = new FormData(form);
  const employee = state.roleTab === "employee";
  const payload = employee
    ? { surname: data.get("surname") }
    : { login: data.get("login"), password: data.get("password") };
  if (employee) {
    state.surname = String(data.get("surname")).trim();
    if (data.get("employee_id"))
      payload.employee_id = Number(data.get("employee_id"));
  }
  try {
    await api(`/api/login/${employee ? "employee" : "admin"}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.session = await api("/api/session");
    state.loginError = "";
    state.candidates = [];
    await loadRole();
  } catch (error) {
    state.loginError = error.message;
    state.candidates =
      error.data?.code === "ambiguous_surname" ? error.data.employees : [];
    render();
    $("#employee-id, #surname, #admin-password")?.focus();
  }
}

async function savePlan(submitted) {
  if (state.saving) return;
  const periods = state.plan.periods.filter((p) => p.start || p.end);
  if (periods.some((p) => !p.start || !p.end)) {
    toast(
      "Выберите обе даты для каждого периода или удалите незаполненный период.",
      true,
    );
    return;
  }
  if (submitted && !periods.length) {
    toast("Добавьте хотя бы один период отпуска.", true);
    return;
  }
  if (
    state.plan.holiday.choice === "selected_dates" &&
    !state.plan.holiday.dates.length
  ) {
    toast(
      "Выберите рабочие дни в новогодние праздники или другой вариант ответа.",
      true,
    );
    return;
  }
  state.saving = true;
  document
    .querySelectorAll('[data-action="save-draft"], [data-action="submit-plan"]')
    .forEach((el) => (el.disabled = true));
  try {
    const result = await api("/api/employee/plan", {
      method: "PUT",
      body: JSON.stringify({ periods, holiday: state.plan.holiday, submitted }),
    });
    state.plan = result.plan;
    state.employee = result.employee;
    if (!state.plan.periods.length)
      state.plan.periods.push({ start: "", end: "" });
    state.dirty = false;
    render();
    toast(
      submitted
        ? "План отправлен в отдел кадров. Спасибо!"
        : "Черновик сохранён. Можно продолжить позже.",
    );
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.saving = false;
    document
      .querySelectorAll(
        '[data-action="save-draft"], [data-action="submit-plan"]',
      )
      .forEach((el) => (el.disabled = false));
  }
}

async function previewImport(form) {
  const button = form.querySelector('button[type="submit"]');
  const data = new FormData();
  if (!state.importFiles.vacations || !state.importFiles.names) {
    toast("Выберите оба документа.", true);
    return;
  }
  data.append("vacations_file", state.importFiles.vacations);
  data.append("names_file", state.importFiles.names);
  button.disabled = true;
  button.textContent = "Сопоставляем документы…";
  try {
    state.preview = await api("/api/admin/import/preview", {
      method: "POST",
      body: data,
    });
    showPreview();
  } catch (error) {
    $("#import-error").innerHTML =
      `<div class="error-box" role="alert">${h(error.message)}</div>`;
    button.disabled = false;
    button.innerHTML = `Проверить список${icon("arrow")}`;
  }
}

async function confirmImport(button) {
  button.disabled = true;
  button.textContent = "Добавляем…";
  try {
    const result = await api("/api/admin/import/confirm", {
      method: "POST",
      body: JSON.stringify({ token: state.preview.token }),
    });
    closeModal();
    state.dashboard = await api("/api/admin/dashboard");
    render();
    toast(
      `Добавлено: ${result.added}. Уже в списке: ${result.existing}. Всего сотрудников: ${result.total}.`,
    );
  } catch (error) {
    const target = $("#import-error");
    if (target)
      target.innerHTML = `<div class="error-box" role="alert">${h(error.message)}</div>`;
    else toast(error.message, true);
    button.disabled = false;
    button.textContent = "Повторить добавление";
  }
}

async function saveEmployee(form) {
  const data = new FormData(form),
    id = form.dataset.id,
    button = form.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    await api(
      id
        ? `/api/admin/employees/${encodeURIComponent(id)}`
        : "/api/admin/employees",
      {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify({
          full_name: String(data.get("full_name")).trim(),
          allowance_days: Number(data.get("allowance_days")),
        }),
      },
    );
    closeModal();
    state.dashboard = await api("/api/admin/dashboard");
    render();
    toast(
      id
        ? "Данные сотрудника сохранены."
        : "Сотрудник добавлен. Теперь он может войти по фамилии.",
    );
  } catch (error) {
    $("#employee-form-error").innerHTML =
      `<div class="error-box" role="alert">${h(error.message)}</div>`;
    button.disabled = false;
  }
}

document.addEventListener("submit", (event) => {
  if (!["login-form", "import-form", "employee-form"].includes(event.target.id))
    return;
  event.preventDefault();
  if (event.target.id === "login-form") login(event.target);
  if (event.target.id === "import-form") previewImport(event.target);
  if (event.target.id === "employee-form") saveEmployee(event.target);
});

document.addEventListener("input", (event) => {
  const el = event.target;
  if (el.id === "surname") {
    state.surname = el.value;
    if (state.candidates.length) {
      state.candidates = [];
      $("#employee-id")?.closest(".field")?.remove();
    }
  }
  if (el.classList.contains("period-input")) {
    state.plan.periods[Number(el.dataset.index)][el.name] = el.value;
    markDirty();
  }
  if (el.id === "holiday-comment") {
    state.plan.holiday.comment = el.value;
    markDirty();
  }
  if (el.id === "staff-search") {
    state.search = el.value;
    updateAdminResults();
  }
});

document.addEventListener("change", (event) => {
  const el = event.target;
  if (el.id === "staff-filter") {
    state.filter = el.value;
    updateAdminResults();
  }
  if (el.matches("input[data-file-key]")) {
    const key = el.dataset.fileKey;
    state.importFiles[key] = el.files[0] || null;
    $(`#filename-${key}`).textContent =
      state.importFiles[key]?.name || "Выберите документ";
    $(`#upload-${key}`).classList.toggle(
      "has-file",
      Boolean(state.importFiles[key]),
    );
  }
});

document.addEventListener("click", async (event) => {
  if (event.target.classList.contains("modal-backdrop")) {
    closeModal();
    return;
  }
  const el = event.target.closest("[data-action]");
  if (!el || el.disabled) return;
  const action = el.dataset.action;
  if (action === "reload") location.reload();
  if (action === "role") {
    if (state.session.role && state.session.role !== el.dataset.role) {
      toast("Чтобы сменить роль, нажмите «Выйти» и войдите в нужную вкладку.");
      return;
    }
    if (!state.session.role) {
      state.roleTab = el.dataset.role;
      state.loginError = "";
      state.candidates = [];
      render();
    }
  }
  if (action === "logout") {
    if (
      state.dirty &&
      !window.confirm("Есть несохранённые изменения. Выйти без сохранения?")
    )
      return;
    try {
      await api("/api/logout", { method: "POST", body: "{}" });
      state.session = await api("/api/session");
      state.plan = null;
      state.dashboard = null;
      state.employee = null;
      state.dirty = false;
      state.loginError = "";
      render();
    } catch (error) {
      toast(error.message, true);
    }
  }
  if (action === "add-period") {
    if (state.plan.periods.length >= 24) {
      toast("Можно добавить не более 24 периодов.", true);
      return;
    }
    state.plan.periods.push({ start: "", end: "" });
    state.dirty = true;
    render();
    $(`#period-start-${state.plan.periods.length - 1}`)?.focus();
  }
  if (action === "remove-period") {
    state.plan.periods.splice(Number(el.dataset.index), 1);
    state.dirty = true;
    render();
  }
  if (action === "holiday-choice") {
    state.plan.holiday.choice = el.dataset.choice;
    if (el.dataset.choice !== "selected_dates") state.plan.holiday.dates = [];
    state.dirty = true;
    render();
  }
  if (action === "holiday-date") {
    const date = el.dataset.date;
    state.plan.holiday.choice = "selected_dates";
    state.plan.holiday.dates = state.plan.holiday.dates.includes(date)
      ? state.plan.holiday.dates.filter((d) => d !== date)
      : [...state.plan.holiday.dates, date].sort();
    state.dirty = true;
    render();
  }
  if (action === "save-draft") await savePlan(false);
  if (action === "submit-plan") await savePlan(true);
  if (action === "view") {
    state.view = el.dataset.view;
    render();
  }
  if (action === "calendar-day") {
    state.selectedDay = el.dataset.date;
    updateAdminResults();
  }
  if (action === "employee-detail") showEmployee(el.dataset.id);
  if (action === "add-employee") showEmployeeForm();
  if (action === "edit-employee") showEmployeeForm(el.dataset.id);
  if (action === "close-modal") closeModal();
  if (action === "import") showImport();
  if (action === "import-back") showImport(false);
  if (action === "confirm-import") await confirmImport(el);
});

document.addEventListener("keydown", (event) => {
  if (
    event.target.matches('tr[data-action="employee-detail"]') &&
    ["Enter", " "].includes(event.key)
  ) {
    event.preventDefault();
    showEmployee(event.target.dataset.id);
  }
  const modal = $(".modal");
  if (!modal) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeModal();
  }
  if (event.key === "Tab") {
    const focusable = [
      ...modal.querySelectorAll(
        "button:not([disabled]),input:not([disabled]),select,textarea,a[href]",
      ),
    ].filter((el) => !el.hidden);
    const first = focusable[0],
      last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
});
window.addEventListener("beforeunload", (event) => {
  if (state.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

async function init() {
  try {
    state.session = await api("/api/session");
    await loadRole();
  } catch (error) {
    $("#app").innerHTML =
      `<main id="main" class="fatal-error card"><div class="empty-icon">${icon("calendar")}</div><h1>Не удалось открыть приложение</h1><p>${h(error.message)}</p><button class="btn btn-primary" data-action="reload">Попробовать ещё раз</button></main>`;
  }
}
init();
