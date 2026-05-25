"""Boundary manifest for the Productivity Tool spreadsheet section."""

from collective_mindgraph.architecture.contracts import DomainContract, SubmoduleContract

MANIFEST = DomainContract(
    spreadsheet_name="Productivity Tool",
    package="collective_mindgraph.productivity_tool",
    responsibility="Tracks decisions, tasks, and summaries automatically.",
    public_interfaces=("ProductivityService", "AccessPolicy", "DataFilter"),
    allowed_dependencies=(
        "collective_mindgraph.shared",
        "collective_mindgraph.knowledge_management_tool",
    ),
    forbidden_dependencies=(
        "collective_mindgraph.enterprise_software",
        "collective_mindgraph.smart_assistant",
        "ui",
    ),
    submodules=(
        SubmoduleContract("On-Prem Inference", "collective_mindgraph.productivity_tool.on_prem_inference", "Runs AI inside company network.", "provider", ("InferenceProvider",)),
        SubmoduleContract("Access Control", "collective_mindgraph.productivity_tool.access_control", "Restricts data access.", "policy", ("AccessPolicy",)),
        SubmoduleContract("Data Filtering", "collective_mindgraph.productivity_tool.data_filtering", "Removes or redacts sensitive information.", "service", ("DataFilter",)),
    ),
)
