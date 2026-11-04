/**
 * TheCore — recovering tool calls from plain text (Electron renderer).
 *
 * Small models often ignore Ollama's structured `tool_calls` field and print
 * the JSON as ordinary text instead.  These helpers recognise that and take it
 * out of the answer again.
 *
 * Mirrors `thecore/ai/tools.py`.
 */

const STOP_WORDS = new Set([
  "a", "about", "after", "all", "also", "am", "an", "and", "any", "are", "as",
  "at", "be", "been", "being", "but", "by", "can", "could", "did", "do",
  "does", "doing", "done", "for", "from", "get", "give", "had", "has", "have",
  "he", "her", "here", "him", "his", "how", "i", "if", "in", "into", "is",
  "it", "its", "just", "know", "like", "make", "me", "mean", "more", "most",
  "much", "my", "need", "no", "not", "of", "on", "one", "only", "or", "other",
  "our", "out", "over", "please", "same", "shall", "she", "should", "show",
  "so", "some", "something", "tell", "than", "that", "the", "their", "them",
  "then", "there", "these", "they", "thing", "things", "this", "those",
  "through", "to", "too", "under", "up", "use", "using", "very", "was", "we",
  "well", "were", "what", "when", "where", "which", "while", "who", "whom",
  "why", "will", "with", "would", "you", "your",
]);

const GENERIC_WORDS = new Set([
  "answer", "best", "color", "colour", "difference", "example", "first",
  "function", "idea", "kind", "made", "make", "manner", "meaning",
  "method", "model", "name", "part", "point", "problem", "question", "reason",
  "result", "sort", "step", "stuff", "system", "test", "thing", "things",
  "time", "type", "value", "way", "ways", "word", "words", "work", "year",
  "bug", "error", "issue",
]);

/** Recover tool calls a model wrote as plain text. */
export function parseToolCalls(content) {
  if (!content) return [];
  const text = String(content).trim();
  if (!text) return [];

  const candidates = [];
  if (text.includes("<tool_call>")) {
    const matches = text.match(/<tool_call>([\s\S]*?)<\/tool_call>/g) || [];
    for (const match of matches) {
      candidates.push(match.replace(/<tool_call>|<\/tool_call>/g, "").trim());
    }
  } else if (text.includes("```")) {
    const matches = text.match(/```(?:json)?\s*([\s\S]*?)```/g) || [];
    for (const match of matches) {
      candidates.push(match.replace(/```(?:json)?/g, "").trim());
    }
  } else {
    candidates.push(text);
  }

  const calls = [];
  for (const candidate of candidates) {
    for (const raw of splitJsonObjects(candidate)) {
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch {
        continue;
      }
      if (!payload || typeof payload !== "object") continue;
      let name = payload.name || payload.function;
      if (name && typeof name === "object") name = name.name;
      if (typeof name !== "string" || !name) continue;
      let args = payload.arguments;
      if (args == null) args = payload.parameters || payload.args || {};
      if (typeof args === "string") {
        try {
          args = JSON.parse(args);
        } catch {
          args = { value: args };
        }
      }
      calls.push({
        type: "function",
        function: { name, arguments: args || {} },
      });
    }
  }
  return calls;
}

/** Split a text into its top-level JSON objects. */
function splitJsonObjects(text) {
  const parts = [];
  let index = 0;
  while (index < text.length) {
    const start = text.indexOf("{", index);
    if (start === -1) break;
    // Find the matching closing brace.
    let depth = 0;
    let end = -1;
    let inString = false;
    let escaped = false;
    for (let i = start; i < text.length; i++) {
      const ch = text[i];
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === '"') {
        inString = !inString;
        continue;
      }
      if (inString) continue;
      if (ch === "{") depth++;
      else if (ch === "}") {
        depth--;
        if (depth === 0) {
          end = i + 1;
          break;
        }
      }
    }
    if (end === -1) break;
    parts.push(text.slice(start, end));
    index = end;
  }
  return parts;
}

/** Remove tool-call JSON that a model printed as plain text. */
export function stripToolCallsFromContent(content) {
  if (!content) return content;
  let text = String(content);
  text = text.replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/g, "");
  text = text.replace(/<tool_call>[\s\S]*?<\/tool_call>/g, "");

  const out = [];
  let index = 0;
  while (index < text.length) {
    const start = text.indexOf("{", index);
    if (start === -1) {
      out.push(text.slice(index));
      break;
    }
    out.push(text.slice(index, start));
    const parts = splitJsonObjects(text.slice(start));
    const raw = parts[0];
    if (!raw) {
      out.push(text[start]);
      index = start + 1;
      continue;
    }
    let payload = null;
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = null;
    }
    const name =
      payload && typeof payload === "object"
        ? payload.name || payload.function
        : null;
    const isToolCall =
      payload &&
      typeof payload === "object" &&
      ((typeof name === "string" && name) ||
        (name && typeof name === "object" && name.name));
    if (isToolCall) {
      index = start + raw.length; // drop it
    } else {
      out.push(raw);
      index = start + raw.length;
    }
  }
  return out.join("").trim();
}
