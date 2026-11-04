"""Free cloud LLM providers.

Everything here has a **free tier** — no credit card required for the
providers marked that way.  The limits were checked in October 2026; they
change often, so treat them as "what is available today" rather than a promise.

Most providers speak the OpenAI chat-completions API, so one client covers
them all.  Google Gemini has its own API shape and is handled separately.

Providers
---------
=============  =========  ==================================================
Provider       Card?      Free allowance
=============  =========  ==================================================
Groq           no         30 rpm, thousands of requests/day, no training
OpenRouter     no         20 rpm, 50/day (1000/day after a $10 top-up)
Cerebras       no         30 rpm, ~1M tokens/day
Mistral        no         free "Experiment" tier, ~1B tokens/month
GitHub Models  no         15 rpm, 150-1000/day
Google Gemini  no         15 rpm / 1500 per day on the Flash models
=============  =========  ==================================================

Privacy note: Google's free tier may use prompts to improve its products
(except in the EU/UK/EEA).  Groq, Cerebras, OpenRouter and GitHub Models do
not train on your data.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterator, Optional


@dataclass(frozen=True)
class CloudProvider:
    """One cloud provider.

    ``free_tier`` says the provider has a usable free allowance at all.
    ``free_models_all`` says *every* model it lists works on that allowance.
    The markers and ids cover the providers that only tag some of their
    models as free (``:free`` and friends).
    """

    id: str
    name: str
    base_url: str
    kind: str = "openai"  # "openai" or "gemini"
    needs_key: bool = True
    signup_url: str = ""
    notes: str = ""
    # Does the provider have a free tier?
    free_tier: bool = True
    # Does the provider also sell paid access (or paid models)?
    paid_models: bool = False
    # Is every listed model usable on the free tier?
    free_models_all: bool = False
    # Substrings that mark a model as free.
    free_markers: tuple[str, ...] = (":free",)
    # Exact model ids that are free.
    free_ids: tuple[str, ...] = ()
    # Shown in the model dropdown even before the provider answers.
    known_models: tuple[str, ...] = ()

    def key_path(self) -> Path:
        return _keys_dir() / f"{self.id}.key"

    def is_free_model(self, model_id: str) -> bool:
        """Is this model usable on the free tier?"""
        if self.free_models_all:
            return True
        if model_id in self.free_ids:
            return True
        return any(marker and marker in model_id for marker in self.free_markers)

    @property
    def tier_label(self) -> str:
        """A short label for the provider's pricing, e.g. ``FREE TIER``."""
        if self.free_tier and self.paid_models:
            return "FREE + PAID"
        if self.free_tier:
            return "FREE TIER"
        return "PAID"


# ---------------------------------------------------------------------- registry

