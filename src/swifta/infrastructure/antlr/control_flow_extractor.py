"""Extract structured template information from Astro source through ANTLR."""

from __future__ import annotations

from swifta.domain.control_flow import (
    ComponentStep,
    ComponentStructure,
    ElementStep,
    ExpressionStep,
    FragmentStep,
    ScriptStep,
    StyleStep,
    StructureDiagram,
    TemplateStep,
    TextStep,
)
from swifta.domain.model import SourceUnit
from swifta.domain.ports import AstroStructureExtractor
from swifta.infrastructure.antlr.runtime import load_generated_types, parse_source_text


class AntlrAstroStructureExtractor(AstroStructureExtractor):
    def __init__(self) -> None:
        self._generated = load_generated_types()

    def extract(self, source_unit: SourceUnit) -> StructureDiagram:
        parse_result = parse_source_text(source_unit.content, self._generated)
        visitor = _build_structure_visitor(self._generated.visitor_type)()
        visitor.visit(parse_result.tree)
        return StructureDiagram(
            source_location=source_unit.location,
            components=tuple(visitor.components),
        )


def _build_structure_visitor(visitor_base: type) -> type:
    class AstroStructureVisitor(visitor_base):
        def __init__(self) -> None:
            super().__init__()
            self.components: list[ComponentStructure] = []
            self._containers: list[str] = []

        def visitAstroFile(self, ctx):
            return self.visitChildren(ctx)

        def visitFrontmatter(self, ctx):
            return None

        def visitComponentElement(self, ctx):
            open_tag = ctx.componentOpenTag() or ctx.componentSelfCloseTag()
            name = open_tag.componentTagName().getText() if open_tag else "Component"
            attrs = _attrs_from_tag(open_tag)
            container = ".".join(self._containers) if self._containers else None

            children: tuple[TemplateStep, ...] = ()
            if ctx.template() is not None:
                children = self._collect_template(ctx.template())

            self.components.append(
                ComponentStructure(
                    name=name,
                    signature=f"<{name}{attrs}>",
                    container=container,
                    steps=children,
                )
            )
            return ComponentStep(name=name, attributes=attrs, children=children)

        def visitHtmlElement(self, ctx):
            open_tag = ctx.htmlOpenTag() or ctx.htmlVoidTag()
            tag_name = open_tag.htmlTagName().getText() if open_tag else "div"
            attrs = _attrs_from_tag(open_tag)

            children: tuple[TemplateStep, ...] = ()
            if ctx.template() is not None:
                children = self._collect_template(ctx.template())

            return ElementStep(tag=tag_name, attributes=attrs, children=children)

        def visitFragmentElement(self, ctx):
            children: tuple[TemplateStep, ...] = ()
            if ctx.template() is not None:
                children = self._collect_template(ctx.template())
            return FragmentStep(children=children)

        def visitScriptBlock(self, ctx):
            content = ctx.getText()
            return ScriptStep(content=content)

        def visitStyleBlock(self, ctx):
            content = ctx.getText()
            return StyleStep(content=content)

        def visitTemplateExpr(self, ctx):
            return ExpressionStep(content=ctx.getText())

        def visitText(self, ctx):
            content = ctx.getText()
            return TextStep(content=content)

        def _collect_template(self, template_ctx) -> tuple[TemplateStep, ...]:
            if template_ctx is None:
                return ()
            results: list[TemplateStep] = []
            for item_ctx in template_ctx.templateItem():
                result = self.visit(item_ctx)
                if result is not None and isinstance(result, TemplateStep):
                    results.append(result)
            return tuple(results)

    return AstroStructureVisitor


def _attrs_from_tag(tag_ctx) -> str:
    if tag_ctx is None:
        return ""
    attr_fn = getattr(tag_ctx, "attribute", None)
    if not callable(attr_fn):
        return ""
    attrs = [a.getText() for a in attr_fn()]
    return " " + " ".join(attrs) if attrs else ""
