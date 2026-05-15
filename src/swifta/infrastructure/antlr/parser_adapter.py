"""ANTLR-backed Astro parser adapter."""

from __future__ import annotations

from time import perf_counter

from swifta.domain.model import (
    GrammarVersion,
    ParseOutcome,
    ParseStatistics,
    SourceUnit,
    StructuralElement,
    StructuralElementKind,
)
from swifta.domain.ports import AstroSyntaxParser
from swifta.infrastructure.antlr.runtime import (
    ANTLR_GRAMMAR_VERSION,
    load_generated_types,
    parse_source_text,
)


class AntlrAstroSyntaxParser(AstroSyntaxParser):
    def __init__(self) -> None:
        self._generated = load_generated_types()

    @property
    def grammar_version(self) -> GrammarVersion:
        return ANTLR_GRAMMAR_VERSION

    def parse(self, source_unit: SourceUnit) -> ParseOutcome:
        started_at = perf_counter()
        try:
            parse_result = parse_source_text(source_unit.content, self._generated)
            structure_visitor = _build_structure_visitor(self._generated.visitor_type)()
            structure_visitor.visit(parse_result.tree)

            elements = tuple(structure_visitor.elements)
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)

            return ParseOutcome.success(
                source_unit=source_unit,
                grammar_version=self.grammar_version,
                diagnostics=parse_result.diagnostics,
                structural_elements=elements,
                statistics=ParseStatistics(
                    token_count=len(parse_result.token_stream.tokens),
                    structural_element_count=len(elements),
                    diagnostic_count=len(parse_result.diagnostics),
                    elapsed_ms=elapsed_ms,
                ),
            )
        except Exception as error:
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return ParseOutcome.technical_failure(
                source_unit=source_unit,
                grammar_version=self.grammar_version,
                message=str(error),
                elapsed_ms=elapsed_ms,
            )


def _build_structure_visitor(visitor_base: type) -> type:
    class AstroStructureVisitor(visitor_base):
        def __init__(self) -> None:
            super().__init__()
            self.elements: list[StructuralElement] = []
            self._containers: list[str] = []

        def visitAstroFile(self, ctx):
            return self.visitChildren(ctx)

        def visitFrontmatter(self, ctx):
            text = ctx.getText()
            self._append(
                StructuralElementKind.FRONTMATTER,
                "frontmatter",
                ctx,
                signature=text[:120],
            )
            return None

        def visitScriptBlock(self, ctx):
            self._append(
                StructuralElementKind.SCRIPT_BLOCK,
                "script",
                ctx,
                signature="<script>",
            )
            return None

        def visitStyleBlock(self, ctx):
            self._append(
                StructuralElementKind.STYLE_BLOCK,
                "style",
                ctx,
                signature="<style>",
            )
            return None

        def visitComponentElement(self, ctx):
            open_tag = ctx.componentOpenTag() or ctx.componentSelfCloseTag()
            name = open_tag.componentTagName().getText() if open_tag else "Component"
            container = ".".join(self._containers) if self._containers else None
            self._append(
                StructuralElementKind.COMPONENT,
                name,
                ctx,
                signature=f"<{name}>",
            )
            if ctx.template() is not None:
                return self._with_container(name, lambda: self.visitTemplate(ctx.template()))
            return None

        def visitHtmlElement(self, ctx):
            open_tag = ctx.htmlOpenTag() or ctx.htmlVoidTag()
            tag_name = open_tag.htmlTagName().getText() if open_tag else "element"
            self._append(
                StructuralElementKind.HTML_ELEMENT,
                tag_name,
                ctx,
                signature=f"<{tag_name}>",
            )
            if ctx.template() is not None:
                return self._with_container(tag_name, lambda: self.visitTemplate(ctx.template()))
            return None

        def visitFragmentElement(self, ctx):
            self._append(
                StructuralElementKind.FRAGMENT,
                "Fragment",
                ctx,
                signature="<Fragment>",
            )
            if ctx.template() is not None:
                return self._with_container("Fragment", lambda: self.visitTemplate(ctx.template()))
            return None

        def visitTemplateExpr(self, ctx):
            content = ctx.getText()
            self._append(
                StructuralElementKind.TEMPLATE_EXPR,
                content[:60],
                ctx,
                signature=content[:96],
            )
            return None

        def visitText(self, ctx):
            content = ctx.getText().strip()
            if content:
                self._append(
                    StructuralElementKind.TEXT,
                    content[:40],
                    ctx,
                    signature=content[:96],
                )
            return None

        def _append(self, kind, name: str, ctx, signature: str | None = None) -> None:
            container = ".".join(self._containers) if self._containers else None
            self.elements.append(
                StructuralElement(
                    kind=kind,
                    name=name,
                    line=ctx.start.line,
                    column=ctx.start.column,
                    container=container,
                    signature=signature,
                )
            )

        def _with_container(self, name: str, callback):
            self._containers.append(name)
            try:
                return callback()
            finally:
                self._containers.pop()

    return AstroStructureVisitor
