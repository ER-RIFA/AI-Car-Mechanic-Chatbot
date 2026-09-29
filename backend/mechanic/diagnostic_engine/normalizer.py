"""Small, dependency-free text normalization helpers for diagnostic matching."""

import re


_CONTRACTIONS = {
    "can't": "cannot",
    "couldn't": "could not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "wasn't": "was not",
    "won't": "will not",
    "wouldn't": "would not",
}

_VARIATIONS = {
    "automobile": "car",
    "auto": "car",
    "truck": "vehicle",
    "van": "vehicle",
    "motor vehicle": "vehicle",
    "engine will not start": "engine start",
    "engine does not start": "engine start",
    "engine will not turn on": "engine start",
    "does not turn on": "does not start",
    "won't turn on": "will not start",
    "will not turn on": "will not start",
    "starting issue": "start problem",
    "starting problem": "start problem",
    "no start": "not start",
    "turning over": "cranking",
    "turn over": "crank",
    "check engine": "engine light",
    "service engine": "engine light",
    "low tyre": "low tire",
    "tyre pressure": "tire pressure",
    "flat tyre": "flat tire",
    "air conditioner": "ac",
    "air conditioning": "ac",
    "brake pedal": "brakes",
    "braking": "brakes",
    "overheating": "overheat",
    "overheated": "overheat",
    "shaking": "vibration",
    "shakes": "vibration",
    "vibrating": "vibration",
    "vibrates": "vibration",
    "vibrated": "vibration",
    "oil dripping": "oil leak",
    "oil drips": "oil leak",
    "smoke coming out": "smoke",
    "cool air": "cold air",
}


def normalize_text(text: str) -> str:
    """Return lowercase, whitespace-normalized text with common variants unified."""
    if not isinstance(text, str):
        return ""

    normalized = text.lower()
    for contraction, expansion in _CONTRACTIONS.items():
        normalized = normalized.replace(contraction, expansion)

    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    for variation, canonical in sorted(_VARIATIONS.items(), key=lambda item: -len(item[0])):
        normalized = re.sub(rf"\b{re.escape(variation)}\b", canonical, normalized)

    return re.sub(r"\s+", " ", normalized).strip()


def text_from_context(context: object) -> str:
    """Flatten user-provided context values into text used for signal detection."""
    if not isinstance(context, dict):
        return ""

    values = []
    for key, value in context.items():
        if isinstance(value, dict):
            values.append(text_from_context(value))
        elif isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value)
        elif value not in (None, "", False):
            values.extend((str(key), str(value)))
    return normalize_text(" ".join(values))