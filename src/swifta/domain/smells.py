"""Domain model for Astro template code smell detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SmellSeverity(StrEnum):
    WARNING = "warning"
    INFO = "info"


class CodeSmellKind(StrEnum):
    DEEP_NESTING = "deep-nesting"
    TOO_MANY_CHILDREN = "too-many-children"
    LARGE_COMPONENT = "large-component"
    TOO_MANY_PROPS = "too-many-props"
    TOO_MANY_COMPONENTS = "too-many-components"
    TOO_MANY_EXPRESSIONS = "too-many-expressions"
    INLINE_STYLE = "inline-style"
    SCRIPT_IN_COMPONENT = "script-in-component"
    DUPLICATE_COMPONENT_NAMES = "duplicate-component-names"
    EMPTY_COMPONENT = "empty-component"


@dataclass(frozen=True, slots=True)
class CodeSmell:
    kind: CodeSmellKind
    severity: SmellSeverity
    message: str
    line: int | None
    context: str


@dataclass(frozen=True, slots=True)
class SmellReport:
    source_location: str
    smells: tuple[CodeSmell, ...]

    @property
    def smell_count(self) -> int:
        return len(self.smells)

    @property
    def warning_count(self) -> int:
        return sum(1 for s in self.smells if s.severity == SmellSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for s in self.smells if s.severity == SmellSeverity.INFO)
