"""Deterministic, rule-based automotive diagnostic engine."""

from .matcher import DiagnosticEngine, DiagnosticMatchResult, MatchStatus

__all__ = ["DiagnosticEngine", "DiagnosticMatchResult", "MatchStatus"]