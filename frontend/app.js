const API = {
  identity: "http://127.0.0.1:5001",
  submission: "http://127.0.0.1:5002",
  review: "http://127.0.0.1:5003",
  masterdata: "http://127.0.0.1:5004",
  notification: "http://127.0.0.1:5005"
};

const state = {
  token: localStorage.getItem("bou_token"),
  user: JSON.parse(localStorage.getItem("bou_user") || "null"),
  view: localStorage.getItem("bou_view") || "dashboard",
  calls: [],
  submissions: [],
  assignments: [],
  notifications: [],
  departments: [],
  users: []
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
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(`${API[service]}${path}`, {
    ...options,
    headers
  });

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
  state.token = loginData.token;
  state.user = {
    id: loginData.user_id,
    roles: loginData.roles,
    email: loginData.email || ""
  };
  localStorage.setItem("bou_token", state.token);
  localStorage.setItem("bou_user", JSON.stringify(state.user));
}

function clearSession() {
  localStorage.removeItem("bou_token");
  localStorage.removeItem("bou_user");
  localStorage.removeItem("bou_view");
  state.token = null;
  state.user = null;
  state.view = "dashboard";
  render();
}

async function hydrate() {
  if (!state.token) {
    renderLogin();
    return;
  }

  try {
    const me = await request("identity", "/api/auth/me");
    state.user = me;
    localStorage.setItem("bou_user", JSON.stringify(me));
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
  ];

  if (hasAnyRole(["Admin", "ResearchOfficer", "EditorialBoard", "InternalReviewer", "ExternalReviewer"])) {
    tasks.push(request("review", "/api/review-assignments").then((data) => (state.assignments = data)).catch(() => (state.assignments = [])));
  }
  if (hasAnyRole(["Admin", "ResearchOfficer", "EditorialBoard"])) {
    tasks.push(request("identity", "/api/users").then((data) => (state.users = data)).catch(() => (state.users = [])));
  }

  await Promise.all(tasks);
}

