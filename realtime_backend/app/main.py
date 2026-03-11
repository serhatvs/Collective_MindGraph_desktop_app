"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from .api.routes import router as http_router
from .api.ws import router as ws_router
from .config import get_settings
from .pipeline.orchestrator import TranscriptionPipeline
from .services.conversation_store import ConversationStore
from .services.media import FFmpegAudioNormalizer
from .services.streaming import StreamingTranscriptionService
from .services.transcription_service import TranscriptionService
from .utils.ids import new_segment_id
from .utils.logging import configure_logging


def build_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    store = ConversationStore(settings.data_dir / "transcripts")
    normalizer = FFmpegAudioNormalizer(sample_rate=settings.sample_rate, channels=settings.channels)
    pipeline = TranscriptionPipeline(settings=settings)
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

    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.state.settings = settings
    app.state.transcription_service = transcription_service
    app.state.streaming_service = streaming_service
    app.state.id_factory = new_segment_id
    app.include_router(http_router)
    app.include_router(ws_router)
    return app


app = build_app()
