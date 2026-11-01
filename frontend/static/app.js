"use strict";
const API = "/api/v1";
const STATUSES = [["todo", "To do"], ["in_progress", "In progress"], ["done", "Done"]];
const PRIORITIES = [["low", "Low"], ["medium", "Medium"], ["high", "High"]];
const NEXT_STEP = { todo: ["in_progress", "Start"], in_progress: ["done", "Mark done"], done: ["todo", "Reopen"] };
const EMPTY_COLUMN = { todo: "Nothing to do.", in_progress: "Nothing in progress.", done: "Nothing finished yet." };
const store = {
  get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { value == null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, String(value)); } catch { /* storage unavailable */ } },
};
const state = {
  token: store.get("tt.token"), me: null, projects: [], project: null, members: [],
  tasks: [], total: 0, filters: { priority: "", assignee_id: "", overdue: "", order: "desc" },
  task: null, comments: [], commentsTotal: 0, editingComment: null, editingProject: false, column: "todo",
  counts: {},
};
const $ = (id) => document.getElementById(id);
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}
function select(name, options, value, attrs = {}) {
  const el = h("select", { name, ...attrs }, options.map(([v, text]) => h("option", { value: v }, text)));
  el.value = value == null ? "" : String(value);
  return el;
}
const labelOf = (pairs, value) => (pairs.find(([v]) => v === value) || [value, value])[1];
const parseUtc = (iso) => new Date(/([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : iso + "Z");
const fmtDate = (iso) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parseUtc(iso));
const toLocalInput = (iso) => { if (!iso) return ""; const d = parseUtc(iso); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null);
const isOverdue = (t) => Boolean(t.due_at) && t.status !== "done" && parseUtc(t.due_at) < new Date();
const personName = (id) => (state.me && id === state.me.id ? "You" : `User #${id}`);
const isOwner = () => state.project && state.me && state.project.owner_id === state.me.id;

let noticeTimer = null;
function notify(message, kind = "error", action = null) {
  const el = $("notice");
  el.className = kind;
  const button = action && h("button", { type: "button", class: "link notice-action",
    onclick: guard(async () => { el.replaceChildren(); await action.run(); }) }, action.label);
  el.replaceChildren(...[message, button].filter(Boolean));
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { el.replaceChildren(); }, action ? 10000 : 6000);
}

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; this.handled = false; }
}
function describeError(response, data) {
  const detail = data && data.detail;
  if (response.status === 429) {
    const wait = response.headers.get("Retry-After");
    return `Too many attempts. Try again in ${wait || "a few"} seconds.`;
  }
  if (Array.isArray(detail)) {
    return detail.map((e) => {
      const field = (e.loc || []).filter((part) => part !== "body").join(".");
      return field ? `${field}: ${e.msg}` : e.msg;
    }).join("; ");
  }
  if (typeof detail === "string" && detail) {
    const text = detail.charAt(0).toUpperCase() + detail.slice(1);
    return /[.!?]$/.test(text) ? text : text + ".";
  }
  return `Request failed (${response.status}).`;
}
async function api(method, path, body) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let response;
  try {
    response = await fetch(API + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that it is running.");
  }
  if (response.status === 204) return null;
  let data = null;
  try { data = await response.json(); } catch { /* empty or non-JSON body */ }
  if (!response.ok) {
    const error = new ApiError(response.status, describeError(response, data));
    if (response.status === 401 && state.token && !path.startsWith("/auth/")) {
      signOut("Your session expired. Sign in again.");
      error.handled = true;
    }
    throw error;
  }
  return data;
}
function guard(fn) {
  return async (...args) => {
    try { await fn(...args); } catch (error) {
      if (error instanceof ApiError) { if (!error.handled) notify(error.message); return; }
      console.error(error);
      notify("Something went wrong. Reload the page and try again.");
    }
  };
}
function formHandler(fn) {
  return guard(async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    if (button) button.disabled = true;
    try { await fn(form, new FormData(form)); } finally { if (button) button.disabled = false; }
  });
}

