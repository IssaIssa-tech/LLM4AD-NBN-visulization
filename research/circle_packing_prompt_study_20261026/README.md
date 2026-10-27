# Circle Packing prompt-effects study (2026-10-26)

This bundle preserves the reproducibility-critical artefacts for the Circle
Packing prompt-effects study: frozen prompts, candidate code and model
responses, pre-registration manifests, evaluator and reporting scripts,
compact result tables, analysis reports, and a portable interactive 3D NBN
viewer.

## What is included

- `prompt_effects/`: controlled prompt-effect results, including the M2-R and
  M2-I negative-result records and the frozen code-checked-M2 protocol.
- `analysis_scripts/`: evaluator, precheck, reporting, and remote-run scripts
  used for this study.
- `combined_nbn_viewer/`: the standalone HTML viewer, its compact 3D data,
  preview, provenance, and region-selection report for the combined 14,030
  node NBN.
- `historical_data/`: the exact 14,000-node historical NBN source graph used
  to construct the combined visualization, plus the original EoH sample
  history archive used by the descriptive historical analysis.
- `paper_studies/`: EoH closure and AEL/Circle-Packing study records used to
  motivate the current experiment.

## Deliberately excluded

The 99 MB derived combined-graph JSON and the 59 MB CodeT5 embedding cache
are not copied here: the historical source graph and compact viewer data are
sufficient to reproduce and inspect the visualization without duplicating
derived caches. The currently running code-checked-M2 server trial is also not
represented as a result until it completes.

Git stores identical file content once, so repeated frozen prompts retained in
the raw execution folders do not add duplicate Git object content.
