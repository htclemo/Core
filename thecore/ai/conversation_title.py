"""Derive a short, meaningful title for a conversation from its first question.

A new conversation starts as "New Conversation"; as soon as the first question
is asked it is renamed after the subject of that question::

    "what is the color of a house mouse"  ->  "Mouse"
    "what is a tesla model s?"            ->  "Tesla"
    "how do I install python"              ->  "Python"

The subject of an English question usually comes last ("the colour of a house
**mouse**"), so the search runs backwards.  Words that say nothing on their own
("model", "colour", "thing") and question words are skipped.
"""

from __future__ import annotations

import re

# Words that never carry the subject of a question.
_STOP_WORDS = {
    # English
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
    # Dutch
    "aan", "al", "als", "bij", "dan", "dat", "de", "der", "deze", "die", "dit",
    "door", "een", "en", "er", "geen", "haar", "heb", "heeft", "het", "hoe",
    "ik", "in", "is", "je", "kan", "kun", "maar", "me", "meer", "met", "mij",
    "mijn", "moet", "na", "naar", "niet", "nog", "nu", "of", "om", "ons",
    "ook", "op", "over", "te", "tot", "uit", "van", "veel", "voor", "waar",
    "wanneer", "wat", "we", "wel", "werd", "wezen", "wie", "wij", "wil",
    "worden", "wordt", "zal", "ze", "zijn", "zo", "zonder", "zou",
}

# Words that are grammatically the subject but say nothing on their own.
_GENERIC_WORDS = {
    "answer", "best", "color", "colour", "difference", "example", "first",
    "function", "idea", "kind", "made", "make", "manner", "meaning",
    "method", "model", "name", "part", "point", "problem", "question", "reason",
    "result", "sort", "step", "stuff", "system", "test", "thing", "things",
    "time", "type", "value", "way", "ways", "word", "words", "work", "year",
    "bug", "error", "issue", "problem",
    "verschil", "kleur", "naam", "voorbeeld", "ding", "dingen", "manier",
    "vraag", "antwoord", "tijd", "jaar", "dag", "deel", "stap",
}

# Verbs that often end a question.  They describe the *action*, not the
# subject, so they must not become the title.
_TRAILING_VERBS = {
    "work", "works", "worked", "help", "helps", "do", "does", "make", "makes",
    "write", "writes", "create", "creates", "build", "builds", "get", "gets",
    "set", "sets", "run", "runs", "start", "starts", "stop", "stops", "show",
    "shows", "explain", "explains", "install", "installs", "sort", "sorts",
    "fix", "fixes", "add", "adds", "remove", "removes", "find", "finds",
    "tell", "tells", "give", "gives", "take", "takes", "need", "needs", "know",
    "knows", "mean", "means", "happen", "happens", "called", "used", "based",
    "possible", "happening", "solve", "solves", "change", "changes", "convert",
    "converts", "generate", "generates", "implement", "implements", "handle",
    "handles", "mean", "happen",
}

# Punctuation that separates words.
_SEPARATORS = re.compile(r"[^0-9A-Za-zÀ-ÿ'’]+")


def _words(text: str) -> list[str]:
    """Split a question into plain words."""
    cleaned = _SEPARATORS.sub(" ", text or "")
    return [word for word in cleaned.split() if word]


def title_from_question(text: str, fallback: str = "New Chat") -> str:
    """Build a short title from the first question of a conversation.

    Returns the subject of the question — "Mouse" for "what is the color of a
    house mouse" — or a short excerpt when no single word stands out.
    """
    words = _words(text)
    if not words:
        return fallback

    lowered = [word.lower() for word in words]

    # Walk backwards: the subject of a question usually comes last.
    for index in range(len(words) - 1, -1, -1):
        word = lowered[index]
        if len(word) < 3:
            continue
        if word in _STOP_WORDS or word in _GENERIC_WORDS or word in _TRAILING_VERBS:
            continue
        if word.isdigit():
            continue
        return words[index].capitalize()

    # Nothing distinctive — take the longest remaining word.
    candidates = [
        (len(w), w) for w in lowered
        if len(w) >= 3 and w not in _STOP_WORDS
    ]
    if candidates:
        best = max(candidates)[1]
        return words[lowered.index(best)].capitalize()

    # Last resort: a short excerpt of the question itself — but only when it
    # actually says something.
    excerpt = [w for w in words if w.lower() not in _STOP_WORDS]
    if not excerpt:
        return fallback
    return " ".join(excerpt[:4])[:40]
