const API = {
  identity: "http://127.0.0.1:8000",
  submission: "http://127.0.0.1:8000",
  review: "http://127.0.0.1:8000",
  masterdata: "http://127.0.0.1:8000",
  notification: "http://127.0.0.1:8000"
};

const state = {
  user: JSON.parse(sessionStorage.getItem("bou_user") || "null"),
  view: localStorage.getItem("bou_view") || "dashboard",
  calls: [],
  submissions: [],
  assignments: [],
  notifications: [],
  departments: [],
  users: [],
  themes: [],
  templates: [],
  auditLogs: [],
  publications: []
};

const roles = [
  "Admin",
  "ResearchOfficer",
  "EditorialBoard",
  "InternalReviewer",
  "ExternalReviewer",
  "Author"
];

function hasRole(role) {
  return state.user && state.user.roles && state.user.roles.includes(role);
}

function hasAnyRole(list) {
  return list.some((role) => hasRole(role));
}

function initials(name) {
  return (name || "BOU")
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function logoMarkup(extraClass = "") {
  return `
    <div class="logo-frame ${extraClass}">
      <img src="assets/bou-logo.webp" alt="Bank of Uganda logo">
    </div>
  `;
}

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3400);
}

async function request(service, path, options = {}) {
  // All API calls include the HTTP-only session cookie. FormData sets its own
  // multipart boundary, so only JSON requests receive an explicit content type.
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  let response;
  try {
    response = await fetch(`${API[service]}${path}`, {
      ...options,
      headers,
      credentials: "include"
    });
  } catch (_error) {
    throw new Error("Cannot reach the Django backend. Make sure python3 run_all.py is running, or start the backend on port 8000.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch (_error) {
    data = {};
  }

  if (!response.ok) {
    const message = data.message || data.error || data.detail || "Request failed";
    throw new Error(message);
  }
  return data;
}

function setSession(loginData) {
  state.user = {
    id: loginData.user_id,
    roles: loginData.roles,
    email: loginData.email || ""
  };
  sessionStorage.setItem("bou_user", JSON.stringify(state.user));
}

function clearSession() {
  fetch(`${API.identity}/api/auth/logout`, { method: "POST", credentials: "include" }).catch(() => {});
  sessionStorage.removeItem("bou_user");
  localStorage.removeItem("bou_view");
  state.user = null;
  state.view = "dashboard";
  render();
}

async function hydrate() {
  if (!state.user) {
    renderLogin();
    return;
  }

  try {
    const me = await request("identity", "/api/auth/me");
    state.user = me;
    sessionStorage.setItem("bou_user", JSON.stringify(me));
    await loadSharedData();
    renderShell();
  } catch (error) {
    clearSession();
    showToast(error.message);
  }
}

async function loadSharedData() {
  const tasks = [
    request("submission", "/api/calls").then((data) => (state.calls = data)).catch(() => (state.calls = [])),
    request("submission", "/api/submissions").then((data) => (state.submissions = data)).catch(() => (state.submissions = [])),
    request("notification", `/notifications/user/${state.user.id}`).then((data) => (state.notifications = data.notifications || [])).catch(() => (state.notifications = [])),
    request("masterdata", "/api/departments").then((data) => (state.departments = data)).catch(() => (state.departments = []))
    ,request("masterdata", "/api/themes").then((data) => (state.themes = data)).catch(() => (state.themes = []))
    ,request("masterdata", "/api/templates").then((data) => (state.templates = data)).catch(() => (state.templates = []))
    ,request("submission", "/api/publications").then((data) => (state.publications = data)).catch(() => (state.publications = []))
  ];

  if (hasAnyRole(["Admin", "ResearchOfficer", "EditorialBoard", "InternalReviewer", "ExternalReviewer"])) {
    tasks.push(request("review", "/api/review-assignments").then((data) => (state.assignments = data)).catch(() => (state.assignments = [])));
  }
  if (hasAnyRole(["Admin", "ResearchOfficer", "EditorialBoard"])) {
    tasks.push(request("identity", "/api/users").then((data) => (state.users = data)).catch(() => (state.users = [])));
  }
  if (hasRole("Admin")) {
    tasks.push(request("identity", "/api/audit-logs").then((data) => (state.auditLogs = data)).catch(() => (state.auditLogs = [])));
  }

  await Promise.all(tasks);
}

function render() {
  if (!state.user) {
    renderLogin();
  } else {
    hydrate();
  }
}

function renderLogin() {
  document.getElementById("app").innerHTML = `
    <main class="login-page">
      <section class="login-shell">
        <div class="brand-panel">
          <div>
            ${logoMarkup("large")}
            <span class="login-institution">Bank of Uganda</span>
            <h1>Publication Management System</h1>
          </div>
        </div>
        <div class="login-card">
          <span class="eyebrow">Bank of Uganda</span>
          <h2>Sign in</h2>
          <p class="muted">Use the account created for you by the System Admin.</p>
          <div id="login-message" class="message"></div>
          <form id="login-form" class="form-grid">
            <div class="form-row">
              <label for="email">Email address</label>
              <input id="email" name="email" type="email" autocomplete="email" required placeholder="gtusiime@bou.or.ug">
            </div>
            <div class="form-row">
              <label for="password">Password</label>
              <input id="password" name="password" type="password" autocomplete="current-password" required placeholder="Enter password">
            </div>
            <button class="button" type="submit">Sign in</button>
          </form>
          <button class="button secondary full-button" id="public-repository-btn" type="button">Browse published working papers</button>
        </div>
      </section>
    </main>
  `;

  document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const message = document.getElementById("login-message");
    message.className = "message";
    try {
      const loginData = await request("identity", "/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password")
        })
      });
      setSession(loginData);
      await hydrate();
    } catch (error) {
      message.textContent = error.message;
      message.className = "message show";
    }
  });
  document.getElementById("public-repository-btn").addEventListener("click", renderPublicRepository);
}

async function renderPublicRepository() {
  document.getElementById("app").innerHTML = `<main class="public-page"><div class="public-hero">${logoMarkup("large")}<div><span class="eyebrow">Bank of Uganda</span><h1>Working Paper Series</h1><p>Browse research approved through the Publication Management System.</p></div><button class="button secondary" id="back-to-login" type="button">Staff sign in</button></div><section class="panel"><div class="empty">Loading publications…</div></section></main>`;
  document.getElementById("back-to-login").addEventListener("click", renderLogin);
  try {
    const response = await fetch(`${API.submission}/api/publications`);
    if (!response.ok) throw new Error("Repository is currently unavailable.");
    state.publications = await response.json();
    document.querySelector(".public-page .panel").innerHTML = `<div class="publication-grid">${state.publications.length ? state.publications.map((item) => `<article class="publication-card"><span class="badge">${escapeHtml(item.publication_reference || `BOU-WP-${item.id}`)}</span><h3>${escapeHtml(item.title)}</h3><p class="muted">${escapeHtml(item.author)} · ${escapeHtml(item.theme_name)} · ${escapeHtml(item.fiscal_year)}</p>${item.paper ? `<a class="button secondary" href="${API.submission}${item.paper}" target="_blank" rel="noopener">Download paper</a>` : ""}</article>`).join("") : `<div class="empty">No papers have been published yet.</div>`}</div>`;
  } catch (error) {
    document.querySelector(".public-page .panel").innerHTML = `<div class="message show">${escapeHtml(error.message)}</div>`;
  }
}

function navItems() {
  const items = [{ id: "dashboard", label: "Dashboard", group: "Overview" }];
  if (hasRole("Admin")) items.push(
    { id: "admin-users", label: "User Accounts", group: "Access control" },
    { id: "admin-departments", label: "Departments", group: "Master data" },
    { id: "admin-themes", label: "Research Themes", group: "Master data" },
    { id: "admin-templates", label: "Templates & Notices", group: "Master data" },
    { id: "publications", label: "Public Repository", group: "Oversight" },
    { id: "admin-audit", label: "Audit Log", group: "Oversight" }
  );
  if (hasRole("ResearchOfficer")) items.push(
    { id: "officer-calls", label: "Manage Calls", group: "Research workflow" },
    { id: "officer-assign", label: "Reviewer Assignment", group: "Research workflow" },
    { id: "officer-verify", label: "Verification Queue", group: "Research workflow" },
    { id: "reports", label: "Reports", group: "Insights" }
  );
  if (hasRole("EditorialBoard")) items.push(
    { id: "editorial-verify", label: "Verification Queue", group: "Editorial workflow" },
    { id: "editorial-publish", label: "Approve for Publishing", group: "Editorial workflow" },
    { id: "reports", label: "Reports", group: "Insights" }
  );
  if (hasAnyRole(["InternalReviewer", "ExternalReviewer"])) items.push({ id: "reviewer-assignments", label: "My Assignments", group: "Review workspace" });
  if (hasRole("Author")) items.push(
    { id: "author-submit", label: "Submit Abstract / Paper", group: "Author workspace" },
    { id: "author-submissions", label: "My Submissions", group: "Author workspace" }
  );
  items.push({ id: "notifications", label: `Notifications (${state.notifications.filter((item) => !item.is_read).length})`, group: "Alerts" });
  return items;
}

function navIcon(id) {
  const icons = {
    dashboard: "◉", "admin-users": "♟", "admin-departments": "▥", "admin-themes": "◆",
    "admin-templates": "▤", publications: "◎", "admin-audit": "⌕", "officer-calls": "▣",
    "officer-assign": "♟", "officer-verify": "✓", reports: "▥", "editorial-verify": "✓",
    "editorial-publish": "✎", "reviewer-assignments": "▧", "author-submit": "↥",
    "author-submissions": "▰", notifications: "♢"
  };
  return icons[id] || "•";
}