PROVIDERS: tuple[CloudProvider, ...] = (
    CloudProvider(
        id="openai",
        name="ChatGPT",
        base_url="https://api.openai.com/v1",
        signup_url="https://platform.openai.com/api-keys",
        notes="GPT-4o, GPT-4.1 and the o-series",
        free_tier=False,
        paid_models=True,
        known_models=(
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o3",
            "o4-mini",
        ),
    ),
    CloudProvider(
        id="anthropic",
        name="Claude",
        base_url="https://api.anthropic.com/v1",
        signup_url="https://console.anthropic.com/settings/keys",
        notes="Claude Opus, Sonnet and Haiku",
        free_tier=False,
        paid_models=True,
        known_models=(
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-3-5-sonnet-latest",
        ),
    ),
    CloudProvider(
        id="xai",
        name="Grok",
        base_url="https://api.x.ai/v1",
        signup_url="https://console.x.ai/",
        notes="Grok models from xAI",
        free_tier=False,
        paid_models=True,
        known_models=("grok-4", "grok-3", "grok-3-mini"),
    ),
    CloudProvider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        signup_url="https://platform.deepseek.com/api_keys",
        notes="DeepSeek Chat and Reasoner",
        free_tier=False,
        paid_models=True,
        known_models=("deepseek-chat", "deepseek-reasoner"),
    ),
    CloudProvider(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        signup_url="https://console.groq.com/keys",
        notes="30 rpm, very fast, no training on your data",
        paid_models=True,
        free_models_all=True,
        known_models=(
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "qwen/qwen3-32b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "moonshotai/kimi-k2-instruct",
        ),
    ),
    CloudProvider(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        signup_url="https://openrouter.ai/keys",
        notes="one key for many providers, 20 free :free models",
        paid_models=True,
        known_models=(
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemma-3-27b-it:free",
            "google/gemma-3-12b-it:free",
            "mistralai/mistral-small-3.2-24b-instruct:free",
            "qwen/qwen3-coder:free",
            "qwen/qwen3-235b-a22b:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "deepseek/deepseek-r1:free",
            "moonshotai/kimi-k2:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "openai/gpt-oss-120b:free",
            "openai/gpt-oss-20b:free",
            "z-ai/glm-4.5-air:free",
        ),
    ),
    CloudProvider(
        id="cerebras",
        name="Cerebras",
        base_url="https://api.cerebras.ai/v1",
        signup_url="https://cloud.cerebras.ai",
        notes="30 rpm, gpt-oss-120b and other large models",
        paid_models=True,
        free_models_all=True,
        known_models=(
            "llama3.1-8b",
            "llama-3.3-70b",
            "qwen-3-32b",
            "gpt-oss-120b",
        ),
    ),
    CloudProvider(
        id="mistral",
        name="Mistral",
        base_url="https://api.mistral.ai/v1",
        signup_url="https://console.mistral.ai/api-keys",
        notes="free tier, Codestral and Devstral for coding",
        paid_models=True,
        free_ids=(
            "codestral-latest",
            "devstral-small-latest",
            "devstral-medium-latest",
            "mistral-small-latest",
            "ministral-3b-latest",
            "ministral-8b-latest",
            "pixtral-12b-2409",
            "pixtral-12b",
            "open-mistral-nemo",
            "mistral-nemo",
            "open-mistral-7b",
            "open-mixtral-8x7b",
            "open-mixtral-8x22b",
        ),
        known_models=(
            "codestral-latest",
            "devstral-small-latest",
            "devstral-medium-latest",
            "mistral-small-latest",
            "ministral-3b-latest",
            "ministral-8b-latest",
            "pixtral-12b-2409",
            "pixtral-12b",
            "open-mistral-nemo",
            "mistral-nemo",
            "open-mistral-7b",
            "open-mixtral-8x7b",
            "open-mixtral-8x22b",
        ),
    ),
    CloudProvider(
        id="github",
        name="GitHub Models",
        base_url="https://models.inference.ai.azure.com",
        signup_url="https://github.com/settings/tokens",
        notes="GPT-4o, Claude and Llama, 15 rpm",
        free_models_all=True,
    ),
    CloudProvider(
        id="gemini",
        name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        kind="gemini",
        signup_url="https://aistudio.google.com/apikey",
        notes="15 rpm / 1500 per day, 1M context, free without a card",
        paid_models=True,
        free_models_all=True,
        known_models=(
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ),
    ),
    CloudProvider(
        id="nvidia",
        name="NVIDIA NIM",
        base_url="https://integrate.api.nvidia.com/v1",
        signup_url="https://build.nvidia.com",
        notes="Nemotron and Llama variants, free developer credits",
        free_models_all=True,
    ),
    CloudProvider(
        id="cloudflare",
        name="Cloudflare Workers AI",
        base_url="https://api.cloudflare.com/client/v4/ai",
        signup_url="https://dash.cloudflare.com",
        notes="10,000 neurons per day, many open models",
        paid_models=True,
        free_models_all=True,
    ),
    CloudProvider(
        id="huggingface",
        name="Hugging Face",
        base_url="https://router.huggingface.co/v1",
        signup_url="https://huggingface.co/settings/tokens",
        notes="100,000+ open models, free monthly credits",
        paid_models=True,
    ),
    CloudProvider(
        id="nebius",
        name="Nebius AI Studio",
        base_url="https://api.studio.nebius.ai/v1",
        signup_url="https://studio.nebius.com",
        notes="free tier with strong open models",
        paid_models=True,
        free_models_all=True,
    ),
    CloudProvider(
        id="siliconflow",
        name="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        signup_url="https://cloud.siliconflow.cn",
        notes="Qwen and DeepSeek, free models, Chinese-first API",
        paid_models=True,
    ),
    CloudProvider(
        id="moonshot",
        name="Moonshot Kimi",
        base_url="https://api.moonshot.cn/v1",
        signup_url="https://platform.moonshot.cn",
        notes="Kimi K2 with a generous free allowance",
        paid_models=True,
    ),
    CloudProvider(
        id="alibaba",
        name="Alibaba DashScope",
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        signup_url="https://bailian.console.aliyun.com",
        notes="Qwen models, free quota in the international region",
        paid_models=True,
    ),
    CloudProvider(
        id="custom",
        name="Custom (OpenAI-compatible)",
        base_url="",
        signup_url="",
        notes="Any OpenAI-compatible endpoint — paste the base URL below",
        free_tier=False,
        paid_models=True,
    ),
)

