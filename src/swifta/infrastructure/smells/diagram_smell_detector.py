"""Detect Astro code smells by analyzing a StructureDiagram tree."""

from __future__ import annotations

import re
from dataclasses import dataclass

from swifta.domain.control_flow import (
    ComponentStep,
    ComponentStructure,
    ElementStep,
    ExpressionStep,
    FragmentStep,
    ScriptStep,
    StructureDiagram,
    StyleStep,
    TemplateStep,
)
from swifta.domain.model import SourceUnit
from swifta.domain.ports import AstroSmellDetector, AstroStructureExtractor
from swifta.domain.smells import CodeSmell, CodeSmellKind, SmellReport, SmellSeverity


@dataclass(slots=True)
class SmellThresholds:
    nesting_depth: int = 6
    max_children: int = 15
    max_descendants: int = 30
    max_props: int = 8
    max_components: int = 10
    max_expressions: int = 20


_ATTR_PATTERN = re.compile(
    r'\b[a-zA-Z_][\w-]*(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|\{[^}]*\}))?\b'
)
_INLINE_STYLE_PATTERN = re.compile(r'\bstyle\s*=\s*["\']')


class StructureDiagramSmellDetector(AstroSmellDetector):
    def __init__(
        self,
        extractor: AstroStructureExtractor,
        thresholds: SmellThresholds | None = None,
    ) -> None:
        self._extractor = extractor
        self._thresholds = thresholds or SmellThresholds()

    def detect(self, source_unit: SourceUnit) -> SmellReport:
        diagram = self._extractor.extract(source_unit)
        smells: list[CodeSmell] = []
        smells.extend(self._check_file_level(diagram))
        for component in diagram.components:
            smells.extend(self._check_component(component))
        return SmellReport(
            source_location=diagram.source_location,
            smells=tuple(smells),
        )

    def _check_file_level(self, diagram: StructureDiagram) -> list[CodeSmell]:
        smells: list[CodeSmell] = []

        if len(diagram.components) > self._thresholds.max_components:
            smells.append(CodeSmell(
                kind=CodeSmellKind.TOO_MANY_COMPONENTS,
                severity=SmellSeverity.WARNING,
                message=f"File has {len(diagram.components)} top-level components "
                        f"(threshold: {self._thresholds.max_components})",
                line=None,
                context="file",
            ))

        seen: dict[str, int] = {}
        for comp in diagram.components:
            seen[comp.qualified_name] = seen.get(comp.qualified_name, 0) + 1
        for name, count in seen.items():
            if count > 1:
                smells.append(CodeSmell(
                    kind=CodeSmellKind.DUPLICATE_COMPONENT_NAMES,
                    severity=SmellSeverity.WARNING,
                    message=f"Component '{name}' appears {count} times",
                    line=None,
                    context=name,
                ))

        total_exprs = sum(
            self._count_expressions(comp.steps) for comp in diagram.components
        )
        if total_exprs > self._thresholds.max_expressions:
            smells.append(CodeSmell(
                kind=CodeSmellKind.TOO_MANY_EXPRESSIONS,
                severity=SmellSeverity.WARNING,
                message=f"File has {total_exprs} template expressions "
                        f"(threshold: {self._thresholds.max_expressions})",
                line=None,
                context="file",
            ))

        return smells

    def _check_component(self, comp: ComponentStructure) -> list[CodeSmell]:
        smells: list[CodeSmell] = []
        name = comp.qualified_name

        descendant_count = self._count_descendants(comp.steps)
        if descendant_count > self._thresholds.max_descendants:
            smells.append(CodeSmell(
                kind=CodeSmellKind.LARGE_COMPONENT,
                severity=SmellSeverity.WARNING,
                message=f"Component '{name}' has {descendant_count} descendants "
                        f"(threshold: {self._thresholds.max_descendants})",
                line=None,
                context=name,
            ))

        if not comp.steps:
            smells.append(CodeSmell(
                kind=CodeSmellKind.EMPTY_COMPONENT,
                severity=SmellSeverity.INFO,
                message=f"Component '{name}' has no children",
                line=None,
                context=name,
            ))

        smells.extend(self._walk_steps(comp.steps, depth=1, parent_name=name))
        return smells

    def _walk_steps(
        self,
        steps: tuple[TemplateStep, ...],
        depth: int,
        parent_name: str,
    ) -> list[CodeSmell]:
        smells: list[CodeSmell] = []

        for step in steps:
            if depth == self._thresholds.nesting_depth + 1:
                ctx_name = _step_name(step)
                smells.append(CodeSmell(
                    kind=CodeSmellKind.DEEP_NESTING,
                    severity=SmellSeverity.WARNING,
                    message=f"Element '{ctx_name}' is nested {depth} levels deep "
                            f"(threshold: {self._thresholds.nesting_depth})",
                    line=None,
                    context=f"{parent_name}/{ctx_name}",
                ))

            if isinstance(step, (ElementStep, ComponentStep)):
                self._check_step_attrs(step, parent_name, smells)

            if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
                child_count = len(step.children)
                if child_count > self._thresholds.max_children:
                    ctx_name = _step_name(step)
                    smells.append(CodeSmell(
                        kind=CodeSmellKind.TOO_MANY_CHILDREN,
                        severity=SmellSeverity.WARNING,
                        message=f"Element '{ctx_name}' has {child_count} direct children "
                                f"(threshold: {self._thresholds.max_children})",
                        line=None,
                        context=f"{parent_name}/{ctx_name}",
                    ))
                smells.extend(self._walk_steps(step.children, depth + 1, parent_name))

        return smells

    def _check_step_attrs(
        self,
        step: ElementStep | ComponentStep,
        parent_name: str,
        smells: list[CodeSmell],
    ) -> None:
        attrs = step.attributes

        attr_count = _count_attributes(attrs)
        if attr_count > self._thresholds.max_props:
            name = _step_name(step)
            smells.append(CodeSmell(
                kind=CodeSmellKind.TOO_MANY_PROPS,
                severity=SmellSeverity.WARNING,
                message=f"Element '{name}' has {attr_count} attributes "
                        f"(threshold: {self._thresholds.max_props})",
                line=None,
                context=f"{parent_name}/{name}",
            ))

        if isinstance(step, ElementStep) and _INLINE_STYLE_PATTERN.search(attrs):
            smells.append(CodeSmell(
                kind=CodeSmellKind.INLINE_STYLE,
                severity=SmellSeverity.WARNING,
                message=f"Element '<{step.tag}>' has inline style attribute",
                line=None,
                context=f"{parent_name}/<{step.tag}>",
            ))

        if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
            for child in step.children:
                if isinstance(child, ScriptStep):
                    ctx_name = _step_name(step)
                    smells.append(CodeSmell(
                        kind=CodeSmellKind.SCRIPT_IN_COMPONENT,
                        severity=SmellSeverity.INFO,
                        message=f"Script block found inside '{ctx_name}'",
                        line=None,
                        context=f"{parent_name}/{ctx_name}",
                    ))

    @staticmethod
    def _count_descendants(steps: tuple[TemplateStep, ...]) -> int:
        count = 0
        for step in steps:
            count += 1
            if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
                count += StructureDiagramSmellDetector._count_descendants(step.children)
        return count

    @staticmethod
    def _count_expressions(steps: tuple[TemplateStep, ...]) -> int:
        count = 0
        for step in steps:
            if isinstance(step, ExpressionStep):
                count += 1
            if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
                count += StructureDiagramSmellDetector._count_expressions(step.children)
        return count


def _step_name(step: TemplateStep) -> str:
    if isinstance(step, ElementStep):
        return f"<{step.tag}>"
    if isinstance(step, ComponentStep):
        return f"<{step.name}>"
    if isinstance(step, FragmentStep):
        return "<Fragment>"
    if isinstance(step, ExpressionStep):
        return step.content[:30]
    if isinstance(step, ScriptStep):
        return "<script>"
    if isinstance(step, StyleStep):
        return "<style>"
    return "text"


def _count_attributes(attrs: str) -> int:
    if not attrs or not attrs.strip():
        return 0
    return len(_ATTR_PATTERN.findall(attrs))
