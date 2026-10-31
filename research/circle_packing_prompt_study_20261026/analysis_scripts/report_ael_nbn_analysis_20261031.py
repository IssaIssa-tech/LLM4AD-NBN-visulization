"""Write a bounded research interpretation from saved, independently checked outputs."""
import json
import shutil
from collections import Counter
from pathlib import Path

base = Path(__file__).resolve().parents[1]
out = base / 'output/ael_nbn_analysis_20261031'
load = lambda name: json.loads((out / name).read_text(encoding='utf-8'))
a = load('NBN_ANALYSIS.json')
v = load('ANALYSIS_VERIFICATION.json')
assert v['passed'] and load('BROWSER_VERIFICATION.json')['passed']
g = load('measured_nbn_graph.json')
nodes = {n['id']:n for n in g['nodes']}
write = lambda name,text: (out / name).write_text(text,encoding='utf-8',newline='\n')
shutil.copyfile(base / 'output/ael_tracking_restore_check_20261031/RESTORE_VERIFICATION.json',out / 'RESTORE_CHECK.json')

text = '''# AEL generated-program NBN analysis — 2026-10-31

## Result and scope

The NBN analysis and tracking preservation are complete for **24 saved generated
programs**: the 12-call original AEL operator pilot and its 12-call revised-prompt
comparison. The 30 existing historical-parent diagnostics are reused. This
analysis makes **zero generation calls and zero candidate executions**. It does
not include older EoH/M2 studies or the separate 14-call GPU prompt pilot.

All 24 generated programs have their nearest historical code association in the
same two large archived branches represented in the eligible AEL parent pool.
All nine valid generated outputs exactly reproduce five saved historical
packing coordinate sets. The best comparable observed score is
**2.5338065697852596**, below **2.6360**; there are **zero target hits**. These
bounded cases do not demonstrate a new valid packing or expansion into another
archive branch. They do not establish that NBN guidance or AEL generally fails.

## Prompt and selection comparison

| Measure | Original AEL pair | Revised structural/import pair |
|---|---:|---:|
| Saved generated records | 12 | 12 |
| Valid / exception / invalid geometry | 8 / 4 / 0 | 1 / 9 / 2 |
| Best observed valid score | 2.5338065697852596 | 2.109107549240501 |
| Valid uniform-selected outputs | 5 / 6 | 0 / 6 |
| Valid NBN-stratified outputs | 3 / 6 | 1 / 6 |
| Distinct complete-source hashes | 9 | 12 |
| Distinct normalized function-body AST hashes | 7 | 9 |
| Selected-parent body matches, all outputs (prior source review) | 11 / 12 | 3 / 12 |
| Valid outputs matching a measured historical body | 8 / 8 | 1 / 1 |
| Nearest archive branch 13793 / 11414 | 8 / 4 | 10 / 2 |
| Nearest-archive cosine distance: min / median / max | 0.042687 / 0.065439 / 0.101891 | 0.050843 / 0.075276 / 0.111405 |
| Generated records exceeding the 512-token representation | 12 / 12 | 12 / 12 |

Selection rows are descriptive six-record groups, including three crossovers
and their three dependent mutations. These are not six independent evolutionary
runs. Revised prompts changed structural requirements and import instructions
together. Greater source/body differences and cosine distances did not produce
demonstrated valid functional novelty here. These small, dependent batches do
not support a general causal ranking of prompt or parent-selection strategies.
The original prompt pair remains a provisional delivery baseline for these
conditions; it is not a validated optimal search policy.

## Two different graph meanings

**Frozen historical context:** the existing 14,000-node graph retains its HNSW
nearest-better edges and archived fitness provenance. Generated vectors are
projected into the same historical-only PCA fit. The archive view uses three
code projection components; its vertical coordinate is **not fitness**. A
selected dashed generated-to-archive link is the exact nearest **code** match
under the saved embedding representation, not a newly established NBN edge.
The 14,000 historical source programs are referenced from their existing
repository dataset, not uploaded as another duplicate dataset.

**Measured NBN:** 22 valid historical diagnostics and nine valid generated
records form the ranked 31-record cohort. They share the saved 20-second worker
budget, one numerical thread and recorded evaluator/environment hashes. All
54 records remain in the data; eight historical timeouts and 15 generated
failures have no usable fitness and receive **no fitness-based edge**. The
interactive view shows these 23 records in a labelled status tray.

For every ranked record x, exhaustively choose the cosine-nearest record y
with strictly larger saved score, f(y) > f(x). The result is **28 edges and three
tied-best roots**, not a forced single tree. The roots are historical sample
9180 and original calls `uniform-2-cross` and `uniform-2-mut`. They reproduce the
same known packing and score; they are not three discovered basins. Equal scores
are not connected merely to produce N−1 edges. Candidate distance ties use a
stable lexical ID rule. Each of the 28 parents was independently rechecked from
the saved full pairwise distances, not inferred from the projection.

The strict-better rule follows Eq.(1), PDF page 3 / printed page 1197, in the
user-supplied *Nearest-Better Network for Visualizing and Analyzing Combinatorial
Optimization Problems: A Potential Unified Tool*. PDF identity is frozen in
[PAPER_SOURCE.json](PAPER_SOURCE.json). CodeT5 cosine over program text is this
research adaptation, not a distance asserted by that paper. Archived HNSW
construction conventions are preserved separately. No full exact 14,024-node
mixed-fitness NBN is claimed, and the old archive best 2.6359372088053568 is not
used as a comparable new-budget incumbent.

## Archive association and region limits

The frozen archive has seven root-descendant branches plus the singleton global
root. Branch 13793 contains 11,147 records and branch 11414 contains 2,726;
together they cover 13,873 / 14,000 (99.09%) archive records. The other descendant
branch sizes are 11, 57, 41, 2 and 15; the global-root singleton is index 12737.
These are graph branches, not demonstrated physical attraction basins. All 24
nearest associations fall in the two dominant branches (18 and six), so there
is no observed association outside them. Their dominant archive sizes and the
restricted eligible-parent pool make this a weak coverage test, not proof that
other regions are unreachable. The old four-region shortlist was a subset,
not a statement that the complete archive has exactly four branches.

## Representation compatibility and limitations

The historical CodeT5+ cache is read-only and its hash remains unchanged.
The initially configured 1024-token setting failed to reproduce seven long
historical anchor vectors. That technical probe and the compatibility tests are
preserved; no generated-source vector was accepted from the failed setting.
A 512-token setting reproduced **62 / 62** anchors (all 30 diagnostic parents
plus evenly spaced archive samples), maximum component error
**8.940696716308594e-08**. See [REPRESENTATION_DIAGNOSTIC.json](REPRESENTATION_DIAGNOSTIC.json)
and [the successful anchor checks](representation_512/ANCHOR_CHECKS.json).

The reconciled embedding uses `Salesforce/codet5p-110m-embedding`, revision
`d9f3a534af4252f04b10cd9f78e05037542d10f6`, 256 dimensions, 512 tokens,
unit-normalized cosine distance, offline CPU inference. Twenty-one distinct
complete source files supply the 24 generated records. **All 24 exceed 512
tokens** (570–1042 full tokens), so later code changes may be invisible.
No distinct-source prefix collision was found within these 24 records, but
that does not remove the truncation limitation. Imports/docstrings also affect
the vectors: a copied computational body can have nonzero archive distance.
Neither embedding distance nor a 3D location proves behavioral diversity.

## Saved packing equality

The fingerprint sorts the full-precision (x,y,r) triples and hashes their JSON
values; it ignores circle row ordering only. It does not use a tolerance,
rotation/reflection equivalence or rerun any candidate. All nine saved valid
outputs match the following five previously evaluated historical packings.

| Historical sample | Matching generated calls |
|---|---|
| 7510 | Original `uniform-1-cross`, `uniform-1-mut` |
| 9180 | Original `uniform-2-cross`, `uniform-2-mut` |
| 12849 | Original `uniform-3-mut` |
| 3445 | Original `nbn_stratified-1-cross`, `nbn_stratified-1-mut` |
| 12852 | Original `nbn_stratified-2-mut`; revised `structural-nbn_stratified-2-mut` |

## Per-program placement and provenance

Every row below links its existing complete source, original prompt, raw request,
response, score/error, selected-parent identities and NBN nodes through
[TRACKING_INDEX.json](TRACKING_INDEX.json). Full nearest-five records and
distinct-source matches, selected-parent distances, AST identities, token audit
and exact measured parent IDs are in [NBN_ANALYSIS.json](NBN_ANALYSIS.json).
`none: failed` means unranked, not zero fitness.

| Arm / call | Outcome | Score | Nearest archive sample | Branch | Cosine distance | Measured NBN parent |
|---|---|---:|---:|---:|---:|---|
'''

