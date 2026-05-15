"""Render Astro template structure as HTML tree diagram."""

from __future__ import annotations

from html import escape

from swifta.domain.control_flow import (
    ComponentStep,
    ComponentStructure,
    ElementStep,
    ExpressionStep,
    FragmentStep,
    StructureDiagram,
    StyleStep,
    TemplateStep,
    TextStep,
    ScriptStep,
)
from swifta.domain.ports import StructureDiagramRenderer


class HtmlStructureDiagramRenderer(StructureDiagramRenderer):
    def render(self, diagram: StructureDiagram) -> str:
        sections = "".join(self._render_component(comp) for comp in diagram.components)
        if not sections:
            sections = '<section class="component-panel"><p class="empty-file">No components found.</p></section>'

        return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Astro Template Structure</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      :root {{
        --bg:          #0a0f18;
        --surface:     #111827;
        --surface-2:   #172131;
        --surface-3:   #1c2940;
        --border:      #2b3b59;
        --border-strong: #3f5378;
        --text:        #cfd8f6;
        --text-bright: #f4f7ff;
        --muted:       #8e9bbb;
        --shadow:      0 24px 72px rgba(3, 8, 18, 0.56);
        --blue:        #82aaff;
        --blue-dim:    #243b69;
        --green:       #a6da95;
        --green-dim:   #163628;
        --teal:        #56d4dd;
        --teal-dim:    #11343b;
        --purple:      #c4a7ff;
        --purple-dim:  #2a1d41;
        --orange:      #ffb86b;
        --orange-dim:  #37230f;
        --mono: "JetBrains Mono", "Fira Code", "SF Mono", "Menlo", monospace;
        --ui:   "IBM Plex Sans", -apple-system, "Segoe UI", system-ui, sans-serif;
      }}
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{
        font-family: var(--ui);
        font-size: 14px;
        color: var(--text);
        background: linear-gradient(180deg, var(--bg) 0%, #0c121d 100%);
        padding: 24px;
        min-height: 100vh;
        color-scheme: dark;
      }}
      .viewer {{
        max-width: 1120px;
        margin: 0 auto;
        border: 1px solid var(--border-strong);
        border-radius: 14px;
        background: var(--surface);
        box-shadow: var(--shadow);
        overflow: hidden;
      }}
      .titlebar {{
        padding: 10px 16px;
        background: var(--surface-3);
        border-bottom: 1px solid var(--border-strong);
        display: flex;
        align-items: center;
        gap: 10px;
      }}
      .titlebar-icon {{
        width: 14px; height: 14px;
        border-radius: 50%;
        background: var(--blue-dim);
        border: 1px solid var(--blue);
      }}
      .titlebar-text {{
        font-size: 13.5px;
        font-weight: 600;
        color: var(--text-bright);
      }}
      .toolbar {{
        padding: 9px 16px;
        border-bottom: 1px solid var(--border);
        background: var(--surface);
        display: flex;
        gap: 8px 14px;
        align-items: baseline;
      }}
      .toolbar-label {{
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--blue);
        background: rgba(130, 170, 255, 0.14);
        border: 1px solid rgba(130, 170, 255, 0.3);
        border-radius: 999px;
        padding: 3px 8px;
      }}
      .toolbar-path {{
        font-family: var(--mono);
        font-size: 12px;
        color: var(--muted);
        overflow-wrap: anywhere;
      }}
      .viewer-body {{ padding: 16px; background: var(--bg); }}
      .component-panel {{
        margin-bottom: 16px;
        border: 1px solid var(--border);
        border-radius: 10px;
        background: rgba(10, 15, 24, 0.72);
        overflow: hidden;
      }}
      .component-panel:last-child {{ margin-bottom: 0; }}
      .component-head {{
        padding: 12px 16px;
        background: var(--surface-3);
        border-bottom: 1px solid var(--border-strong);
      }}
      .component-title {{
        font-size: 15px;
        font-weight: 600;
        color: var(--text-bright);
      }}
      .component-signature {{
        margin-top: 5px;
        font-family: var(--mono);
        font-size: 12px;
        color: var(--muted);
        overflow-wrap: anywhere;
      }}
      .component-body {{ padding: 12px; background: rgba(7, 11, 18, 0.84); }}
      .tree-node {{
        margin-left: 20px;
        padding: 4px 0;
        border-left: 1px solid var(--border);
      }}
      .tree-label {{
        font-family: var(--mono);
        font-size: 12px;
        line-height: 1.6;
        color: var(--text-bright);
        padding: 2px 8px;
        border-radius: 4px;
      }}
      .tree-label.tag {{ background: var(--blue-dim); }}
      .tree-label.component {{ background: var(--green-dim); color: var(--green); }}
      .tree-label.expr {{ background: var(--purple-dim); color: var(--purple); }}
      .tree-label.text {{ color: var(--muted); }}
      .tree-label.script {{ background: var(--orange-dim); color: var(--orange); }}
      .tree-label.style {{ background: var(--teal-dim); color: var(--teal); }}
      .tree-label.fragment {{ background: var(--blue-dim); color: var(--blue); }}
      .empty {{ color: var(--muted); font-style: italic; font-size: 12px; padding: 12px; }}
      .empty-file {{ padding: 24px; color: var(--muted); }}
    </style>
  </head>
  <body>
    <div class="viewer">
      <div class="titlebar">
        <div class="titlebar-icon"></div>
        <span class="titlebar-text">Swifta &middot; Astro Structure Viewer</span>
      </div>
      <div class="toolbar">
        <span class="toolbar-label">Astro</span>
        <code class="toolbar-path">{escape(diagram.source_location)}</code>
      </div>
      <main class="viewer-body">{sections}</main>
    </div>
  </body>