/* Auth */
function showAuth() {
  $("app").hidden = true;
  $("auth").hidden = false;
  if ($("task-dialog").open) $("task-dialog").close();
}
function setAuthMode(register) {
  $("login-form").hidden = register;
  $("register-form").hidden = !register;
  $("show-login").setAttribute("aria-pressed", String(!register));
  $("show-register").setAttribute("aria-pressed", String(register));
  (register ? $("register-form") : $("login-form")).querySelector("input").focus();
}
async function signIn(email, password) {
  const token = await api("POST", "/auth/login", { email, password });
  state.token = token.access_token;
  store.set("tt.token", state.token);
  await boot();
}
function signOut(message) {
  state.token = null;
  state.me = null;
  state.project = null;
  state.projects = [];
  state.counts = {};
  $("progress").replaceChildren();
  store.set("tt.token", null);
  showAuth();
  if (message) notify(message, "info");
}
async function boot() {
  if (!state.token) { showAuth(); return; }
  try {
    state.me = await api("GET", "/users/me");
  } catch (error) {
    showAuth();
    if (!error.handled) notify(error.message);
    return;
  }
  $("auth").hidden = true;
  $("app").hidden = false;
  $("me-name").textContent = state.me.full_name;
  $("me-id").textContent = `Your ID ${state.me.id}`;
  await loadProjects(Number(store.get("tt.project")) || null);
}

/* Projects */
async function loadProjects(preferredId) {
  const page = await api("GET", "/projects?limit=100");
  state.projects = page.items;
  const next = state.projects.find((p) => p.id === preferredId) || state.projects[0] || null;
  if (next) await selectProject(next.id);
  else { state.project = null; renderProjects(); renderProjectView(); }
  guard(loadAllCounts)();
}
async function selectProject(id) {
  state.project = state.projects.find((p) => p.id === id) || null;
  state.editingProject = false;
  Object.assign(state.filters, { priority: "", assignee_id: "", overdue: "" });
  store.set("tt.project", id);
  renderProjects();
  const [members, counts] = await Promise.all([api("GET", `/projects/${id}/members?limit=100`), fetchCounts(id), loadTasks(false)]);
  state.members = members.items;
  state.membersTotal = members.total;
  state.counts[id] = counts;
  $("progress").replaceChildren();
  renderProjects();
  renderProjectView();
}