function renderShell() {
  const nav = navItems();
  const transientViews = ["officer-call-create", "officer-assignment-create", "admin-user-create", "admin-department-create", "admin-theme-create", "admin-template-create"];
  if (!nav.find((item) => item.id === state.view) && !transientViews.includes(state.view)) {
    state.view = "dashboard";
  }

  document.getElementById("app").innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="side-brand">
          ${logoMarkup()}
          <div>
            <strong>Publication<br>Management</strong>
            <small>Bank of Uganda</small>
          </div>
        </div>
        <nav class="nav">
          ${nav.map((item, index) => `${index === 0 || nav[index - 1].group !== item.group ? `<span class="nav-group-label">${item.group}</span>` : ""}<button data-view="${item.id}" class="${state.view === item.id ? "active" : ""}"><span class="nav-icon">${navIcon(item.id)}</span><span>${item.label}</span>${item.id === "notifications" && state.notifications.some((notification) => !notification.is_read) ? `<span class="nav-count">${state.notifications.filter((notification) => !notification.is_read).length}</span>` : ""}</button>`).join("")}
        </nav>
        <button class="button gold" id="refresh-btn" type="button">Refresh data</button>
      </aside>
      <main class="main">
        <div class="topbar">
          <div>
            <span class="eyebrow">${pageMeta()[0]}</span>
            <h2>${pageMeta()[1]}</h2>
          </div>
          <div class="profile-pill">
            <div class="avatar">${initials(state.user.name || state.user.email)}</div>
            <div>
              <strong>${state.user.name || state.user.email}</strong><br>
              <small class="muted">${state.user.roles.join(", ")}</small>
            </div>
            <button class="button secondary" id="logout-btn" type="button">Logout</button>
          </div>
        </div>
        <div id="view-root">${renderCurrentView()}</div>
      </main>
      <dialog id="detail-dialog"><button class="dialog-close" type="button" aria-label="Close">×</button><div id="dialog-content"></div></dialog>
    </div>
  `;

  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      localStorage.setItem("bou_view", state.view);
      renderShell();
    });
  });
  document.querySelectorAll("[data-go-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.goView;
      localStorage.setItem("bou_view", state.view);
      renderShell();
      window.scrollTo(0, 0);
    });
  });
  document.getElementById("logout-btn").addEventListener("click", clearSession);
  document.getElementById("refresh-btn").addEventListener("click", hydrate);
  bindCurrentView();
}

function pageTitle() {
  const map = {
    dashboard: "Dashboard",
    "author-submit": "Submit Abstract or Working Paper",
    "author-submissions": "My Submissions",
    "officer-calls": "Manage Calls",
    "officer-call-create": "Create Call for Papers",
    "officer-assignment-create": "Assign Reviewer",
    "officer-assign": "Reviewer Assignment",
    "officer-verify": "Verification Queue",
    "editorial-verify": "Assignment Verification",
    "editorial-publish": "Approve for Publishing",
    "reviewer-assignments": "My Review Assignments",
    "admin-users": "User Accounts",
    "admin-user-create": "Create User Account",
    "admin-departments": "Departments",
    "admin-department-create": "Add Department",
    "admin-themes": "Research Themes",
    "admin-theme-create": "Add Research Theme",
    "admin-templates": "Templates & Notices",
    "admin-template-create": "Add Template or Notice",
    "admin-audit": "Audit Log",
    publications: "Public Working Paper Repository",
    reports: "Reports & Insights",
    notifications: "Notifications"
  };
  return map[state.view] || "Dashboard";
}

function pageMeta() {
  const eyebrow = {
    dashboard: "BOU PMS", "author-submit": "SUBMISSION", "author-submissions": "TRACKING",
    "officer-calls": "MANAGE CALLS", "officer-call-create": "MANAGE CALLS", "officer-assign": "REVIEWER ASSIGNMENT", "officer-assignment-create": "REVIEWER ASSIGNMENT",
    "officer-verify": "VERIFICATION QUEUE", reports: "INSIGHTS", "editorial-verify": "VERIFICATION QUEUE",
    "editorial-publish": "FINAL STAGE", "reviewer-assignments": "REVIEW WORKSPACE", "admin-users": "ACCESS CONTROL",
    "admin-user-create": "ACCESS CONTROL", "admin-departments": "MASTER DATA", "admin-department-create": "MASTER DATA", "admin-themes": "MASTER DATA", "admin-theme-create": "MASTER DATA", "admin-templates": "MASTER DATA", "admin-template-create": "MASTER DATA",
    "admin-audit": "OVERSIGHT", publications: "PUBLIC SITE PREVIEW", notifications: "ALERTS"
  };
  return [eyebrow[state.view] || "BOU PMS", pageTitle()];
}

function renderCurrentView() {
  if (state.view === "author-submit") return renderAuthorSubmitPage();
  if (state.view === "author-submissions") return renderAuthorSubmissionsPage();
  if (state.view === "officer-calls") return renderOfficerCallsPage();
  if (state.view === "officer-call-create") return renderOfficerCallCreatePage();
  if (state.view === "officer-assign") return renderOfficerAssignmentPage();
  if (state.view === "officer-assignment-create") return renderOfficerAssignmentCreatePage();
  if (state.view === "officer-verify") return renderOfficerVerificationPage();
  if (state.view === "editorial-verify") return renderEditorialVerificationPage();
  if (state.view === "editorial-publish") return renderEditorialPublishingPage();
  if (state.view === "reviewer-assignments") return renderReviewerView();
  if (state.view === "admin-users") return renderAdminUsersPage();
  if (state.view === "admin-user-create") return renderAdminUserCreatePage();
  if (state.view === "admin-departments") return renderAdminDepartmentsPage();
  if (state.view === "admin-department-create") return renderAdminDepartmentCreatePage();
  if (state.view === "admin-themes") return renderAdminThemesPage();
  if (state.view === "admin-theme-create") return renderAdminThemeCreatePage();
  if (state.view === "admin-templates") return renderAdminTemplatesPage();
  if (state.view === "admin-template-create") return renderAdminTemplateCreatePage();
  if (state.view === "admin-audit") return renderAuditPage();
  if (state.view === "publications") return renderPublicationsPage();
  if (state.view === "reports") return renderReportsPage();
  if (state.view === "notifications") return renderNotificationsView();
  return renderDashboard();
}

function renderDashboard() {
  const publishedCalls = state.calls.filter((call) => call.status === "published").length;
  const unread = state.notifications.filter((item) => !item.is_read).length;
  const pendingAssignments = state.assignments.filter((item) => item.status !== "verified").length;
  if (hasRole("Author") && !hasAnyRole(["Admin", "ResearchOfficer", "EditorialBoard", "InternalReviewer", "ExternalReviewer"])) {
    return `<section class="grid three dashboard-stats">${metricCard("Open calls you can submit to", publishedCalls, "Active")}${metricCard("Your submissions", state.submissions.length, "Total")}${metricCard("Unread alerts", unread, "Notifications")}</section><section class="grid two dashboard-panels"><div class="panel">${pageHeader("Tracking", "Recent submissions", "Status of your most recent papers.")}${renderSubmissionList(state.submissions.slice(0, 3), false)}<button class="button secondary compact" data-go-view="author-submissions" type="button">View all submissions</button></div><div class="panel">${pageHeader("Shortcuts", "Get started", "Jump straight into a task.")}<div class="stack-actions"><button class="button" data-go-view="author-submit" type="button">Submit an abstract or paper</button><button class="button secondary" data-go-view="notifications" type="button">View notifications (${unread})</button></div></div></section>`;
  }
  if (hasAnyRole(["InternalReviewer", "ExternalReviewer"]) && !hasAnyRole(["Admin", "ResearchOfficer", "EditorialBoard"])) {
    const mine = state.assignments.filter((item) => item.reviewer_id === state.user.id);
    return `<section class="grid three dashboard-stats">${metricCard("Assigned papers", mine.length, "Total")}${metricCard("Awaiting your review", mine.filter((item) => item.status === "verified").length, "Action needed")}${metricCard("Unread alerts", unread, "Notifications")}</section><section class="panel dashboard-panels">${pageHeader("Review workspace", "Your queue", `Papers assigned to you as ${state.user.roles.map(humanize).join(", ")}.`)}${renderAssignmentList(mine)}<button class="button secondary compact" data-go-view="reviewer-assignments" type="button">Go to My Assignments</button></section>`;
  }
  if (hasRole("ResearchOfficer") && !hasRole("Admin")) {
    const comments = state.assignments.flatMap((assignment) => assignment.comments || []).filter((comment) => comment.verification_status === "pending");
    return `<section class="grid three dashboard-stats">${metricCard("Active calls", publishedCalls, "Open calls authors can submit to")}${metricCard("Submissions", state.submissions.length, "Visible to your role")}${metricCard("Unread alerts", unread, "Notifications requiring attention")}</section><section class="grid two dashboard-panels"><div class="panel">${pageHeader("Workflow", "Needs a reviewer assignment")} ${renderSubmissionList(state.submissions.filter((item) => ["submitted", "internal_review_complete"].includes(item.status)).slice(0, 4))}<button class="button secondary compact" data-go-view="officer-assign" type="button">Go to Reviewer Assignment</button></div><div class="panel">${pageHeader("Review", `Verification queue`, `${comments.length} pending`)}${renderOfficerQueues()}<button class="button secondary compact" data-go-view="officer-verify" type="button">Go to Verification Queue</button></div></section>`;
  }
  if (hasRole("EditorialBoard") && !hasRole("Admin")) {
    const pending = state.assignments.filter((item) => item.status === "pending_editorial_verification");
    return `<section class="grid three dashboard-stats">${metricCard("Pending verifications", pending.length, "Awaiting Editorial Board")}${metricCard("Submissions", state.submissions.length, "Across all calls")}${metricCard("Unread alerts", unread, "Notifications")}</section><section class="panel dashboard-panels">${pageHeader("Review", "Verification queue")}${renderAssignmentList(pending)}<div class="item-actions"><button class="button secondary compact" data-go-view="editorial-verify" type="button">Go to Verification Queue</button><button class="button secondary compact" data-go-view="editorial-publish" type="button">Go to Approve for Publishing</button></div></section>`;
  }
  return `
    <section class="grid three dashboard-stats">
      ${metricCard("Active calls", publishedCalls, "Open calls authors can submit to")}
      ${metricCard("Submissions", state.submissions.length, "Visible to your role")}
      ${metricCard("Unread alerts", unread, "Notifications requiring attention")}
    </section>
    <section class="grid two dashboard-panels">
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Workflow</span>
            <h2>Recent submissions</h2>
          </div>
        </div>
        ${renderSubmissionList(state.submissions.slice(0, 4))}
      </div>
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Review</span>
            <h2>Assignment queue</h2>
          </div>
          <span class="badge">${pendingAssignments} pending</span>
        </div>
        ${renderAssignmentList(state.assignments.slice(0, 4))}
      </div>
    </section>
  `;
}

function metricCard(label, value, detail) {
  return `
    <div class="panel metric">
      <span class="muted">${label}</span>
      <strong>${value}</strong>
      <span>${detail}</span>
    </div>
  `;
}

function pageHeader(eyebrow, title, description = "", actions = "") {
  return `<div class="section-title"><div><span class="eyebrow">${eyebrow}</span><h2>${title}</h2>${description ? `<p class="muted">${description}</p>` : ""}</div>${actions}</div>`;
}

function submissionFormMarkup() {
  const publishedCalls = state.calls.filter((call) => call.status === "published");
  return `<form id="submission-form" class="form-grid">
    <div class="form-row"><label>Call for papers</label><select name="call_id" id="call-select" required><option value="">Select a published call</option>${publishedCalls.map((call) => `<option value="${call.id}">${escapeHtml(call.fiscal_year)} — ${escapeHtml(call.description)}</option>`).join("")}</select></div>
    <div class="form-row"><label>Research theme</label><select name="theme_id" id="theme-select" required><option value="">Select a call first</option></select></div>
    <div class="form-row"><label>Abstract / working paper title</label><input name="title" maxlength="300" required placeholder="Enter the full research title"></div>
    <div class="subpanel"><strong>Authors</strong><p class="muted">The first row is the corresponding author. Every co-author requires a valid email and either a BOU department or institution.</p><div id="authors-box" class="grid"></div><button class="button secondary" id="add-author-btn" type="button">+ Add co-author</button></div>
    <button class="button" type="submit">Submit to Research Department</button>
  </form>`;
}

function renderAuthorSubmitPage() {
  return `<section class="grid two"><div class="panel">${pageHeader("Submission", "Submit abstract or working paper idea", "The corresponding author is the logged-in author. Add co-authors and their institutions or BOU departments.")}${submissionFormMarkup()}</div><aside class="panel"><span class="eyebrow">Guidance</span><h2>Before you submit</h2><div class="kv"><span>Approved file types</span><strong>.docx, .pdf</strong></div><div class="kv"><span>Max file size</span><strong>10 MB</strong></div><div class="kv"><span>Co-authors</span><strong>Unlimited, valid e-mail required</strong></div><div class="kv"><span>Multiple submissions per call</span><strong>Allowed</strong></div><div class="divider"></div><p class="hint">After creating the submission, upload the abstract or complete working paper from My Submissions. You will receive an on-screen acknowledgement and notification.</p></aside></section>`;
}

function renderAuthorSubmissionsPage() {
  return `<section class="panel">${pageHeader("Tracking", "My submissions", "Track every stage, upload new document versions, and respond when revision is requested.")}${renderSubmissionList(state.submissions, true)}</section>`;
}

function callFormMarkup() {
  return `<form id="call-form" class="form-grid"><div class="inline-fields"><div class="form-row"><label>Fiscal year</label><input name="fiscal_year" required placeholder="2026/2027"></div><div class="form-row"><label>Abstract deadline</label><input name="abstract_deadline" type="datetime-local" required></div><div class="form-row"><label>Paper deadline</label><input name="paper_deadline" type="datetime-local" required></div></div><div class="form-row"><label>Description</label><textarea name="description" required placeholder="Purpose and scope of this call"></textarea></div><div class="form-row"><label>Approved research themes</label><div class="theme-picker">${state.themes.filter((item) => item.is_active).map((item) => `<label><input type="checkbox" name="theme_choice" value="${escapeAttribute(item.name)}"> ${escapeHtml(item.name)}</label>`).join("") || `<span class="muted">No master themes configured; enter themes below.</span>`}</div></div><div class="form-row"><label>Additional themes (one per line)</label><textarea name="themes" placeholder="Macroeconomic Policy&#10;Financial Stability"></textarea></div><button class="button" type="submit">Create draft call</button></form>`;
}

function renderOfficerCallsPage() {
  return `<section class="panel">${pageHeader("Calls", "Existing calls", "View existing calls created in the system.")}${renderCallsTable()}</section><button class="fab-button" data-go-view="officer-call-create" type="button"><span>＋</span> Create Call for Papers</button>`;
}

function renderOfficerCallCreatePage() {
  return `<section class="panel centered-form">${pageHeader("Calls", "Create Call for Papers", "Fill in the details below to create a new call.")}${callFormMarkup().replace('<button class="button" type="submit">Create draft call</button>', '<div class="item-actions"><button class="button secondary" data-go-view="officer-calls" type="button">Back to calls</button><button class="button" type="submit">Create draft call</button></div>')}</section>`;
}

function assignmentFormMarkup() {
  return `<form id="assignment-form" class="form-grid"><div class="form-row"><label>Submission</label><select name="submission_id" required><option value="">Select submission</option>${state.submissions.map((item) => `<option value="${item.id}">#${item.id} — ${escapeHtml(item.title)}</option>`).join("")}</select></div><div class="inline-fields"><div class="form-row"><label>Reviewer type</label><select name="reviewer_type" id="reviewer-type" required><option value="internal">Internal reviewer</option><option value="external">External reviewer</option></select></div><div class="form-row"><label>Reviewer</label><select name="reviewer_id" required><option value="">Select reviewer</option>${reviewerOptions()}</select></div></div><div id="coi-result" class="message"></div><button class="button" type="submit">Send assignment for Editorial Board verification</button></form>`;
}

function renderOfficerAssignmentPage() {
  return `<section class="panel">${pageHeader("Reviewer assignment", "Assignment register", "View reviewer assignments and their Editorial Board verification status.")}${renderAssignmentsTable(state.assignments)}</section><button class="fab-button" data-go-view="officer-assignment-create" type="button"><span>＋</span> Assign Reviewer</button>`;
}

function renderOfficerAssignmentCreatePage() {
  return `<section class="panel centered-form">${pageHeader("Reviewer assignment", "Assign internal or external reviewer", "The assignment is sent to the Editorial Board for verification before the reviewer can begin.")}${assignmentFormMarkup().replace('<button class="button" type="submit">Send assignment for Editorial Board verification</button>', '<div class="item-actions"><button class="button secondary" data-go-view="officer-assign" type="button">Back to assignments</button><button class="button" type="submit">Send to Editorial Board</button></div>')}</section>`;
}

function renderOfficerVerificationPage() {
  const revisions = state.submissions.filter((item) => item.status === "revised_submission" || item.current_stage === "revised_submission");
  return `<section class="panel">${pageHeader("Officer verification", "Verification queue", "Review one type of pending work at a time.")}<div class="subtabs"><button class="subtab active" data-tab-target="comments-queue" type="button">Reviewer comments</button><button class="subtab" data-tab-target="revisions-queue" type="button">Revised working papers <span class="tab-count">${revisions.length}</span></button></div><div class="tab-panel" data-tab-panel="comments-queue">${renderOfficerQueues()}</div><div class="tab-panel hidden" data-tab-panel="revisions-queue">${revisions.map((item) => `<div class="queue-row"><strong>${escapeHtml(item.title)}</strong><div class="item-actions"><button class="button success-outline compact" data-status="${item.id}" data-stage="external_review" data-label="Revised paper verified and ready for the next review stage" type="button">Verify & proceed</button><button class="button danger-outline compact" data-status="${item.id}" data-stage="author_revision" data-label="The revised paper was returned for correction" type="button">Return to author</button></div></div>`).join("") || `<div class="empty">No revised working papers pending verification.</div>`}</div></section>`;
}

function renderEditorialVerificationPage() {
  const assignments = state.assignments.filter((item) => item.status === "pending_editorial_verification" || item.status === "returned_to_research_officer");
  const officerApprovals = state.submissions.filter((item) => item.status === "editorial_board" || item.current_stage === "editorial_board");
  return `<section class="panel">${pageHeader("Verification queue", "Assignment & approval verification", "Work through one verification queue at a time.")}<div class="subtabs"><button class="subtab active" data-tab-target="assignment-verification" type="button">Reviewer assignments <span class="tab-count">${assignments.length}</span></button><button class="subtab" data-tab-target="officer-approvals" type="button">Officer approvals <span class="tab-count">${officerApprovals.length}</span></button></div><div class="tab-panel" data-tab-panel="assignment-verification">${renderAssignmentList(assignments, false, true)}</div><div class="tab-panel hidden" data-tab-panel="officer-approvals">${officerApprovals.map((item) => `<div class="queue-row"><strong>${escapeHtml(item.title)}</strong><div class="item-actions"><button class="button success-outline compact" data-status="${item.id}" data-stage="approved_for_publishing" data-label="Officer approval verified; ready for the final publishing decision" type="button">Approve</button><button class="button danger-outline compact" data-status="${item.id}" data-stage="internal_review" data-label="Editorial Board returned the approval to the Research Officer" type="button">Return with reason</button></div></div>`).join("") || `<div class="empty">No officer approvals pending verification.</div>`}</div></section>`;
}

function renderEditorialPublishingPage() {
  return `<section class="panel">${pageHeader("Final stage", "Approve for publishing", "Record the Editorial Board’s final decision and publication reference.")}${renderFinalDecisionList()}</section>`;
}

function userFormMarkup() {
  return `<form id="user-form" class="form-grid"><div class="form-row"><label>Full name</label><input name="name" required placeholder="e.g. Brenda Auma"></div><div class="form-row"><label>Email address</label><input name="email" type="email" required placeholder="e.g. bauma@bou.or.ug"></div><div class="form-row"><label>Temporary password</label><input name="password" type="password" minlength="12" autocomplete="new-password" required placeholder="At least 12 characters"></div><div class="form-row"><label>Roles (select one or more)</label><div class="role-checkbox-grid">${roles.map((role) => `<label><input name="roles" type="checkbox" value="${role}" ${role === "Author" ? "checked" : ""}> ${humanize(role)}</label>`).join("")}</div></div><div id="user-form-message" class="message error-message" role="alert" aria-live="polite"></div><button class="button" type="submit">Create account</button></form>`;
}

function renderAdminUsersPage() {
  return `<section class="panel">${pageHeader("Access control", "Current user accounts", "Manage roles, account status, and password resets from one account register.")}${renderUsersTable()}</section><button class="fab-button" data-go-view="admin-user-create" type="button"><span>＋</span> Create User Account</button>`;
}

function renderAdminUserCreatePage() {
  return `<section class="panel centered-form">${pageHeader("Access control", "Create user account", "There is no public registration; administrators provision every account.")}${userFormMarkup().replace('<button class="button" type="submit">Create account</button>', '<div class="item-actions"><button class="button secondary" data-go-view="admin-users" type="button">Back to users</button><button class="button" type="submit">Create account</button></div>')}</section>`;
}

function renderAdminDepartmentsPage() {
  return `<section class="panel">${pageHeader("Master data", "Departments", "Departments populate the BOU-staff co-author affiliation field.")}${renderDepartmentsTable()}</section><button class="fab-button" data-go-view="admin-department-create" type="button"><span>＋</span> Add Department</button>`;
}

function renderAdminDepartmentCreatePage() {
  return `<section class="panel centered-form">${pageHeader("Master data", "Add department", "Add a department to the BOU staff affiliation list.")}<form id="department-form" class="form-grid"><div class="form-row"><label>Department name</label><input name="name" required placeholder="e.g. Legal Department"></div><div class="item-actions"><button class="button secondary" data-go-view="admin-departments" type="button">Back to departments</button><button class="button" type="submit">Add department</button></div></form></section>`;
}

function renderAdminThemesPage() {
  return `<section class="panel">${pageHeader("Master data", "Research themes", "Manage the approved theme catalogue used when creating Calls for Papers.")}${renderThemesTable()}</section><button class="fab-button" data-go-view="admin-theme-create" type="button"><span>＋</span> Add Research Theme</button>`;
}

function renderAdminThemeCreatePage() {
  return `<section class="panel centered-form">${pageHeader("Master data", "Add research theme", "Create a theme that Research Officers can select for a Call for Papers.")}<form id="theme-form" class="form-grid"><div class="form-row"><label>Theme name</label><input name="name" required placeholder="e.g. Financial Inclusion"></div><div class="item-actions"><button class="button secondary" data-go-view="admin-themes" type="button">Back to themes</button><button class="button" type="submit">Add theme</button></div></form></section>`;
}

function renderAdminTemplatesPage() {
  const resources = state.templates.filter((item) => item.template_type !== "notification");
  const notices = state.templates.filter((item) => item.template_type === "notification");
  return `<section class="panel">${pageHeader("Master data", "Templates & notification notices", "Manage reviewer resources and automated notices from one register.")}<div class="subtabs"><button class="subtab active" data-tab-target="reviewer-templates" type="button">Reviewer templates <span class="tab-count">${resources.length}</span></button><button class="subtab" data-tab-target="notification-notices" type="button">Notification notices <span class="tab-count">${notices.length}</span></button></div><div class="tab-panel" data-tab-panel="reviewer-templates"><div class="file-list">${resources.map(renderTemplateFileChip).join("") || `<div class="empty">No reviewer templates uploaded.</div>`}</div></div><div class="tab-panel hidden" data-tab-panel="notification-notices">${notices.map((item) => `<div class="notice-row"><div><strong>${escapeHtml(item.name)}</strong><p class="hint">${escapeHtml(item.body || item.subject)}</p></div><button class="button secondary compact" data-edit-template="${item.id}" type="button">Edit</button></div>`).join("") || `<div class="empty">No notification notices configured.</div>`}</div></section><button class="fab-button" data-go-view="admin-template-create" type="button"><span>＋</span> Add Template or Notice</button>`;
}

function renderAdminTemplateCreatePage() {
  return `<section class="panel centered-form">${pageHeader("Master data", "Add template or notice", "Choose one resource type and complete its details.")}<form class="template-form form-grid"><div class="form-row"><label>Name</label><input name="name" required></div><div class="form-row"><label>Type</label><select name="template_type" required><option value="review_comments">Reviewer comments template</option><option value="review_guidelines">Reviewer guidelines</option><option value="notification">Notification notice</option></select></div><div class="form-row"><label>Subject</label><input name="subject"></div><div class="form-row"><label>Body / instructions</label><textarea name="body"></textarea></div><div class="form-row"><label>Attachment (optional)</label><input name="file" type="file" accept=".pdf,.doc,.docx"></div><div class="item-actions"><button class="button secondary" data-go-view="admin-templates" type="button">Back to templates</button><button class="button" type="submit">Save</button></div></form></section>`;
}

function templateFormMarkup(defaultType) {
  return `<form class="template-form form-grid"><div class="form-row"><label>Name</label><input name="name" required></div><input name="template_type" type="hidden" value="${defaultType}"><div class="form-row"><label>Subject</label><input name="subject"></div><div class="form-row"><label>Body / instructions</label><textarea name="body"></textarea></div><div class="form-row"><label>Attachment (optional)</label><input name="file" type="file" accept=".pdf,.doc,.docx"></div><button class="button" type="submit">Save</button></form>`;
}

function renderTemplateFileChip(item) {
  const extension = item.file_path.split(".").pop().toUpperCase() || "DOC";
  return `<div class="file-chip"><span class="file-icon">${escapeHtml(extension)}</span><div><strong>${escapeHtml(item.name)}</strong><div class="hint">Version ${item.version} · updated ${formatDate(item.updated_at)}</div></div>${item.file_path ? `<a class="button secondary compact" href="${API.masterdata}${item.file_path}" target="_blank" rel="noopener">Download</a>` : ""}<button class="button danger-outline compact" data-delete-template="${item.id}" type="button">Deactivate</button></div>`;
}

function renderAuditPage() {
  return `<section class="panel">${pageHeader("Oversight", "Audit log", "Tamper-resistant record of authentication and administrative actions.", `<button class="button secondary" data-export="audit" type="button">Export CSV</button>`)}${renderAuditTable()}</section>`;
}

function renderPublicationsPage() {
  return `<section class="panel">${pageHeader("Public site preview", "BOU Working Paper Series", "This is what visitors of the public BOU Working Paper Series page see — no login required.")}${state.publications.length ? state.publications.map((item) => `<article class="paper-card"><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(item.publication_reference || `BOU-WP-${item.id}`)} · Published ${formatDate(item.publication_date)} · Theme: ${escapeHtml(item.theme_name)}</p><p>Authors: ${escapeHtml(item.author)}</p>${item.paper ? `<a class="button secondary compact" href="${API.submission}${item.paper}" target="_blank" rel="noopener">Download PDF</a>` : `<span class="hint">Paper file pending</span>`}</article>`).join("") : `<div class="empty">No papers published yet.</div>`}</section>`;
}

function renderReportsPage() {
  const byStatus = state.submissions.reduce((totals, item) => ({ ...totals, [item.status]: (totals[item.status] || 0) + 1 }), {});
  const workload = state.assignments.reduce((totals, item) => ({ ...totals, [item.reviewer_name || `User #${item.reviewer_id}`]: (totals[item.reviewer_name || `User #${item.reviewer_id}`] || 0) + 1 }), {});
  return `<section class="panel">${pageHeader("Reporting", "Reports & insights", "Choose one report to analyse or export.", `<div class="item-actions"><button class="button secondary compact" data-export="submissions" type="button">Export to Excel/CSV</button><button class="button secondary compact" id="print-report" type="button">Export to PDF</button></div>`)}<div class="subtabs"><button class="subtab active" data-tab-target="status-report" type="button">Submissions by status</button><button class="subtab" data-tab-target="workload-report" type="button">Reviewer workload</button><button class="subtab" data-tab-target="turnaround-report" type="button">Turnaround time</button></div><div class="tab-panel" data-tab-panel="status-report"><div class="table-wrap"><table><thead><tr><th>Status</th><th>Count</th></tr></thead><tbody>${Object.entries(byStatus).map(([status, count]) => `<tr><td>${humanize(status)}</td><td>${count}</td></tr>`).join("") || `<tr><td colspan="2">No submissions yet.</td></tr>`}</tbody></table></div></div><div class="tab-panel hidden" data-tab-panel="workload-report"><div class="table-wrap"><table><thead><tr><th>Reviewer</th><th>Assigned papers</th></tr></thead><tbody>${Object.entries(workload).map(([reviewer, count]) => `<tr><td>${escapeHtml(reviewer)}</td><td>${count}</td></tr>`).join("") || `<tr><td colspan="2">No assignments yet.</td></tr>`}</tbody></table></div></div><div class="tab-panel hidden" data-tab-panel="turnaround-report"><div class="empty">Turnaround metrics become available as completed workflow history accumulates.</div></div></section>`;
}

