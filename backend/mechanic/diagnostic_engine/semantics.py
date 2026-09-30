"""Reusable component and complaint concepts for deterministic classification."""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re

from .normalizer import normalize_text


@dataclass(frozen=True)
class IntentProfile:
    components: tuple[str, ...]
    complaints: tuple[str, ...]
    required_components: tuple[str, ...] = ()
    required_complaints: tuple[str, ...] = ()
    related_components: tuple[str, ...] = ()
    complaint_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentInterpretation:
    component: str | None
    complaint: str | None
    confidence: float
    evidence: tuple[str, ...]
    conflicting_components: tuple[str, ...]


@dataclass(frozen=True)
class SemanticEvidence:
    components: dict[str, float]
    complaints: dict[str, float]
    interpretation: ComponentInterpretation
    negated_complaints: dict[str, float] = field(default_factory=dict)


COMPONENT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "brakes": ("brake", "brakes", "braking", "stopping", "brake pedal"),
    "tires": ("tire", "tyre", "wheel"),
    "battery": ("battery", "charging"),
    "alternator": ("alternator",),
    "engine": ("engine", "motor"),
    "cooling_system": ("coolant", "antifreeze", "radiator", "cooling system"),
    "oil": ("oil",),
    "transmission": ("transmission", "gearbox", "gear", "shifting"),
    "clutch": ("clutch",),
    "steering": ("steering", "steering wheel"),
    "suspension": ("suspension",),
    "exhaust": ("exhaust", "tailpipe"),
    "ac": ("ac", "air conditioning", "air conditioner"),
    "fuel_system": ("fuel", "fuel pump", "gasoline"),
    "dashboard": ("dashboard", "dash", "check engine", "engine light"),
    "lights": ("lights", "headlight", "headlights", "tail light", "tail lights", "brake light", "brake lights", "indicator", "turn signal", "fog light", "fog lights", "warning light"),
    "horn": ("horn",),
    "wipers": ("wiper", "wipers", "windshield wiper"),
    "windshield": ("windshield",),
    "windows": ("window", "windows"),
    "doors": ("door", "doors"),
    "mirrors": ("mirror", "mirrors"),
    "seatbelt": ("seatbelt", "seat belt"),
    "starting_system": ("starter", "starter motor", "ignition", "crank", "cranking"),
}

_RELATED_COMPONENT_CONTEXT = {"steering": ("wheel",)}
_COMPONENT_COMPLAINT_CONTEXT = {"brakes": ("noise", "squeal", "grinding")}


COMPLAINT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "failure": ("broken", "does not work", "do not work", "not working", "stopped working", "will not stop", "not usable", "cannot", "failed", "useless", "dead", "weak"),
    "no_start": ("will not start", "does not start", "cannot start", "refuses to start", "not start", "will not crank", "does not crank", "cannot crank", "no crank", "nothing happens", "cranks but"),
    "clicking": ("click", "clicking", "rapid clicks"),
    "overheating": ("overheat", "overheating", "temperature high", "in the red"),
    "noise": ("noise", "sound", "squeal", "squeaking", "grind", "grinding", "scraping"),
    "squeal": ("squeal", "squeaking", "squeak"),
    "grinding": ("grind", "grinding", "scraping"),
    "vibration": ("vibration", "vibrate", "shaking", "shake", "wobble", "judder"),
    "pulling": ("pull", "pulling", "drift", "one side"),
    "flat": ("flat", "blowout"),
    "low_pressure": ("low pressure", "low", "underinflated", "no air", "tire light"),
    "puncture_damage": ("puncture", "punctured", "nail", "screw", "cut", "bulge", "sidewall damage", "damaged"),
    "warning_light": ("warning light", "battery light", "charging light", "engine light"),
    "leaking": ("leak", "leaking", "drip", "dripping", "puddle"),
    "smoke": ("smoke", "smoking", "steam"),
    "not_cooling": ("not cooling", "not cold", "warm air", "hot air"),
    "slipping": ("slipping", "slips", "delayed shifting", "harsh shifting"),
    "generic_problem": ("problem", "issue", "wrong", "something is wrong"),
}


