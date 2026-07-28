"""Engine composition root for canonical use cases and persistence."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.application import (
    ArchiveMeeting,
    CreateMeeting,
    DeleteMeeting,
    GetDashboard,
    GetMeeting,
    ListMeetings,
    RenameMeeting,
    ReviewInsight,
    UpdateTranscriptSegment,
)
from collective_mindgraph.application.transcription.build_quality_report import (
    BuildTranscriptQualityReport,
)
from collective_mindgraph.application.transcription.live_capture import CaptureLiveAudio
from collective_mindgraph.application.transcription.process_recording import (
    ProcessRecording,
)
from collective_mindgraph.application.transcription.transcribe_recording import (
    TranscribeRecording,
)
from collective_mindgraph.infrastructure.audio.recording_storage import (
    ManagedRecordingStorage,
)
from collective_mindgraph.infrastructure.persistence import (
    CanonicalTranscriptionResultArchive,
    LegacyDataMigrator,
    MigrationReport,
    SqliteDatabase,
    SqliteDataExchange,
    SqliteEmbeddingStore,
    SqliteInsightStore,
    SqliteJobStore,
    SqliteKnowledgeGraphStore,
    SqliteMeetingStore,
    SqliteRecordingStore,
    SqliteTranscriptStore,
    discover_legacy_sources,
)
from collective_mindgraph.infrastructure.settings import EnginePreferenceStore

from .recording_jobs import RecordingJobCoordinator
from .runtime_manager import EngineRuntimeBundle, EngineRuntimeManager
from .runtime_paths import canonical_database_path
from .settings import EngineSettings


@dataclass(frozen=True, slots=True)
class EngineContext:
    settings: EngineSettings
    migration: MigrationReport
    database: SqliteDatabase
    data_exchange: SqliteDataExchange
    preferences: EnginePreferenceStore
    meetings: SqliteMeetingStore
    recordings: SqliteRecordingStore
    transcripts: SqliteTranscriptStore
    insights: SqliteInsightStore
    knowledge: SqliteKnowledgeGraphStore
    embeddings: SqliteEmbeddingStore
    jobs: SqliteJobStore
    create_meeting: CreateMeeting
    get_meeting: GetMeeting
    list_meetings: ListMeetings
    rename_meeting: RenameMeeting
    archive_meeting: ArchiveMeeting
    delete_meeting: DeleteMeeting
    dashboard: GetDashboard
    review_insight: ReviewInsight
    update_transcript_segment: UpdateTranscriptSegment
    build_quality_report: BuildTranscriptQualityReport
    runtime: EngineRuntimeManager
    recording_storage: ManagedRecordingStorage
    recording_jobs: RecordingJobCoordinator

    @property
    def runtime_bundle(self) -> EngineRuntimeBundle:
        return self.runtime.snapshot()

    @property
    def transcribe_recording(self) -> TranscribeRecording:
        return self.runtime_bundle.transcribe_recording

    @property
    def process_recording(self) -> ProcessRecording:
        return self.runtime_bundle.process_recording

    @property
    def capture_live_audio(self) -> CaptureLiveAudio:
        return self.runtime_bundle.capture_live_audio

    @property
    def search_memory(self):
        return self.runtime_bundle.search_memory

    @property
    def answer_memory(self):
        return self.runtime_bundle.answer_memory


def build_engine_context(settings: EngineSettings) -> EngineContext:
    """Prepare storage and wire pure application use cases."""

    settings.ensure_directories()
    preferences = EnginePreferenceStore(settings.data_dir / "engine_preferences.json")
    for key, value in preferences.load().items():
        setattr(settings, key, value)
    legacy_sources = discover_legacy_sources(
        canonical_path=settings.database_path,
        data_directory=settings.data_dir,
        working_directory=(
            None
            if settings.database_path.resolve() == canonical_database_path().resolve()
            else settings.data_dir
        ),
    )
    migration = LegacyDataMigrator(
        settings.database_path,
        backend_database_paths=legacy_sources.backend_databases,
        transcript_directories=legacy_sources.transcript_directories,
    ).run()
    database = SqliteDatabase(settings.database_path)
    meetings = SqliteMeetingStore(database)
    recordings = SqliteRecordingStore(database)
    transcripts = SqliteTranscriptStore(database)
    insights = SqliteInsightStore(database)
    knowledge = SqliteKnowledgeGraphStore(database)
    jobs = SqliteJobStore(database)
    embeddings = SqliteEmbeddingStore(
        database,
        expected_dimension=settings.embedding_dimension,
    )
    result_archive = CanonicalTranscriptionResultArchive(
        meetings,
        recordings,
        transcripts,
        insights,
        knowledge,
    )
    runtime = EngineRuntimeManager(
        settings=settings,
        preferences=preferences,
        archive=result_archive,
        knowledge=knowledge,
        embeddings=embeddings,
        jobs=jobs,
    )
    recording_storage = ManagedRecordingStorage(settings.data_dir / "recordings")
    recording_jobs = RecordingJobCoordinator(
        runtime=runtime,
        jobs=jobs,
        meetings=meetings,
        recordings=recordings,
        storage=recording_storage,
    )
    return EngineContext(
        settings=settings,
        migration=migration,
        database=database,
        data_exchange=SqliteDataExchange(database),
        preferences=preferences,
        meetings=meetings,
        recordings=recordings,
        transcripts=transcripts,
        insights=insights,
        knowledge=knowledge,
        embeddings=embeddings,
        jobs=jobs,
        create_meeting=CreateMeeting(meetings),
        get_meeting=GetMeeting(meetings),
        list_meetings=ListMeetings(meetings),
        rename_meeting=RenameMeeting(meetings),
        archive_meeting=ArchiveMeeting(meetings),
        delete_meeting=DeleteMeeting(meetings),
        dashboard=GetDashboard(meetings, transcripts, insights, knowledge),
        review_insight=ReviewInsight(insights, knowledge),
        update_transcript_segment=UpdateTranscriptSegment(
            transcripts,
            insights,
            knowledge,
        ),
        build_quality_report=BuildTranscriptQualityReport(),
        runtime=runtime,
        recording_storage=recording_storage,
        recording_jobs=recording_jobs,
    )
