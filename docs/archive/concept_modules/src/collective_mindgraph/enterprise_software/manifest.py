"""Boundary manifest for the Enterprise Software spreadsheet section."""

from collective_mindgraph.architecture.contracts import DomainContract, SubmoduleContract

MANIFEST = DomainContract(
    spreadsheet_name="Enterprise Software",
    package="collective_mindgraph.enterprise_software",
    responsibility="Helps teams manage internal knowledge efficiently.",
    public_interfaces=("EnterpriseRuntimeService",),
    allowed_dependencies=("collective_mindgraph.shared",),
    forbidden_dependencies=(
        "collective_mindgraph.knowledge_management_tool",
        "collective_mindgraph.smart_assistant",
        "ui",
    ),
    submodules=(
        SubmoduleContract("Microphone Array", "collective_mindgraph.enterprise_software.microphone_array", "Captures room audio.", "provider", ("AudioCaptureDevice",)),
        SubmoduleContract("Embedded Controller", "collective_mindgraph.enterprise_software.embedded_controller", "Manages device operations.", "service", ("EmbeddedController",)),
        SubmoduleContract("Status Display", "collective_mindgraph.enterprise_software.status_display", "Shows AI and device state.", "service", ("StatusDisplay",)),
        SubmoduleContract("Connectivity Module", "collective_mindgraph.enterprise_software.connectivity_module", "Sends data to processing server.", "provider", ("ProcessingTransport",)),
    ),
)