function renderAuthorView() {
  const publishedCalls = state.calls.filter((call) => call.status === "published");
  return `
    <section class="grid two">
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Submission</span>
            <h2>Submit abstract or working paper idea</h2>
            <p class="muted">The corresponding author is the logged-in author. Add co-authors and their institutions or BOU departments.</p>
          </div>
        </div>
        <form id="submission-form" class="form-grid">
          <div class="form-row">
            <label>Call</label>
            <select name="call_id" id="call-select" required>
              <option value="">Select a published call</option>
              ${publishedCalls.map((call) => `<option value="${call.id}">${call.fiscal_year} - ${call.description}</option>`).join("")}
            </select>
          </div>
          <div class="form-row">
            <label>Theme</label>
            <select name="theme_id" id="theme-select" required>
              <option value="">Select a call first</option>
            </select>
          </div>
          <div class="form-row">
            <label>Title</label>
            <input name="title" required placeholder="Enter the abstract or working paper title">
          </div>
          <div class="panel compact-panel">
            <strong>Authors</strong>
            <p class="muted margin-top-small">First row should be the corresponding author.</p>
            <div id="authors-box" class="grid margin-top-medium"></div>
            <button class="button secondary" id="add-author-btn" type="button">Add co-author</button>
          </div>
          <button class="button" type="submit">Submit to Research Department</button>
        </form>
      </div>
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Tracking</span>
            <h2>My submissions</h2>
          </div>
        </div>
        ${renderSubmissionList(state.submissions, true)}
      </div>
    </section>
  `;
}