/* Progress: unfiltered task counts per status, for the rail and the sidebar */
async function fetchCounts(projectId) {
  const totals = await Promise.all(STATUSES.map(([status]) =>
    api("GET", `/projects/${projectId}/tasks?status=${status}&limit=1`).then((page) => [status, page.total])));
  return Object.fromEntries(totals);
}
async function loadAllCounts() {
  const missing = state.projects.filter((p) => !state.counts[p.id]);
  for (let i = 0; i < missing.length; i += 5) {
    const chunk = missing.slice(i, i + 5);
    const results = await Promise.all(chunk.map((p) => fetchCounts(p.id)));
    chunk.forEach((p, k) => { state.counts[p.id] = results[k]; });
    renderProjects();
  }
}
function countTotal(c) { return STATUSES.reduce((sum, [status]) => sum + c[status], 0); }
function bumpCount(from, to) {
  const c = state.project && state.counts[state.project.id];
  if (!c) return;
  if (from) c[from] = Math.max(0, c[from] - 1);
  if (to) c[to] += 1;
  renderProgress();
  renderProjects();
}
function railSegments(c, cls) {
  return h("span", { class: cls, "aria-hidden": "true" }, STATUSES.map(([status]) => {
    const seg = h("span", { class: `seg seg-${status}` });
    seg.style.flexGrow = String(c ? c[status] : 0);
    return seg;
  }));
}
function renderProgress() {
  const box = $("progress");
  const c = state.counts[state.project.id];
  if (!c) { box.replaceChildren(); return; }
  const total = countTotal(c);
  if (!box.firstChild) {
    box.append(railSegments(c, "rail"), h("div", { class: "rail-text" }, h("strong", { class: "rail-done mono" }), h("span", { class: "rail-legend" })));
  }
  const rail = box.querySelector(".rail");
  for (const [status] of STATUSES) rail.querySelector(`.seg-${status}`).style.flexGrow = String(c[status]);
  rail.classList.toggle("is-empty", total === 0);
  rail.classList.toggle("is-complete", total > 0 && c.done === total);
  box.setAttribute("role", "img");
  box.setAttribute("aria-label", total
    ? `${c.done} of ${total} tasks done: ${c.todo} to do, ${c.in_progress} in progress.`
    : "No tasks yet.");
  box.querySelector(".rail-done").textContent = total ? `${c.done}/${total} done` : "No tasks yet";
  box.querySelector(".rail-legend").replaceChildren(...STATUSES.map(([status, text]) =>
    h("span", { class: "legend-item" }, h("span", { class: `swatch seg-${status}` }), `${text} ${c[status]}`)));
}
function renderProjects() {
  const list = $("project-list");
  list.replaceChildren(...state.projects.map((p) => h("li", {},
    h("button", { type: "button", "aria-current": state.project && p.id === state.project.id ? "true" : "false",
      onclick: guard(() => selectProject(p.id)) },
      h("span", { class: "project-name" }, p.name),
      state.counts[p.id] && countTotal(state.counts[p.id]) > 0 && railSegments(state.counts[p.id], "rail mini")))));
  if (!state.projects.length) list.append(h("li", { class: "muted" }, "No projects yet."));
}
function renderProjectView() {
  $("no-project").hidden = Boolean(state.project);
  $("project-view").hidden = !state.project;
  if (!state.project) return;
  renderProjectHead();
  renderProgress();
  renderMembers();
  renderFilters();
  renderBoard();
}
function renderProjectHead() {
  const p = state.project;
  const head = $("project-head");
  if (state.editingProject) {
    const form = h("form", { class: "stack", onsubmit: formHandler(async (_, data) => {
      const name = data.get("name").trim();
      const description = data.get("description").trim() ? data.get("description") : null;
      const changes = {};
      if (name !== p.name) changes.name = name;
      if (description !== p.description) changes.description = description;
      if (Object.keys(changes).length) {
        const updated = await api("PATCH", `/projects/${p.id}`, changes);
        state.projects = state.projects.map((x) => (x.id === updated.id ? updated : x));
        state.project = updated;
        renderProjects();
      }
      state.editingProject = false;
      renderProjectHead();
    }) },
      h("label", {}, "Project name", h("input", { name: "name", value: p.name, maxlength: "100", required: true })),
      h("label", {}, "Description", h("textarea", { name: "description", rows: 3, maxlength: "5000" }, p.description || "")),
      h("div", { class: "actions" },
        h("button", { class: "primary", type: "submit" }, "Save project"),
        h("button", { type: "button", onclick: () => { state.editingProject = false; renderProjectHead(); } }, "Cancel")));
    head.replaceChildren(form);
    form.querySelector("input").focus();
    return;
  }
  const owner = isOwner();
  const edit = () => { state.editingProject = true; renderProjectHead(); };
  let description = h("p", { class: "muted" }, "No description.");
  if (p.description) description = h("p", {}, p.description);
  else if (owner) description = h("p", { class: "muted" }, "No description yet. ", h("button", { type: "button", class: "link", onclick: edit }, "Add a description"));
  head.replaceChildren(
    h("div", { class: "row" },
      h("h1", {}, p.name),
      owner && h("div", { class: "actions" },
        h("button", { type: "button", onclick: edit }, "Edit name and description"),
        h("button", { type: "button", class: "danger", onclick: guard(deleteProject) }, "Delete project"))),
    description);
}
async function deleteProject() {
  const p = state.project;
  if (!confirm(`Delete "${p.name}" with all its tasks and comments? This cannot be undone.`)) return;
  await api("DELETE", `/projects/${p.id}`);
  notify(`Deleted "${p.name}".`, "info");
  await loadProjects(null);
}
$("new-project").addEventListener("submit", formHandler(async (form, data) => {
  const project = await api("POST", "/projects", { name: data.get("name") });
  form.reset();
  state.projects = [project, ...state.projects];
  await selectProject(project.id);
}));

