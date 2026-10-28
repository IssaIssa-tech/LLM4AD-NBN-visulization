# Circle Packing prompt-effects study (2026-10-26)

This bundle preserves the reproducibility-critical artefacts for the Circle
Packing prompt-effects study: frozen prompts, candidate code and model
responses, pre-registration manifests, evaluator and reporting scripts,
compact result tables, analysis reports, and a portable interactive 3D NBN
viewer.

## Current research scope and status

The new 2026-10-28 instruction set and verified platform import are documented
in [historical_import_audit_20261028/HISTORICAL_IMPORT_REPORT.md](historical_import_audit_20261028/HISTORICAL_IMPORT_REPORT.md).
The isolated platform now has 14,000 verified historical program/node mappings.
The source snapshot is HNSW-based; later exact study graphs remain separate.

The supervisor requested analysis of prompt effects to identify useful prompts
and solutions, followed by algorithm design based on that evidence. Beating the
historical champion was not a required completion criterion. See
[`RESEARCH_SCOPE_AND_STATUS.md`](RESEARCH_SCOPE_AND_STATUS.md) for the current
interpretation, evidence boundaries, and remaining design work.

The current workflow specification is
[`prompt_effects/PROMPT_GUIDED_ALGORITHM_DESIGN.md`](prompt_effects/PROMPT_GUIDED_ALGORITHM_DESIGN.md).
Its draft plan is under `prompt_effects/prompt_guided_design_v1/`; it has not
been registered or executed as a new search experiment.

The repository contains prompt-effect experiments and later supporting
researcher-specified packing-code tests. Those tests are preserved research
records; they do not establish a completed prompt/parent selection algorithm.
The exact meaning and scope of that higher-level algorithm must be stated in
the design, rather than attributed to the supervisor's brief message.

## What is included

- `prompt_effects/`: controlled prompt-effect results, including the M2-R and
  M2-I negative-result records and the frozen code-checked-M2 protocol.
- `analysis_scripts/`: evaluator, precheck, reporting, and remote-run scripts
  used for this study.
- `combined_nbn_viewer/`: the standalone HTML viewer, its compact 3D data,
  preview, provenance, and region-selection report for the combined 14,030
  node NBN.
- `combined_nbn_m2ip_20261027/`: the versioned exact NBN and interactive viewer
  after adding the five M2-I-P trials (14,035 nodes total).
- `combined_nbn_m2ipd_20261027/`: 14,040-node comparison including five prepared
  Sobol-seed variants.
- `combined_nbn_feasible_20261027/`: 14,045-node exploratory comparison including
  five prepared feasible-initialization variants. It excludes the later twenty
  held-out validation records and other follow-up failures retained in ledgers.
- `historical_data/`: the exact 14,000-node historical NBN source graph used
  to construct the combined visualization, plus the original EoH sample
  history archive used by the descriptive historical analysis.
- `paper_studies/`: EoH closure and AEL/Circle-Packing study records used to
  motivate the current experiment.

## Storage and viewing requirements

Versioned derived graph JSON files are included in the graph folders. The
private CodeT5 embedding cache and model weights are not included in this study
bundle. Exact rebuilding requires the model, dependencies, backend configuration
and original code inputs; a compact viewer export alone cannot rebuild embeddings
or certify nearest-better edges. The code-checked-M2 run has completed and its
negative result is preserved in `prompt_effects/`.

The newer viewers fetch their adjacent data JSON and reference the existing
Three.js installation under `llm4ad_from_server/visual_platform/static/vendor/`.
Use a local HTTP server from the project root with those dependencies available.
Opening an HTML file alone or viewing its source on GitHub does not guarantee
an operational standalone visualization.

Git stores identical file content once, so repeated frozen prompts retained in
the raw execution folders do not add duplicate Git object content.