PROVIDERS_BY_ID = {p.id: p for p in PROVIDERS}


# ---------------------------------------------------------------------- key storage


def _keys_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "TheCore"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_key(provider_id: str, key: str) -> None:
    """Store an API key for a provider."""
    provider = PROVIDERS_BY_ID.get(provider_id)
    if provider is None:
        raise ValueError(f"unknown provider: {provider_id}")
    path = provider.key_path()
    if key:
        path.write_text(key.strip(), encoding="utf-8")
    elif path.exists():
        path.unlink()


def load_key(provider_id: str) -> str:
    """Read the stored API key (empty string when there is none)."""
    provider = PROVIDERS_BY_ID.get(provider_id)
    if provider is None:
        return ""
    path = provider.key_path()
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def has_key(provider_id: str) -> bool:
    return bool(load_key(provider_id))


def _base_url_path() -> Path:
    return _keys_dir() / "custom-base-url.txt"


def save_base_url(url: str) -> None:
    """Store the base URL of the custom OpenAI-compatible endpoint."""
    path = _base_url_path()
    if url:
        path.write_text(url.strip(), encoding="utf-8")
    elif path.exists():
        path.unlink()


def load_base_url() -> str:
    """Read the base URL of the custom endpoint (empty when unset)."""
    path = _base_url_path()
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ---------------------------------------------------------------------- catalogue


def configured_providers() -> list[CloudProvider]:
    """The providers that have an API key stored — the enabled ones."""
    return [p for p in PROVIDERS if has_key(p.id)]


def provider_for(provider_id: str) -> Optional[CloudProvider]:
    """The provider with this id, with the custom base URL applied."""
    provider = PROVIDERS_BY_ID.get(provider_id)
    if provider is None:
        return None
    if provider.id == "custom":
        base_url = load_base_url()
        if not base_url:
            return None
        return replace(provider, base_url=base_url)
    return provider


def list_configured_models(
    timeout_seconds: float = 20.0,
) -> list[CloudModel]:
    """Every model of every provider that has a key stored.

    The models carry the provider they came from, so the UI can show
    ``Provider · model  ● FREE`` and route the answer to the right backend.
    """
    models: list[CloudModel] = []
    for provider in configured_providers():
        resolved = provider_for(provider.id)
        if resolved is None:
            continue
        client = CloudClient(
            provider=resolved,
            api_key=load_key(provider.id),
            timeout_seconds=timeout_seconds,
        )
        models.extend(client.list_models())
    models.sort(key=lambda m: (not m.free, m.provider_name, m.id))
    return models


# ---------------------------------------------------------------------- client


@dataclass
class CloudModel:
    id: str
    label: str = ""
    free: bool = False
    # The provider this model came from — set when the models are gathered
    # from several providers at once.
    provider_id: str = ""
    provider_name: str = ""

    @property
    def display(self) -> str:
        return self.label or self.id

    @property
    def tier_label(self) -> str:
        """``● FREE`` or ``○ PAID``."""
        return "● FREE" if self.free else "○ PAID"


def cloud_capabilities(model_id: str) -> set[str]:
    """Tools, vision and reasoning for a cloud model, judged from its name.

    Cloud providers do not report this the way Ollama does. The same three
    flags the local models use are derived from the id.
    """
    name = (model_id or "").lower()
    caps: set[str] = set()
    blocked = ("embed", "whisper", "tts", "transcri", "rerank", "moderation")
    if not any(mark in name for mark in blocked):
        caps.add("tools")
    vision = (
        "vision", "pixtral", "gpt-4o", "gpt-4.1", "gpt-4-turbo", "gemini",
        "claude", "grok-4", "grok-2", "llama-4", "gemma-3", "qwen-vl",
        "qwen2.5-vl", "llava", "moondream", "internvl",
    )
    if any(mark in name for mark in vision) and "embed" not in name:
        caps.add("vision")
    reasoning = (
        "reason", "think", "qwq", "qwen3", "magistral", "gemini-2.5",
        "-r1", "/r1", "o1", "o3", "o4",
    )
    if any(mark in name for mark in reasoning):
        caps.add("thinking")
    return caps


