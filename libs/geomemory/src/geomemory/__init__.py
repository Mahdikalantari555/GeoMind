"""GeoMemory — multimodal, spatiotemporal knowledge engine for remote sensing research."""

from __future__ import annotations

__version__ = "0.1.0"

from geomemory.core.exceptions import (
    AbstentionError,
    AssetNotFoundError,
    CollectionNotFoundError,
    DatabaseError,
    EmbeddingUnavailableError,
    GeoMemoryError,
    ModelNotLoadedError,
    NetworkDisabledError,
    UnsupportedFormatError,
    WorkspaceExistsError,
    WorkspaceNotFoundError,
)
from geomemory.core.models import (
    Answer,
    Asset,
    AssetRevision,
    CandidateMemory,
    Citation,
    Collection,
    EmbeddingRecord,
    Entity,
    FeedbackEvent,
    Job,
    KnowledgeChangeProposal,
    QAResult,
    RetrievalRun,
    SearchFilters,
    SearchHit,
    SearchResult,
    Segment,
    SpatialFilter,
    TemporalFilter,
    Turn,
    Workspace,
    WorkspaceConfig,
)
from geomemory.core.workspace import GeoMemory
from geomemory.embeddings.hub import EmbeddingModelHub
from geomemory.services.doctor import (
    doctor_embedding,
    doctor_environment,
    doctor_llm_provider,
    doctor_workspace,
)

__all__ = [
    "__version__",
    # Entry point
    "GeoMemory",
    "EmbeddingModelHub",
    "doctor_embedding",
    "doctor_environment",
    "doctor_llm_provider",
    "doctor_workspace",
    # Exceptions
    "AbstentionError",
    "AssetNotFoundError",
    "CollectionNotFoundError",
    "DatabaseError",
    "EmbeddingUnavailableError",
    "GeoMemoryError",
    "ModelNotLoadedError",
    "NetworkDisabledError",
    "UnsupportedFormatError",
    "WorkspaceExistsError",
    "WorkspaceNotFoundError",
    # Models
    "Answer",
    "Asset",
    "AssetRevision",
    "CandidateMemory",
    "Citation",
    "Collection",
    "EmbeddingRecord",
    "Entity",
    "FeedbackEvent",
    "Job",
    "KnowledgeChangeProposal",
    "QAResult",
    "RetrievalRun",
    "SearchFilters",
    "SearchResult",
    "SearchHit",
    "Segment",
    "SpatialFilter",
    "TemporalFilter",
    "Workspace",
    "WorkspaceConfig",
    "Turn",
]