/* Members */
function renderMembers() {
  const box = $("members");
  const owner = isOwner();
  const items = state.members.map((m) => h("li", {},
    h("span", {}, personName(m.user_id)),
    h("span", { class: "mono muted" }, `#${m.user_id}`),
    m.role === "owner" && h("span", { class: "muted" }, "Owner"),
    owner && m.role !== "owner" && h("button", { type: "button", class: "link danger",
      onclick: guard(() => removeMember(m.user_id)) }, "Remove")));
  const form = owner && h("form", { class: "inline-form", onsubmit: formHandler(async (f, data) => {
    const member = await api("POST", `/projects/${state.project.id}/members`, { user_id: Number(data.get("user_id")) });
    f.reset();
    state.members = [member, ...state.members];
    state.membersTotal += 1;
    renderMembers();
    renderFilters();
    $("members").open = true;
  }) },
    h("input", { name: "user_id", type: "number", min: 1, step: 1, required: true, placeholder: "User ID", "aria-label": "User ID to add" }),
    h("button", { type: "submit" }, "Add member"));
  box.replaceChildren(
    h("summary", {}, `Members (${state.membersTotal})`),
    h("ul", { class: "member-list" }, items),
    form || h("p", { class: "muted" }, "Only the project owner can add or remove members."),
    owner && h("p", { class: "muted hint" }, "People find their ID in the top bar after signing in."));
}
async function removeMember(userId) {
  if (!confirm(`Remove User #${userId} from this project?`)) return;
  await api("DELETE", `/projects/${state.project.id}/members/${userId}`);
  state.members = state.members.filter((m) => m.user_id !== userId);
  state.membersTotal -= 1;
  renderMembers();
  renderFilters();
}