function render() {
  if (!state.token) {
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
            <h1>Publication Management System</h1>
            <p>Research submissions, reviewer assignments, decisions, and notifications in one controlled workflow.</p>
          </div>
          <div class="brand-strip">
            <span>Research Department</span>
            <span>Role based access</span>
            <span>No public signup</span>
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
          <p class="muted" style="margin-top:18px;font-size:13px;">Local dev admin: admin@bou.or.ug / Admin123!</p>
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
}

function navItems() {
  const items = [{ id: "dashboard", label: "Dashboard" }];
  if (hasRole("Author")) items.push({ id: "author", label: "Author Workspace" });
  if (hasRole("ResearchOfficer")) items.push({ id: "officer", label: "Research Officer" });
  if (hasRole("EditorialBoard")) items.push({ id: "editorial", label: "Editorial Board" });
  if (hasAnyRole(["InternalReviewer", "ExternalReviewer"])) items.push({ id: "reviewer", label: "Reviewer Workspace" });
  if (hasRole("Admin")) items.push({ id: "admin", label: "Admin" });
  items.push({ id: "notifications", label: `Notifications (${state.notifications.filter((item) => !item.is_read).length})` });
  return items;
}

function renderShell() {
  const nav = navItems();
  if (!nav.find((item) => item.id === state.view)) {
    state.view = "dashboard";
  }

  document.getElementById("app").innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="side-brand">
          ${logoMarkup()}
          <div>
            <strong>Publication<br>Management</strong>
            <small>Research Department</small>
          </div>
        </div>
        <nav class="nav">
          ${nav.map((item) => `<button data-view="${item.id}" class="${state.view === item.id ? "active" : ""}">${item.label}</button>`).join("")}
        </nav>
        <button class="button gold" id="refresh-btn" type="button">Refresh data</button>
      </aside>
      <main class="main">
        <div class="topbar">
          <div>
            <span class="eyebrow">BOU PMS</span>
            <h2 style="margin:6px 0 0;">${pageTitle()}</h2>
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
    </div>
  `;

  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      localStorage.setItem("bou_view", state.view);
      renderShell();
    });
  });
  document.getElementById("logout-btn").addEventListener("click", clearSession);
  document.getElementById("refresh-btn").addEventListener("click", hydrate);
  bindCurrentView();
}

function pageTitle() {
  const map = {
    dashboard: "Dashboard",
    author: "Author Workspace",
    officer: "Research Officer Workspace",
    editorial: "Editorial Board Workspace",
    reviewer: "Reviewer Workspace",
    admin: "System Admin",
    notifications: "Notifications"
  };
  return map[state.view] || "Dashboard";
}

function renderCurrentView() {
  if (state.view === "author") return renderAuthorView();
  if (state.view === "officer") return renderOfficerView();
  if (state.view === "editorial") return renderEditorialView();
  if (state.view === "reviewer") return renderReviewerView();
  if (state.view === "admin") return renderAdminView();
  if (state.view === "notifications") return renderNotificationsView();
  return renderDashboard();
}

function renderDashboard() {
  const publishedCalls = state.calls.filter((call) => call.status === "published").length;
  const unread = state.notifications.filter((item) => !item.is_read).length;
  const pendingAssignments = state.assignments.filter((item) => item.status !== "verified").length;
  return `
    <section class="grid three">
      ${metricCard("Active calls", publishedCalls, "Open calls authors can submit to")}
      ${metricCard("Submissions", state.submissions.length, "Visible to your role")}
      ${metricCard("Unread alerts", unread, "Notifications requiring attention")}
    </section>
    <section class="grid two" style="margin-top:16px;">
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
          <div class="panel" style="padding:12px;">
            <strong>Authors</strong>
            <p class="muted" style="margin-top:5px;">First row should be the corresponding author.</p>
            <div id="authors-box" class="grid" style="margin-top:12px;"></div>
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
    <section class="grid two" style="margin-top:16px;">
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
            <input name="password" required placeholder="Password123!">
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
    <section class="grid two" style="margin-top:16px;">
      <div class="panel">
        <div class="section-title"><div><span class="eyebrow">Master data</span><h2>Departments</h2></div></div>
        <form id="department-form" class="form-grid">
          <div class="form-row"><label>Department name</label><input name="name" required></div>
          <button class="button secondary" type="submit">Add department</button>
        </form>
        <div style="margin-top:16px;">
          ${renderDepartmentsTable()}
        </div>
      </div>
      <div class="panel">
        <div class="section-title"><div><span class="eyebrow">Research setup</span><h2>Theme ownership</h2></div></div>
        <p class="muted">
          Themes are added by the Research Officer while creating a call for papers.
          This keeps themes tied to the correct call and avoids Admin creating research workflow content.
        </p>
        <div class="empty" style="margin-top:14px;">Use Research Officer &gt; Create call for papers to add call themes.</div>
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
      <div class="list">
        ${state.notifications.length ? state.notifications.map(renderNotificationCard).join("") : `<div class="empty">No notifications yet.</div>`}
      </div>
    </section>
  `;
}

function renderNotificationCard(item) {
  return `
    <div class="card">
      <div class="item-head">
        <div>
          <h3>${escapeHtml(item.title)}</h3>
          <p class="muted">${escapeHtml(item.message)}</p>
          <small class="muted">${item.created_at || ""}</small>
        </div>
        <span class="badge">${item.is_read ? "Read" : "Unread"}</span>
      </div>
      <div class="item-actions">
        <button class="button secondary" data-read="${item.id}" type="button">Mark read</button>
        <button class="button danger" data-delete-notification="${item.id}" type="button">Delete</button>
      </div>
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
  return `<div class="tracking">${steps.map((step) => `<div class="step ${step.state}">${escapeHtml(step.label)}</div>`).join("")}</div>`;
}

function renderAssignmentList(assignments, reviewerMode = false, editorialMode = false) {
  if (!assignments.length) return `<div class="empty">No assignments found.</div>`;
  return `<div class="list">${assignments.map((item) => renderAssignmentCard(item, reviewerMode, editorialMode)).join("")}</div>`;
}

function renderAssignmentCard(item, reviewerMode = false, editorialMode = false) {
  const comments = item.comments || [];
  return `
    <article class="card">
      <div class="item-head">
        <div>
          <h3>Submission #${item.submission_id}</h3>
          <p class="muted">${item.reviewer_type} reviewer ID ${item.reviewer_id}</p>
        </div>
        <span class="badge">${item.status}</span>
      </div>
      ${comments.map((comment) => `<p class="muted"><strong>${comment.recommendation}:</strong> ${escapeHtml(comment.comments)} (${comment.verification_status})</p>`).join("")}
      ${editorialMode ? `
        <div class="item-actions">
          <button class="button gold" data-verify-assignment="${item.id}" data-approved="true" type="button">Approve assignment</button>
          <button class="button secondary" data-verify-assignment="${item.id}" data-approved="false" type="button">Return to officer</button>
        </div>
      ` : ""}
      ${reviewerMode && item.status === "verified" ? `
        <form class="form-grid review-comment-form" data-assignment-id="${item.id}" style="margin-top:12px;">
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
      ${call.status !== "published" ? `<button class="button gold" data-publish-call="${call.id}" type="button">Publish call</button>` : ""}
    </article>
  `).join("")}</div>`;
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
  if (!state.submissions.length) return `<div class="empty">No submissions ready for final decision.</div>`;
  return `<div class="list">${state.submissions.map((item) => `
    <article class="card">
      <div class="item-head">
        <div>
          <h3>#${item.id} ${escapeHtml(item.title)}</h3>
          <p class="muted">${escapeHtml(item.current_stage)}</p>
        </div>
        <span class="badge">${escapeHtml(item.status)}</span>
      </div>
      <div class="item-actions">
        <button class="button gold" data-final="${item.id}" data-decision="approved_for_publishing" type="button">Approve for publishing</button>
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
        <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Roles</th><th>Status</th></tr></thead>
        <tbody>
          ${state.users.map((user) => `
            <tr>
              <td>${user.id}</td>
              <td>${escapeHtml(user.name)}</td>
              <td>${escapeHtml(user.email)}</td>
              <td>${user.roles.map((role) => `<span class="badge">${role}</span>`).join(" ")}</td>
              <td>${user.is_active ? "Active" : "Inactive"}</td>
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
        <thead><tr><th>ID</th><th>Department name</th></tr></thead>
        <tbody>
          ${state.departments.map((department) => `
            <tr>
              <td>${department.id}</td>
              <td>${escapeHtml(department.name)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function reviewerOptions() {
  return state.users
    .filter((user) => user.roles.includes("InternalReviewer") || user.roles.includes("ExternalReviewer"))
    .map((user) => `<option value="${user.id}">${escapeHtml(user.name)} - ${user.roles.join(", ")}</option>`)
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
    row.className = "author-row";
    row.innerHTML = `
      <div class="form-row"><label>Name</label><input name="author_name" required value="${escapeAttribute(author.name || state.user.name || "")}"></div>
      <div class="form-row"><label>Email</label><input name="author_email" type="email" required value="${escapeAttribute(author.email || state.user.email || "")}"></div>
      <div class="form-row"><label>BOU staff?</label><select name="is_bou_staff"><option value="true">Yes</option><option value="false">No</option></select></div>
      <div class="form-row"><label>Department / Institution</label><input name="institution" placeholder="Department or institution"></div>
      <button class="button secondary" type="button" data-remove-author>Remove</button>
    `;
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
      const themes = (form.get("themes") || "").split("\n").map((item) => item.trim()).filter(Boolean);
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

  const assignmentForm = document.getElementById("assignment-form");
  if (assignmentForm) {
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
      const approved = button.dataset.decision === "approved_for_publishing";
      await request("submission", `/api/submissions/${button.dataset.final}/status`, {
        method: "PUT",
        body: JSON.stringify({
          status: button.dataset.decision,
          current_stage: "published",
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
      const form = new FormData(userForm);
      const selectedRoles = [...userForm.querySelector('[name="roles"]').selectedOptions].map((option) => option.value);
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
      await hydrate();
    });
  }

  bindMasterForm("department-form", "departments", "Department added.");
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
