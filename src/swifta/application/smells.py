"""Use cases for Astro template code smell detection."""

from __future__ import annotations

from dataclasses import dataclass

from swifta.domain.ports import AstroSmellDetector, SourceRepository


@dataclass(frozen=True, slots=True)
class DetectSmellsCommand:
    path: str


@dataclass(frozen=True, slots=True)
class DetectDirectorySmellsCommand:
    root_path: str


@dataclass(frozen=True, slots=True)
class SmellDTO:
    kind: str
    severity: str
    message: str
    line: int | None
    context: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "context": self.context,
        }


@dataclass(frozen=True, slots=True)
class SmellReportDTO:
    source_location: str
    smell_count: int
    warning_count: int
    info_count: int
    smells: tuple[SmellDTO, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_location": self.source_location,
            "smell_count": self.smell_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "smells": [s.to_dict() for s in self.smells],
        }


@dataclass(frozen=True, slots=True)
class SmellBundleDTO:
    root_path: str
    file_count: int
    total_smells: int
    total_warnings: int
    reports: tuple[SmellReportDTO, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "root_path": self.root_path,
            "file_count": self.file_count,
            "total_smells": self.total_smells,
            "total_warnings": self.total_warnings,
            "reports": [r.to_dict() for r in self.reports],
        }


@dataclass(slots=True)
class SmellDetectionService:
    source_repository: SourceRepository
    detector: AstroSmellDetector

    def detect_file_smells(self, command: DetectSmellsCommand) -> SmellReportDTO:
        source_unit = self.source_repository.load_file(command.path)
        return self._detect(source_unit)

    def detect_directory_smells(self, command: DetectDirectorySmellsCommand) -> SmellBundleDTO:
        source_units = tuple(self.source_repository.list_astro_sources(command.root_path))
        reports = tuple(self._detect(su) for su in source_units)
        return SmellBundleDTO(
            root_path=command.root_path,
            file_count=len(reports),
            total_smells=sum(r.smell_count for r in reports),
            total_warnings=sum(r.warning_count for r in reports),
            reports=reports,
        )

    def _detect(self, source_unit) -> SmellReportDTO:
        report = self.detector.detect(source_unit)
        return SmellReportDTO(
            source_location=report.source_location,
            smell_count=report.smell_count,
            warning_count=report.warning_count,
            info_count=report.info_count,
            smells=tuple(
                SmellDTO(
                    kind=smell.kind.value,
                    severity=smell.severity.value,
                    message=smell.message,
                    line=smell.line,
                    context=smell.context,
                )
                for smell in report.smells
            ),
        )