/* Tasks */
async function loadTasks(append) {
  const f = state.filters;
  const params = new URLSearchParams({ limit: "100", offset: String(append ? state.tasks.length : 0), sort: "created_at", order: f.order });
  for (const key of ["priority", "assignee_id", "overdue"]) if (f[key]) params.set(key, f[key]);
  const page = await api("GET", `/projects/${state.project.id}/tasks?${params}`);
  state.tasks = append ? state.tasks.concat(page.items) : page.items;
  state.total = page.total;
}
function memberOptions() {
  return state.members.map((m) => [String(m.user_id), m.user_id === state.me.id ? `You (#${m.user_id})` : `User #${m.user_id}`]);
}
function renderFilters() {
  const f = state.filters;
  const onChange = (key) => guard(async (event) => { f[key] = event.target.value; await loadTasks(false); renderBoard(); });
  $("filters").replaceChildren(
    h("label", {}, "Priority", select("priority", [["", "Any"], ...PRIORITIES], f.priority, { onchange: onChange("priority") })),
    h("label", {}, "Assignee", select("assignee_id", [["", "Anyone"], ...memberOptions()], f.assignee_id, { onchange: onChange("assignee_id") })),
    h("label", {}, "Due", select("overdue", [["", "Any"], ["true", "Overdue only"], ["false", "Not overdue"]], f.overdue, { onchange: onChange("overdue") })),
    h("label", {}, "Order", select("order", [["desc", "Newest first"], ["asc", "Oldest first"]], f.order, { onchange: onChange("order") })));
  renderNewTaskAssignee();
}
function renderNewTaskAssignee() {
  const el = $("new-task-assignee");
  const options = [["", "Unassigned"], ...memberOptions()];
  const previous = el.value;
  el.replaceChildren(...options.map(([v, text]) => h("option", { value: v }, text)));
  el.value = options.some(([v]) => v === previous) ? previous : "";
}
const filtersActive = () => Boolean(state.filters.priority || state.filters.assignee_id || state.filters.overdue);
async function clearFilters() {
  Object.assign(state.filters, { priority: "", assignee_id: "", overdue: "" });
  await loadTasks(false);
  renderFilters();
  renderBoard();
}
function renderFilterStatus() {
  const box = $("filter-status");
  box.hidden = !filtersActive();
  if (box.hidden) { box.replaceChildren(); return; }
  const n = state.total;
  const text = n ? `Filters on: ${n} matching ${n === 1 ? "task" : "tasks"}. Tasks that don't match are hidden.` : "No tasks match the current filters.";
  box.replaceChildren(h("span", {}, text), h("button", { type: "button", onclick: guard(clearFilters) }, "Clear filters"));
}
function taskCard(t) {
  const overdue = isOverdue(t);
  const [nextStatus, nextLabel] = NEXT_STEP[t.status];
  return h("li", { class: `card prio-${t.priority}`, "data-id": String(t.id) },
    h("button", { type: "button", class: "card-title", onclick: guard(() => openTask(t.id)) }, t.title),
    h("p", { class: "card-meta" },
      h("span", {}, `${labelOf(PRIORITIES, t.priority)} priority`),
      t.due_at && h("span", { class: overdue ? "overdue" : "" }, overdue ? `Overdue since ${fmtDate(t.due_at)}` : `Due ${fmtDate(t.due_at)}`),
      t.assignee_id && h("span", {}, `Assigned to ${personName(t.assignee_id)}`)),
    h("button", { type: "button", class: "card-move", onclick: guard(() => moveTask(t, nextStatus)) }, nextLabel));
}
function renderBoard() {
  renderFilterStatus();
  const tabs = STATUSES.map(([status, text]) => {
    const count = state.tasks.filter((t) => t.status === status).length;
    return h("button", { type: "button", role: "tab", "aria-selected": String(state.column === status),
      onclick: () => { state.column = status; renderBoard(); } }, `${text} (${count})`);
  });
  $("col-tabs").replaceChildren(...tabs);
  $("board").replaceChildren(...STATUSES.map(([status, text]) => {
    const tasks = state.tasks.filter((t) => t.status === status);
    return h("section", { class: `column${state.column === status ? " is-active" : ""}`, "data-status": status, "aria-label": text },
      h("div", { class: "column-head" }, h("h2", {}, text), h("span", { class: "mono muted" }, String(tasks.length))),
      tasks.length ? h("ul", { class: "cards" }, tasks.map(taskCard)) : h("p", { class: "column-empty" }, EMPTY_COLUMN[status]));
  }));
  const more = $("more");
  more.replaceChildren();
  if (state.tasks.length < state.total) {
    more.append(h("button", { type: "button", onclick: guard(async () => { await loadTasks(true); renderBoard(); }) },
      `Load more tasks (${state.tasks.length} of ${state.total} shown)`));
  }
}
function cardRects() {
  const rects = new Map();
  for (const el of $("board").querySelectorAll(".card")) rects.set(el.dataset.id, el.getBoundingClientRect());
  return rects;
}
function slideCard(before, id) {
  const el = $("board").querySelector(`.card[data-id="${id}"]`);
  const from = before.get(String(id));
  if (!el || !from || reducedMotion.matches) return Boolean(el && el.offsetParent);
  const to = el.getBoundingClientRect();
  if (!to.width) return false;
  el.animate(
    [{ transform: `translate(${from.left - to.left}px, ${from.top - to.top}px)`, boxShadow: "0 8px 24px rgb(0 0 0 / 0.18)" },
      { transform: "none", boxShadow: "none" }],
    { duration: 360, easing: "cubic-bezier(.2,.7,.2,1)" });
  return true;
}
function replaceTask(updated) {
  state.tasks = state.tasks.map((t) => (t.id === updated.id ? updated : t));
}
async function moveTask(task, status) {
  const before = cardRects();
  const updated = await api("PATCH", `/tasks/${task.id}`, { status });
  replaceTask(updated);
  renderBoard();
  bumpCount(task.status, updated.status);
  if (!slideCard(before, updated.id)) notify(`"${updated.title}" moved to ${labelOf(STATUSES, status)}.`, "info");
}
$("new-task").addEventListener("submit", formHandler(async (form, data) => {
  const body = { title: data.get("title"), priority: data.get("priority") };
  const due = fromLocalInput(data.get("due_at"));
  if (due) body.due_at = due;
  if (data.get("assignee_id")) body.assignee_id = Number(data.get("assignee_id"));
  const created = await api("POST", `/projects/${state.project.id}/tasks`, body);
  bumpCount(null, created.status);
  form.reset();
  await loadTasks(false);
  state.column = "todo";
  renderBoard();
  form.querySelector("input").focus();
  const card = $("board").querySelector(`.card[data-id="${created.id}"]`);
  if (card) {
    card.classList.add("is-new");
    card.scrollIntoView({ block: "nearest", behavior: reducedMotion.matches ? "auto" : "smooth" });
    notify(`"${created.title}" added to To do.`, "info");
  } else if (filtersActive()) {
    notify(`"${created.title}" was added to To do, but your filters hide it.`, "info", { label: "Clear filters", run: clearFilters });
  } else {
    notify(`"${created.title}" added to To do. Use "Load more tasks" to see it.`, "info");
  }
}));

