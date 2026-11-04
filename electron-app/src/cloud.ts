/**
 * TheCore — free cloud LLM providers (Electron main process).
 *
 * Mirrors `thecore/ai/cloud_client.py`.  Most providers speak the OpenAI
 * chat-completions API, so one client covers them all; Google Gemini has its
 * own shape and is handled separately.
 *
 * The free allowances below were checked in October 2026 — they change often,
 * so treat them as "what is available today" rather than a promise.
 */

import * as fs from "fs";
import * as path from "path";
import { app } from "electron";

export const CLOUD_PROVIDERS = [
  {
    id: "openai",
    name: "ChatGPT",
    baseUrl: "https://api.openai.com/v1",
    kind: "openai",
    signupUrl: "https://platform.openai.com/api-keys",
    notes: "GPT-4o, GPT-4.1 and the o-series",
    freeTier: false,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "anthropic",
    name: "Claude",
    baseUrl: "https://api.anthropic.com/v1",
    kind: "openai",
    signupUrl: "https://console.anthropic.com/settings/keys",
    notes: "Claude Opus, Sonnet and Haiku",
    freeTier: false,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "xai",
    name: "Grok",
    baseUrl: "https://api.x.ai/v1",
    kind: "openai",
    signupUrl: "https://console.x.ai/",
    notes: "Grok models from xAI",
    freeTier: false,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    kind: "openai",
    signupUrl: "https://platform.deepseek.com/api_keys",
    notes: "DeepSeek Chat and Reasoner",
    freeTier: false,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "groq",
    name: "Groq",
    baseUrl: "https://api.groq.com/openai/v1",
    kind: "openai",
    signupUrl: "https://console.groq.com/keys",
    notes: "30 rpm, very fast, no training on your data",
    freeTier: true,
    paidModels: true,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    baseUrl: "https://openrouter.ai/api/v1",
    kind: "openai",
    signupUrl: "https://openrouter.ai/keys",
    notes: "one key for many providers, 20 free :free models",
    freeTier: true,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "cerebras",
    name: "Cerebras",
    baseUrl: "https://api.cerebras.ai/v1",
    kind: "openai",
    signupUrl: "https://cloud.cerebras.ai",
    notes: "30 rpm, gpt-oss-120b and other large models",
    freeTier: true,
    paidModels: true,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "mistral",
    name: "Mistral",
    baseUrl: "https://api.mistral.ai/v1",
    kind: "openai",
    signupUrl: "https://console.mistral.ai/api-keys",
    notes: "free tier, Codestral and Devstral for coding",
    freeTier: true,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [
      "codestral-latest",
      "devstral-small-latest",
      "devstral-medium-latest",
      "mistral-small-latest",
      "ministral-3b-latest",
      "ministral-8b-latest",
      "pixtral-12b-2409",
      "pixtral-12b",
      "open-mistral-nemo",
    ],
  },
  {
    id: "github",
    name: "GitHub Models",
    baseUrl: "https://models.inference.ai.azure.com",
    kind: "openai",
    signupUrl: "https://github.com/settings/tokens",
    notes: "GPT-4o, Claude and Llama, 15 rpm",
    freeTier: true,
    paidModels: false,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "gemini",
    name: "Google Gemini",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta",
    kind: "gemini",
    signupUrl: "https://aistudio.google.com/apikey",
    notes: "15 rpm / 1500 per day, 1M context, free without a card",
    freeTier: true,
    paidModels: true,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "nvidia",
    name: "NVIDIA NIM",
    baseUrl: "https://integrate.api.nvidia.com/v1",
    kind: "openai",
    signupUrl: "https://build.nvidia.com",
    notes: "Nemotron and Llama variants, free developer credits",
    freeTier: true,
    paidModels: false,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "cloudflare",
    name: "Cloudflare Workers AI",
    baseUrl: "https://api.cloudflare.com/client/v4/ai",
    kind: "openai",
    signupUrl: "https://dash.cloudflare.com",
    notes: "10,000 neurons per day, many open models",
    freeTier: true,
    paidModels: true,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "huggingface",
    name: "Hugging Face",
    baseUrl: "https://router.huggingface.co/v1",
    kind: "openai",
    signupUrl: "https://huggingface.co/settings/tokens",
    notes: "100,000+ open models, free monthly credits",
    freeTier: true,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "nebius",
    name: "Nebius AI Studio",
    baseUrl: "https://api.studio.nebius.ai/v1",
    kind: "openai",
    signupUrl: "https://studio.nebius.com",
    notes: "free tier with strong open models",
    freeTier: true,
    paidModels: true,
    freeModelsAll: true,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "siliconflow",
    name: "SiliconFlow",
    baseUrl: "https://api.siliconflow.cn/v1",
    kind: "openai",
    signupUrl: "https://cloud.siliconflow.cn",
    notes: "Qwen and DeepSeek, free models",
    freeTier: true,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "moonshot",
    name: "Moonshot Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    kind: "openai",
    signupUrl: "https://platform.moonshot.cn",
    notes: "Kimi K2 with a generous free allowance",
    freeTier: true,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "alibaba",
    name: "Alibaba DashScope",
    baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    kind: "openai",
    signupUrl: "https://bailian.console.aliyun.com",
    notes: "Qwen models, free quota in the international region",
    freeTier: true,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
  {
    id: "custom",
    name: "Custom (OpenAI-compatible)",
    baseUrl: "",
    kind: "openai",
    signupUrl: "",
    notes: "Any OpenAI-compatible endpoint — paste the base URL below",
    freeTier: false,
    paidModels: true,
    freeModelsAll: false,
    freeMarkers: [":free"],
    freeIds: [],
  },
];

/** The pricing label of a provider: FREE TIER, FREE + PAID or PAID. */
export function tierLabel(provider: any): string {
  if (provider.freeTier && provider.paidModels) return "FREE + PAID";
  if (provider.freeTier) return "FREE TIER";
  return "PAID";
}

/** Is this model usable on the provider's free tier? */
export function isFreeModel(provider: any, modelId: string): boolean {
  if (!provider) return false;
  if (provider.freeModelsAll) return true;
  if ((provider.freeIds || []).includes(modelId)) return true;
  return (provider.freeMarkers || []).some((m: string) => m && modelId.includes(m));
}

export const CLOUD_PROVIDERS_BY_ID = Object.fromEntries(
  CLOUD_PROVIDERS.map((p) => [p.id, p])
);

// ------------------------------------------------------------------ key storage
//
// The keys are stored as one text file per provider, exactly like the Python
// app does (`%APPDATA%\TheCore\<provider>.key`).  Both apps therefore share
// the same keys — a key set in one works in the other.

function keyFile(providerId: string): string {
  return path.join(app.getPath("userData"), `${providerId}.key`);
}

// The old single-file format, still read so nothing is lost.
function legacyKeysFile(): string {
  return path.join(app.getPath("userData"), "cloud-keys.json");
}

export function loadCloudKeys(): Record<string, string> {
  const keys: Record<string, string> = {};

  for (const provider of CLOUD_PROVIDERS) {
    try {
      const file = keyFile(provider.id);
      if (fs.existsSync(file)) {
        const value = fs.readFileSync(file, "utf8").trim();
        if (value) keys[provider.id] = value;
      }
    } catch {
      // Ignore — the key is simply not there.
    }
  }

  try {
    const legacy = JSON.parse(fs.readFileSync(legacyKeysFile(), "utf8"));
    for (const [id, value] of Object.entries(legacy || {})) {
      if (!keys[id] && typeof value === "string" && value) {
        keys[id] = value;
      }
    }
  } catch {
    // No legacy file — nothing to merge.
  }

  return keys;
}

export function saveCloudKey(providerId: string, key: string): void {
  const file = keyFile(providerId);
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (key) {
      fs.writeFileSync(file, key.trim(), "utf8");
    } else if (fs.existsSync(file)) {
      fs.unlinkSync(file);
    }
  } catch {
    // Ignore — the key is simply not persisted.
  }

  // Keep the legacy file in step, so nothing is lost there either.
  try {
    const legacy = JSON.parse(fs.readFileSync(legacyKeysFile(), "utf8"));
    if (key) {
      legacy[providerId] = key.trim();
    } else {
      delete legacy[providerId];
    }
    fs.writeFileSync(legacyKeysFile(), JSON.stringify(legacy, null, 2), "utf8");
  } catch {
    // The legacy file is optional.
  }
}

