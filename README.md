# Core

Local AI workspace for Windows and Linux. Chat with Ollama, OpenCode, and cloud models. Your chats stay on your machine.

## Download

There will be a Windows installer and a Linux installer. When the first demo is finished, the program can be downloaded and installed from those installers.

## Tabs

| Tab | Purpose |
|-----|---------|
| **AI** | Chat with your local Ollama model. Organize chats into workspaces and projects. |

## AI / Ollama features

- **Model selector** — one dropdown with the **whole catalogue**: the models already pulled in Ollama (`ollama list`) *and* the models of every cloud provider that has a key in the settings. Each cloud model is labelled `Provider · model  ● FREE` or `○ PAID`. Switching models loads the model and measures the VRAM/RAM delta.
- **Live chat** — streaming responses from `http://127.0.0.1:11434/api/chat`. Stop mid-stream anytime.
- **Memory tracking** — shows how much of the model lands in GPU VRAM vs system RAM when loaded.
- **Workspaces & projects** — saved to a local SQLite database (`thecore_ai.db` in the project folder). Conversations and messages persist across restarts.
- **Settings** — the gear in the bottom-left corner of the sidebar (or `Ctrl+,`) opens a page with every program setting: the cloud providers and their keys, the free/paid label of every model, the local models, the text size and the about box.

## Notes

- Ollama must be running (`ollama serve`) on the default port `11434` for the local models to work.
