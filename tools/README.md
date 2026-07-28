# Reusable Development Tools

`tools/` contains maintained, reusable developer-facing applications and libraries that are not part of the production desktop or backend runtime.

`transcript_annotation/` is the authoritative annotation tool. Its dataset schema and persistence live in `dataset.py`, experiment mechanics in `experiments.py`, exports in `exporter.py`, pipeline integration in `pipeline.py`, and UI in `app.py`. Launch it through `scripts/launch/launch_transcript_annotation.py`.

Thin operational entry points stay under `scripts/`; reusable implementations with their own domain model belong here. No current tool is classified as obsolete.
