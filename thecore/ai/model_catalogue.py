"""The model catalogue: every model the user can pick, in one list.

The chat's model dropdown shows **all** of them — the local Ollama models
*and* the models of every cloud provider that has an API key in the
settings.  Each cloud model carries its provider and a ``● FREE`` / ``○ PAID``
label, so it is obvious what a turn will cost before it is sent.

The same shape is mirrored in the Electron app
(``electron-app/src/renderer/model_catalogue.js``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class ModelEntry:
    """One selectable model."""

    kind: str  # "local" or "cloud"
    model_id: str
    provider_id: str = ""
    provider_name: str = ""
    free: bool = False
    label: str = ""
    size_gb: float = 0.0

    @property
    def display(self) -> str:
        """The text shown in the dropdown."""
        if self.kind == "cloud":
            tier = "● FREE" if self.free else "○ PAID"
            name = self.label or self.model_id
            return f"{name}  {tier}"
        return self.label or self.model_id

    @property
    def is_local(self) -> bool:
        return self.kind == "local"


def local_entry(name: str, size_gb: float = 0.0) -> ModelEntry:
    """A local Ollama model."""
    return ModelEntry(kind="local", model_id=name, label=name, size_gb=size_gb)


def cloud_entry(
    model_id: str,
    provider_id: str,
    provider_name: str,
    free: bool,
    label: str = "",
) -> ModelEntry:
    """A model that lives in the cloud."""
    return ModelEntry(
        kind="cloud",
        model_id=model_id,
        provider_id=provider_id,
        provider_name=provider_name,
        free=free,
        label=label or model_id,
    )


@dataclass(frozen=True)
class CatalogueRow:
    """One row of the dropdown: a section header or a model."""

    header: str = ""
    entry: Optional[ModelEntry] = None

    @property
    def is_header(self) -> bool:
        return self.entry is None


def build_entries(
    local_models: Sequence = (),
    cloud_models: Sequence = (),
) -> list[CatalogueRow]:
    """The dropdown contents.

    The cloud models are grouped per provider and the free ones come first.
    """
    rows: list[CatalogueRow] = []

    if local_models:
        rows.append(CatalogueRow(header="LOCAL"))
        for model in local_models:
            rows.append(
                CatalogueRow(
                    entry=local_entry(
                        getattr(model, "name", str(model)),
                        float(getattr(model, "size_gb", 0.0) or 0.0),
                    )
                )
            )

    # Group the cloud models per provider, free ones first.
    grouped: dict[str, list] = {}
    for model in cloud_models:
        grouped.setdefault(model.provider_id or "", []).append(model)

    for provider_id, models in grouped.items():
        if not models:
            continue
        provider_name = models[0].provider_name or provider_id or "CLOUD"
        rows.append(CatalogueRow(header=provider_name.upper()))
        for model in sorted(
            models,
            key=lambda m: (not m.free, getattr(m, "id", "") or getattr(m, "model_id", "")),
        ):
            rows.append(
                CatalogueRow(
                    entry=cloud_entry(
                        getattr(model, "id", "") or getattr(model, "model_id", ""),
                        provider_id,
                        provider_name,
                        bool(model.free),
                        getattr(model, "label", "") or "",
                    )
                )
            )

    return rows
