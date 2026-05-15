import json
import subprocess
import sys
from pathlib import Path

from swifta.application.smells import (
    DetectDirectorySmellsCommand,
    DetectSmellsCommand,
    SmellDetectionService,
)
from swifta.domain.model import SourceUnit, SourceUnitId
from swifta.domain.smells import CodeSmellKind, SmellSeverity
from swifta.infrastructure.antlr.control_flow_extractor import AntlrAstroStructureExtractor
from swifta.infrastructure.filesystem.source_repository import FileSystemSourceRepository
from swifta.infrastructure.smells.diagram_smell_detector import (
    SmellThresholds,
    StructureDiagramSmellDetector,
)

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


def _build_service(thresholds: SmellThresholds | None = None) -> SmellDetectionService:
    _ensure_generated_parser()
    extractor = AntlrAstroStructureExtractor()
    return SmellDetectionService(
        source_repository=FileSystemSourceRepository(),
        detector=StructureDiagramSmellDetector(extractor=extractor, thresholds=thresholds),
    )


def _detect_source(content: str, thresholds: SmellThresholds | None = None) -> list[CodeSmellKind]:
    _ensure_generated_parser()
    extractor = AntlrAstroStructureExtractor()
    detector = StructureDiagramSmellDetector(extractor=extractor, thresholds=thresholds)
    source = SourceUnit(
        identifier=SourceUnitId("test"),
        location="test.astro",
        content=content,
    )
    report = detector.detect(source)
    return [smell.kind for smell in report.smells]


# --- Structural smells ---

def test_empty_component_detected() -> None:
    kinds = _detect_source("---\n---\n<Layout></Layout>")
    assert CodeSmellKind.EMPTY_COMPONENT in kinds


def test_deep_nesting_detected() -> None:
    kinds = _detect_source(
        "---\n---\n"
        "<A><B><C><D><E><F><G><H>deep</H></G></F></E></D></C></B></A>"
    )
    assert CodeSmellKind.DEEP_NESTING in kinds


def test_no_deep_nesting_under_threshold() -> None:
    kinds = _detect_source(
        "---\n---\n<A><B><C>ok</C></B></A>",
        thresholds=SmellThresholds(nesting_depth=6),
    )
    assert CodeSmellKind.DEEP_NESTING not in kinds


def test_duplicate_component_names_detected() -> None:
    kinds = _detect_source(
        "---\n---\n<Card />\n<Card />"
    )
    assert CodeSmellKind.DUPLICATE_COMPONENT_NAMES in kinds


def test_inline_style_detected() -> None:
    kinds = _detect_source(
        '---\n---\n<Layout><div style="color: red;">styled</div></Layout>'
    )
    assert CodeSmellKind.INLINE_STYLE in kinds


def test_too_many_components_detected() -> None:
    components = "\n".join(f"<Comp{i} />" for i in range(12))
    kinds = _detect_source(
        f"---\n---\n{components}",
        thresholds=SmellThresholds(max_components=10),
    )
    assert CodeSmellKind.TOO_MANY_COMPONENTS in kinds


def test_large_component_detected() -> None:
    children = "".join(f"<div>{i}</div>" for i in range(35))
    kinds = _detect_source(
        f"---\n---\n<Big>{children}</Big>",
        thresholds=SmellThresholds(max_descendants=30),
    )
    assert CodeSmellKind.LARGE_COMPONENT in kinds


# --- Astro-specific smells ---

def test_client_directive_overuse_detected() -> None:
    kinds = _detect_source(
        "---\n---\n"
        "<Widget client:load />\n"
        "<Chart client:load />\n"
        "<Map client:load />\n"
        "<Modal client:load />",
        thresholds=SmellThresholds(max_client_load=3),
    )
    assert CodeSmellKind.CLIENT_DIRECTIVE_OVERUSE in kinds


def test_no_client_overuse_under_threshold() -> None:
    kinds = _detect_source(
        "---\n---\n<Widget client:load />\n<Chart client:load />",
        thresholds=SmellThresholds(max_client_load=3),
    )
    assert CodeSmellKind.CLIENT_DIRECTIVE_OVERUSE not in kinds


def test_missing_client_directive_detected() -> None:
    kinds = _detect_source(
        '---\nimport Counter from "./Counter.tsx"\n---\n<Counter />'
    )
    assert CodeSmellKind.MISSING_CLIENT_DIRECTIVE in kinds


