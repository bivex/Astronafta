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
    max_client_load: int = 3


_ATTR_PATTERN = re.compile(
    r'\b[a-zA-Z_][\w-]*(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|\{[^}]*\}))?\b'
)
_INLINE_STYLE_PATTERN = re.compile(r'\bstyle\s*=\s*["\']')
_CLIENT_LOAD_PATTERN = re.compile(r'\bclient:load\b')
_CLIENT_ANY_PATTERN = re.compile(r'\bclient:\w+')
_HARDCODED_URL_PATTERN = re.compile(r'https?://localhost[:/]')
_GLOBAL_STYLE_PATTERN = re.compile(r'is:global')
_ENV_SECRET_PATTERN = re.compile(r'import\.meta\.env\.\w*SECRET\w*', re.IGNORECASE)
_IMPORT_PATTERN = re.compile(
    r'import\s+(?:(?:\w+\s*,?\s*)*\{[^}]*\}|\w+)\s+from\s+["\']([^"\']+)["\']'
)
_DEFAULT_IMPORT_PATTERN = re.compile(r'import\s+(\w+)\s+from\s+["\']([^"\']+)["\']')
_FRAMEWORK_EXTENSIONS = ('.tsx', '.jsx', '.vue', '.svelte')
_IMG_TAG = 'img'


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
        smells.extend(self._check_source_level(source_unit.content, diagram))
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

    def _check_source_level(
        self, source_content: str, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        smells: list[CodeSmell] = []
        frontmatter = _extract_frontmatter(source_content)

        smells.extend(self._check_client_directive_overuse(diagram))
        smells.extend(self._check_missing_client_directive(frontmatter, diagram))
        smells.extend(self._check_unused_imports(frontmatter, diagram))
        smells.extend(self._check_env_in_client_component(diagram))
        smells.extend(self._check_hardcoded_base_url(source_content, diagram))
        smells.extend(self._check_excessive_global_styles(source_content, diagram))

        return smells

    def _check_client_directive_overuse(
        self, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        client_load_count = 0
        for comp in diagram.components:
            if _CLIENT_LOAD_PATTERN.search(comp.signature):
                client_load_count += 1
            client_load_count += _count_in_tree(comp.steps, _has_client_load)

        if client_load_count > self._thresholds.max_client_load:
            return [CodeSmell(
                kind=CodeSmellKind.CLIENT_DIRECTIVE_OVERUSE,
                severity=SmellSeverity.WARNING,
                message=f"File has {client_load_count} client:load directives "
                        f"(threshold: {self._thresholds.max_client_load}). "
                        f"Consider client:idle or client:visible.",
                line=None,
                context="file",
            )]
        return []

    def _check_missing_client_directive(
        self, frontmatter: str, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        framework_imports = _extract_framework_import_names(frontmatter)
        if not framework_imports:
            return []

        used_names = set()
        for comp in diagram.components:
            used_names.add(comp.name)
            _collect_component_names(comp.steps, used_names)

        smells: list[CodeSmell] = []
        client_components = set()
        for comp in diagram.components:
            if _CLIENT_ANY_PATTERN.search(comp.signature):
                client_components.add(comp.name)
            if _has_client_directive_in_tree(comp.steps):
                client_components.add(comp.name)

        for name in framework_imports & used_names:
            if name not in client_components:
                smells.append(CodeSmell(
                    kind=CodeSmellKind.MISSING_CLIENT_DIRECTIVE,
                    severity=SmellSeverity.WARNING,
                    message=f"Framework component '<{name}>' used without client:* directive "
                            f"— will render as static HTML only",
                    line=None,
                    context=name,
                ))
        return smells

    def _check_unused_imports(
        self, frontmatter: str, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        import_names = _extract_all_import_names(frontmatter)
        if not import_names:
            return []

        used_names: set[str] = set()
        for comp in diagram.components:
            used_names.add(comp.name)
            _collect_component_names(comp.steps, used_names)

        smells: list[CodeSmell] = []
        for name in sorted(import_names - used_names):
            smells.append(CodeSmell(
                kind=CodeSmellKind.UNUSED_IMPORT,
                severity=SmellSeverity.INFO,
                message=f"Component '{name}' imported but not used in template",
                line=None,
                context=name,
            ))
        return smells

    def _check_env_in_client_component(
        self, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        smells: list[CodeSmell] = []
        for comp in diagram.components:
            has_client = _CLIENT_ANY_PATTERN.search(comp.signature) or \
                         _has_client_directive_in_tree(comp.steps)
            if not has_client:
                continue
            env_matches = _collect_env_secrets(comp.steps)
            if env_matches:
                smells.append(CodeSmell(
                    kind=CodeSmellKind.ENV_IN_CLIENT_COMPONENT,
                    severity=SmellSeverity.WARNING,
                    message=f"Secret env variable(s) {', '.join(env_matches)} "
                            f"used in client component '<{comp.name}>' — "
                            f"exposed to browser",
                    line=None,
                    context=comp.name,
                ))
        return smells

    def _check_hardcoded_base_url(
        self, source_content: str, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        matches = _HARDCODED_URL_PATTERN.findall(source_content)
        if not matches:
            return []
        return [CodeSmell(
            kind=CodeSmellKind.HARDCODED_BASE_URL,
            severity=SmellSeverity.WARNING,
            message=f"Hardcoded localhost URL found — will break in production",
            line=None,
            context="file",
        )]

    def _check_excessive_global_styles(
        self, source_content: str, diagram: StructureDiagram,
    ) -> list[CodeSmell]:
        if not _GLOBAL_STYLE_PATTERN.search(source_content):
            return []
        # Only warn if not in a layout file
        loc = diagram.source_location.lower()
        if 'layout' in loc:
            return []
        return [CodeSmell(
            kind=CodeSmellKind.EXCESSIVE_GLOBAL_STYLES,
            severity=SmellSeverity.INFO,
            message="Global styles (<style is:global>) in non-layout component "
                    "break style isolation",
            line=None,
            context="file",
        )]

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

        if isinstance(step, ElementStep) and step.tag.lower() == _IMG_TAG:
            if not _has_img_dimensions(attrs):
                smells.append(CodeSmell(
                    kind=CodeSmellKind.IMAGE_WITHOUT_DIMENSIONS,
                    severity=SmellSeverity.WARNING,
                    message=f"<img> without width/height causes CLS",
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


def _extract_frontmatter(source: str) -> str:
    if not source.startswith('---'):
        return ""
    end = source.find('---', 3)
    if end == -1:
        return ""
    return source[3:end]


def _extract_framework_import_names(frontmatter: str) -> set[str]:
    names: set[str] = set()
    for match in _DEFAULT_IMPORT_PATTERN.finditer(frontmatter):
        name, path = match.group(1), match.group(2)
        if any(path.endswith(ext) for ext in _FRAMEWORK_EXTENSIONS):
            names.add(name)
    return names


def _extract_all_import_names(frontmatter: str) -> set[str]:
    names: set[str] = set()
    for match in _DEFAULT_IMPORT_PATTERN.finditer(frontmatter):
        names.add(match.group(1))
    return names


def _has_client_load(step: TemplateStep) -> bool:
    if isinstance(step, ComponentStep):
        return bool(_CLIENT_LOAD_PATTERN.search(step.attributes))
    return False


def _has_client_directive_in_tree(steps: tuple[TemplateStep, ...]) -> bool:
    for step in steps:
        if isinstance(step, ComponentStep):
            if _CLIENT_ANY_PATTERN.search(step.attributes):
                return True
        if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
            if _has_client_directive_in_tree(step.children):
                return True
    return False


def _collect_component_names(
    steps: tuple[TemplateStep, ...], out: set[str],
) -> None:
    for step in steps:
        if isinstance(step, ComponentStep):
            out.add(step.name)
        if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
            _collect_component_names(step.children, out)


def _collect_env_secrets(steps: tuple[TemplateStep, ...]) -> list[str]:
    found: list[str] = []
    for step in steps:
        if isinstance(step, ExpressionStep):
            for m in _ENV_SECRET_PATTERN.finditer(step.content):
                found.append(m.group(0))
        if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
            found.extend(_collect_env_secrets(step.children))
    return found


def _count_in_tree(
    steps: tuple[TemplateStep, ...],
    predicate: callable,
) -> int:
    count = 0
    for step in steps:
        if predicate(step):
            count += 1
        if isinstance(step, (ElementStep, ComponentStep, FragmentStep)):
            count += _count_in_tree(step.children, predicate)
    return count


def _has_img_dimensions(attrs: str) -> bool:
    return bool(re.search(r'\bwidth\b', attrs)) and bool(re.search(r'\bheight\b', attrs))
