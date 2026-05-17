# Collective MindGraph V2 Architecture

This design is derived from `/home/serxc/Downloads/Book.xlsx`. The workbook is
treated as the product/module source of truth for the V2 scaffold.

## 1. Spreadsheet Interpretation

The spreadsheet is a six-column product architecture matrix. Each column is a
top-level product section and each later heading/description pair is a
subsection under that section.

| Spreadsheet section | Responsibility | Subsections |
| --- | --- | --- |
| AI Meeting Assistant | Understands and processes conversations in real time | Speech-to-Text Engine, Speaker Diarization, Live Summarization, Action Item Extraction, Decision Detection, Query Assistant |
| Knowledge Management Tool | Stores and organizes important company information | Knowledge Database, Metadata Tagging, Search Engine, Context Linking |
| Productivity Tool | Tracks decisions, tasks, and summaries automatically | On-Prem Inference, Access Control, Data Filtering |
| Enterprise Software | Helps teams manage internal knowledge efficiently | Microphone Array, Embedded Controller, Status Display, Connectivity Module |
| Collaboration Tool | Supports communication and information sharing | Shared Knowledge Access, Cross-Meeting Linking, Team Memory Sync, Multi-User Workspace, Discussion Context Sharing |
| Smart Assistant | Answers questions based on past conversations | Natural Language Query Engine, Retrieval System, Context Builder, Response Generator, Source Attribution, Follow-Up Handling, Self-Improvement Loop, Adaptive Response Tuning, Contextual Personalization, Knowledge Refinement, Confidence Scoring, Ambiguity Detection |

## 2. Proposed Module Mapping

| Spreadsheet section | V2 domain package | Notes |
| --- | --- | --- |
| AI Meeting Assistant | `collective_mindgraph.meeting_assistant` | Conversation ingestion and meeting intelligence. |
| Knowledge Management Tool | `collective_mindgraph.knowledge_management_tool` | Durable memory records, metadata, search, and links. |
| Productivity Tool | `collective_mindgraph.productivity_tool` | Governance, safe automation, access control, filtering, and on-prem inference boundary. |
| Enterprise Software | `collective_mindgraph.enterprise_software` | Hardware/device runtime, embedded controller, status display, connectivity. |
| Collaboration Tool | `collective_mindgraph.collaboration_tool` | Workspaces, team memory visibility, sync, and shared context. |
| Smart Assistant | `collective_mindgraph.smart_assistant` | Grounded Q&A, retrieval, answer generation, reliability, and learning loop. |

## 3. Folder Tree

```text
src/collective_mindgraph/
  architecture/
    contracts.py
    registry.py
  shared/
    events.py
    ids.py
  meeting_assistant/
    manifest.py
    models.py
    services.py
    speech_to_text/
      providers/
    speaker_diarization/
      providers/
    live_summarization/
    action_item_extraction/
    decision_detection/
    query_assistant/
  knowledge_management_tool/
    manifest.py
    models.py
    services.py
    knowledge_database/
    metadata_tagging/
    search_engine/
    context_linking/
  productivity_tool/
    manifest.py
    models.py
    services.py
    on_prem_inference/
      providers/
    access_control/
    data_filtering/
  enterprise_software/
    manifest.py
    models.py
    services.py
    microphone_array/
      providers/
    embedded_controller/
    status_display/
    connectivity_module/
  collaboration_tool/
    manifest.py
    models.py
    services.py
    shared_knowledge_access/
    cross_meeting_linking/
    team_memory_sync/
    multi_user_workspace/
    discussion_context_sharing/
  smart_assistant/
    manifest.py
    models.py
    services.py
    natural_language_query_engine/
    retrieval_system/
      providers/
    context_builder/
    response_generator/
      providers/
    source_attribution/
    follow_up_handling/
    self_improvement_loop/
    adaptive_response_tuning/
    contextual_personalization/
    knowledge_refinement/
    confidence_scoring/
    ambiguity_detection/
```

## 4. Dependency Rules

- UI and clients may call public domain services.
- Domain services may call repositories, providers, policies, and other domain
  services only through public interfaces.
- Providers may call external systems, hardware, model runtimes, and APIs, but
  providers may not call UI code.
- Repositories own persistence and may not call AI providers, UI code, hardware
  adapters, or response generators.
- `shared` may not import any domain package.
- `enterprise_software` captures audio and transports payloads, but it must not
  import meeting, memory, or assistant internals.
- `meeting_assistant` may produce transcript and insight artifacts, but durable
  organization memory belongs to `knowledge_management_tool`.
- `knowledge_management_tool` owns storage/search/linking primitives and should
  not import assistant generation, meeting ingestion, hardware, or UI.
- `productivity_tool` provides governance services such as access control,
  filtering, and on-prem inference boundaries.
- `collaboration_tool` depends on memory and governance abstractions for
  workspaces, not on hardware or meeting internals.
- `smart_assistant` depends on memory retrieval and governance abstractions; it
  must not import device runtime or raw meeting pipeline internals.

Recommended flow:

```text
clients/UI/device
  -> public domain services
    -> domain services
      -> providers / repositories / policies
        -> external APIs, local models, databases, hardware

domain events
  -> cross-domain async integration later
```

## 5. Merge, Split, Rename, Defer

- Keep all six spreadsheet sections as major modules. This preserves the workbook
  hierarchy exactly.
- Rename in code only enough to make package names Pythonic:
  `AI Meeting Assistant` becomes `meeting_assistant`,
  `Knowledge Management Tool` becomes `knowledge_management_tool`,
  `Productivity Tool` becomes `productivity_tool`,
  `Enterprise Software` becomes `enterprise_software`,
  `Collaboration Tool` becomes `collaboration_tool`,
  and `Smart Assistant` becomes `smart_assistant`.
- Treat `Enterprise Software` as the device/runtime domain. Its spreadsheet
  subsections are hardware and embedded concerns, so that module should stay
  separate from AI processing.
- Do not merge `Query Assistant` and `Smart Assistant` yet. `Query Assistant` is
  meeting-scoped, while `Smart Assistant` is organization-memory scoped.
- Split future concrete implementations under `providers/`, `repositories/`, or
  `policies/` as they become real. The starter scaffold intentionally defines
  protocols first.
- Defer concrete vector database, knowledge graph, auth provider, mobile client,
  embedded firmware, and cloud/on-prem inference implementations. Their extension
  points exist, but implementation should follow product priority.

## 6. Starter Scaffold

The scaffold currently provides:

- `architecture.contracts`: dataclasses for domain and submodule manifests.
- `architecture.registry`: canonical domain list matching the workbook order.
- `shared`: typed IDs, source references, and domain events.
- One package per spreadsheet section, each with `manifest.py`, `models.py`, and
  `services.py`.
- One package per spreadsheet subsection, each exposing a public protocol or
  implementation slot.
- Explicit `providers/` folders where local/cloud/hardware/model adapters should
  live.

Concrete implementation should start by wiring one vertical slice, for example:

```text
enterprise_software.microphone_array.providers.qt
  -> meeting_assistant.speech_to_text.providers.realtime_backend
  -> meeting_assistant.live_summarization
  -> knowledge_management_tool.knowledge_database.sqlite
  -> smart_assistant.retrieval_system.providers.sqlite_vector
```

Keep each slice behind the protocol that already exists in the matching
submodule so later local/cloud replacements do not require UI or domain rewrites.