export function loadCloudKey(providerId: string): string {
  return loadCloudKeys()[providerId] || "";
}

// ------------------------------------------------------------------ base url

function baseUrlFile(): string {
  return path.join(app.getPath("userData"), "custom-base-url.txt");
}

export function loadBaseUrl(): string {
  try {
    return fs.readFileSync(baseUrlFile(), "utf8").trim();
  } catch {
    return "";
  }
}

export function saveBaseUrl(url: string): void {
  try {
    fs.mkdirSync(path.dirname(baseUrlFile()), { recursive: true });
    if (url) {
      fs.writeFileSync(baseUrlFile(), url.trim(), "utf8");
    } else if (fs.existsSync(baseUrlFile())) {
      fs.unlinkSync(baseUrlFile());
    }
  } catch {
    // Ignore — the URL is simply not persisted.
  }
}

/** The provider with this id, with the custom base URL applied. */
export function providerFor(providerId: string): any {
  const provider = CLOUD_PROVIDERS_BY_ID[providerId];
  if (!provider) return null;
  if (provider.id === "custom") {
    const baseUrl = loadBaseUrl();
    if (!baseUrl) return null;
    return { ...provider, baseUrl };
  }
  return provider;
}

/** The providers that have an API key stored — the enabled ones. */
export function configuredProviders(): any[] {
  return CLOUD_PROVIDERS.filter((p) => !!loadCloudKey(p.id));
}