/* Task dialog */
async function openTask(id) {
  state.task = state.tasks.find((t) => t.id === id);
  state.editingComment = null;
  await loadComments();
  renderSheet();
  if (!$("task-dialog").open) $("task-dialog").showModal();
}
async function loadComments() {
  const page = await api("GET", `/tasks/${state.task.id}/comments?limit=100`);
  state.comments = page.items.slice().reverse();
  state.commentsTotal = page.total;
}
function closeTask() { $("task-dialog").close(); }
$("task-dialog").addEventListener("close", () => { state.task = null; });
function renderSheet() {
  const t = state.task;
  const form = h("form", { class: "stack", onsubmit: formHandler(async (_, data) => saveTask(data)) },
    h("label", {}, "Title", h("input", { name: "title", value: t.title, maxlength: "150", required: true })),
    h("label", {}, "Description", h("textarea", { name: "description", rows: 4, maxlength: "5000" }, t.description || "")),
    h("div", { class: "field-row" },
      h("label", {}, "Status", select("status", STATUSES, t.status)),
      h("label", {}, "Priority", select("priority", PRIORITIES, t.priority))),
    h("div", { class: "field-row" },
      h("label", {}, "Assignee", select("assignee_id", [["", "Unassigned"], ...memberOptions()], t.assignee_id)),
      h("label", {}, "Due", h("input", { name: "due_at", type: "datetime-local", value: toLocalInput(t.due_at) }))),
    h("p", { class: "muted note" }, `Created ${fmtDate(t.created_at)}, updated ${fmtDate(t.updated_at)}`),
    h("div", { class: "actions" },
      h("button", { class: "primary", type: "submit" }, "Save task"),
      h("button", { type: "button", class: "danger", onclick: guard(deleteTask) }, "Delete task")));
  $("sheet").replaceChildren(
    h("div", { class: "sheet-head" },
      h("h2", { id: "task-dialog-title" }, h("span", { class: "mono muted" }, `#${t.id} `), "Task"),
      h("button", { type: "button", onclick: closeTask }, "Close")),
    form,
    renderComments());
}
async function saveTask(data) {
  const t = state.task;
  const changes = {};
  const title = data.get("title").trim();
  if (title !== t.title) changes.title = title;
  const description = data.get("description").trim() ? data.get("description") : null;
  if (description !== t.description) changes.description = description;
  for (const key of ["status", "priority"]) if (data.get(key) !== t[key]) changes[key] = data.get(key);
  const assignee = data.get("assignee_id") ? Number(data.get("assignee_id")) : null;
  if (assignee !== t.assignee_id) changes.assignee_id = assignee;
  if (data.get("due_at") !== toLocalInput(t.due_at)) changes.due_at = fromLocalInput(data.get("due_at"));
  if (!Object.keys(changes).length) { notify("Nothing changed.", "info"); return; }
  const updated = await api("PATCH", `/tasks/${t.id}`, changes);
  if (updated.status !== t.status) bumpCount(t.status, updated.status);
  replaceTask(updated);
  state.task = updated;
  renderBoard();
  renderSheet();
  notify("Task saved.", "info");
}
async function deleteTask() {
  const t = state.task;
  if (!confirm(`Delete "${t.title}" and its comments? This cannot be undone.`)) return;
  await api("DELETE", `/tasks/${t.id}`);
  bumpCount(t.status, null);
  state.tasks = state.tasks.filter((x) => x.id !== t.id);
  state.total -= 1;
  closeTask();
  renderBoard();
  notify(`Deleted "${t.title}".`, "info");
}