def short_id(node_id):
    if node_id is None:
        return ''
    node = nodes[node_id]
    return 'historical s' + str(node['sample_order']) if node['kind'] == 'historical_diagnostic' else node['call_id']

for p in a['programs']:
    n=nodes[p['id']]
    label=('Original' if 'operator_pilot' in p['case'] else 'Revised')+' / '+p['call_id']
    source='../'+p['source_file']
    nearest=p['nearest_historical']
    parent=short_id(n['nbn_parent_id']) or ('tied-best root' if p['evaluation_status']=='valid' else 'none: failed')
    score=f"{p['score']:.10f}" if p['score'] is not None else 'unavailable'
    text+=f"| [{label}]({source}) | {p['evaluation_status']} | {score} | {nearest['historical_sample']} | {nearest['historical_region_index']} | {nearest['cosine_distance']:.8f} | {parent} |\n"

text+='''
## Tracking and reproducibility

- Four original histories retain **205 original events**, unchanged IDs,
  timestamps and payloads; a separate derived-analysis revision adds **28**
  events linking all 24 original calls. Total: **233 events in five histories**.
- The restore check reconstructs all 233 event files with their byte hashes,
  verifies 24 program/prompt byte identities, request/response JSON-value
  equality, failed fitness and parent links, and copies 616 protected existing
  artifacts. See [RESTORE_CHECK.json](RESTORE_CHECK.json). JSON-value equality
  does not assert identical request/response serialization ordering.
- Original protected case manifests still verify 214 and 228 files, respectively.
  [ANALYSIS_VERIFICATION.json](ANALYSIS_VERIFICATION.json) also independently
  rechecks all 24 exhaustive nearest-archive queries, all measured pairwise
  distances, all 28 strict parents, the common projection and packing hashes.
- [ael_nbn_3d.html](ael_nbn_3d.html) is a self-contained offline interactive
  viewer. Browser checks cover actual 3D rotation, all 24 program inspectors,
  both graph meanings, failure visibility, labelled PNG export and mobile
  layout, with zero HTTP requests or browser exceptions.
- New derived artifacts have their own integrity manifest. Source programs,
  model weights, the historical cache and old experimental results are not
  modified. Historical vectors and intermediate metadata are retained locally
  and in the researcher-owned server analysis folder, excluded from Git.
  Their hashes and the local backup identity are recorded separately.

## Implication for the supervisor's research question

These cases support using full outcome/lineage tracking and explicit copying
checks before treating generated code differences as discoveries. The stricter
prompt wording increased code differences while validity decreased, and no new
valid packing was observed. They do **not yet establish that NBN-based selection
improves high-quality discovery** or identify a generally superior selection
policy. No further generation, adaptive rule or changed representation is
silently introduced by this analysis. Future changes require a separately
specified comparison that retains the current negative results and addresses
both eligible-region coverage and the representation limit.
'''
write('NBN_RESULTS.md',text)

write('README.md','''# AEL NBN analysis and preserved tracking — 2026-10-31

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
''')
write('.gitattributes','* -text whitespace=cr-at-eol\n')
write('.gitignore','browser_profile_*/\nprivate_hf*/\n__pycache__/\n*.local.zip\n*.private.npy\nhistorical_metadata.json\nhistorical_vector_order.json\n')
print('Wrote findings, 24-row provenance table, README and copied restore verification.')
