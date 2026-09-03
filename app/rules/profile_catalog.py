"""Discipline review profiles, loaded from ``app/rules/profiles/*.json``.

The report review engine used to carry one ``_check_*`` method per discipline
rule, each one a wall of Turkish vocabulary wrapped around the same generic
"are these requirement groups mentioned anywhere in the report?" test. The
vocabulary lives here instead: one JSON file per discipline, so adding a check
-- or a whole discipline -- is a data edit plus a golden case rather than a
Python change.

Everything is validated at load time, unknown keys included, so a typo in a data
file is an import-time error naming the file and the offending path rather than
a rule that silently stops firing.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

SEVERITIES = ("critical", "warning", "info")

_PROFILE_KEYS = {"profile", "label", "detect_priority", "aliases", "detect_patterns", "rules"}
_RULE_KEYS = {
    "rule_id",
    "label",
    "category",
    "severity",
    "message",
    "suggested_fix",
    "requirement_groups",
}
_GROUP_KEYS = {"label", "aliases"}


class ProfileCatalogError(ValueError):
    """A discipline data file is malformed."""


@dataclass(frozen=True, slots=True)
class RequirementGroup:
    """One thing a report must mention, and the wordings that count as mentioning it."""

    label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProfileRequirement:
    """A discipline rule: the groups it wants, and what to say when one is missing."""

    rule_id: str
    label: str
    category: str
    severity: str
    message: str
    suggested_fix: str
    groups: tuple[RequirementGroup, ...]


@dataclass(frozen=True, slots=True)
class DisciplineProfile:
    name: str
    label: str
    detect_priority: int
    aliases: tuple[str, ...]
    detect_patterns: tuple[re.Pattern[str], ...]
    rules: tuple[ProfileRequirement, ...]


def _fail(source: Path, where: str, problem: str) -> ProfileCatalogError:
    return ProfileCatalogError(f"{source.name}: {where}: {problem}")


def _require_keys(payload: dict, allowed: set[str], source: Path, where: str) -> None:
    missing = sorted(allowed - payload.keys())
    if missing:
        raise _fail(source, where, "missing key(s) " + ", ".join(missing))
    unknown = sorted(payload.keys() - allowed)
    if unknown:
        raise _fail(source, where, "unknown key(s) " + ", ".join(unknown))


def _text(payload: dict, key: str, source: Path, where: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise _fail(source, f"{where}.{key}", "must be a non-empty string")
    return value


def _string_tuple(payload: dict, key: str, source: Path, where: str) -> tuple[str, ...]:
    value = payload[key]
    if not isinstance(value, list) or not value:
        raise _fail(source, f"{where}.{key}", "must be a non-empty list")
    items: list[str] = []
    for index, item in enumerate(value):
        # An alias may legitimately carry a trailing space ("iso ") so it does
        # not match "isolation", so strip() here is only the emptiness test.
        if not isinstance(item, str) or not item.strip():
            raise _fail(source, f"{where}.{key}[{index}]", "must be a non-empty string")
        items.append(item)
    duplicates = sorted({item for item in items if items.count(item) > 1})
    if duplicates:
        raise _fail(
            source,
            f"{where}.{key}",
            "duplicate entries " + ", ".join(repr(item) for item in duplicates),
        )
    return tuple(items)


def _parse_group(payload: object, source: Path, where: str) -> RequirementGroup:
    if not isinstance(payload, dict):
        raise _fail(source, where, "must be an object")
    _require_keys(payload, _GROUP_KEYS, source, where)
    return RequirementGroup(
        label=_text(payload, "label", source, where),
        aliases=_string_tuple(payload, "aliases", source, where),
    )


def _parse_rule(payload: object, source: Path, profile: str, index: int) -> ProfileRequirement:
    where = f"rules[{index}]"
    if not isinstance(payload, dict):
        raise _fail(source, where, "must be an object")
    _require_keys(payload, _RULE_KEYS, source, where)

    rule_id = _text(payload, "rule_id", source, where)
    prefix = f"{profile}."
    if not rule_id.startswith(prefix):
        raise _fail(source, f"{where}.rule_id", f"{rule_id!r} must start with {prefix!r}")

    severity = payload["severity"]
    if severity not in SEVERITIES:
        raise _fail(source, f"{where}.severity", "must be one of " + ", ".join(SEVERITIES))

    groups_payload = payload["requirement_groups"]
    if not isinstance(groups_payload, list) or not groups_payload:
        raise _fail(source, f"{where}.requirement_groups", "must be a non-empty list")
    groups = tuple(
        _parse_group(group, source, f"{where}.requirement_groups[{group_index}]")
        for group_index, group in enumerate(groups_payload)
    )
    labels = [group.label for group in groups]
    duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
    if duplicate_labels:
        raise _fail(
            source,
            f"{where}.requirement_groups",
            "duplicate group label(s) " + ", ".join(repr(label) for label in duplicate_labels),
        )

    return ProfileRequirement(
        rule_id=rule_id,
        label=_text(payload, "label", source, where),
        category=_text(payload, "category", source, where),
        severity=severity,
        message=_text(payload, "message", source, where),
        suggested_fix=_text(payload, "suggested_fix", source, where),
        groups=groups,
    )


def _parse_profile(source: Path) -> DisciplineProfile:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise _fail(source, "file", f"invalid JSON ({error})") from error
    if not isinstance(payload, dict):
        raise _fail(source, "file", "must be a JSON object")
    _require_keys(payload, _PROFILE_KEYS, source, "profile")

    name = _text(payload, "profile", source, "profile")
    if name != source.stem:
        raise _fail(source, "profile", f"{name!r} does not match the file name {source.stem!r}")
    if name in {"general", "auto"}:
        raise _fail(source, "profile", f"{name!r} is reserved for the built-in profiles")

    priority = payload["detect_priority"]
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise _fail(source, "profile.detect_priority", "must be an integer")

    patterns: list[re.Pattern[str]] = []
    for index, pattern in enumerate(_string_tuple(payload, "detect_patterns", source, "profile")):
        try:
            patterns.append(re.compile(pattern))
        except re.error as error:
            raise _fail(
                source, f"profile.detect_patterns[{index}]", f"invalid regex ({error})"
            ) from error

    rules_payload = payload["rules"]
    if not isinstance(rules_payload, list) or not rules_payload:
        raise _fail(source, "profile.rules", "must be a non-empty list")
    rules = tuple(_parse_rule(rule, source, name, index) for index, rule in enumerate(rules_payload))
    rule_ids = [rule.rule_id for rule in rules]
    duplicates = sorted({rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1})
    if duplicates:
        raise _fail(source, "profile.rules", "duplicate rule_id " + ", ".join(duplicates))

    return DisciplineProfile(
        name=name,
        label=_text(payload, "label", source, "profile"),
        detect_priority=priority,
        aliases=_string_tuple(payload, "aliases", source, "profile"),
        detect_patterns=tuple(patterns),
        rules=rules,
    )


def load_profile_directory(directory: Path) -> tuple[DisciplineProfile, ...]:
    """Parse every ``*.json`` under `directory`, ordered by detect priority.

    Detection order is data, not directory order: `_resolve_document_profile`
    tries the identity patterns in this order and keeps the first match, so a
    profile whose patterns are broad belongs later in the sequence.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise ProfileCatalogError(f"discipline profile directory not found: {directory}")

    profiles = tuple(
        sorted(
            (_parse_profile(path) for path in sorted(directory.glob("*.json"))),
            key=lambda profile: (profile.detect_priority, profile.name),
        )
    )
    if not profiles:
        raise ProfileCatalogError(f"no discipline profiles found in {directory}")
    # Rule ids are unique across files without a check here: each rule_id must
    # carry its profile as a prefix, and a profile is named by its file, so two
    # files cannot reach the same id. Collisions with the *general* rules the
    # service owns are caught there, where those ids are known.
    return profiles


@lru_cache(maxsize=1)
def discipline_profiles() -> tuple[DisciplineProfile, ...]:
    """The shipped catalog, parsed once."""
    return load_profile_directory(PROFILES_DIR)