def catalogue_models(provider: CloudProvider) -> list[CloudModel]:
    """The models shown for a provider before its live list arrives."""
    return [
        CloudModel(
            id=model_id,
            label=model_id,
            free=provider.is_free_model(model_id),
            provider_id=provider.id,
            provider_name=provider.name,
        )
        for model_id in dict.fromkeys((*provider.known_models, *provider.free_ids))
    ]

    @property
    def combo_label(self) -> str:
        """The text shown in the model dropdown."""
        base = self.display
        if self.provider_name:
            base = f"{self.provider_name} · {base}"
        return f"{base}  {self.tier_label}"


@dataclass
class CloudClient:
    """Talks to a free cloud provider."""

    provider: CloudProvider
    api_key: str = ""
    timeout_seconds: float = 60.0

    # ---------------------------------------------------------------- helpers

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.provider.kind != "gemini":
            # Gemini passes its key as ?key= in the URL, not as a Bearer token.
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _gemini_headers(self) -> dict[str, str]:
        """Headers for Gemini requests — no Authorization, key is in the URL."""
        return {"Content-Type": "application/json"}

    def _request(self, url: str, payload: Optional[dict] = None) -> Iterator[dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(),
            method="POST" if data else "GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line or line.startswith(":"):
                    continue
                # OpenAI-style providers (Mistral included) prefix every event.
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    continue
                if not line.startswith("{"):
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    # ---------------------------------------------------------------- models

    def list_models(self) -> list[CloudModel]:
        """The models this provider offers (free ones first)."""
        if not self.api_key:
            return []
        if self.provider.kind == "gemini":
            return self._list_gemini_models()
        try:
            url = f"{self.provider.base_url}/models"
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:240]
            raise RuntimeError(f"HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(str(exc)) from exc

        models: list[CloudModel] = []
        for entry in payload.get("data") or []:
            model_id = str(entry.get("id", ""))
            if not model_id:
                continue
            models.append(
                CloudModel(
                    id=model_id,
                    label=model_id,
                    free=self.provider.is_free_model(model_id),
                    provider_id=self.provider.id,
                    provider_name=self.provider.name,
                )
            )
        models.sort(key=lambda m: (not m.free, m.id))
        return models

    def _list_gemini_models(self) -> list[CloudModel]:
        try:
            url = f"{self.provider.base_url}/models?key={self.api_key}"
            req = urllib.request.Request(
                url, headers=self._gemini_headers(), method="GET"
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return []

        models: list[CloudModel] = []
        for entry in payload.get("models") or []:
            name = str(entry.get("name", ""))
            if not name.startswith("models/"):
                continue
            model_id = name.split("/", 1)[1]
            methods = entry.get("supportedGenerationMethods") or []
            # Accept either generateContent or streamGenerateContent.
            if "generateContent" not in methods and "streamGenerateContent" not in methods:
                continue
            models.append(
                CloudModel(
                    id=model_id,
                    label=model_id,
                    free=self.provider.is_free_model(model_id),
                    provider_id=self.provider.id,
                    provider_name=self.provider.name,
                )
            )
        models.sort(key=lambda m: m.id)
        return models

    # ---------------------------------------------------------------- chat

    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Stream the assistant's reply, chunk by chunk."""
        if self.provider.kind == "gemini":
            yield from self._chat_stream_gemini(model, messages, temperature, max_tokens)
            return

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        url = f"{self.provider.base_url}/chat/completions"
        for event in self._request(url, payload):
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                yield piece

    def _chat_stream_gemini(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        contents = []
        for message in messages:
            role = "user" if message.get("role") == "user" else "model"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": str(message.get("content", ""))}],
                }
            )
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, **(
                {"maxOutputTokens": max_tokens} if max_tokens else {}
            )},
        }
        url = (
            f"{self.provider.base_url}/models/{model}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers=self._gemini_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line:
                    continue
                # SSE frames start with "data: " — strip the prefix.
                if line.startswith("data: "):
                    line = line[6:]
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for candidate in event.get("candidates") or []:
                    for part in (candidate.get("content") or {}).get("parts") or []:
                        piece = part.get("text")
                        if piece:
                            yield piece

    def chat(
        self, model: str, messages: list[dict], temperature: float = 0.7
    ) -> str:
        """A single, non-streaming reply (used for simple checks)."""
        return "".join(self.chat_stream(model, messages, temperature))

    def ping(self, model: str) -> str:
        """A tiny request. Returns the reply, or raises when the model is dead."""
        text = "".join(
            self.chat_stream(
                model,
                [{"role": "user", "content": "Reply with OK."}],
                temperature=0,
                max_tokens=8,
            )
        ).strip()
        if not text:
            raise RuntimeError("empty reply")
        return text
