"""Boundary manifest for the Collaboration Tool spreadsheet section."""

from collective_mindgraph.architecture.contracts import DomainContract, SubmoduleContract

MANIFEST = DomainContract(
    spreadsheet_name="Collaboration Tool",
    package="collective_mindgraph.collaboration_tool",
    responsibility="Supports communication and information sharing.",
    public_interfaces=("CollaborationService", "WorkspaceRepository"),
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
        SubmoduleContract("Shared Knowledge Access", "collective_mindgraph.collaboration_tool.shared_knowledge_access", "Allows team-wide visibility of extracted information.", "service", ("SharedKnowledgeAccess",)),
        SubmoduleContract("Cross-Meeting Linking", "collective_mindgraph.collaboration_tool.cross_meeting_linking", "Connects related discussions across sessions.", "service", ("CrossMeetingLinker",)),
        SubmoduleContract("Team Memory Sync", "collective_mindgraph.collaboration_tool.team_memory_sync", "Keeps shared organizational knowledge updated.", "service", ("TeamMemorySync",)),
        SubmoduleContract("Multi-User Workspace", "collective_mindgraph.collaboration_tool.multi_user_workspace", "Enables multiple users and teams to interact with memory.", "repository", ("WorkspaceRepository",)),
        SubmoduleContract("Discussion Context Sharing", "collective_mindgraph.collaboration_tool.discussion_context_sharing", "Preserves context behind decisions for all members.", "service", ("DiscussionContextSharing",)),
    ),
)
