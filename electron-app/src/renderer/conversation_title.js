/* TheCore — automatic conversation names (Electron renderer).
 *
 * A new conversation is named after the subject of its first question:
 *
 *   "what is the color of a house mouse"  ->  "Mouse"
 *   "what is a tesla model s?"            ->  "Tesla"
 *
 * The subject of an English question usually comes last, so the search runs
 * backwards; question words, generic words and trailing verbs are skipped.
 */

const TITLE_STOP_WORDS = new Set([
  // English
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
  // Dutch
  "aan", "al", "als", "bij", "dan", "dat", "de", "der", "deze", "die", "dit",
  "door", "een", "en", "er", "geen", "haar", "heb", "heeft", "het", "hoe",
  "ik", "in", "is", "je", "kan", "kun", "maar", "me", "meer", "met", "mij",
  "mijn", "moet", "na", "naar", "niet", "nog", "nu", "of", "om", "ons",
  "ook", "op", "over", "te", "tot", "uit", "van", "veel", "voor", "waar",
  "wanneer", "wat", "we", "wel", "werd", "wezen", "wie", "wij", "wil",
  "worden", "wordt", "zal", "ze", "zijn", "zo", "zonder", "zou",
]);

const TITLE_GENERIC_WORDS = new Set([
  "answer", "best", "color", "colour", "difference", "example", "first",
  "function", "idea", "kind", "made", "make", "manner", "meaning",
  "method", "model", "name", "part", "point", "problem", "question", "reason",
  "result", "sort", "step", "stuff", "system", "test", "thing", "things",
  "time", "type", "value", "way", "ways", "word", "words", "work", "year",
  "bug", "error", "issue",
  "verschil", "kleur", "naam", "voorbeeld", "ding", "dingen", "manier",
  "vraag", "antwoord", "tijd", "jaar", "dag", "deel", "stap",
]);

const TITLE_TRAILING_VERBS = new Set([
  "work", "works", "worked", "help", "helps", "do", "does", "make", "makes",
  "write", "writes", "create", "creates", "build", "builds", "get", "gets",
  "set", "sets", "run", "runs", "start", "starts", "stop", "stops", "show",
  "shows", "explain", "explains", "install", "installs", "sort", "sorts",
  "fix", "fixes", "add", "adds", "remove", "removes", "find", "finds",
  "tell", "tells", "give", "gives", "take", "takes", "need", "needs", "know",
  "knows", "mean", "means", "happen", "happens", "called", "used", "based",
  "possible", "solve", "solves", "change", "changes", "convert", "converts",
  "generate", "generates", "implement", "implements", "handle", "handles",
]);

function titleFromQuestion(text, fallback = "New Chat") {
  const words = String(text || "")
    .split(/[^0-9A-Za-zÀ-ÿ'’]+/)
    .filter(Boolean);
  if (!words.length) return fallback;

  const lowered = words.map((w) => w.toLowerCase());

  // Walk backwards: the subject of a question usually comes last.
  for (let i = words.length - 1; i >= 0; i--) {
    const word = lowered[i];
    if (word.length < 3) continue;
    if (TITLE_STOP_WORDS.has(word)) continue;
    if (TITLE_GENERIC_WORDS.has(word)) continue;
    if (TITLE_TRAILING_VERBS.has(word)) continue;
    if (/^\d+$/.test(word)) continue;
    return words[i].charAt(0).toUpperCase() + words[i].slice(1);
  }

  // Nothing distinctive — take the longest remaining word.
  let best = null;
  for (let i = 0; i < lowered.length; i++) {
    const word = lowered[i];
    if (word.length < 3 || TITLE_STOP_WORDS.has(word)) continue;
    if (!best || word.length > best.length) best = word;
  }
  if (best) {
    const index = lowered.indexOf(best);
    return words[index].charAt(0).toUpperCase() + words[index].slice(1);
  }

  // Last resort: a short excerpt — but only when it actually says something.
  const excerpt = words.filter((w) => !TITLE_STOP_WORDS.has(w.toLowerCase()));
  if (!excerpt.length) return fallback;
  return excerpt.slice(0, 4).join(" ").slice(0, 40);
}