/**
 * Every model of every provider that has a key stored.
 *
 * Each model carries its provider so the UI can show
 * `Provider · model  ● FREE` and route the answer to the right backend.
 */
export async function listConfiguredModels(): Promise<
  { id: string; label: string; free: boolean; providerId: string; providerName: string }[]
> {
  const models: any[] = [];
  for (const provider of configuredProviders()) {
    const resolved = providerFor(provider.id);
    if (!resolved) continue;
    const client = new CloudClient(resolved, loadCloudKey(provider.id), 20);
    const list = await client.listModels();
    for (const model of list) {
      models.push({
        ...model,
        providerId: provider.id,
        providerName: provider.name,
      });
    }
  }
  models.sort(
    (a, b) =>
      Number(b.free) - Number(a.free) ||
      a.providerName.localeCompare(b.providerName) ||
      a.id.localeCompare(b.id)
  );
  return models;
}

// ------------------------------------------------------------------ client

export class CloudClient {
  provider: any;
  apiKey: string;
  timeoutSeconds: number;

  constructor(provider: any, apiKey: string, timeoutSeconds = 60) {
    this.provider = provider;
    this.apiKey = apiKey;
    this.timeoutSeconds = timeoutSeconds;
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) headers["Authorization"] = `Bearer ${this.apiKey}`;
    return headers;
  }

  async listModels(): Promise<{ id: string; label: string; free: boolean }[]> {
    if (!this.apiKey) return [];
    try {
      if (this.provider.kind === "gemini") {
        const url = `${this.provider.baseUrl}/models?key=${this.apiKey}`;
        const response = await fetch(url, { headers: this.headers() });
        const payload = await response.json();
        const models = [];
        for (const entry of payload.models || []) {
          const name = String(entry.name || "");
          if (!name.startsWith("models/")) continue;
          const methods = entry.supportedGenerationMethods || [];
          if (!methods.includes("generateContent")) continue;
          const id = name.split("/")[1];
          models.push({ id, label: id, free: isFreeModel(this.provider, id) });
        }
        return models.sort((a, b) => a.id.localeCompare(b.id));
      }

      const response = await fetch(`${this.provider.baseUrl}/models`, {
        headers: this.headers(),
      });
      const payload = await response.json();
      const models = [];
      for (const entry of payload.data || []) {
        const id = String(entry.id || "");
        if (!id) continue;
        models.push({ id, label: id, free: isFreeModel(this.provider, id) });
      }
      return models.sort((a, b) => Number(b.free) - Number(a.free) || a.id.localeCompare(b.id));
    } catch {
      return [];
    }
  }

  /** Stream the assistant's reply, chunk by chunk. */
  async *chatStream(
    model: string,
    messages: { role: string; content: string }[],
    temperature = 0.7
  ): AsyncGenerator<string> {
    if (this.provider.kind === "gemini") {
      yield* this._geminiStream(model, messages, temperature);
      return;
    }

    const response = await fetch(`${this.provider.baseUrl}/chat/completions`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ model, messages, temperature, stream: true }),
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${await response.text()}`);
    }

    for await (const line of streamLines(response)) {
      let event: any;
      try {
        event = JSON.parse(line);
      } catch {
        continue;
      }
      const piece = event?.choices?.[0]?.delta?.content;
      if (piece) yield piece;
    }
  }

  private async *_geminiStream(
    model: string,
    messages: { role: string; content: string }[],
    temperature: number
  ): AsyncGenerator<string> {
    const contents = messages.map((m) => ({
      role: m.role === "user" ? "user" : "model",
      parts: [{ text: String(m.content || "") }],
    }));
    const url = `${this.provider.baseUrl}/models/${model}:streamGenerateContent?alt=sse&key=${this.apiKey}`;
    const response = await fetch(url, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ contents, generationConfig: { temperature } }),
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${await response.text()}`);
    }
    for await (const line of streamLines(response)) {
      let event: any;
      try {
        event = JSON.parse(line);
      } catch {
        continue;
      }
      for (const candidate of event?.candidates || []) {
        for (const part of candidate?.content?.parts || []) {
          if (part.text) yield part.text;
        }
      }
    }
  }
}

/** Yield the JSON lines of a streaming response. */
async function* streamLines(response: Response): AsyncGenerator<string> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n");
    while (index !== -1) {
      const line = buffer.slice(0, index).trim();
      buffer = buffer.slice(index + 1);
      if (line.startsWith("data:")) {
        const payload = line.slice(5).trim();
        if (payload && payload !== "[DONE]") yield payload;
      }
      index = buffer.indexOf("\n");
    }
  }
}
