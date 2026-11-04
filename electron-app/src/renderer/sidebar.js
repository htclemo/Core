/* TheCore — Sidebar (Electron renderer).
 *
 * Workspaces → Projects → Conversations, with a trash button on every row.
 * The rows are real elements (not list overlays) so the title and the delete
 * button are always visible and clickable.
 */

(function () {
  "use strict";

  const API = window.thecoreAPI;
  const $ = (id) => document.getElementById(id);

  const state = {
    workspaces: [],
    projects: [],
    conversations: [],
    workspaceId: null,
    projectId: null,
    conversationId: null,
  };

  // conversation id -> row element, so a rename can be applied in place.
  const conversationRows = new Map();

  const listeners = {
    conversationSelected: [],
    projectSelected: [],
    projectDeleted: [],
    conversationDeleted: [],
  };

  function on(event, fn) {
    listeners[event].push(fn);
  }

  function emit(event, payload) {
    listeners[event].forEach((fn) => fn(payload));
  }

  // ------------------------------------------------------------------ confirm

  /** A styled confirmation dialog (window.confirm is not used). */
  function confirmDialog(title, message, confirmLabel = "Delete") {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "confirm-overlay";

      const box = document.createElement("div");
      box.className = "confirm-box";

      const head = document.createElement("div");
      head.className = "confirm-title";
      head.textContent = title;

      const text = document.createElement("div");
      text.className = "confirm-text";
      text.textContent = message;

      const row = document.createElement("div");
      row.className = "confirm-row";

      const cancel = document.createElement("button");
      cancel.className = "confirm-btn";
      cancel.textContent = "Cancel";

      const ok = document.createElement("button");
      ok.className = "confirm-btn danger";
      ok.textContent = confirmLabel;

      row.appendChild(cancel);
      row.appendChild(ok);
      box.appendChild(head);
      box.appendChild(text);
      box.appendChild(row);
      overlay.appendChild(box);
      document.body.appendChild(overlay);

      const done = (value) => {
        overlay.remove();
        resolve(value);
      };
      cancel.addEventListener("click", () => done(false));
      ok.addEventListener("click", () => done(true));
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) done(false);
      });
      ok.focus();
    });
  }

  // ------------------------------------------------------------------ search + collapse

  const searchInput = $("sidebar-search");
  const collapseBtn = $("btn-collapse");
  const expandBtn = $("btn-expand");
  const sidebarEl = $("ai-sidebar");

  let filter = "";

  /** Hide the rows that do not match the search text. */
  function applyFilter() {
    const needle = filter.trim().toLowerCase();
    const boxes = [
      ["list-workspaces", state.workspaces],
      ["list-projects", state.projects],
      ["list-conversations", state.conversations],
    ];
    for (const [id] of boxes) {
      const box = $(id);
      if (!box) continue;
      let shown = 0;
      box.querySelectorAll(".side-row").forEach((row) => {
        const title = (
          row.querySelector(".side-row-title")?.textContent || ""
        ).toLowerCase();
        const visible = !needle || title.includes(needle);
        row.style.display = visible ? "" : "none";
        if (visible) shown++;
      });
      // Hide a section when nothing in it matches.
      const label = box.previousElementSibling;
      if (label && label.classList.contains("section-label")) {
        label.style.display = shown ? "" : "none";
      }
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      filter = searchInput.value || "";
      applyFilter();
    });
  }

  if (collapseBtn) {
    collapseBtn.addEventListener("click", () => {
      if (sidebarEl) sidebarEl.classList.add("collapsed");
      if (expandBtn) expandBtn.hidden = false;
    });
  }
  if (expandBtn) {
    expandBtn.addEventListener("click", () => {
      if (sidebarEl) sidebarEl.classList.remove("collapsed");
      expandBtn.hidden = true;
    });
  }

  // ------------------------------------------------------------------ rows

  function makeRow(title, tooltip, onSelect, onDelete) {
    const row = document.createElement("div");
    row.className = "side-row";

    const label = document.createElement("span");
    label.className = "side-row-title";
    label.textContent = title;
    label.title = title;

    const del = document.createElement("button");
    del.className = "side-row-delete";
    del.textContent = "🗑";
    del.title = tooltip;
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      onDelete();
    });

    row.appendChild(label);
    row.appendChild(del);
    row.addEventListener("click", onSelect);
    return row;
  }

  function clear(box) {
    while (box.firstChild) box.removeChild(box.firstChild);
  }

  /** Update a conversation's row in place after it was named automatically. */
  function renameConversation(conversationId, title) {
    const row = conversationRows.get(Number(conversationId));
    if (!row) return false;
    row.querySelector(".side-row-title").textContent = title;
    return true;
  }

  function markSelected(container, id) {
    container.querySelectorAll(".side-row").forEach((row) => {
      const isSel = Number(row.dataset.id) === id;
      row.classList.toggle("selected", isSel);
    });
  }

  // ------------------------------------------------------------------ render

  function renderWorkspaces() {
    const box = $("list-workspaces");
    clear(box);
    state.workspaces.forEach((ws) => {
      const row = makeRow(
        ws.name,
        `Delete workspace '${ws.name}'`,
        () => selectWorkspace(ws.id),
        () => deleteWorkspace(ws)
      );
      row.dataset.id = ws.id;
      box.appendChild(row);
    });
    markSelected(box, state.workspaceId);
  }

  function renderProjects() {
    const box = $("list-projects");
    clear(box);
    state.projects.forEach((pr) => {
      const row = makeRow(
        pr.name,
        `Delete project '${pr.name}' and its chats`,
        () => selectProject(pr.id),
        () => deleteProject(pr)
      );
      row.dataset.id = pr.id;
      box.appendChild(row);
    });
    markSelected(box, state.projectId);
  }

  function renderConversations() {
    const box = $("list-conversations");
    clear(box);
    conversationRows.clear();
    state.conversations.forEach((cv) => {
      const row = makeRow(
        cv.title,
        `Delete chat '${cv.title}'`,
        () => selectConversation(cv.id),
        () => deleteConversation(cv)
      );
      row.dataset.id = cv.id;
      box.appendChild(row);
      conversationRows.set(cv.id, row);
    });
    markSelected(box, state.conversationId);
  }

  function renderAll() {
    renderWorkspaces();
    renderProjects();
    renderConversations();
    // The rows were recreated — apply the search again.
    applyFilter();
  }

  // ------------------------------------------------------------------ load

  async function loadWorkspaces() {
    state.workspaces = (await API.listWorkspaces()) || [];
    renderWorkspaces();

    if (!state.workspaces.length) {
      state.workspaceId = null;
      state.projectId = null;
      state.conversations = [];
      renderProjects();
      renderConversations();
      return;
    }
    const stillThere = state.workspaces.some(
      (w) => w.id === state.workspaceId
    );
    if (!stillThere) {
      state.workspaceId = state.workspaces[0].id;
    }
    renderWorkspaces();
    await loadProjects();
  }

  async function loadProjects() {
    if (state.workspaceId == null) {
      state.projects = [];
      state.conversations = [];
      renderProjects();
      renderConversations();
      return;
    }
    state.projects = (await API.listProjects(state.workspaceId)) || [];
    renderProjects();

    if (!state.projects.length) {
      state.projectId = null;
      state.conversations = [];
      renderConversations();
      return;
    }
    const stillThere = state.projects.some((p) => p.id === state.projectId);
    if (!stillThere) {
      state.projectId = state.projects[0].id;
    }
    renderProjects();
    await loadConversations();
  }

  async function loadConversations() {
    if (state.projectId == null) {
      state.conversations = [];
      renderConversations();
      return;
    }
    state.conversations =
      (await API.listConversations(state.projectId)) || [];
    renderConversations();
  }

  // ------------------------------------------------------------------ select

  async function selectWorkspace(id) {
    state.workspaceId = id;
    state.projectId = null;
    state.conversationId = null;
    renderWorkspaces();
    await loadProjects();
    emit("projectSelected", state.projectId);
  }

  async function selectProject(id) {
    state.projectId = id;
    state.conversationId = null;
    renderProjects();
    await loadConversations();
    emit("projectSelected", id);
  }

  function selectConversation(id) {
    state.conversationId = id;
    renderConversations();
    emit("conversationSelected", id);
  }

  // ------------------------------------------------------------------ delete

  async function deleteWorkspace(ws) {
    const projects = (await API.listProjects(ws.id)) || [];
    let chats = 0;
    for (const p of projects) {
      chats += await API.countConversations(p.id);
    }
    const extra = projects.length
      ? `\n\nThis will also delete ${projects.length} project(s) and ${chats} conversation(s).`
      : "";
    const ok = await confirmDialog(
      "Delete Workspace",
      `Are you sure you want to delete the workspace "${ws.name}"?${extra}\n\nThis cannot be undone.`
    );
    if (!ok) return;
    await API.deleteWorkspace(ws.id);
    if (state.workspaceId === ws.id) {
      state.workspaceId = null;
      state.projectId = null;
      state.conversationId = null;
    }
    await loadWorkspaces();
  }

  async function deleteProject(pr) {
    const count = await API.countConversations(pr.id);
    const extra = count
      ? `\n\nThis will also delete ${count} conversation(s) and all of their messages.`
      : "";
    const ok = await confirmDialog(
      "Delete Project",
      `Are you sure you want to delete the project "${pr.name}"?${extra}\n\nThis cannot be undone.`
    );
    if (!ok) return;
    // Tell the host before reloading: reloading auto-selects another project.
    emit("projectDeleted", pr.id);
    await API.deleteProject(pr.id);
    if (state.projectId === pr.id) {
      state.projectId = null;
      state.conversationId = null;
    }
    await loadProjects();
  }

  async function deleteConversation(cv) {
    const ok = await confirmDialog(
      "Delete Conversation",
      `Are you sure you want to delete the conversation "${cv.title}"?\n\nAll of its messages will be removed. This cannot be undone.`
    );
    if (!ok) return;
    emit("conversationDeleted", cv.id);
    await API.deleteConversation(cv.id);
    if (state.conversationId === cv.id) {
      state.conversationId = null;
    }
    await loadConversations();
  }

  // ------------------------------------------------------------------ create

  async function createWorkspace() {
    const name = prompt("Workspace name:");
    if (!name) return;
    const wsPath = prompt(
      "Folder for this workspace:",
      "C:\\Users\\Lemo\\Documents\\TheCore"
    );
    if (!wsPath) return;
    const ws = await API.createWorkspace(name.trim(), wsPath.trim());
    state.workspaceId = ws.id;
    await loadWorkspaces();
  }

  async function createProject() {
    if (state.workspaceId == null) {
      alert("Create a workspace first.");
      return;
    }
    const name = prompt("Project name:");
    if (!name) return;
    const pr = await API.createProject(
      state.workspaceId,
      name.trim(),
      ""
    );
    state.projectId = pr.id;
    await loadProjects();
  }

  async function createConversation() {
    if (state.projectId == null) {
      alert("Create a project first.");
      return;
    }
    const conv = await API.createConversation(
      state.projectId,
      "New Conversation",
      ""
    );
    state.conversationId = conv.id;
    await loadConversations();
    emit("conversationSelected", conv.id);
  }

  // ------------------------------------------------------------------ init

  function init() {
    $("btn-add-ws").addEventListener("click", createWorkspace);
    $("btn-new-proj").addEventListener("click", createProject);
    $("btn-new-chat").addEventListener("click", createConversation);
    loadWorkspaces().catch((e) => console.error("sidebar load failed", e));
  }

  window.TheCoreSidebar = {
    state,
    init,
    refresh: loadWorkspaces,
    on,
    selectWorkspace,
    selectProject,
    selectConversation,
    createConversation,
    renameConversation,
    get currentProjectId() {
      return state.projectId;
    },
    get currentWorkspaceId() {
      return state.workspaceId;
    },
    get currentConversationId() {
      return state.conversationId;
    },
  };
})();
