import json
import subprocess
import sys
from pathlib import Path

from swifta.application.control_flow import (
    BuildStructDiagramCommand,
    BuildStructDirectoryCommand,
    StructDiagramService,
)
from swifta.domain.control_flow import (
    ComponentStructure,
    StructureDiagram,
)
from swifta.domain.model import SourceUnit, SourceUnitId
from swifta.infrastructure.antlr.control_flow_extractor import AntlrAstroStructureExtractor
from swifta.infrastructure.filesystem.source_repository import FileSystemSourceRepository
from swifta.infrastructure.rendering.struct_html_renderer import HtmlStructureDiagramRenderer


ROOT = Path(__file__).resolve().parent.parent


def _ensure_generated_parser() -> None:
    generated_parser = (
        ROOT / "src" / "swifta" / "infrastructure" / "antlr" / "generated" / "astro" / "AstroParser.py"
    )
    if generated_parser.exists():
        return
    subprocess.run(
        [sys.executable, "scripts/generate_astro_parser.py"],
        cwd=ROOT,
        check=True,
    )


def _build_service() -> StructDiagramService:
    _ensure_generated_parser()
    return StructDiagramService(
        source_repository=FileSystemSourceRepository(),
        extractor=AntlrAstroStructureExtractor(),
        renderer=HtmlStructureDiagramRenderer(),
    )


def test_struct_service_builds_html_document() -> None:
    service = _build_service()
    document = service.build_file_diagram(
        BuildStructDiagramCommand(path=str(ROOT / "tests" / "fixtures" / "components.astro"))
    )

    assert document.component_count >= 1
    assert "Header" in document.component_names or "Main" in document.component_names
    assert "Astro" in document.html


def test_struct_service_builds_directory_bundle() -> None:
    service = _build_service()
    bundle = service.build_directory_diagrams(
        BuildStructDirectoryCommand(root_path=str(ROOT / "tests" / "fixtures"))
    )

    assert bundle.document_count >= 2
    assert bundle.root_path == str((ROOT / "tests" / "fixtures").resolve())


def test_structure_extractor_extracts_components() -> None:
    _ensure_generated_parser()
    extractor = AntlrAstroStructureExtractor()
    source = SourceUnit(
        identifier=SourceUnitId("test"),
        location="test.astro",
        content="""---
title: Test
---
<Layout>
  <Header />
  <Card title="hello" />
</Layout>
""",
    )

    diagram = extractor.extract(source)
    assert len(diagram.components) >= 1
    names = [comp.name for comp in diagram.components]
    assert "Layout" in names


def test_struct_cli_writes_html_file(tmp_path: Path) -> None:
    _ensure_generated_parser()
    output_path = tmp_path / "components.html"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "swifta.presentation.cli.main",
            "struct-file",
            str(ROOT / "tests" / "fixtures" / "components.astro"),
            "--out",
            str(output_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["output_path"] == str(output_path.resolve())
    assert output_path.exists()
    assert "Astro Structure Viewer" in output_path.read_text(encoding="utf-8")


def test_struct_dir_cli_writes_html_bundle(tmp_path: Path) -> None:
    _ensure_generated_parser()
    output_dir = tmp_path / "struct-bundle"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "swifta.presentation.cli.main",
            "struct-dir",
            str(ROOT / "tests" / "fixtures"),
            "--out",
            str(output_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["output_dir"] == str(output_dir.resolve())
    assert (output_dir / "index.html").exists()
    assert "Astro Index" in (output_dir / "index.html").read_text(encoding="utf-8")


def test_renderer_produces_html() -> None:
    renderer = HtmlStructureDiagramRenderer()
    diagram = StructureDiagram(
        source_location="test.astro",
        components=(
            ComponentStructure(
                name="Layout",
                signature="<Layout>",
                container=None,
                steps=(),
            ),
        ),
    )
    html = renderer.render(diagram)
    assert "Layout" in html
    assert "Astro" in html
