"""Boundary manifest for the Knowledge Management Tool spreadsheet section."""

from collective_mindgraph.architecture.contracts import DomainContract, SubmoduleContract

MANIFEST = DomainContract(
    spreadsheet_name="Knowledge Management Tool",
    package="collective_mindgraph.knowledge_management_tool",
    responsibility="Stores and organizes important company information.",
    public_interfaces=("KnowledgeManagementService", "KnowledgeRepository"),
    allowed_dependencies=("collective_mindgraph.shared",),
    forbidden_dependencies=(
        "collective_mindgraph.meeting_assistant",
        "collective_mindgraph.enterprise_software",
        "collective_mindgraph.smart_assistant",
        "ui",
    ),
    submodules=(
        SubmoduleContract("Knowledge Database", "collective_mindgraph.knowledge_management_tool.knowledge_database", "Stores structured information.", "repository", ("KnowledgeRepository",)),
        SubmoduleContract("Metadata Tagging", "collective_mindgraph.knowledge_management_tool.metadata_tagging", "Categorizes stored knowledge.", "service", ("MetadataTagger",)),
        SubmoduleContract("Search Engine", "collective_mindgraph.knowledge_management_tool.search_engine", "Enables retrieval of past information.", "provider", ("KnowledgeSearchProvider",)),
        SubmoduleContract("Context Linking", "collective_mindgraph.knowledge_management_tool.context_linking", "Connects related discussions and topics.", "service", ("ContextLinker",)),
    ),
)
