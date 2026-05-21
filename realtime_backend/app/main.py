"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from .api.routes import router as http_router
from .api.ws import router as ws_router
from .config import get_settings
from .pipeline.orchestrator import TranscriptionPipeline
from .services.conversation_store import ConversationStore
from .services.media import FFmpegAudioNormalizer
from .services.quality import TranscriptQualityService
from .services.query import KeywordMemoryQueryService
from .services.hybrid_memory_query_service import HybridMemoryQueryService
from .services.graph_reasoning import GraphReasoningService
from .services.graph_repository import ProductionGraphRepository
from .services.vector_repository import VectorRepository
from .services.local_embedding_provider import MockLocalEmbeddingProvider, SentenceTransformerEmbeddingProvider
from .services.streaming import StreamingTranscriptionService
from .services.transcription_service import TranscriptionService
from .services.job_manager import JobManager
from .utils.ids import new_segment_id
from .utils.logging import configure_logging
from .database_proxy import DatabaseProxy


def build_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    store = ConversationStore(settings.data_dir / "transcripts")
    
    # Production Data Layer
    db_path = settings.data_dir / "collective_mindgraph.sqlite3"
    db = DatabaseProxy(db_path)
    db.initialize()
    graph_repo = ProductionGraphRepository(db)
    # Embedding Provider
    if settings.embedding_provider == "sentence_transformer":
        embedding_provider = SentenceTransformerEmbeddingProvider(
            model_path=settings.embedding_model_path,
            device="cpu"  # Default to cpu for stability in backend
        )
    else:
        embedding_provider = MockLocalEmbeddingProvider(dim=settings.embedding_dimension)
    
    vector_repo = VectorRepository(db, expected_dim=embedding_provider.dimension)
    
    normalizer = FFmpegAudioNormalizer(sample_rate=settings.sample_rate, channels=settings.channels)
    pipeline = TranscriptionPipeline(settings=settings)
    quality_service = TranscriptQualityService()
    transcription_service = TranscriptionService(
        settings=settings,
        pipeline=pipeline,
        store=store,
        normalizer=normalizer,
    )
    streaming_service = StreamingTranscriptionService(
        settings=settings,
        pipeline=pipeline,
        normalizer=normalizer,
        store=store,
    )
    
    # Hybrid Query Service
    query_service = HybridMemoryQueryService(
        graph_repo=graph_repo,
        vector_repo=vector_repo,
        embedding_provider=embedding_provider
    )
    
    from .services.evidence_answer_service import EvidenceAnswerService
    from .services.llm_assisted_ask_service import LLMAssistedAskService
    from .pipeline.local_llm_provider import LocalLLMEndpointProvider

    # ... (inside build_app)
    reasoning_service = GraphReasoningService(graph_repo=graph_repo)
    evidence_service = EvidenceAnswerService(reasoning_service)
    
    llm_endpoint = settings.llm_endpoint or "http://127.0.0.1:1234/v1"
    llm_provider = LocalLLMEndpointProvider(
        base_url=llm_endpoint, 
        timeout=int(settings.llm_timeout_seconds),
        allow_remote=settings.allow_remote_access
    )
    llm_assisted_service = LLMAssistedAskService(llm_provider)
    
    # Job Manager
    job_manager = JobManager(db)

    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.state.settings = settings
    app.state.transcription_service = transcription_service
    app.state.streaming_service = streaming_service
    app.state.quality_service = quality_service
    app.state.query_service = query_service
    app.state.reasoning_service = reasoning_service
    app.state.evidence_service = evidence_service
    app.state.llm_assisted_service = llm_assisted_service
    app.state.graph_repo = graph_repo
    app.state.vector_repo = vector_repo
    app.state.job_manager = job_manager
    app.state.id_factory = new_segment_id
    app.include_router(http_router)
    app.include_router(ws_router)
    return app


app = build_app()
