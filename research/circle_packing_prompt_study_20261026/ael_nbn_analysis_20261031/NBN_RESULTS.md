# AEL generated-program NBN analysis — 2026-10-31

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
| [Original / uniform-1-cross](../ael_operator_pilot_20261031/uniform-1-cross/candidate.py) | valid | 1.9721451517 | 7510 | 13793 | 0.04704565 | historical s3221 |
| [Original / uniform-1-mut](../ael_operator_pilot_20261031/uniform-1-mut/candidate.py) | valid | 1.9721451517 | 7510 | 13793 | 0.04704565 | historical s3221 |
| [Original / uniform-2-cross](../ael_operator_pilot_20261031/uniform-2-cross/candidate.py) | valid | 2.5338065698 | 2372 | 13793 | 0.08792546 | tied-best root |
| [Original / uniform-2-mut](../ael_operator_pilot_20261031/uniform-2-mut/candidate.py) | valid | 2.5338065698 | 2372 | 13793 | 0.08792546 | tied-best root |
| [Original / uniform-3-cross](../ael_operator_pilot_20261031/uniform-3-cross/candidate.py) | exception | unavailable | 9824 | 13793 | 0.04804476 | none: failed |
| [Original / uniform-3-mut](../ael_operator_pilot_20261031/uniform-3-mut/candidate.py) | valid | 2.1392974802 | 9824 | 13793 | 0.05525851 | historical s6613 |
| [Original / nbn_stratified-1-cross](../ael_operator_pilot_20261031/nbn_stratified-1-cross/candidate.py) | valid | 1.8604153645 | 2562 | 11414 | 0.07424613 | uniform-3-mut |
| [Original / nbn_stratified-1-mut](../ael_operator_pilot_20261031/nbn_stratified-1-mut/candidate.py) | valid | 1.8604153645 | 2562 | 11414 | 0.07424613 | uniform-3-mut |
| [Original / nbn_stratified-2-cross](../ael_operator_pilot_20261031/nbn_stratified-2-cross/candidate.py) | exception | unavailable | 9824 | 13793 | 0.10189137 | none: failed |
| [Original / nbn_stratified-2-mut](../ael_operator_pilot_20261031/nbn_stratified-2-mut/candidate.py) | valid | 2.1091075492 | 12852 | 13793 | 0.08101317 | uniform-3-mut |
| [Original / nbn_stratified-3-cross](../ael_operator_pilot_20261031/nbn_stratified-3-cross/candidate.py) | exception | unavailable | 8075 | 11414 | 0.04268661 | none: failed |
| [Original / nbn_stratified-3-mut](../ael_operator_pilot_20261031/nbn_stratified-3-mut/candidate.py) | exception | unavailable | 7918 | 11414 | 0.05663217 | none: failed |
| [Revised / structural-uniform-1-cross](../ael_structural_prompt_comparison_20261031/structural-uniform-1-cross/candidate.py) | exception | unavailable | 4169 | 13793 | 0.07101938 | none: failed |
| [Revised / structural-uniform-1-mut](../ael_structural_prompt_comparison_20261031/structural-uniform-1-mut/candidate.py) | exception | unavailable | 3777 | 13793 | 0.08890946 | none: failed |
| [Revised / structural-uniform-2-cross](../ael_structural_prompt_comparison_20261031/structural-uniform-2-cross/candidate.py) | invalid_geometry | unavailable | 9943 | 13793 | 0.09135735 | none: failed |
| [Revised / structural-uniform-2-mut](../ael_structural_prompt_comparison_20261031/structural-uniform-2-mut/candidate.py) | invalid_geometry | unavailable | 9180 | 13793 | 0.06278708 | none: failed |
| [Revised / structural-uniform-3-cross](../ael_structural_prompt_comparison_20261031/structural-uniform-3-cross/candidate.py) | exception | unavailable | 9824 | 13793 | 0.05084268 | none: failed |
| [Revised / structural-uniform-3-mut](../ael_structural_prompt_comparison_20261031/structural-uniform-3-mut/candidate.py) | exception | unavailable | 10612 | 13793 | 0.07088702 | none: failed |
| [Revised / structural-nbn_stratified-1-cross](../ael_structural_prompt_comparison_20261031/structural-nbn_stratified-1-cross/candidate.py) | exception | unavailable | 9824 | 13793 | 0.10338123 | none: failed |
| [Revised / structural-nbn_stratified-1-mut](../ael_structural_prompt_comparison_20261031/structural-nbn_stratified-1-mut/candidate.py) | exception | unavailable | 9824 | 13793 | 0.11140522 | none: failed |
| [Revised / structural-nbn_stratified-2-cross](../ael_structural_prompt_comparison_20261031/structural-nbn_stratified-2-cross/candidate.py) | exception | unavailable | 12852 | 13793 | 0.07262309 | none: failed |
| [Revised / structural-nbn_stratified-2-mut](../ael_structural_prompt_comparison_20261031/structural-nbn_stratified-2-mut/candidate.py) | valid | 2.1091075492 | 12852 | 13793 | 0.08453135 | uniform-3-mut |
| [Revised / structural-nbn_stratified-3-cross](../ael_structural_prompt_comparison_20261031/structural-nbn_stratified-3-cross/candidate.py) | exception | unavailable | 4836 | 11414 | 0.07792904 | none: failed |
| [Revised / structural-nbn_stratified-3-mut](../ael_structural_prompt_comparison_20261031/structural-nbn_stratified-3-mut/candidate.py) | exception | unavailable | 7918 | 11414 | 0.05425143 | none: failed |

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