function renderOfficerView() {
  return `
    <section class="grid two">
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Calls</span>
            <h2>Create call for papers</h2>
          </div>
        </div>
        <form id="call-form" class="form-grid">
          <div class="inline-fields">
            <div class="form-row">
              <label>Fiscal year</label>
              <input name="fiscal_year" required placeholder="2026/2027">
            </div>
            <div class="form-row">
              <label>Abstract deadline</label>
              <input name="abstract_deadline" type="datetime-local" required>
            </div>
          </div>
          <div class="form-row">
            <label>Paper deadline</label>
            <input name="paper_deadline" type="datetime-local" required>
          </div>
          <div class="form-row">
            <label>Description</label>
            <textarea name="description" required placeholder="Describe the call"></textarea>
          </div>
          <div class="form-row">
            <label>Themes, one per line</label>
            <textarea name="themes" placeholder="Macroeconomic Policy&#10;Financial Stability"></textarea>
          </div>
          <button class="button" type="submit">Create draft call</button>
        </form>
      </div>
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Reviewer assignment</span>
            <h2>Assign internal or external reviewer</h2>
          </div>
        </div>
        <form id="assignment-form" class="form-grid">
          <div class="form-row">
            <label>Submission</label>
            <select name="submission_id" required>
              <option value="">Select submission</option>
              ${state.submissions.map((item) => `<option value="${item.id}">#${item.id} - ${item.title}</option>`).join("")}
            </select>
          </div>
          <div class="inline-fields">
            <div class="form-row">
              <label>Reviewer type</label>
              <select name="reviewer_type" required>
                <option value="internal">Internal reviewer</option>
                <option value="external">External reviewer</option>
              </select>
            </div>
            <div class="form-row">
              <label>Reviewer</label>
              <select name="reviewer_id" required>
                <option value="">Select reviewer</option>
                ${reviewerOptions()}
              </select>
            </div>
          </div>
          <button class="button" type="submit">Send to Editorial Board</button>
        </form>
      </div>
    </section>
    <section class="grid two margin-top-large">
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Calls</span>
            <h2>Manage calls</h2>
          </div>
        </div>
        ${renderCallsList()}
      </div>
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Officer verification</span>
            <h2>Review comments and submission status</h2>
          </div>
        </div>
        ${renderOfficerQueues()}
      </div>
    </section>
  `;
}

function renderEditorialView() {
  return `
    <section class="grid two">
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Director / Editorial Board</span>
            <h2>Verify reviewer assignments</h2>
          </div>
        </div>
        ${renderAssignmentList(state.assignments, false, true)}
      </div>
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Final decision</span>
            <h2>Approve or decline publication</h2>
          </div>
        </div>
        ${renderFinalDecisionList()}
      </div>
    </section>
  `;
}

function renderReviewerView() {
  const mine = state.assignments.filter((item) => item.reviewer_id === state.user.id || hasRole("Admin"));
  return `
    <section class="panel">
      <div class="section-title">
        <div>
          <span class="eyebrow">Reviewer</span>
          <h2>Assigned papers</h2>
          <p class="muted">Submit comments using the template and guidelines received from the Research Officer.</p>
        </div>
      </div>
      <div class="reviewer-downloads">${state.templates.filter((item) => ["review_comments", "review_guidelines"].includes(item.template_type)).map((item) => item.file_path ? `<a class="button secondary compact" href="${API.masterdata}${item.file_path}" target="_blank" rel="noopener">Download ${escapeHtml(item.name)}</a>` : "").join("") || `<span class="hint">No reviewer resources uploaded yet.</span>`}</div>
      ${renderAssignmentList(mine, true)}
    </section>
  `;
}

function renderAdminView() {
  return `
    <section class="grid two">
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Access control</span>
            <h2>Create user account</h2>
            <p class="muted">This replaces public registration and matches the requirement that accounts are created by an authorized role.</p>
          </div>
        </div>
        <form id="user-form" class="form-grid">
          <div class="form-row">
            <label>Full name</label>
            <input name="name" required placeholder="Gareth Tusiime">
          </div>
          <div class="form-row">
            <label>Email</label>
            <input name="email" type="email" required placeholder="gtusiime@bou.or.ug">
          </div>
          <div class="form-row">
            <label>Temporary password</label>
            <input name="password" type="password" minlength="12" autocomplete="new-password" required placeholder="At least 12 characters">
          </div>
          <div class="form-row">
            <label>Roles</label>
            <select name="roles" multiple size="6">
              ${roles.map((role) => `<option value="${role}">${role}</option>`).join("")}
            </select>
          </div>
          <button class="button" type="submit">Create account</button>
        </form>
      </div>
      <div class="panel">
        <div class="section-title">
          <div>
            <span class="eyebrow">Users</span>
            <h2>Current accounts</h2>
          </div>
        </div>
        ${renderUsersTable()}
      </div>
    </section>
    <section class="grid two margin-top-large">
      <div class="panel">
        <div class="section-title"><div><span class="eyebrow">Master data</span><h2>Departments</h2></div></div>
        <form id="department-form" class="form-grid">
          <div class="form-row"><label>Department name</label><input name="name" required></div>
          <button class="button secondary" type="submit">Add department</button>
        </form>
        <div class="margin-top-large">
          ${renderDepartmentsTable()}
        </div>
      </div>
      <div class="panel">
        <div class="section-title"><div><span class="eyebrow">Research setup</span><h2>Theme ownership</h2></div></div>
        <p class="muted">
          Themes are added by the Research Officer while creating a call for papers.
          This keeps themes tied to the correct call and avoids Admin creating research workflow content.
        </p>
        <div class="empty margin-top-medium">Use Research Officer &gt; Create call for papers to add call themes.</div>
      </div>
    </section>
  `;
}

function renderNotificationsView() {
  return `
    <section class="panel">
      <div class="section-title">
        <div>
          <span class="eyebrow">Alerts</span>
          <h2>Notifications</h2>
        </div>
        <button class="button secondary" id="mark-all-read" type="button">Mark all read</button>
      </div>
      <div class="notification-list">
        ${state.notifications.length ? state.notifications.map(renderNotificationCard).join("") : `<div class="empty">No notifications yet.</div>`}
      </div>
    </section>
  `;
}

function renderNotificationCard(item) {
  return `
    <div class="notification-item ${item.is_read ? "read" : ""}">
      <span class="notification-dot"></span>
      <div class="notification-copy"><strong>${escapeHtml(item.title)}</strong><div>${escapeHtml(item.message)}</div><small>${formatDate(item.created_at)}</small></div>
      <div class="row-actions">${item.is_read ? "" : `<button class="button secondary compact" data-read="${item.id}" type="button">Mark read</button>`}<button class="button danger-outline compact" data-delete-notification="${item.id}" type="button">Delete</button></div>
    </div>
  `;
}

function renderSubmissionList(submissions, authorMode = false) {
  if (!submissions.length) return `<div class="empty">No submissions found.</div>`;
  return `<div class="list">${submissions.map((item) => renderSubmissionCard(item, authorMode)).join("")}</div>`;
}

function renderSubmissionCard(item, authorMode = false) {
  return `
    <article class="card">
      <div class="item-head">
        <div>
          <h3>#${item.id} ${escapeHtml(item.title)}</h3>
          <p class="muted">${escapeHtml(item.theme_name || "No theme")} - ${escapeHtml(item.current_stage || item.status)}</p>
        </div>
        <span class="badge">${escapeHtml(item.status)}</span>
      </div>
      ${renderTracking(item.tracking_steps || [])}
      <div class="item-actions"><button class="button secondary" data-view-submission="${item.id}" type="button">View details</button></div>
      ${authorMode ? `
        <form class="item-actions upload-form" data-submission-id="${item.id}">
          <select name="doc_type">
            <option value="abstract">Abstract</option>
            <option value="paper">Working paper</option>
            <option value="revision">Revised paper</option>
          </select>
          <input name="file" type="file" accept=".pdf,.docx" required>
          <button class="button secondary" type="submit">Upload document</button>
          <button class="button secondary" data-edit-submission="${item.id}" type="button">Edit</button>
          <button class="button danger" data-delete-submission="${item.id}" type="button">Delete</button>
        </form>
      ` : `
        <div class="item-actions">
          <button class="button secondary" data-status="${item.id}" data-stage="author_revision" data-label="Return to author for revision" type="button">Return to author</button>
          <button class="button secondary" data-status="${item.id}" data-stage="external_review" data-label="Send to external review" type="button">External review needed</button>
          <button class="button gold" data-status="${item.id}" data-stage="editorial_board" data-label="Forward to Editorial Board" type="button">Forward to Editorial Board</button>
        </div>
      `}
    </article>
  `;
}

function renderTracking(steps) {
  if (!steps.length) return "";
  return `<div class="tracker">${steps.map((step, index) => `<div class="tstep ${step.state === "completed" ? "done" : step.state}"><span class="track-line"></span><span class="track-dot">${step.state === "completed" ? "✓" : index + 1}</span><span class="track-label">${escapeHtml(step.label)}</span></div>`).join("")}</div>`;
}

function renderAssignmentList(assignments, reviewerMode = false, editorialMode = false) {
  if (!assignments.length) return `<div class="empty">No assignments found.</div>`;
  return `<div class="list">${assignments.map((item) => renderAssignmentCard(item, reviewerMode, editorialMode)).join("")}</div>`;
}

function renderAssignmentsTable(assignments) {
  return `<div class="table-wrap"><table><thead><tr><th>Submission</th><th>Reviewer</th><th>Type</th><th>Status</th><th>Assigned</th></tr></thead><tbody>${assignments.length ? assignments.map((item) => `<tr><td><strong>${escapeHtml(item.submission_title || `Submission #${item.submission_id}`)}</strong></td><td>${escapeHtml(item.reviewer_name || `User #${item.reviewer_id}`)}<div class="hint">${escapeHtml(item.reviewer_email || "")}</div></td><td>${humanize(item.reviewer_type)}</td><td><span class="badge status-${escapeAttribute(item.status)}">${humanize(item.status)}</span></td><td>${item.created_at ? formatDate(item.created_at) : "—"}</td></tr>`).join("") : `<tr><td colspan="5">No assignments have been created.</td></tr>`}</tbody></table></div>`;
}

function renderAssignmentCard(item, reviewerMode = false, editorialMode = false) {
  const comments = item.comments || [];
  return `
    <article class="card">
      <div class="item-head">
        <div>
          <h3>${escapeHtml(item.submission_title || `Submission #${item.submission_id}`)}</h3>
          <p class="muted">${humanize(item.reviewer_type)} reviewer: ${escapeHtml(item.reviewer_name || `User #${item.reviewer_id}`)}</p>
        </div>
        <span class="badge">${humanize(item.status)}</span>
      </div>
      ${comments.map((comment) => `<p class="muted"><strong>${humanize(comment.recommendation)}:</strong> ${escapeHtml(comment.comments)} (${humanize(comment.verification_status)})</p>`).join("")}
      ${editorialMode ? `
        <div class="item-actions">
          <button class="button gold" data-verify-assignment="${item.id}" data-approved="true" type="button">Approve assignment</button>
          <button class="button secondary" data-verify-assignment="${item.id}" data-approved="false" type="button">Return to officer</button>
        </div>
      ` : ""}
      ${reviewerMode && item.status === "verified" ? `
        <form class="form-grid review-comment-form margin-top-medium" data-assignment-id="${item.id}">
          <div class="form-row">
            <label>Recommendation</label>
            <select name="recommendation" required>
              <option value="accept_with_minor_changes">Accept with minor changes</option>
              <option value="major_revision">Major revision</option>
              <option value="external_review_needed">External review needed</option>
              <option value="decline">Decline</option>
            </select>
          </div>
          <div class="form-row">
            <label>Comments</label>
            <textarea name="comments" required placeholder="Enter comments using the template and guidelines"></textarea>
          </div>
          <button class="button" type="submit">Submit comments</button>
        </form>
      ` : ""}
    </article>
  `;
}

function renderCallsList() {
  if (!state.calls.length) return `<div class="empty">No calls have been created.</div>`;
  return `<div class="list">${state.calls.map((call) => `
    <article class="card">
      <div class="item-head">
        <div>
          <h3>${escapeHtml(call.fiscal_year)}</h3>
          <p class="muted">${escapeHtml(call.description)}</p>
          <small class="muted">Abstract: ${formatDate(call.abstract_deadline)} | Paper: ${formatDate(call.paper_deadline)}</small>
        </div>
        <span class="badge">${call.status}</span>
      </div>
      <p>${(call.themes || []).map((theme) => `<span class="badge">${escapeHtml(theme.name)}</span>`).join(" ")}</p>
      <div class="item-actions">
        ${call.status === "draft" ? `<button class="button gold" data-publish-call="${call.id}" type="button">Publish call</button>` : ""}
        ${call.status === "published" ? `<button class="button secondary" data-edit-call="${call.id}" type="button">Edit deadlines</button><button class="button danger" data-close-call="${call.id}" type="button">Close call</button>` : ""}
      </div>
    </article>
  `).join("")}</div>`;
}

function renderCallsTable() {
  return `<div class="table-wrap"><table><thead><tr><th>FY</th><th>Themes</th><th>Abstract deadline</th><th>Paper deadline</th><th>Status</th><th></th></tr></thead><tbody>${state.calls.length ? state.calls.map((call) => `<tr><td><strong>${escapeHtml(call.fiscal_year)}</strong></td><td>${(call.themes || []).map((theme) => escapeHtml(theme.name)).join(", ")}</td><td>${formatDate(call.abstract_deadline)}</td><td>${formatDate(call.paper_deadline)}</td><td><span class="badge status-${escapeAttribute(call.status)}">${humanize(call.status)}</span></td><td><div class="row-actions">${call.status === "draft" ? `<button class="button secondary compact" data-publish-call="${call.id}" type="button">Publish</button>` : ""}${call.status === "published" ? `<button class="button secondary compact" data-edit-call="${call.id}" type="button">Edit deadline</button><button class="button danger-outline compact" data-close-call="${call.id}" type="button">Close</button>` : ""}</div></td></tr>`).join("") : `<tr><td colspan="6">No calls have been created.</td></tr>`}</tbody></table></div>`;
}

function renderOfficerQueues() {
  const comments = state.assignments.flatMap((assignment) => (assignment.comments || []).map((comment) => ({ ...comment, assignment })));
  const pendingComments = comments.filter((item) => item.verification_status === "pending");
  const commentList = pendingComments.length ? pendingComments.map((comment) => `
    <article class="card">
      <h3>Comment #${comment.id} for submission #${comment.assignment.submission_id}</h3>
      <p class="muted">${escapeHtml(comment.comments)}</p>
      <div class="item-actions">
        <button class="button gold" data-verify-comment="${comment.id}" data-approved="true" type="button">Approve comments</button>
        <button class="button secondary" data-verify-comment="${comment.id}" data-approved="false" type="button">Return to reviewer</button>
      </div>
    </article>
  `).join("") : `<div class="empty">No reviewer comments pending verification.</div>`;

  return `<div class="list">${commentList}</div>`;
}

function renderFinalDecisionList() {
  const eligible = state.submissions.filter((item) => ["editorial_board", "approved_for_publishing"].includes(item.current_stage) || ["editorial_board", "approved_for_publishing"].includes(item.status));
  if (!eligible.length) return `<div class="empty">No submissions ready for final decision.</div>`;
  return `<div class="list">${eligible.map((item) => `
    <article class="card">
      <div class="item-head">
        <div>
          <h3>#${item.id} ${escapeHtml(item.title)}</h3>
          <p class="muted">${escapeHtml(item.current_stage)}</p>
        </div>
        <span class="badge">${escapeHtml(item.status)}</span>
      </div>
      <div class="item-actions">
        <button class="button gold" data-final="${item.id}" data-decision="published" type="button">Approve & publish</button>
        <button class="button danger" data-final="${item.id}" data-decision="declined" type="button">Decline</button>
      </div>
    </article>
  `).join("")}</div>`;
}

function renderUsersTable() {
  if (!state.users.length) return `<div class="empty">No users found.</div>`;
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Roles</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${state.users.map((user) => `
            <tr>
              <td>${user.id}</td>
              <td>${escapeHtml(user.name)}</td>
              <td>${escapeHtml(user.email)}</td>
              <td>${user.roles.map((role) => `<span class="badge">${role}</span>`).join(" ")}</td>
              <td>${user.is_active ? "Active" : "Inactive"}</td>
              <td class="item-actions">
                <button class="button secondary" data-edit-user="${user.id}" type="button">Edit roles</button>
                <button class="button secondary" data-reset-user="${user.id}" type="button">Reset password</button>
                <button class="button ${user.is_active ? "danger" : "gold"}" data-toggle-user="${user.id}" data-active="${user.is_active}" type="button">${user.is_active ? "Deactivate" : "Activate"}</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDepartmentsTable() {
  if (!state.departments.length) return `<div class="empty">No departments found.</div>`;
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Department name</th><th>Actions</th></tr></thead>
        <tbody>
          ${state.departments.map((department) => `
            <tr>
              <td>${department.id}</td>
              <td>${escapeHtml(department.name)}</td>
              <td class="item-actions"><button class="button secondary" data-edit-department="${department.id}" type="button">Edit</button><button class="button danger" data-disable-department="${department.id}" type="button">Deactivate</button></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderThemesTable() {
  if (!state.themes.length) return `<div class="empty">No research themes configured.</div>`;
  return `<div class="table-wrap"><table><thead><tr><th>Theme</th><th>Status</th><th>Actions</th></tr></thead><tbody>${state.themes.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td><span class="badge ${item.is_active ? "success" : "danger-badge"}">${item.is_active ? "Active" : "Inactive"}</span></td><td class="item-actions"><button class="button secondary" data-edit-theme="${item.id}" type="button">Edit</button><button class="button ${item.is_active ? "danger" : "gold"}" data-toggle-theme="${item.id}" data-active="${item.is_active}" type="button">${item.is_active ? "Deactivate" : "Activate"}</button></td></tr>`).join("")}</tbody></table></div>`;
}

function renderTemplatesList() {
  if (!state.templates.length) return `<div class="empty">No templates or notices configured.</div>`;
  return `<div class="list">${state.templates.map((item) => `<article class="card"><div class="item-head"><div><h3>${escapeHtml(item.name)}</h3><p class="muted">${humanize(item.template_type)} · Version ${item.version}</p></div><span class="badge">v${item.version}</span></div>${item.subject ? `<strong>${escapeHtml(item.subject)}</strong>` : ""}${item.body ? `<p>${escapeHtml(item.body)}</p>` : ""}<div class="item-actions">${item.file_path ? `<a class="button secondary" href="${API.masterdata}${item.file_path}" target="_blank" rel="noopener">Download</a>` : ""}<button class="button danger" data-delete-template="${item.id}" type="button">Deactivate</button></div></article>`).join("")}</div>`;
}

function renderAuditTable() {
  if (!state.auditLogs.length) return `<div class="empty">No audited activity yet.</div>`;
  return `<div class="table-wrap"><table><thead><tr><th>User</th><th>Action</th><th>Timestamp</th><th>Outcome</th></tr></thead><tbody>${state.auditLogs.map((item) => `<tr><td>${escapeHtml(item.user || item.email)}</td><td>${escapeHtml(item.action)}${item.details ? `<div class="hint">${escapeHtml(item.details)}</div>` : ""}</td><td>${formatDate(item.created_at)}</td><td><span class="badge ${item.outcome === "success" ? "success" : "danger-badge"}">${humanize(item.outcome)}</span></td></tr>`).join("")}</tbody></table></div>`;
}

function reviewerOptions() {
  return state.users
    .filter((user) => user.roles.includes("InternalReviewer") || user.roles.includes("ExternalReviewer"))
    .map((user) => `<option value="${user.id}" data-roles="${escapeAttribute(user.roles.join(","))}" data-email="${escapeAttribute(user.email)}">${escapeHtml(user.name)} — ${user.roles.map(humanize).join(", ")}</option>`)
    .join("");
}

function bindCurrentView() {
  bindAuthorView();
  bindOfficerView();
  bindEditorialView();
  bindReviewerView();
  bindAdminView();
  bindNotificationsView();
  bindStatusButtons();
  bindStandaloneSubmissionActions();
  bindEnhancements();
}

function bindStandaloneSubmissionActions() {
  if (document.getElementById("submission-form")) return;
  document.querySelectorAll(".upload-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await request("submission", `/api/submissions/${form.dataset.submissionId}/documents`, { method: "POST", body: new FormData(form), headers: {} });
      showToast("Document uploaded successfully.");
      await hydrate();
    });
  });
  document.querySelectorAll("[data-delete-submission]").forEach((button) => button.addEventListener("click", async () => {
    if (!confirm("Delete this submission? This cannot be undone.")) return;
    await request("submission", `/api/submissions/${button.dataset.deleteSubmission}`, { method: "DELETE" });
    showToast("Submission deleted.");
    await hydrate();
  }));
  document.querySelectorAll("[data-edit-submission]").forEach((button) => button.addEventListener("click", async () => {
    const submission = state.submissions.find((item) => String(item.id) === button.dataset.editSubmission);
    const title = prompt("Update submission title", submission?.title || "");
    if (!title) return;
    await request("submission", `/api/submissions/${button.dataset.editSubmission}`, { method: "PUT", body: JSON.stringify({ title }) });
    showToast("Submission updated.");
    await hydrate();
  }));
}

function bindEnhancements() {
  const dialog = document.getElementById("detail-dialog");
  dialog?.querySelector(".dialog-close")?.addEventListener("click", () => dialog.close());
  document.querySelectorAll("[data-view-submission]").forEach((button) => button.addEventListener("click", async () => {
    try {
      const item = await request("submission", `/api/submissions/${button.dataset.viewSubmission}`);
      document.getElementById("dialog-content").innerHTML = `<span class="eyebrow">Submission #${item.id}</span><h2>${escapeHtml(item.title)}</h2><p><span class="badge">${humanize(item.status)}</span> <span class="badge">${escapeHtml(item.theme_name)}</span></p>${item.decision_reason ? `<div class="message show"><strong>Decision note</strong><br>${escapeHtml(item.decision_reason)}</div>` : ""}<h3>Authors</h3><div class="list">${(item.authors || []).map((author) => `<div class="detail-row"><strong>${escapeHtml(author.name)}${author.is_corresponding ? " (Corresponding)" : ""}</strong><span>${escapeHtml(author.email)} · ${author.is_bou_staff ? "BOU staff" : escapeHtml(author.institution)}</span></div>`).join("")}</div><h3>Documents</h3><div class="list">${(item.documents || []).map((document) => `<div class="detail-row"><span>${humanize(document.type)} · Version ${document.version_number} · ${formatDate(document.uploaded_at)}</span><a class="button secondary" href="${API.submission}${document.file_path}" target="_blank" rel="noopener">Download</a></div>`).join("") || `<div class="empty">No documents uploaded.</div>`}</div>${renderTracking(item.tracking_steps || [])}`;
      dialog.showModal();
    } catch (error) {
      showToast(error.message);
    }
  }));
  const themeForm = document.getElementById("theme-form");
  if (themeForm) themeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(themeForm);
    await request("masterdata", "/api/themes", { method: "POST", body: JSON.stringify({ name: data.get("name") }) });
    showToast("Research theme added.");
    state.view = "admin-themes";
    localStorage.setItem("bou_view", state.view);
    await hydrate();
  });
  document.querySelectorAll("[data-edit-theme]").forEach((button) => button.addEventListener("click", async () => {
    const item = state.themes.find((theme) => String(theme.id) === button.dataset.editTheme);
    const name = prompt("Research theme name", item?.name || "");
    if (!name) return;
    await request("masterdata", `/api/themes/${button.dataset.editTheme}`, { method: "PUT", body: JSON.stringify({ name }) });
    await hydrate();
  }));
  document.querySelectorAll("[data-toggle-theme]").forEach((button) => button.addEventListener("click", async () => {
    await request("masterdata", `/api/themes/${button.dataset.toggleTheme}`, { method: "PUT", body: JSON.stringify({ is_active: button.dataset.active !== "true" }) });
    showToast("Theme status updated.");
    await hydrate();
  }));
  document.querySelectorAll(".template-form").forEach((templateForm) => templateForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await request("masterdata", "/api/templates", { method: "POST", body: new FormData(templateForm), headers: {} });
    showToast("Template saved.");
    state.view = "admin-templates";
    localStorage.setItem("bou_view", state.view);
    await hydrate();
  }));
  document.querySelectorAll("[data-edit-template]").forEach((button) => button.addEventListener("click", async () => {
    const item = state.templates.find((template) => String(template.id) === button.dataset.editTemplate);
    const body = prompt(`Edit notice — ${item?.name || "Notification"}`, item?.body || "");
    if (body === null) return;
    await request("masterdata", `/api/templates/${button.dataset.editTemplate}`, { method: "PUT", body: JSON.stringify({ body }) });
    showToast("Notice updated.");
    await hydrate();
  }));
  document.querySelectorAll("[data-delete-template]").forEach((button) => button.addEventListener("click", async () => {
    if (!confirm("Deactivate this template?")) return;
    await request("masterdata", `/api/templates/${button.dataset.deleteTemplate}`, { method: "DELETE" });
    showToast("Template deactivated.");
    await hydrate();
  }));
  document.querySelectorAll("[data-export]").forEach((button) => button.addEventListener("click", () => exportCsv(button.dataset.export)));
  document.getElementById("print-report")?.addEventListener("click", () => window.print());
  document.querySelectorAll("[data-tab-target]").forEach((button) => button.addEventListener("click", () => {
    const container = button.closest(".panel");
    container.querySelectorAll("[data-tab-target]").forEach((tab) => tab.classList.toggle("active", tab === button));
    container.querySelectorAll("[data-tab-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.tabPanel !== button.dataset.tabTarget));
  }));
}

