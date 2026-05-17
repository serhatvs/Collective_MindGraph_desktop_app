"""Boundary manifest for the AI Meeting Assistant spreadsheet section."""

from collective_mindgraph.architecture.contracts import DomainContract, SubmoduleContract

MANIFEST = DomainContract(
    spreadsheet_name="AI Meeting Assistant",
    package="collective_mindgraph.meeting_assistant",
    responsibility="Understands and processes conversations in real time.",
    public_interfaces=("MeetingAssistantService",),
    allowed_dependencies=(
        "collective_mindgraph.shared",
        "collective_mindgraph.knowledge_management_tool",
        "collective_mindgraph.smart_assistant",
    ),
    forbidden_dependencies=(
        "collective_mindgraph.enterprise_software",
        "collective_mindgraph.collaboration_tool",
        "ui",
    ),
    submodules=(
        SubmoduleContract("Speech-to-Text Engine", "collective_mindgraph.meeting_assistant.speech_to_text", "Converts speech into transcript.", "provider", ("SpeechToTextProvider",)),
        SubmoduleContract("Speaker Diarization", "collective_mindgraph.meeting_assistant.speaker_diarization", "Identifies who is speaking.", "provider", ("SpeakerDiarizationProvider",)),
        SubmoduleContract("Live Summarization", "collective_mindgraph.meeting_assistant.live_summarization", "Generates meeting summaries.", "service", ("LiveSummarizer",)),
        SubmoduleContract("Action Item Extraction", "collective_mindgraph.meeting_assistant.action_item_extraction", "Detects tasks and assignments.", "service", ("ActionItemExtractor",)),
        SubmoduleContract("Decision Detection", "collective_mindgraph.meeting_assistant.decision_detection", "Identifies decisions made.", "service", ("DecisionDetector",)),
        SubmoduleContract("Query Assistant", "collective_mindgraph.meeting_assistant.query_assistant", "Answers questions during or after meetings.", "service", ("MeetingQueryAssistant",)),
    ),
)
