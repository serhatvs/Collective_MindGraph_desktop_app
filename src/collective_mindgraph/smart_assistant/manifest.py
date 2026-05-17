"""Boundary manifest for the Smart Assistant spreadsheet section."""

from collective_mindgraph.architecture.contracts import DomainContract, SubmoduleContract

MANIFEST = DomainContract(
    spreadsheet_name="Smart Assistant",
    package="collective_mindgraph.smart_assistant",
    responsibility="Answers questions based on past conversations.",
    public_interfaces=("SmartAssistantService",),
    allowed_dependencies=(
        "collective_mindgraph.shared",
        "collective_mindgraph.knowledge_management_tool",
        "collective_mindgraph.productivity_tool",
    ),
    forbidden_dependencies=(
        "collective_mindgraph.enterprise_software",
        "collective_mindgraph.meeting_assistant",
        "ui",
    ),
    submodules=(
        SubmoduleContract("Natural Language Query Engine", "collective_mindgraph.smart_assistant.natural_language_query_engine", "Understands user questions.", "service", ("QueryInterpreter",)),
        SubmoduleContract("Retrieval System", "collective_mindgraph.smart_assistant.retrieval_system", "Finds relevant past conversation data.", "provider", ("RetrievalProvider",)),
        SubmoduleContract("Context Builder", "collective_mindgraph.smart_assistant.context_builder", "Combines relevant memory and context.", "service", ("AssistantContextBuilder",)),
        SubmoduleContract("Response Generator", "collective_mindgraph.smart_assistant.response_generator", "Produces grounded AI answers.", "provider", ("ResponseGenerator",)),
        SubmoduleContract("Source Attribution", "collective_mindgraph.smart_assistant.source_attribution", "Shows where answer came from.", "service", ("SourceAttributor",)),
        SubmoduleContract("Follow-Up Handling", "collective_mindgraph.smart_assistant.follow_up_handling", "Supports multi-turn questioning.", "service", ("FollowUpHandler",)),
        SubmoduleContract("Self-Improvement Loop", "collective_mindgraph.smart_assistant.self_improvement_loop", "Learns from feedback and corrections over time.", "service", ("FeedbackLearner",)),
        SubmoduleContract("Adaptive Response Tuning", "collective_mindgraph.smart_assistant.adaptive_response_tuning", "Adjusts answer style and format to preferences.", "service", ("ResponseTuner",)),
        SubmoduleContract("Contextual Personalization", "collective_mindgraph.smart_assistant.contextual_personalization", "Adapts outputs based on organizational context.", "service", ("PersonalizationService",)),
        SubmoduleContract("Knowledge Refinement", "collective_mindgraph.smart_assistant.knowledge_refinement", "Improves stored memory structure over time.", "service", ("KnowledgeRefiner",)),
        SubmoduleContract("Confidence Scoring", "collective_mindgraph.smart_assistant.confidence_scoring", "Estimates reliability of generated answers.", "service", ("ConfidenceScorer",)),
        SubmoduleContract("Ambiguity Detection", "collective_mindgraph.smart_assistant.ambiguity_detection", "Flags uncertain or conflicting information.", "service", ("AmbiguityDetector",)),
    ),
)