RULE_INTENTS: dict[str, IntentProfile] = {
    "no_start": IntentProfile(("starting_system", "engine"), ("no_start",), required_complaints=("no_start",), related_components=("dashboard", "lights")),
    "starting_click": IntentProfile(("starting_system", "battery"), ("clicking",), required_components=("starting_system",), required_complaints=("clicking",), related_components=("dashboard", "lights")),
    "engine_overheat": IntentProfile(("engine", "cooling_system"), ("overheating", "smoke"), required_components=("engine",), required_complaints=("overheating",)),
    "engine_noise": IntentProfile(("engine",), ("noise",), required_components=("engine",), required_complaints=("noise",)),
    "brake_failure": IntentProfile(("brakes",), ("failure",), required_components=("brakes",), required_complaints=("failure",)),
    "steering_failure": IntentProfile(("steering",), ("failure",), required_components=("steering",), required_complaints=("failure",)),
    "brake_noise": IntentProfile(("brakes",), ("noise", "squeal", "grinding"), required_components=("brakes",), required_complaints=("noise",)),
    "check_engine_light": IntentProfile(("engine", "dashboard", "lights"), ("warning_light", "failure"), required_components=("dashboard",), required_complaints=("warning_light",)),
    "brake_pull_vibration": IntentProfile(("brakes",), ("vibration", "pulling"), required_components=("brakes",), required_complaints=("vibration",), related_components=("steering",)),
    "tire_pressure": IntentProfile(("tires",), ("flat", "low_pressure", "puncture_damage", "failure"), required_components=("tires",), complaint_options=("flat", "low_pressure", "puncture_damage", "failure")),
    "battery_warning": IntentProfile(("battery", "alternator"), ("failure", "warning_light", "clicking"), required_components=("battery",), related_components=("dashboard", "lights")),
    "oil_leak": IntentProfile(("oil",), ("leaking",), required_components=("oil",), required_complaints=("leaking",)),
    "steering_vibration": IntentProfile(("steering",), ("vibration",), required_components=("steering",), required_complaints=("vibration",)),
    "exhaust_smoke": IntentProfile(("exhaust",), ("smoke",), required_components=("exhaust",), required_complaints=("smoke",)),
    "ac_not_cooling": IntentProfile(("ac",), ("not_cooling",), required_components=("ac",), required_complaints=("not_cooling",)),
}


def extract_semantics(text: str) -> SemanticEvidence:
    normalized = normalize_text(text)
    complaints, negated_complaints = _score_complaints(normalized)
    components = _score_component_concepts(normalized, complaints)
    ordered_components = sorted(components.items(), key=lambda item: item[1], reverse=True)
    primary_component = ordered_components[0][0] if ordered_components else None
    second_score = ordered_components[1][1] if len(ordered_components) > 1 else 0.0
    primary_score = ordered_components[0][1] if ordered_components else 0.0
    confidence = (
        min(0.99, primary_score / (primary_score + second_score + 0.5))
        if primary_component
        else 0.0
    )
    conflicting = tuple(
        component for component, score in ordered_components[1:]
        if primary_score - score < 0.35
    )
    complaint = max(complaints, key=complaints.get) if complaints else None
    return SemanticEvidence(
        components,
        complaints,
        ComponentInterpretation(
            primary_component,
            complaint,
            confidence,
            tuple(f"component:{component}" for component in components),
            conflicting,
        ),
        negated_complaints,
    )


def _score_component_concepts(text: str, complaints: dict[str, float]) -> dict[str, float]:
    scores: dict[str, float] = {}
    steering_context = _fuzzy_token_present("steering", text)
    for component, aliases in COMPONENT_CONCEPTS.items():
        score = 0.0
        for alias in aliases:
            normalized_alias = normalize_text(alias)
            if normalized_alias == "wheel" and (re.search(r"\bsteering wheel\b", text) or steering_context):
                continue
            if component == "brakes" and re.search(r"\bbrake lights?\b", text):
                continue
            if _vocabulary_alias_present(normalized_alias, text):
                score = max(score, 1.0 + min(len(normalized_alias.split()), 3) * 0.1)
            elif " " not in normalized_alias and len(normalized_alias) >= 5:
                if _fuzzy_token_present(normalized_alias, text):
                    score = max(score, 0.8)
        related_terms = _RELATED_COMPONENT_CONTEXT.get(component, ())
        if score and any(re.search(rf"\b{re.escape(term)}\b", text) for term in related_terms):
            score += 0.5
        if score and component in _COMPONENT_COMPLAINT_CONTEXT:
            score += 0.7 * sum(
                complaints.get(complaint, 0.0)
                for complaint in _COMPONENT_COMPLAINT_CONTEXT[component]
            )
        if score:
            scores[component] = score
    return scores


