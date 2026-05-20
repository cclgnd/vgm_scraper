"""
Canonical console classification for acquisition and catalog boundaries.

Source adapters should pass the strongest context they have (source console
page, archive filename, detail title). This module turns that noisy context into
one catalog console without relying on unsafe substring matches.
"""

from dataclasses import dataclass, field
import re

from vgm_scraper.config import CONSOLE_CANONICAL


@dataclass(frozen=True)
class ConsoleMatch:
    """Result of matching source text to a canonical catalog console."""

    slug: str
    canonical_name: str
    maker: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    @property
    def is_known(self) -> bool:
        return self.slug != "unknown"


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def classify_console(*contexts: str) -> ConsoleMatch:
    """Classify a console from ordered source contexts.

    Context order matters: callers should pass authoritative source metadata
    before weaker title/filename hints. Matching is token/phrase based, never a
    raw substring, so short aliases like "nes" cannot match inside "genesis".
    """

    for context_index, raw in enumerate(contexts):
        text = normalize_context(raw)
        if not text:
            continue

        best = _best_alias_match(text)
        if best:
            slug, canonical_name, maker, alias = best
            confidence = 1.0 if context_index == 0 else max(0.65, 0.95 - (context_index * 0.1))
            return ConsoleMatch(
                slug=slug,
                canonical_name=canonical_name,
                maker=maker,
                confidence=confidence,
                evidence=[f"alias:{alias}", f"context:{context_index}"],
            )

    return ConsoleMatch(
        slug="unknown",
        canonical_name="Unknown Console",
        confidence=0.0,
        evidence=["no_console_alias_match"],
    )


def normalize_console_name(name: str) -> tuple[str, str]:
    """Compatibility wrapper returning ``(canonical_name, slug)``."""

    match = classify_console(name)
    if match.is_known:
        return match.canonical_name, match.slug
    return "Unknown Console", "unknown"


def normalize_context(value: str) -> str:
    """Normalize noisy source text into comparable tokens."""

    if not value:
        return ""
    return " ".join(_TOKEN_RE.findall(value.lower()))


def _best_alias_match(normalized_text: str) -> tuple[str, str, str, str] | None:
    candidates = []
    text_tokens = normalized_text.split()

    for slug, info in CONSOLE_CANONICAL.items():
        aliases = set(info["aliases"]) | {info["canonical"], slug}
        for alias in aliases:
            normalized_alias = normalize_context(alias)
            if not normalized_alias:
                continue
            alias_tokens = normalized_alias.split()
            if _contains_phrase(text_tokens, alias_tokens):
                candidates.append((
                    len(alias_tokens),
                    len(normalized_alias),
                    slug,
                    info["canonical"],
                    info.get("maker", ""),
                    normalized_alias,
                ))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    _, _, slug, canonical_name, maker, alias = candidates[0]
    return slug, canonical_name, maker, alias


def _contains_phrase(tokens: list[str], phrase: list[str]) -> bool:
    if not phrase or len(phrase) > len(tokens):
        return False
    last_start = len(tokens) - len(phrase)
    return any(tokens[index:index + len(phrase)] == phrase for index in range(last_start + 1))