/* Comments */
function renderComments() {
  const items = state.comments.map((c) => {
    const mine = c.author_id === state.me.id;
    const edited = parseUtc(c.updated_at) - parseUtc(c.created_at) > 1000;
    if (state.editingComment === c.id) {
      return h("li", { class: "comment" }, h("form", { class: "stack", onsubmit: formHandler(async (_, data) => {
        const updated = await api("PATCH", `/comments/${c.id}`, { body: data.get("body") });
        state.comments = state.comments.map((x) => (x.id === updated.id ? updated : x));
        state.editingComment = null;
        renderSheet();
      }) },
        h("textarea", { name: "body", rows: 3, maxlength: "2000", required: true, "aria-label": "Edit comment" }, c.body),
        h("div", { class: "actions" },
          h("button", { class: "primary", type: "submit" }, "Save comment"),
          h("button", { type: "button", onclick: () => { state.editingComment = null; renderSheet(); } }, "Cancel"))));
    }
    return h("li", { class: "comment" },
      h("div", { class: "comment-head" },
        h("strong", {}, personName(c.author_id)),
        h("span", { class: "muted" }, fmtDate(c.created_at) + (edited ? " (edited)" : "")),
        mine && h("button", { type: "button", class: "link", onclick: () => { state.editingComment = c.id; renderSheet(); } }, "Edit"),
        mine && h("button", { type: "button", class: "link danger", onclick: guard(() => deleteComment(c.id)) }, "Delete")),
      h("p", {}, c.body));
  });
  const shown = state.comments.length < state.commentsTotal
    ? h("p", { class: "muted" }, `Showing the newest ${state.comments.length} of ${state.commentsTotal} comments.`) : null;
  return h("section", { class: "stack", "aria-label": "Comments" },
    h("h2", {}, `Comments (${state.commentsTotal})`),
    shown,
    items.length ? h("ol", { class: "comment-list" }, items) : h("p", { class: "muted" }, "No comments yet."),
    h("form", { class: "stack", onsubmit: formHandler(async (form, data) => {
      await api("POST", `/tasks/${state.task.id}/comments`, { body: data.get("body") });
      form.reset();
      await loadComments();
      renderSheet();
    }) },
      h("textarea", { name: "body", rows: 3, maxlength: "2000", required: true, placeholder: "Write a comment", "aria-label": "New comment" }),
      h("button", { type: "submit", class: "self-start" }, "Add comment")));
}
async function deleteComment(id) {
  if (!confirm("Delete this comment?")) return;
  await api("DELETE", `/comments/${id}`);
  await loadComments();
  renderSheet();
}

/* Theme: "system", "light" or "dark"; theme.js applies the saved choice before first paint */
function renderThemeSwitch() {
  const current = document.documentElement.dataset.theme;
  for (const button of document.querySelectorAll("[data-theme-choice]")) {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === current));
  }
}
function setTheme(choice) {
  document.documentElement.dataset.theme = choice;
  try { localStorage.setItem("tt.theme", choice); } catch { /* storage unavailable */ }
  renderThemeSwitch();
}
for (const button of document.querySelectorAll("[data-theme-choice]")) {
  button.addEventListener("click", () => setTheme(button.dataset.themeChoice));
}
renderThemeSwitch();

/* Wiring */
$("show-login").addEventListener("click", () => setAuthMode(false));
$("show-register").addEventListener("click", () => setAuthMode(true));
$("login-form").addEventListener("submit", formHandler(async (form, data) => {
  await signIn(data.get("email"), data.get("password"));
  form.reset();
}));
$("register-form").addEventListener("submit", formHandler(async (form, data) => {
  const email = data.get("email");
  const password = data.get("password");
  await api("POST", "/auth/register", { full_name: data.get("full_name"), email, password });
  form.reset();
  await signIn(email, password);
}));
$("sign-out").addEventListener("click", () => signOut());
guard(boot)();
