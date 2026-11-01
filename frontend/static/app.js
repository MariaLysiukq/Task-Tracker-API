"use strict";
const API = "/api/v1";
const STATUSES = [["todo", "To do"], ["in_progress", "In progress"], ["done", "Done"]];
const PRIORITIES = [["low", "Low"], ["medium", "Medium"], ["high", "High"]];
const NEXT_STEP = { todo: ["in_progress", "Start"], in_progress: ["done", "Mark done"], done: ["todo", "Reopen"] };
const DUE_FILTERS = [["", "Any"], ["overdue", "Overdue"], ["week", "Due in 7 days"], ["not_overdue", "Not overdue"]];
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
const EMPTY_COLUMN = { todo: "Nothing to do.", in_progress: "Nothing in progress.", done: "Nothing finished yet." };
const LIST_ORDER = ["in_progress", "todo", "done"];
const prefs = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* storage unavailable */ } },
};
const store = {
  get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { value == null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, String(value)); } catch { /* storage unavailable */ } },
};
const state = {
  token: store.get("tt.token"), me: null, projects: [], project: null, members: [],
  tasks: [], total: 0, filters: { priority: "", assignee_id: "", due: "", order: "desc" },
  task: null, comments: [], commentsTotal: 0, editingComment: null, editingProject: false, column: "todo",
  counts: {}, view: "project", layout: prefs.get("tt.layout") === "list" ? "list" : "board", mine: null,
};
const $ = (id) => document.getElementById(id);
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const narrowScreen = window.matchMedia("(max-width: 760px)");
const SVG_NS = "http://www.w3.org/2000/svg";

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
function svg(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  el.append(...children);
  return el;
}
function select(name, options, value, attrs = {}) {
  const el = h("select", { name, ...attrs }, options.map(([v, text]) => h("option", { value: v }, text)));
  el.value = value == null ? "" : String(value);
  return el;
}
const labelOf = (pairs, value) => (pairs.find(([v]) => v === value) || [value, value])[1];
const parseUtc = (iso) => new Date(/([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : iso + "Z");
const fmtShort = (iso) => {
  const d = parseUtc(iso);
  const sameYear = d.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat(undefined, sameYear ? { month: "short", day: "numeric" } : { dateStyle: "medium" }).format(d);
};
const initialOf = (name) => (name.trim()[0] || "?").toUpperCase();
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
  state.view = "project";
  state.mine = null;
  $("mine-view").replaceChildren();
  $("progress").replaceChildren();
  closePopovers();
  setNav(false);
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
  $("me-id").textContent = `ID ${state.me.id}`;
  $("me-avatar").textContent = initialOf(state.me.full_name);
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
  state.view = "project";
  state.editingProject = false;
  Object.assign(state.filters, { priority: "", assignee_id: "", due: "" });
  closePopovers();
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
function progressRing(c) {
  const total = c ? countTotal(c) : 0;
  const share = (n) => (total ? (n / total) * 100 : 0);
  const arc = (status, length, offset) => length > 0 && svg("circle", { class: `ring-arc ring-${status}`, cx: "8", cy: "8", r: "6",
    pathLength: "100", "stroke-dasharray": `${length} ${100 - length}`, "stroke-dashoffset": String(-offset) });
  const done = share(c ? c.done : 0);
  const active = share(c ? c.in_progress : 0);
  return svg("svg", { class: `ring${total && c.done === total ? " is-complete" : ""}`, viewBox: "0 0 16 16", width: "16", height: "16", "aria-hidden": "true" },
    svg("g", { transform: "rotate(-90 8 8)" },
      svg("circle", { class: "ring-track", cx: "8", cy: "8", r: "6" }),
      arc("done", done, 0) || "", arc("in_progress", active, done) || ""));
}
function renderProjects() {
  const list = $("project-list");
  list.replaceChildren(...state.projects.map((p) => {
    const c = state.counts[p.id];
    const summary = c ? (countTotal(c) ? `${c.done} of ${countTotal(c)} done` : "no tasks") : "";
    return h("li", {},
      h("button", { type: "button", class: "nav-item", "aria-current": state.view === "project" && state.project && p.id === state.project.id ? "page" : "false",
        onclick: guard(async () => { setNav(false); await selectProject(p.id); }) },
        progressRing(c),
        h("span", { class: "project-name" }, p.name),
        summary && h("span", { class: "sr-only" }, `, ${summary}`)));
  }));
  if (!state.projects.length) list.append(h("li", { class: "muted nav-empty" }, "No projects yet."));
}
function renderCrumb() {
  const mine = state.view === "mine";
  const inProject = !mine && Boolean(state.project);
  $("crumb-root").hidden = mine;
  document.querySelector(".crumb-sep").hidden = !inProject;
  $("crumb-project").textContent = mine ? "My tasks" : inProject ? state.project.name : "";
  $("new-task-open").hidden = !inProject;
  $("layout-toggle").hidden = !inProject;
}
function renderView() {
  const mine = state.view === "mine";
  $("mine-view").hidden = !mine;
  $("no-project").hidden = mine || Boolean(state.project);
  $("project-view").hidden = mine || !state.project;
  $("my-tasks").setAttribute("aria-current", mine ? "page" : "false");
  renderCrumb();
}
function renderProjectView() {
  renderView();
  if (state.view === "mine" || !state.project) { closePopovers(); return; }
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
        renderCrumb();
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
function setNewProjectForm(open) {
  $("new-project").hidden = !open;
  $("new-project-toggle").setAttribute("aria-expanded", String(open));
  if (open) $("new-project").querySelector("input").focus();
}
$("new-project-toggle").addEventListener("click", () => setNewProjectForm($("new-project").hidden));
$("new-project").addEventListener("submit", formHandler(async (form, data) => {
  const project = await api("POST", "/projects", { name: data.get("name") });
  form.reset();
  setNewProjectForm(false);
  setNav(false);
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
    owner && h("p", { class: "muted hint" }, "People find their ID under their name at the bottom of the sidebar."));
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
  for (const key of ["priority", "assignee_id"]) if (f[key]) params.set(key, f[key]);
  if (f.due) params.set("overdue", f.due === "overdue" ? "true" : "false");
  const page = await api("GET", `/projects/${state.project.id}/tasks?${params}`);
  state.tasks = append ? state.tasks.concat(page.items) : page.items;
  state.total = page.total;
}
function memberOptions() {
  return state.members.map((m) => [String(m.user_id), m.user_id === state.me.id ? `You (#${m.user_id})` : `User #${m.user_id}`]);
}
/* "Due in 7 days" has no API filter: the server drops overdue tasks, the client keeps the next 7 days. */
function visibleTasks() {
  if (state.filters.due !== "week") return state.tasks;
  const now = Date.now();
  return state.tasks.filter((t) => {
    if (!t.due_at || t.status === "done") return false;
    const due = parseUtc(t.due_at).getTime();
    return due >= now && due <= now + WEEK_MS;
  });
}
function filterLabel(key, value) {
  if (key === "priority") return `Priority: ${labelOf(PRIORITIES, value)}`;
  if (key === "assignee_id") return `Assignee: ${personName(Number(value))}`;
  return labelOf(DUE_FILTERS, value);
}
async function setFilter(key, value) {
  const focusKey = document.activeElement && document.activeElement.dataset.focusKey;
  state.filters[key] = value;
  await loadTasks(false);
  renderFilters();
  renderBoard();
  const again = focusKey && document.querySelector(`[data-focus-key="${focusKey}"]`);
  (again || $("filter-open")).focus();
}
function renderFilters() {
  const f = state.filters;
  const quick = [["Overdue", "due", "overdue"], ["Due in 7 days", "due", "week"],
    ["Assigned to me", "assignee_id", String(state.me.id)], ["High priority", "priority", "high"]];
  const field = (text, key, options) => h("label", {}, text, select(key, options, f[key],
    { "data-focus-key": key, onchange: guard((event) => setFilter(key, event.target.value)) }));
  $("filter-pop").replaceChildren(
    h("p", { class: "pop-label", id: "quick-label" }, "Quick filters"),
    h("div", { class: "quick", role: "group", "aria-labelledby": "quick-label" }, quick.map(([text, key, value], i) =>
      h("button", { type: "button", class: "chip", "aria-pressed": String(f[key] === value), "data-focus-key": `quick-${i}`,
        onclick: guard(() => setFilter(key, f[key] === value ? "" : value)) }, text))),
    h("div", { class: "field-grid" },
      field("Priority", "priority", [["", "Any"], ...PRIORITIES]),
      field("Assignee", "assignee_id", [["", "Anyone"], ...memberOptions()]),
      h("div", { class: "span-2" }, field("Due", "due", DUE_FILTERS))));
  const active = ["priority", "assignee_id", "due"].filter((key) => f[key]);
  $("filter-pills").replaceChildren(...active.map((key) => h("li", {},
    h("button", { type: "button", class: "pill", "aria-label": `Remove filter ${filterLabel(key, f[key])}`,
      onclick: guard(() => setFilter(key, "")) }, filterLabel(key, f[key]), h("span", { class: "pill-x", "aria-hidden": "true" }, "×")))));
  $("filter-open").classList.toggle("has-filters", active.length > 0);
  $("order-select").value = f.order;
  renderNewTaskAssignee();
}
function renderNewTaskAssignee() {
  const el = $("new-task-assignee");
  const options = [["", "Unassigned"], ...memberOptions()];
  const previous = el.value;
  el.replaceChildren(...options.map(([v, text]) => h("option", { value: v }, text)));
  el.value = options.some(([v]) => v === previous) ? previous : "";
}
const filtersActive = () => Boolean(state.filters.priority || state.filters.assignee_id || state.filters.due);
async function clearFilters() {
  Object.assign(state.filters, { priority: "", assignee_id: "", due: "" });
  await loadTasks(false);
  renderFilters();
  renderBoard();
}
function renderFilterStatus() {
  const box = $("filter-status");
  if (!filtersActive()) { box.replaceChildren(); return; }
  const n = state.filters.due === "week" ? visibleTasks().length : state.total;
  const c = state.counts[state.project.id];
  const of = c ? ` of ${countTotal(c)}` : "";
  const text = n ? `${n}${of} ${n === 1 && !of ? "task" : "tasks"} match` : "No tasks match these filters.";
  box.replaceChildren(h("span", {}, text), h("button", { type: "button", class: "link", onclick: guard(clearFilters) }, "Clear filters"));
}
$("order-select").addEventListener("change", guard(async (event) => {
  state.filters.order = event.target.value;
  await loadTasks(false);
  renderBoard();
}));
/* Task visuals: status circle (from the ring logo), priority bars, ID, assignee avatar, due date */
function statusIcon(status) {
  const ring = () => svg("circle", { class: "st-ring", cx: "8", cy: "8", r: "6" });
  const parts = {
    todo: [ring()],
    in_progress: [ring(), svg("path", { class: "st-fill", d: "M8 4.5a3.5 3.5 0 0 1 0 7z" })],
    done: [svg("circle", { class: "st-solid", cx: "8", cy: "8", r: "7" }), svg("path", { class: "st-check", d: "M5.2 8.2l1.9 1.9 3.7-3.9" })],
  };
  return svg("svg", { class: `status-icon st-${status}`, viewBox: "0 0 16 16", width: "14", height: "14", "aria-hidden": "true" }, ...parts[status]);
}
function priorityIcon(priority) {
  const level = { low: 1, medium: 2, high: 3 }[priority];
  const text = `${labelOf(PRIORITIES, priority)} priority`;
  return h("span", { class: `prio-icon prio-icon-${priority}`, title: text },
    svg("svg", { viewBox: "0 0 16 16", width: "14", height: "14", "aria-hidden": "true" }, ...[0, 1, 2].map((i) =>
      svg("rect", { class: i < level ? "bar on" : "bar", x: String(2 + i * 4.5), y: String(10 - i * 3.5), width: "3", height: String(4 + i * 3.5), rx: "1" }))),
    h("span", { class: "sr-only" }, text));
}
const taskId = (t) => h("span", { class: "task-id" }, `TT-${t.id}`);
function avatar(userId) {
  if (!userId) return h("span", { class: "avatar sm empty", title: "Unassigned" }, h("span", { class: "sr-only" }, "Unassigned"));
  const me = state.me && userId === state.me.id;
  const name = me ? `${state.me.full_name} (you)` : `User #${userId}`;
  return h("span", { class: "avatar sm", title: name },
    h("span", { "aria-hidden": "true" }, me ? initialOf(state.me.full_name) : String(userId)),
    h("span", { class: "sr-only" }, `Assigned to ${me ? "you" : name}`));
}
function dueChip(t) {
  if (!t.due_at) return null;
  const overdue = isOverdue(t);
  return h("span", { class: `due${overdue ? " overdue" : ""}`, title: `${overdue ? "Overdue, was due" : "Due"} ${fmtDate(t.due_at)}` },
    h("span", { class: "sr-only" }, overdue ? "Overdue, was due " : "Due "), fmtShort(t.due_at));
}
function taskCard(t) {
  const [nextStatus, nextLabel] = NEXT_STEP[t.status];
  return h("li", { class: "card", "data-id": String(t.id) },
    h("div", { class: "card-top" }, statusIcon(t.status), taskId(t), avatar(t.assignee_id)),
    h("button", { type: "button", class: "card-title", onclick: guard(() => openTask(t.id)) }, t.title),
    h("div", { class: "card-meta" }, priorityIcon(t.priority), dueChip(t),
      h("button", { type: "button", class: "card-move ghost small", onclick: guard(() => moveTask(t, nextStatus)) }, nextLabel)));
}
function taskRow(t, onOpen) {
  return h("li", { class: `row${t.status === "done" ? " is-done" : ""}`, "data-id": String(t.id) },
    h("button", { type: "button", class: "row-main", onclick: guard(() => onOpen(t)) },
      priorityIcon(t.priority), taskId(t), statusIcon(t.status), h("span", { class: "sr-only" }, labelOf(STATUSES, t.status)),
      h("span", { class: "row-title" }, t.title), dueChip(t), avatar(t.assignee_id)));
}
function taskGroup(icon, title, items, onOpen, extra = null) {
  return h("section", { class: "group", "aria-label": title },
    h("div", { class: "group-head" }, icon, h("h2", { class: "group-title" }, title), h("span", { class: "mono muted" }, String(items.length)), extra),
    h("ul", { class: "rows" }, items.map((t) => taskRow(t, onOpen))));
}
const byStatus = (items) => items.slice().sort((a, b) => LIST_ORDER.indexOf(a.status) - LIST_ORDER.indexOf(b.status));
function renderList() {
  const tasks = visibleTasks();
  const groups = LIST_ORDER.map((status) => [status, tasks.filter((t) => t.status === status)]).filter(([, items]) => items.length);
  const empty = h("p", { class: "column-empty" }, filtersActive() ? "No tasks match these filters." : "No tasks yet. Press C to add one.");
  $("list").replaceChildren(...(groups.length
    ? groups.map(([status, items]) => taskGroup(statusIcon(status), labelOf(STATUSES, status), items, (t) => openTask(t.id)))
    : [empty]));
}
function renderBoard() {
  renderFilterStatus();
  const list = state.layout === "list";
  $("board").hidden = list;
  $("list").hidden = !list;
  $("col-tabs").hidden = list;
  if (list) renderList();
  else {
    $("col-tabs").replaceChildren(...STATUSES.map(([status, text]) => {
      const count = visibleTasks().filter((t) => t.status === status).length;
      return h("button", { type: "button", role: "tab", "aria-selected": String(state.column === status),
        onclick: () => { state.column = status; renderBoard(); } }, statusIcon(status), `${text} (${count})`);
    }));
    $("board").replaceChildren(...STATUSES.map(([status, text]) => {
      const tasks = visibleTasks().filter((t) => t.status === status);
      return h("section", { class: `column${state.column === status ? " is-active" : ""}`, "data-status": status, "aria-label": text },
        h("div", { class: "column-head" }, statusIcon(status), h("h2", {}, text), h("span", { class: "mono muted" }, String(tasks.length))),
        tasks.length ? h("ul", { class: "cards" }, tasks.map(taskCard)) : h("p", { class: "column-empty" }, EMPTY_COLUMN[status]));
    }));
  }
  const more = $("more");
  more.replaceChildren();
  if (state.tasks.length < state.total) {
    more.append(h("button", { type: "button", onclick: guard(async () => { await loadTasks(true); renderBoard(); }) },
      `Load more tasks (${state.tasks.length} of ${state.total} shown)`));
  }
}
function renderLayoutToggle() {
  for (const button of document.querySelectorAll("[data-layout]")) {
    button.setAttribute("aria-pressed", String(button.dataset.layout === state.layout));
  }
}
for (const button of document.querySelectorAll("[data-layout]")) {
  button.addEventListener("click", () => {
    state.layout = button.dataset.layout;
    prefs.set("tt.layout", state.layout);
    renderLayoutToggle();
    renderBoard();
  });
}
renderLayoutToggle();

/* My tasks: tasks assigned to me in every project (no cross-project endpoint, so one request per project) */
async function openMyTasks() {
  state.view = "mine";
  closePopovers();
  setNav(false);
  renderProjects();
  renderView();
  $("mine-view").replaceChildren(h("h1", {}, "My tasks"), h("p", { class: "muted" }, "Loading your tasks…"));
  const pages = [];
  for (let i = 0; i < state.projects.length; i += 5) {
    const chunk = state.projects.slice(i, i + 5);
    pages.push(...await Promise.all(chunk.map((p) =>
      api("GET", `/projects/${p.id}/tasks?assignee_id=${state.me.id}&limit=100&sort=created_at&order=desc`))));
  }
  state.mine = state.projects.map((project, i) => ({ project, page: pages[i] })).filter((g) => g.page.total > 0);
  if (state.view === "mine") renderMine();
}
async function openFromMine(t) {
  await selectProject(t.project_id);
  await openTask(t.id);
}
function renderMine() {
  const all = state.mine.flatMap((g) => g.page.items);
  const open = all.filter((t) => t.status !== "done").length;
  const where = `${state.mine.length} ${state.mine.length === 1 ? "project" : "projects"}`;
  const summary = all.length ? `${open} open, ${all.length - open} done, in ${where}.` : "Nothing is assigned to you yet. Tasks assigned to you in any project show up here.";
  $("mine-view").replaceChildren(
    h("div", { class: "stack" }, h("h1", {}, "My tasks"), h("p", { class: "muted" }, summary)),
    ...state.mine.map((g) => h("div", { class: "stack" },
      taskGroup(progressRing(state.counts[g.project.id]), g.project.name, byStatus(g.page.items), openFromMine,
        h("button", { type: "button", class: "ghost small group-action", onclick: guard(() => selectProject(g.project.id)) }, "Open project")),
      g.page.total > g.page.items.length && h("p", { class: "muted note" }, `Showing the newest ${g.page.items.length} of ${g.page.total}.`))));
}
$("my-tasks").addEventListener("click", guard(openMyTasks));
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
  closePopovers(true);
  await loadTasks(false);
  state.column = "todo";
  renderBoard();
  const card = document.querySelector(`#board:not([hidden]) .card[data-id="${created.id}"], #list:not([hidden]) .row[data-id="${created.id}"]`);
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
  state.task = state.tasks.find((t) => t.id === id) || await api("GET", `/tasks/${id}`);
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

/* Shell: popovers, mobile navigation drawer, shortcuts */
const POPOVER_BUTTONS = ["new-task-open", "filter-open"];
const panelOf = (buttonId) => $($(buttonId).getAttribute("aria-controls"));
function setPopover(buttonId, open) {
  panelOf(buttonId).hidden = !open;
  $(buttonId).setAttribute("aria-expanded", String(open));
}
function openPopover(buttonId) {
  closePopovers();
  setPopover(buttonId, true);
  const first = panelOf(buttonId).querySelector("input, select, button");
  if (first) first.focus();
}
function closePopovers(restoreFocus = false) {
  for (const id of POPOVER_BUTTONS) {
    if (panelOf(id).hidden) continue;
    setPopover(id, false);
    if (restoreFocus) $(id).focus();
  }
}
for (const id of POPOVER_BUTTONS) {
  $(id).addEventListener("click", () => (panelOf(id).hidden ? openPopover(id) : closePopovers()));
}
$("new-task-cancel").addEventListener("click", () => closePopovers(true));
document.addEventListener("pointerdown", (event) => {
  for (const id of POPOVER_BUTTONS) {
    if (!panelOf(id).hidden && !panelOf(id).contains(event.target) && !$(id).contains(event.target)) setPopover(id, false);
  }
});
function setNav(open) {
  const wasOpen = $("sidebar").classList.contains("is-open");
  $("sidebar").classList.toggle("is-open", open);
  $("nav-backdrop").hidden = !open;
  $("nav-open").setAttribute("aria-expanded", String(open));
  $("main").inert = open;
  if (open) $("nav-close").focus();
  else if (wasOpen && narrowScreen.matches) $("nav-open").focus();
}
$("nav-open").addEventListener("click", () => setNav(true));
$("nav-close").addEventListener("click", () => setNav(false));
$("nav-backdrop").addEventListener("click", () => setNav(false));
narrowScreen.addEventListener("change", () => setNav(false));
const isTyping = (el) => Boolean(el && el.closest && el.closest("input, textarea, select, [contenteditable]"));
document.addEventListener("keydown", (event) => {
  if ($("app").hidden || $("task-dialog").open || event.isComposing) return;
  if (event.key === "Escape") {
    if (POPOVER_BUTTONS.some((id) => !panelOf(id).hidden)) { event.preventDefault(); closePopovers(true); return; }
    if (!$("new-project").hidden && $("new-project").contains(document.activeElement)) { setNewProjectForm(false); $("new-project-toggle").focus(); return; }
    if ($("sidebar").classList.contains("is-open")) setNav(false);
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || isTyping(event.target)) return;
  if ((event.key.toLowerCase() === "c" || event.code === "KeyC") && state.project && state.view === "project") {
    event.preventDefault();
    setNav(false);
    openPopover("new-task-open");
  }
});

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
