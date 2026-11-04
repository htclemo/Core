import { contextBridge, ipcRenderer } from "electron";

/** Subscribe to a main-process channel. */
function on(channel: string, cb: (...args: any[]) => void) {
  const subscription = (_event: unknown, ...args: any[]) => cb(...args);
  ipcRenderer.on(channel, subscription);
  return () => ipcRenderer.removeListener(channel, subscription);
}

// TheCore — Preload script.
// Secure bridge between the Electron main process and the renderer. Only
// exposes the specific IPC channels the renderer needs via contextBridge.

contextBridge.exposeInMainWorld("thecoreAPI", {
  // Memory used by TheCore and Ollama only.
  getAiMemory: () => ipcRenderer.invoke("system:aiMemory"),

  // ---- OpenCode (the real CLI, hosted on a ConPTY pseudo console) ----
  isOpenCodeAvailable: () => ipcRenderer.invoke("opencode:available"),
  startOpencode: (cwd: string, cols: number, rows: number) =>
    ipcRenderer.send("opencode:start", cwd, cols, rows),
  stopOpencode: () => ipcRenderer.send("opencode:stop"),
  // Send raw keystrokes to the console.
  writeOpencode: (data: string) => ipcRenderer.send("opencode:data", data),
  // Tell the console how big the terminal is.
  resizeOpencode: (cols: number, rows: number) =>
    ipcRenderer.send("opencode:resize", cols, rows),
  onOpenCodeOutput: (callback: (text: string) => void) => {
    const subscription = (_event: unknown, text: string) => callback(text);
    ipcRenderer.on("opencode:output", subscription);
    return () => ipcRenderer.removeListener("opencode:output", subscription);
  },
  onOpenCodeStatus: (callback: (status: string) => void) => {
    const subscription = (_event: unknown, status: string) => callback(status);
    ipcRenderer.on("opencode:status", subscription);
    return () => ipcRenderer.removeListener("opencode:status", subscription);
  },
  onOpenCodeDone: (callback: (code: number) => void) => {
    const subscription = (_event: unknown, code: number) => callback(code);
    ipcRenderer.on("opencode:done", subscription);
    return () => ipcRenderer.removeListener("opencode:done", subscription);
  },

  // ---- microphone ----
  micStatus: () => ipcRenderer.invoke("mic:status"),
  micToggle: () => ipcRenderer.invoke("mic:toggle"),

  // ---- cloud LLM providers ----
  cloudProviders: () => ipcRenderer.invoke("cloud:providers"),
  cloudListModels: (providerId: string) =>
    ipcRenderer.invoke("cloud:listModels", providerId),
  // Every model of every provider that has a key stored.
  cloudCatalogue: () => ipcRenderer.invoke("cloud:catalogue"),
  // The providers that have a key stored.
  cloudConfigured: () => ipcRenderer.invoke("cloud:configured"),
  cloudSaveKey: (providerId: string, key: string) =>
    ipcRenderer.invoke("cloud:saveKey", providerId, key),
  cloudHasKey: (providerId: string) =>
    ipcRenderer.invoke("cloud:hasKey", providerId),
  cloudSaveBaseUrl: (url: string) => ipcRenderer.invoke("cloud:baseUrl", url),
  cloudGetBaseUrl: () => ipcRenderer.invoke("cloud:getBaseUrl"),
  cloudChat: (providerId: string, model: string, messages: any[]) =>
    ipcRenderer.send("cloud:chat", providerId, model, messages),
  onCloudChunk: (callback: (text: string) => void) => {
    const subscription = (_event: unknown, text: string) => callback(text);
    ipcRenderer.on("cloud:chunk", subscription);
    return () => ipcRenderer.removeListener("cloud:chunk", subscription);
  },
  onCloudDone: (callback: (text: string) => void) => {
    const subscription = (_event: unknown, text: string) => callback(text);
    ipcRenderer.on("cloud:done", subscription);
    return () => ipcRenderer.removeListener("cloud:done", subscription);
  },
  onCloudError: (callback: (text: string) => void) => {
    const subscription = (_event: unknown, text: string) => callback(text);
    ipcRenderer.on("cloud:error", subscription);
    return () => ipcRenderer.removeListener("cloud:error", subscription);
  },

  // ---- model capabilities (tools / vision / reasoning) ----
  modelCapabilities: (model: string) =>
    ipcRenderer.invoke("ollama:capabilities", model),

  // ---- tools ----
  toolDefinitions: (root: string) => ipcRenderer.invoke("tools:definitions", root),
  toolExecute: (root: string, name: string, args: any) =>
    ipcRenderer.invoke("tools:execute", root, name, args),

  // ---- images ----
  pickImage: () => ipcRenderer.invoke("images:pick"),

  // ---- voice ----
  startDictation: () => ipcRenderer.invoke("voice:dictate"),
  speak: (text: string) => ipcRenderer.invoke("voice:speak", text),

  // ---- menu actions ----
  onMenuNewChat: (cb: () => void) => on("menu:newChat", cb),
  onMenuNewWorkspace: (cb: () => void) => on("menu:newWorkspace", cb),
  onMenuNewProject: (cb: () => void) => on("menu:newProject", cb),
  onMenuToggleSidebar: (cb: () => void) => on("menu:toggleSidebar", cb),
  onMenuReload: (cb: () => void) => on("menu:reload", cb),
  onMenuSettings: (cb: () => void) => on("menu:settings", cb),
  onMenuAbout: (cb: () => void) => on("menu:about", cb),

  // ---- app ----
  readyToShow: () => ipcRenderer.send("app:readyToShow"),
  isAdmin: () => ipcRenderer.invoke("app:isAdmin"),
  openExternal: (url: string) => ipcRenderer.send("app:openExternal", url),
  playSound: (name: string) => ipcRenderer.send("app:playSound", name),
  relaunchAsAdmin: () => ipcRenderer.invoke("app:relaunchAsAdmin"),
  quitApp: () => ipcRenderer.send("app:quit"),

  // ---- database ----
  listWorkspaces: () => ipcRenderer.invoke("db:listWorkspaces"),
  listProjects: (workspaceId: number) =>
    ipcRenderer.invoke("db:listProjects", workspaceId),
  listConversations: (projectId: number) =>
    ipcRenderer.invoke("db:listConversations", projectId),
  listMessages: (conversationId: number) =>
    ipcRenderer.invoke("db:listMessages", conversationId),
  countConversations: (projectId: number) =>
    ipcRenderer.invoke("db:countConversations", projectId),
  createWorkspace: (name: string, wsPath: string) =>
    ipcRenderer.invoke("db:createWorkspace", name, wsPath),
  createProject: (workspaceId: number, name: string, description: string) =>
    ipcRenderer.invoke("db:createProject", workspaceId, name, description),
  createConversation: (projectId: number, title: string, model: string) =>
    ipcRenderer.invoke("db:createConversation", projectId, title, model),
  deleteWorkspace: (id: number) => ipcRenderer.invoke("db:deleteWorkspace", id),
  deleteProject: (id: number) => ipcRenderer.invoke("db:deleteProject", id),
  deleteConversation: (id: number) =>
    ipcRenderer.invoke("db:deleteConversation", id),
  addMessage: (conversationId: number, role: string, content: string) =>
    ipcRenderer.invoke("db:addMessage", conversationId, role, content),
  touchConversation: (conversationId: number) =>
    ipcRenderer.invoke("db:touchConversation", conversationId),
  renameConversation: (conversationId: number, title: string) =>
    ipcRenderer.invoke("db:renameConversation", conversationId, title),
  countMessages: (conversationId: number) =>
    ipcRenderer.invoke("db:countMessages", conversationId),
});
