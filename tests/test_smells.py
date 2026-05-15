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