function bindAuthorView() {
  const callSelect = document.getElementById("call-select");
  const themeSelect = document.getElementById("theme-select");
  const authorsBox = document.getElementById("authors-box");
  if (!callSelect || !themeSelect || !authorsBox) return;

  function updateThemes() {
    const call = state.calls.find((item) => String(item.id) === callSelect.value);
    const themes = call ? call.themes || [] : [];
    themeSelect.innerHTML = `<option value="">Select theme</option>${themes.map((theme) => `<option value="${theme.id}">${escapeHtml(theme.name)}</option>`).join("")}`;
  }

  function addAuthorRow(author = {}) {
    const row = document.createElement("div");
    const isCorresponding = authorsBox.children.length === 0;
    row.className = "author-row";
    row.innerHTML = `
      <div class="form-row"><label>Name</label><input name="author_name" required value="${escapeAttribute(author.name || state.user.name || "")}"></div>
      <div class="form-row"><label>Email</label><input name="author_email" type="email" required value="${escapeAttribute(author.email || state.user.email || "")}"></div>
      <div class="form-row"><label>BOU staff?</label><select name="is_bou_staff"><option value="true">Yes</option><option value="false" ${author.name === "" ? "selected" : ""}>No</option></select></div>
      <div class="form-row affiliation-field"><label>Department / Institution</label><select name="department_id"><option value="">Select department</option>${state.departments.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}</select><input name="institution" class="hidden" placeholder="External institution"></div>
      <button class="button secondary" type="button" data-remove-author ${isCorresponding ? "disabled title=\"Corresponding author cannot be removed\"" : ""}>${isCorresponding ? "Primary" : "Remove"}</button>
    `;
    const staffSelect = row.querySelector('[name="is_bou_staff"]');
    const departmentSelect = row.querySelector('[name="department_id"]');
    const institutionInput = row.querySelector('[name="institution"]');
    const toggleAffiliation = () => {
      const isStaff = staffSelect.value === "true";
      departmentSelect.classList.toggle("hidden", !isStaff);
      institutionInput.classList.toggle("hidden", isStaff);
      departmentSelect.required = isStaff;
      institutionInput.required = !isStaff;
    };
    staffSelect.addEventListener("change", toggleAffiliation);
    toggleAffiliation();
    row.querySelector("[data-remove-author]").addEventListener("click", () => row.remove());
    authorsBox.appendChild(row);
  }

  callSelect.addEventListener("change", updateThemes);
  document.getElementById("add-author-btn").addEventListener("click", () => addAuthorRow({ name: "", email: "" }));
  addAuthorRow();

  document.getElementById("submission-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const rows = [...authorsBox.querySelectorAll(".author-row")];
    const authors = rows.map((row, index) => ({
      name: row.querySelector('[name="author_name"]').value,
      email: row.querySelector('[name="author_email"]').value,
      is_bou_staff: row.querySelector('[name="is_bou_staff"]').value === "true",
      department_id: Number(row.querySelector('[name="department_id"]').value) || null,
      institution: row.querySelector('[name="institution"]').value,
      is_corresponding: index === 0
    }));
    await request("submission", "/api/submissions", {
      method: "POST",
      body: JSON.stringify({
        call_id: Number(form.get("call_id")),
        theme_id: Number(form.get("theme_id")),
        title: form.get("title"),
        authors
      })
    });
    showToast("Submission received and sent to Research Department.");
    await hydrate();
  });

  document.querySelectorAll(".upload-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      await request("submission", `/api/submissions/${form.dataset.submissionId}/documents`, {
        method: "POST",
        body: data,
        headers: {}
      });
      showToast("Document uploaded.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-delete-submission]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this submission?")) return;
      await request("submission", `/api/submissions/${button.dataset.deleteSubmission}`, { method: "DELETE" });
      showToast("Submission deleted.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-edit-submission]").forEach((button) => {
    button.addEventListener("click", async () => {
      const submission = state.submissions.find((item) => String(item.id) === button.dataset.editSubmission);
      const title = prompt("Update submission title", submission ? submission.title : "");
      if (!title) return;
      await request("submission", `/api/submissions/${button.dataset.editSubmission}`, {
        method: "PUT",
        body: JSON.stringify({ title })
      });
      showToast("Submission updated.");
      await hydrate();
    });
  });
}

