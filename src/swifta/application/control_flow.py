"""Use cases for structured template diagrams."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from swifta.domain.ports import AstroStructureExtractor, NassiDiagramRenderer, SourceRepository


@dataclass(frozen=True, slots=True)
class BuildNassiDiagramCommand:
    path: str


@dataclass(frozen=True, slots=True)
class BuildNassiDirectoryCommand:
    root_path: str


@dataclass(frozen=True, slots=True)
class NassiDiagramDocumentDTO:
    source_location: str
    component_count: int
    component_names: tuple[str, ...]
    html: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_location": self.source_location,
            "component_count": self.component_count,
            "component_names": list(self.component_names),
        }


@dataclass(frozen=True, slots=True)
class NassiDiagramBundleDTO:
    root_path: str
    document_count: int
    documents: tuple[NassiDiagramDocumentDTO, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "root_path": self.root_path,
            "document_count": self.document_count,
            "documents": [document.to_dict() for document in self.documents],
        }


@dataclass(slots=True)
class NassiDiagramService:
    source_repository: SourceRepository
    extractor: AstroStructureExtractor
    renderer: NassiDiagramRenderer

    def build_file_diagram(self, command: BuildNassiDiagramCommand) -> NassiDiagramDocumentDTO:
        source_unit = self.source_repository.load_file(command.path)
        return self._build_document(source_unit)

    def build_directory_diagrams(self, command: BuildNassiDirectoryCommand) -> NassiDiagramBundleDTO:
        source_units = tuple(self.source_repository.list_astro_sources(command.root_path))
        documents = tuple(self._build_document(source_unit) for source_unit in source_units)
        return NassiDiagramBundleDTO(
            root_path=str(Path(command.root_path).expanduser().resolve()),
            document_count=len(documents),
            documents=documents,
        )

    def _build_document(self, source_unit) -> NassiDiagramDocumentDTO:
        diagram = self.extractor.extract(source_unit)
        return NassiDiagramDocumentDTO(
            source_location=diagram.source_location,
            component_count=len(diagram.components),
            component_names=tuple(comp.qualified_name for comp in diagram.components),
            html=self.renderer.render(diagram),
        )
