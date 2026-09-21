"""Search normalisation that works across Cyrillic and Latin spellings.

Macedonian names get typed in either script, with or without diacritics:
"Петровски", "Petrovski"; "Ѓорѓиевски", "Gjorgjievski", "Đorđievski", "gorgievski".
Both the stored text and the search query are reduced to the same loose ASCII form,
so any of those spellings finds the others.
"""

from __future__ import annotations

import re
import unicodedata

# Macedonian (and Serbian) Cyrillic → standard Latin transliteration.
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ѓ": "gj", "ђ": "gj", "е": "e",
    "ж": "zh", "з": "z", "ѕ": "dz", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj",
    "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "ќ": "kj", "ћ": "kj", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "џ": "dzh",
    "ш": "sh",
}  # fmt: skip

# Latin letters with diacritics → the same ASCII spelling as the Cyrillic map.
_LATIN = {
    "ž": "zh", "š": "sh", "č": "ch", "ć": "kj", "đ": "gj", "ǵ": "gj", "ḱ": "kj",
    "ѐ": "e", "ѝ": "i",
}  # fmt: skip

# Loose form: digraphs collapse to one letter so "zivko" matches "zhivko".
_LOOSE = (
    ("dzh", "dz"), ("zh", "z"), ("sh", "s"), ("ch", "c"), ("kj", "k"), ("gj", "g"),
    ("lj", "l"), ("nj", "n"),
)  # fmt: skip

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def transliterate(text: str) -> str:
    """Lower-case ASCII transliteration of Cyrillic/Latin text."""
    out = []
    for char in text.lower():
        mapped = _CYRILLIC.get(char) or _LATIN.get(char)
        if mapped is None:
            # Strip any remaining accents (é → e); drop what can't be represented.
            decomposed = unicodedata.normalize("NFKD", char)
            mapped = "".join(c for c in decomposed if not unicodedata.combining(c))
            mapped = mapped.encode("ascii", "ignore").decode()
        out.append(mapped)
    return "".join(out)


def normalize_search(text: str) -> str:
    """Loose, script-independent form used for both stored text and queries."""
    value = transliterate(text or "")
    for digraph, single in _LOOSE:
        value = value.replace(digraph, single)
    return _NON_ALNUM.sub(" ", value).strip()


def search_terms(query: str) -> list[str]:
    """Split a query into normalised words (all of which must match)."""
    return [term for term in normalize_search(query).split() if term]


def digits_only(text: str) -> str:
    return "".join(c for c in text or "" if c.isdigit())
