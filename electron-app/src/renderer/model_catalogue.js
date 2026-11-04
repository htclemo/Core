/**
 * TheCore — the model catalogue (renderer).
 *
 * Mirrors `thecore/ai/model_catalogue.py`: the chat's model dropdown shows
 * **every** model that is available — the local Ollama models *and* the
 * models of every cloud provider that has an API key in the settings.  A
 * cloud model is labelled with its provider and with `● FREE` / `○ PAID`.
 */

/** One selectable model. */
function modelEntry(kind, modelId, providerId, providerName, free, label) {
  return {
    kind: kind, // "local" or "cloud"
    modelId: modelId,
    providerId: providerId || "",
    providerName: providerName || "",
    free: !!free,
    label: label || modelId,
  };
}

/** The text shown in the dropdown. */
function modelEntryDisplay(entry) {
  if (entry.kind === "cloud") {
    const tier = entry.free ? "● FREE" : "○ PAID";
    return `${entry.providerName} · ${entry.modelId}  ${tier}`;
  }
  return entry.label || entry.modelId;
}

/** The value of the <option> — unique across the whole catalogue. */
function modelEntryKey(entry) {
  return entry.kind === "cloud"
    ? `cloud:${entry.providerId}:${entry.modelId}`
    : `local:${entry.modelId}`;
}

/**
 * The dropdown contents: an array of {header, entry}.
 *
 * The cloud models are grouped per provider and the free ones come first.
 */
function buildCatalogue(localModels, cloudModels, kind) {
  const rows = [];

  if (kind !== "cloud" && localModels && localModels.length) {
    rows.push({ header: "LOCAL", entry: null });
    for (const m of localModels) {
      rows.push({
        header: "",
        entry: modelEntry("local", m.name, "", "", false, m.name),
      });
    }
  }

  if (kind !== "local") {
    const grouped = new Map();
    for (const m of cloudModels || []) {
      const key = m.providerId || "";
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(m);
    }

    for (const [providerId, models] of grouped.entries()) {
      if (!models.length) continue;
      const providerName = models[0].providerName || providerId || "CLOUD";
      rows.push({ header: providerName.toUpperCase(), entry: null });
      models.sort(
        (a, b) => Number(b.free) - Number(a.free) || a.id.localeCompare(b.id)
      );
      for (const m of models) {
        rows.push({
          header: "",
          entry: modelEntry(
            "cloud",
            m.id,
            providerId,
            providerName,
            m.free,
            m.label
          ),
        });
      }
    }
  }

  return rows;
}

/** Fill a <select> with the catalogue, using <optgroup> per section. */
function fillModelCombo(select, rows) {
  const previous = select.value;
  select.innerHTML = "";

  let group = null;
  for (const row of rows) {
    if (row.header) {
      group = document.createElement("optgroup");
      group.label = row.header;
      select.appendChild(group);
      continue;
    }
    const option = document.createElement("option");
    option.value = modelEntryKey(row.entry);
    option.textContent = modelEntryDisplay(row.entry);
    option.dataset.kind = row.entry.kind;
    option.dataset.modelId = row.entry.modelId;
    option.dataset.providerId = row.entry.providerId;
    option.dataset.providerName = row.entry.providerName;
    option.dataset.free = row.entry.free ? "1" : "";
    if (group) {
      group.appendChild(option);
    } else {
      select.appendChild(option);
    }
  }

  // Keep the previous pick when it is still there.
  if (previous) {
    const match = select.querySelector(`option[value="${CSS.escape(previous)}"]`);
    if (match) select.value = previous;
  }
  return select.value;
}

/** The entry of the picked option (null when there is none). */
function selectedModelEntry(select) {
  const option = select.selectedOptions && select.selectedOptions[0];
  if (!option || !option.dataset || !option.dataset.kind) return null;
  return modelEntry(
    option.dataset.kind,
    option.dataset.modelId,
    option.dataset.providerId,
    option.dataset.providerName,
    option.dataset.free === "1",
    option.dataset.modelId
  );
}