function bindOfficerView() {
  const callForm = document.getElementById("call-form");
  if (callForm) {
    callForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(callForm);
      const themes = [...new Set([...form.getAll("theme_choice"), ...(form.get("themes") || "").split("\n").map((item) => item.trim()).filter(Boolean)])];
      if (!themes.length) return showToast("Select or enter at least one research theme.");
      await request("submission", "/api/calls", {
        method: "POST",
        body: JSON.stringify({
          fiscal_year: form.get("fiscal_year"),
          description: form.get("description"),
          abstract_deadline: form.get("abstract_deadline"),
          paper_deadline: form.get("paper_deadline"),
          themes
        })
      });
      showToast("Call draft created.");
      state.view = "officer-calls";
      localStorage.setItem("bou_view", state.view);
      await hydrate();
    });
  }

  document.querySelectorAll("[data-publish-call]").forEach((button) => {
    button.addEventListener("click", async () => {
      await request("submission", `/api/calls/${button.dataset.publishCall}/publish`, { method: "PUT" });
      showToast("Call published.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-close-call]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Close this call for papers?")) return;
      await request("submission", `/api/calls/${button.dataset.closeCall}`, { method: "PUT", body: JSON.stringify({ status: "closed" }) });
      showToast("Call closed.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-edit-call]").forEach((button) => {
    button.addEventListener("click", async () => {
      const call = state.calls.find((item) => String(item.id) === button.dataset.editCall);
      const abstractDeadline = prompt("New abstract deadline (YYYY-MM-DDTHH:MM)", call.abstract_deadline.slice(0, 16));
      if (!abstractDeadline) return;
      const paperDeadline = prompt("New paper deadline (YYYY-MM-DDTHH:MM)", call.paper_deadline.slice(0, 16));
      if (!paperDeadline) return;
      await request("submission", `/api/calls/${call.id}`, { method: "PUT", body: JSON.stringify({ abstract_deadline: abstractDeadline, paper_deadline: paperDeadline }) });
      showToast("Call deadlines updated.");
      await hydrate();
    });
  });

  const assignmentForm = document.getElementById("assignment-form");
  if (assignmentForm) {
    const reviewerType = assignmentForm.querySelector('[name="reviewer_type"]');
    const reviewerSelect = assignmentForm.querySelector('[name="reviewer_id"]');
    const submissionSelect = assignmentForm.querySelector('[name="submission_id"]');
    const coiResult = document.getElementById("coi-result");
    const refreshReviewerChoices = () => {
      const requiredRole = reviewerType.value === "internal" ? "InternalReviewer" : "ExternalReviewer";
      [...reviewerSelect.options].forEach((option) => {
        if (!option.value) return;
        option.hidden = !(option.dataset.roles || "").split(",").includes(requiredRole);
        if (option.selected && option.hidden) reviewerSelect.value = "";
      });
      const submission = state.submissions.find((item) => String(item.id) === submissionSelect.value);
      const email = reviewerSelect.selectedOptions[0]?.dataset.email?.toLowerCase();
      const conflict = email && submission && [submission.corresponding_author?.email, ...(submission.author_emails || [])].filter(Boolean).map((value) => value.toLowerCase()).includes(email);
      if (coiResult) {
        coiResult.textContent = conflict ? "Conflict of interest: this reviewer is listed as an author or co-author." : email && submission ? "No author-email conflict detected." : "";
        coiResult.className = `message ${email && submission ? "show" : ""} ${conflict ? "error-message" : "success-message"}`;
      }
      assignmentForm.querySelector('button[type="submit"]').disabled = Boolean(conflict);
    };
    reviewerType.addEventListener("change", refreshReviewerChoices);
    reviewerSelect.addEventListener("change", refreshReviewerChoices);
    submissionSelect.addEventListener("change", refreshReviewerChoices);
    refreshReviewerChoices();
    assignmentForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(assignmentForm);
      await request("review", "/api/review-assignments", {
        method: "POST",
        body: JSON.stringify({
          submission_id: Number(form.get("submission_id")),
          reviewer_id: Number(form.get("reviewer_id")),
          reviewer_type: form.get("reviewer_type")
        })
      });
      showToast("Assignment sent to Editorial Board for verification.");
      state.view = "officer-assign";
      localStorage.setItem("bou_view", state.view);
      await hydrate();
    });
  }

  document.querySelectorAll("[data-verify-comment]").forEach((button) => {
    button.addEventListener("click", async () => {
      const approved = button.dataset.approved === "true";
      const reason = approved ? "Comments approved by Research Officer." : prompt("Reason for returning comments") || "Please revise comments.";
      await request("review", `/api/review-comments/${button.dataset.verifyComment}/verify`, {
        method: "PUT",
        body: JSON.stringify({ approved, reason })
      });
      showToast("Comment verification recorded.");
      await hydrate();
    });
  });
}

