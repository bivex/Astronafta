# Swifta

Swifta is a hexagonal Astro template parser built on top of ANTLR. It parses `.astro` files and produces a structural model of components, HTML elements, expressions, scripts, and styles — rendered as interactive HTML tree diagrams.

The project starts from the domain, not from the framework:

* **business goal**: convert Astro source into a stable structural model for downstream tooling
* **architectural style**: DDD-inspired layered monolith with hexagonal boundaries
* **parser engine**: ANTLR4 with a custom Astro grammar (lexer modes for frontmatter, tags, expressions, scripts, and styles)
* **delivery channel**: CLI that parses a file or directory and outputs HTML structure diagrams

## What the system does

* **Parsing Astro templates**
  * parse a single `.astro` file
  * parse a directory of `.astro` files recursively
  * extract a structural model: frontmatter, HTML elements, components (PascalCase tags), fragments, template expressions, scripts, and styles

* **Structure diagrams**
  * build an HTML tree diagram for a single `.astro` file showing the full component hierarchy
  * build diagram bundles for entire directories with an index page linking all files
  * color-coded node types: HTML tags (blue), components (green), expressions (purple), text (muted), scripts (orange), styles (teal), fragments (blue)
  * dark theme with JetBrains Mono and IBM Plex Sans fonts

* **Architecture**
  * parser infrastructure behind ports so the application layer stays independent from ANTLR, filesystem, and CLI details

## Quick Start

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Generate the ANTLR parser from the vendored grammar:

```bash
uv run python scripts/generate_astro_parser.py
```

3. Parse a single file:

```bash
uv run swifta parse-file path/to/page.astro
```

4. Parse a directory:

```bash
uv run swifta parse-dir path/to/astro-project/src
```

5. Build a structure diagram for a single file:

```bash
uv run swifta struct-file path/to/page.astro --out output/page.struct.html
```

6. Build structure diagrams for an entire directory:

```bash
uv run swifta struct-dir path/to/astro-project/src --out output/struct-bundle
```

## Code Smells

Swifta can detect common Astro code smells and anti-patterns in your templates:

### Detect smells in a single file:

```bash
uv run swifta smell-file src/components/hero.astro
```

### Detect smells in an entire directory:

```bash
uv run swifta smell-dir src/
```

### Output format

Results are returned as JSON with detailed information:

```json
{
  "root_path": "src/",
  "file_count": 23,
  "total_smells": 29,
  "total_warnings": 26,
  "reports": [
    {
      "source_location": "src/components/hero.astro",
      "smell_count": 3,
      "warning_count": 2,
      "info_count": 1,
      "smells": [
        {
          "kind": "duplicate-component-names",
          "severity": "warning",
          "message": "Component 'Icon' appears 2 times",
          "line": null,
          "context": "Icon"
        },
        {
          "kind": "unused-import",
          "severity": "info",
          "message": "Component 'heroImage' imported but not used in template",
          "line": null,
          "context": "heroImage"
        }
      ]
    }
  ]
}
```

### Detected smell types

| Smell | Severity | Description |
|-------|----------|-------------|
| `deep-nesting` | ⚠️ Warning | Elements nested >6 levels deep |
| `too-many-children` | ⚠️ Warning | Parent element with >10 direct children |
| `large-component` | ⚠️ Warning | Component with >100 lines of code |
| `too-many-props` | ⚠️ Warning | HTML element with >8 attributes |
| `too-many-components` | ⚠️ Warning | File imports >10 different components |
| `too-many-expressions` | ⚠️ Warning | >15 template expressions in one file |
| `inline-style` | ⚠️ Warning | Inline `style` attributes found |
| `script-in-component` | ⚠️ Warning | `<script>` tag without `is:inline` in component |
| `duplicate-component-names` | ⚠️ Warning | Same component imported multiple times |
| `empty-component` | ⚠️ Warning | Component with no content or children |
| `client-directive-overuse` | ⚠️ Warning | >30% of elements have `client:*` directives |
| `missing-client-directive` | ⚠️ Warning | Interactive element without `client:*` directive |
| `env-in-client-component` | ⚠️ Warning | `Import.meta.env` used in client-side component |
| `unused-import` | ℹ️ Info | Imported component never used in template |
| `image-without-dimensions` | ℹ️ Info | `<img>` without explicit width/height |
| `hardcoded-base-url` | ℹ️ Info | Hardcoded `/` base path instead of `import.meta.env.BASE_URL` |
| `excessive-global-styles` | ℹ️ Info | Global CSS rules that may cause conflicts |

### Exit codes

- `0` — No warnings found (clean)
- `1` — Warnings detected (non-zero for CI/CD)
- `2` — Technical failure (parser error, file not found)

### Filtering output

Extract only files with warnings:

```bash
uv run swifta smell-dir src/ | python3 -c "
import json, sys
data = json.load(sys.stdin)
for report in data['reports']:
    if report['warning_count'] > 0:
        print(f\"{report['source_location']}: {report['warning_count']} warnings\")
"
```

## Screenshots

**Structure diagram** — component hierarchy for an Astro page with nested HTML elements and component tags:

![Structure diagram](docs/screenshots/struct_diagram.png)

**Directory index** — overview of all parsed `.astro` files with component counts:

![Directory index](docs/screenshots/struct_index.png)

## Architecture

The codebase is split into four explicit layers:

* `domain`: domain model, control flow types, ports, and domain events
* `application`: use cases and DTOs
* `infrastructure`: ANTLR adapter, filesystem adapters, HTML rendering
* `presentation`: CLI contract

```
src/swifta/
├── domain/
│   ├── model.py              # StructuralElementKind, SourceUnit
│   ├── control_flow.py       # TemplateStep types, StructureDiagram
│   └── ports.py              # AstroSyntaxParser, AstroStructureExtractor, NassiDiagramRenderer
├── application/
│   └── control_flow.py       # Use case: parse & render
├── infrastructure/
│   ├── antlr/
│   │   ├── runtime.py        # ANTLR loader and parse helpers
│   │   ├── parser_adapter.py # AntlrAstroSyntaxParser
│   │   └── control_flow_extractor.py  # AntlrAstroStructureExtractor
│   ├── filesystem/
│   │   └── source_repository.py       # .astro file discovery
│   └── rendering/
│       └── struct_html_renderer.py    # HTML tree diagram renderer
└── presentation/
    └── cli/
        └── main.py           # Typer CLI
```

## Grammar

The Astro grammar lives in `resources/grammars/astro/` as a git submodule. The lexer uses seven modes:

| Mode | Purpose |
|---|---|
| `DEFAULT` | Top-level template content |
| `FRONTMATTER` | Content between `---` delimiters |
| `TAG` | Inside HTML/component tag attributes |
| `EXPR` | Template expressions `{...}` |
| `SCRIPT` | `<script>` block content |
| `STYLE` | `<style>` block content |

## Next Steps

Useful future extensions:

* component prop type extraction from frontmatter
* component dependency graph visualization
* unused component detection
* interactive HTML diagrams with collapsible nodes
* export to other formats (SVG, Mermaid)
* integration with Astro dev server as a plugin