def _fuzzy_token_present(term: str, text: str) -> bool:
    forms = _vocabulary_forms(term)
    return any(
        len(token) >= 5
        and any(SequenceMatcher(None, form, token).ratio() >= 0.82 for form in forms)
        for token in text.split()
    )


def _vocabulary_alias_present(alias: str, text: str) -> bool:
    pattern = "|".join(
        rf"\b{re.escape(form)}\b" for form in _vocabulary_forms(alias)
    )
    return bool(re.search(pattern, text))


def _vocabulary_forms(alias: str) -> tuple[str, ...]:
    """Return scoped singular/plural forms for a known vocabulary alias."""
    words = alias.split()
    if not words:
        return ()
    last = words[-1]
    if len(last) <= 2:
        return (alias,)

    singular = last
    if last.endswith("ies") and len(last) > 3:
        singular = f"{last[:-3]}y"
    elif last.endswith(("ses", "xes", "zes", "ches", "shes")):
        singular = last[:-2]
    elif last.endswith("s") and not last.endswith("ss"):
        singular = last[:-1]

    plural = f"{singular}ies" if singular.endswith("y") else f"{singular}s"
    forms = {alias, " ".join((*words[:-1], singular)), " ".join((*words[:-1], plural))}
    return tuple(sorted(forms, key=lambda item: (len(item.split()), len(item))))


def _score_concepts(text: str, concepts: dict[str, tuple[str, ...]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for concept, aliases in concepts.items():
        score = 0.0
        for alias in aliases:
            normalized_alias = normalize_text(alias)
            if normalized_alias == "wheel" and re.search(r"\bsteering wheel\b", text):
                continue
            if re.search(rf"\b{re.escape(normalized_alias)}\b", text):
                score = max(score, 1.0 + min(len(normalized_alias.split()), 3) * 0.1)
        if score:
            scores[concept] = score
    return scores


_NEGATABLE_COMPLAINTS = {
    "broken", "failed", "dead", "weak", "low", "flat", "damaged", "leak", "leaking",
    "smoke", "smoking", "slipping", "vibration", "shaking", "pulling", "noise", "sound",
}


def _score_complaints(text: str) -> tuple[dict[str, float], dict[str, float]]:
    positive: dict[str, float] = {}
    negated: dict[str, float] = {}
    for concept, aliases in COMPLAINT_CONCEPTS.items():
        for alias in aliases:
            normalized_alias = normalize_text(alias)
            if concept == "no_start" and normalized_alias == "nothing happens" and not re.search(
                r"\b(?:start|starting|key|crank|turn on)\b", text
            ):
                continue
            if not re.search(rf"\b{re.escape(normalized_alias)}\b", text):
                continue
            score = 1.0 + min(len(normalized_alias.split()), 3) * 0.1
            if normalized_alias in _NEGATABLE_COMPLAINTS and _is_negated(text, normalized_alias):
                negated[concept] = max(negated.get(concept, 0.0), score)
            else:
                positive[concept] = max(positive.get(concept, 0.0), score)
    return positive, negated


def _is_negated(text: str, phrase: str) -> bool:
    tokens = text.split()
    phrase_tokens = phrase.split()
    for index in range(len(tokens) - len(phrase_tokens) + 1):
        if tokens[index:index + len(phrase_tokens)] != phrase_tokens:
            continue
        window = tokens[max(0, index - 3):index]
        if any(token in {"not", "never", "no", "without", "cannot", "wont", "doesnt", "isnt"} for token in window):
            return True
    return False