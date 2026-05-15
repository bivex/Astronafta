"""Domain model for Astro template structure."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateStep:
    """Base type for a template structure step."""


@dataclass(frozen=True, slots=True)
class ElementStep(TemplateStep):
    tag: str
    attributes: str
    children: tuple[TemplateStep, ...]


@dataclass(frozen=True, slots=True)
class ComponentStep(TemplateStep):
    name: str
    attributes: str
    children: tuple[TemplateStep, ...]


@dataclass(frozen=True, slots=True)
class ExpressionStep(TemplateStep):
    content: str


@dataclass(frozen=True, slots=True)
class TextStep(TemplateStep):
    content: str


@dataclass(frozen=True, slots=True)
class ScriptStep(TemplateStep):
    content: str


@dataclass(frozen=True, slots=True)
class StyleStep(TemplateStep):
    content: str


@dataclass(frozen=True, slots=True)
class FragmentStep(TemplateStep):
    children: tuple[TemplateStep, ...]


@dataclass(frozen=True, slots=True)
class ComponentStructure:
    name: str
    signature: str
    container: str | None
    steps: tuple[TemplateStep, ...]

    @property
    def qualified_name(self) -> str:
        if self.container:
            return f"{self.container}.{self.name}"
        return self.name


@dataclass(frozen=True, slots=True)
class StructureDiagram:
    source_location: str
    components: tuple[ComponentStructure, ...]