function bindEditorialView() {
  document.querySelectorAll("[data-verify-assignment]").forEach((button) => {
    button.addEventListener("click", async () => {
      const approved = button.dataset.approved === "true";
      const reason = approved ? "Reviewer assignment approved." : prompt("Reason for returning assignment") || "Assignment returned to Research Officer.";
      await request("review", `/api/review-assignments/${button.dataset.verifyAssignment}/verify`, {
        method: "PUT",
        body: JSON.stringify({ approved, reason })
      });
      showToast("Reviewer assignment verification recorded.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-final]").forEach((button) => {
    button.addEventListener("click", async () => {
      const approved = button.dataset.decision === "published";
      const reason = prompt(approved ? "Decision note (optional)" : "Reason for declining (required)", "");
      if (!approved && !reason) return showToast("A decline reason is required.");
      const publicationReference = approved ? prompt("Publication reference", `BOU-WP-${new Date().getFullYear()}-${String(button.dataset.final).padStart(3, "0")}`) : "";
      if (approved && !publicationReference) return showToast("A publication reference is required.");
      await request("submission", `/api/submissions/${button.dataset.final}/status`, {
        method: "PUT",
        body: JSON.stringify({
          status: button.dataset.decision,
          current_stage: approved ? "published" : "editorial_board",
          reason,
          publication_reference: publicationReference,
          title: approved ? "Submission approved" : "Submission declined",
          message: approved ? "Your paper has been approved for publishing." : "Your paper has been declined after final review."
        })
      });
      showToast("Final decision sent to author.");
      await hydrate();
    });
  });
}

function bindReviewerView() {
  document.querySelectorAll(".review-comment-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      await request("review", `/api/review-assignments/${form.dataset.assignmentId}/comments`, {
        method: "POST",
        body: JSON.stringify({
          recommendation: data.get("recommendation"),
          comments: data.get("comments")
        })
      });
      showToast("Review comments submitted to Research Officer.");
      await hydrate();
    });
  });
}

