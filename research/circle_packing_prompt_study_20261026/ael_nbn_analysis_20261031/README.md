# AEL NBN analysis and preserved tracking — 2026-10-31

Completed analysis of the **24 saved programs** from the original AEL pilot and
its revised-prompt comparison, reusing 30 recorded historical diagnostics.
No new optimization programs were generated, repaired or executed.

- [Research findings and per-program table](NBN_RESULTS.md)
- [Offline interactive 3D viewer](ael_nbn_3d.html): download/open this HTML;
  embedded code/data need no web server. GitHub's source view does not run it.
- [Archive preview](archive_context_preview.png) and [measured NBN preview](measured_nbn_preview.png)
- [Tracking index](TRACKING_INDEX.json): source histories, prompts, programs,
  scores/errors, parent/NBN identities, modifications and derived links.
- [Verified restore](RESTORE_CHECK.json), [scientific checks](ANALYSIS_VERIFICATION.json),
  [browser checks](BROWSER_VERIFICATION.json), [local backup identity](LOCAL_BACKUP.json).

**Result:** 31 valid measured records, 28 strict nearest-better edges, three
tied-best roots; 23 failed/timed-out records preserved without fitness edges.
All 24 nearest archive associations fall in two dominant existing branches.
The nine valid generated outputs repeat five known historical packings.
Best comparable score 2.5338065697852596; zero scores >=2.6360.

**Representation:** CodeT5+ cosine, 256 dimensions, reconciled 512-token limit,
62/62 historical anchors verified. All 24 generated sources exceed this limit;
code-space distance/projection is not proof of full-program or packing diversity.
The 14k archived HNSW graph and the new exact measured-only NBN have separate
edge/fitness provenance. See [METHOD.md](METHOD.md) and the results report.

## Restore tracking from the existing repository

From a repository checkout, use a new, empty destination:

```powershell
python research/circle_packing_prompt_study_20261026/analysis_scripts/restore_ael_tracking_20261031.py --repo-root . --index research/circle_packing_prompt_study_20261026/ael_nbn_analysis_20261031/TRACKING_INDEX.json --destination C:/path/to/new-restored-history
```

The tool never executes candidate code. It reconstructs exact event files for
205 original +28 analysis events, verifies 24 generated records and restores
616 existing referenced artifacts. Historical programs/graphs already in the
repository are reused, not duplicated into another Git dataset. The local
portable ZIP additionally contains the verified restore and new analysis files;
ZIP/model/cache/private vectors/browser profiles are excluded from Git.

## Reproduce the numerical analysis

Saved measured pairwise distances, new generated vectors and the common PCA
transform are included. Independent verification also needs the read-only
historical vector matrix plus `historical_metadata.json` and
`historical_vector_order.json`; these intermediate files are preserved in the
local ZIP and server analysis directory, with hashes in LOCAL_BACKUP.json.
The original cache/model paths, hashes, evaluator provenance, input identities
and offline model environment are frozen in INPUT_MANIFEST.json, INPUT_AUDIT.json,
MODEL_ASSETS.json and representation_512/EMBEDDING_RESULT.json. Recomputing new
embeddings requires the identified checkpoint/tokenizer and dependencies; no
model weights or private cache are uploaded here.

The initial 1024-token anchor failure and successful 512-token reconciliation
remain separate records. Do not replace old frozen analysis or rerun completed
LLM experiments to reproduce this derived analysis. Scripts and their hashes
are listed in ANALYSIS_SCRIPTS.json and stored in the sibling analysis_scripts
folder. Restore/verification scripts state their local working-directory layout;
remote scripts expect the researcher-owned analysis/deployment paths recorded
in the manifest. They are research records, not a path-independent installer.

Use ARTIFACT_INTEGRITY.json to verify the released files. The original AEL case
folders remain unchanged; this folder is a derived follow-up, not extra trials.