def test_no_missing_client_when_directive_present() -> None:
    kinds = _detect_source(
        '---\nimport Counter from "./Counter.tsx"\n---\n<Counter client:load />'
    )
    assert CodeSmellKind.MISSING_CLIENT_DIRECTIVE not in kinds


def test_unused_import_detected() -> None:
    kinds = _detect_source(
        '---\nimport Header from "./Header.astro"\n---\n<Layout>content</Layout>'
    )
    assert CodeSmellKind.UNUSED_IMPORT in kinds


def test_no_unused_import_when_used() -> None:
    kinds = _detect_source(
        '---\nimport Header from "./Header.astro"\n---\n<Header />'
    )
    assert CodeSmellKind.UNUSED_IMPORT not in kinds


def test_image_without_dimensions_detected() -> None:
    kinds = _detect_source(
        '---\n---\n<Layout><img src="photo.jpg" alt="photo" /></Layout>'
    )
    assert CodeSmellKind.IMAGE_WITHOUT_DIMENSIONS in kinds


def test_image_with_dimensions_not_flagged() -> None:
    kinds = _detect_source(
        '---\n---\n<Layout><img src="photo.jpg" width="800" height="600" /></Layout>'
    )
    assert CodeSmellKind.IMAGE_WITHOUT_DIMENSIONS not in kinds


def test_hardcoded_base_url_detected() -> None:
    kinds = _detect_source(
        '---\n---\n<Layout><a href="http://localhost:4321/api">API</a></Layout>'
    )
    assert CodeSmellKind.HARDCODED_BASE_URL in kinds


def test_env_in_client_component_detected() -> None:
    kinds = _detect_source(
        '---\n---\n<Widget client:load>{import.meta.env.SECRET_KEY}</Widget>'
    )
    assert CodeSmellKind.ENV_IN_CLIENT_COMPONENT in kinds


def test_no_env_warning_without_secret() -> None:
    kinds = _detect_source(
        '---\n---\n<Widget client:load>{import.meta.env.PUBLIC_API_URL}</Widget>'
    )
    assert CodeSmellKind.ENV_IN_CLIENT_COMPONENT not in kinds


def test_excessive_global_styles_detected() -> None:
    kinds = _detect_source(
        '---\n---\n<Component><style is:global>p { color: red; }</style></Component>'
    )
    assert CodeSmellKind.EXCESSIVE_GLOBAL_STYLES in kinds


def test_global_styles_ok_in_layout() -> None:
    extractor = AntlrAstroStructureExtractor()
    detector = StructureDiagramSmellDetector(extractor=extractor)
    source = SourceUnit(
        identifier=SourceUnitId("test"),
        location="src/layouts/Layout.astro",
        content="---\n---\n<style is:global>p { color: red; }</style>",
    )
    report = detector.detect(source)
    kinds = [s.kind for s in report.smells]
    assert CodeSmellKind.EXCESSIVE_GLOBAL_STYLES not in kinds


# --- Integration tests ---

def test_smell_service_detects_file() -> None:
    service = _build_service()
    report = service.detect_file_smells(
        DetectSmellsCommand(path=str(ROOT / "tests" / "fixtures" / "deeply_nested.astro"))
    )
    assert report.smell_count > 0
    assert report.source_location.endswith("deeply_nested.astro")


def test_smell_service_detects_directory() -> None:
    service = _build_service()
    bundle = service.detect_directory_smells(
        DetectDirectorySmellsCommand(root_path=str(ROOT / "tests" / "fixtures"))
    )
    assert bundle.file_count >= 4
    assert bundle.total_smells > 0


def test_smell_file_cli_outputs_json() -> None:
    _ensure_generated_parser()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "swifta.presentation.cli.main",
            "smell-file",
            str(ROOT / "tests" / "fixtures" / "deeply_nested.astro"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1)
    payload = json.loads(result.stdout)
    assert "smells" in payload
    assert payload["smell_count"] > 0


def test_smell_dir_cli_outputs_json() -> None:
    _ensure_generated_parser()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "swifta.presentation.cli.main",
            "smell-dir",
            str(ROOT / "tests" / "fixtures"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1)
    payload = json.loads(result.stdout)
    assert "reports" in payload
    assert payload["file_count"] >= 4


def test_smell_severity_counts() -> None:
    _ensure_generated_parser()
    detector = StructureDiagramSmellDetector(
        extractor=AntlrAstroStructureExtractor(),
    )
    source = SourceUnit(
        identifier=SourceUnitId("test"),
        location="test.astro",
        content="---\n---\n<Layout></Layout>",
    )
    report = detector.detect(source)
    assert report.warning_count + report.info_count == report.smell_count