function bindAdminView() {
  const userForm = document.getElementById("user-form");
  if (userForm) {
    userForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = userForm.querySelector("#user-form-message");
      const submitButton = userForm.querySelector('button[type="submit"]');
      const form = new FormData(userForm);
      const selectedRoles = [...userForm.querySelectorAll('[name="roles"]:checked')].map((input) => input.value);
      message.textContent = "";
      message.classList.remove("show");
      submitButton.disabled = true;
      try {
        await request("identity", "/api/users", {
          method: "POST",
          body: JSON.stringify({
            name: form.get("name"),
            email: form.get("email"),
            password: form.get("password"),
            roles: selectedRoles.length ? selectedRoles : ["Author"]
          })
        });
        showToast("User account created.");
        state.view = "admin-users";
        localStorage.setItem("bou_view", state.view);
        await hydrate();
      } catch (error) {
        message.textContent = error.message;
        message.classList.add("show");
      } finally {
        submitButton.disabled = false;
      }
    });
  }

  bindMasterForm("department-form", "departments", "Department added.");

  document.querySelectorAll("[data-edit-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const user = state.users.find((item) => String(item.id) === button.dataset.editUser);
      const value = prompt(`Roles for ${user.name} (comma separated)`, user.roles.join(", "));
      if (!value) return;
      const selected = value.split(",").map((role) => role.trim()).filter((role) => roles.includes(role));
      await request("identity", `/api/users/${user.id}`, { method: "PUT", body: JSON.stringify({ roles: selected }) });
      showToast("User roles updated.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-reset-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const password = prompt("Enter a new temporary password (minimum 8 characters)");
      if (!password) return;
      if (password.length < 8) return showToast("Password must be at least 8 characters.");
      await request("identity", `/api/users/${button.dataset.resetUser}`, { method: "PUT", body: JSON.stringify({ password }) });
      showToast("Temporary password set.");
    });
  });

  document.querySelectorAll("[data-toggle-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const isActive = button.dataset.active === "true";
      if (isActive && !confirm("Deactivate this account?")) return;
      await request("identity", `/api/users/${button.dataset.toggleUser}`, { method: "PUT", body: JSON.stringify({ is_active: !isActive }) });
      showToast(isActive ? "Account deactivated." : "Account activated.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-edit-department]").forEach((button) => {
    button.addEventListener("click", async () => {
      const department = state.departments.find((item) => String(item.id) === button.dataset.editDepartment);
      const name = prompt("Department name", department.name);
      if (!name) return;
      await request("masterdata", `/api/departments/${department.id}`, { method: "PUT", body: JSON.stringify({ name }) });
      showToast("Department updated.");
      await hydrate();
    });
  });

  document.querySelectorAll("[data-disable-department]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Deactivate this department?")) return;
      await request("masterdata", `/api/departments/${button.dataset.disableDepartment}`, { method: "PUT", body: JSON.stringify({ is_active: false }) });
      showToast("Department deactivated.");
      await hydrate();
    });
  });
}

function bindMasterForm(formId, path, successMessage) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    await request("masterdata", `/api/${path}`, {
      method: "POST",
      body: JSON.stringify({ name: data.get("name") })
    });
    showToast(successMessage);
    if (path === "departments") {
      state.view = "admin-departments";
      localStorage.setItem("bou_view", state.view);
    }
    await hydrate();
  });
}

function bindNotificationsView() {
  const markAll = document.getElementById("mark-all-read");
  if (markAll) {
    markAll.addEventListener("click", async () => {
      await request("notification", `/notifications/user/${state.user.id}/read-all`, { method: "PUT" });
      showToast("All notifications marked as read.");
      await hydrate();
    });
  }

  document.querySelectorAll("[data-read]").forEach((button) => {
    button.addEventListener("click", async () => {
      await request("notification", `/notifications/${button.dataset.read}/read`, { method: "PUT" });
      await hydrate();
    });
  });

  document.querySelectorAll("[data-delete-notification]").forEach((button) => {
    button.addEventListener("click", async () => {
      await request("notification", `/notifications/${button.dataset.deleteNotification}`, { method: "DELETE" });
      await hydrate();
    });
  });
}

function bindStatusButtons() {
  document.querySelectorAll("[data-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      const message = button.dataset.label;
      await request("submission", `/api/submissions/${button.dataset.status}/status`, {
        method: "PUT",
        body: JSON.stringify({
          status: button.dataset.stage,
          current_stage: button.dataset.stage,
          title: "Submission status updated",
          message
        })
      });
      showToast("Submission status updated.");
      await hydrate();
    });
  });
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function humanize(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function exportCsv(kind) {
  const source = kind === "audit" ? state.auditLogs : state.submissions;
  const rows = kind === "audit"
    ? [["Date", "User", "Email", "Action", "Entity Type", "Entity ID", "Outcome", "Details"], ...source.map((item) => [item.created_at, item.user, item.email, item.action, item.entity_type, item.entity_id, item.outcome, item.details])]
    : [["ID", "Title", "Theme", "Fiscal Year", "Status", "Stage", "Created"], ...source.map((item) => [item.id, item.title, item.theme_name, item.call?.fiscal_year, item.status, item.current_stage, item.created_at])];
  const csv = rows.map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  link.download = `bou-pms-${kind}-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

hydrate();
/*
 * Dependency-free single-page client for the BOU Publication Management System.
 * Authorization is always enforced by Django; role checks here only shape the UI.
 * The session token lives in an HTTP-only cookie and is never available to JS.
 */