</html>
"""

    def _render_component(self, comp: ComponentStructure) -> str:
        body = self._render_steps(comp.steps) if comp.steps else ""
        if not body:
            body = '<div class="empty">Self-closing</div>'
        return (
            '<section class="component-panel">'
            '<div class="component-head">'
            f'<h2 class="component-title">{escape(comp.qualified_name)}</h2>'
            f'<div class="component-signature">{escape(comp.signature)}</div>'
            "</div>"
            f'<div class="component-body">{body}</div>'
            "</section>"
        )

    def _render_steps(self, steps: tuple[TemplateStep, ...]) -> str:
        if not steps:
            return ""
        return "".join(self._render_step(step) for step in steps)

    def _render_step(self, step: TemplateStep) -> str:
        if isinstance(step, ElementStep):
            children_html = self._render_steps(step.children) if step.children else ""
            return (
                f'<div class="tree-node">'
                f'<span class="tree-label tag">&lt;{escape(step.tag)}&gt;{escape(step.attributes)}</span>'
                f"{children_html}"
                "</div>"
            )
        if isinstance(step, ComponentStep):
            children_html = self._render_steps(step.children) if step.children else ""
            return (
                f'<div class="tree-node">'
                f'<span class="tree-label component">&lt;{escape(step.name)}&gt;{escape(step.attributes)}</span>'
                f"{children_html}"
                "</div>"
            )
        if isinstance(step, FragmentStep):
            children_html = self._render_steps(step.children) if step.children else ""
            return (
                '<div class="tree-node">'
                '<span class="tree-label fragment">&lt;Fragment&gt;</span>'
                f"{children_html}"
                "</div>"
            )
        if isinstance(step, ExpressionStep):
            return (
                f'<div class="tree-node">'
                f'<span class="tree-label expr">{escape(step.content)}</span>'
                "</div>"
            )
        if isinstance(step, TextStep):
            content = step.content.strip()
            if not content:
                return ""
            return (
                f'<div class="tree-node">'
                f'<span class="tree-label text">{escape(content)}</span>'
                "</div>"
            )
        if isinstance(step, ScriptStep):
            return (
                '<div class="tree-node">'
                f'<span class="tree-label script">&lt;script&gt;</span>'
                "</div>"
            )
        if isinstance(step, StyleStep):
            return (
                '<div class="tree-node">'
                f'<span class="tree-label style">&lt;style&gt;</span>'
                "</div>"
            )
        return ""
