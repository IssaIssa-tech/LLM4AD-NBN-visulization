# Source inspection after the fixed AEL pilot

This is analysis of saved programs and one-time evaluations, not an extra experiment or a manual repair. Every generated program and error remains unchanged.

The strongest finding is copying rather than successful recombination: all six crossover function ASTs match one of their selected historical parents when import and docstring nodes are omitted. Source hashes differ because imports, formatting and descriptions differ. A docstring claiming a hybrid is not evidence that the implementation combines parent mechanisms.

| Chain | Inspected crossover implementation | Mutation behavior | Observed outcome |
|---|---|---|---|
| uniform-1 | Historical sample 7510 body: seeded initialization, L-BFGS-B center optimization, final radius adjustment | Byte-identical extracted source to crossover | Both valid, identical saved coordinate set, 1.9721451517211663 |
| uniform-2 | Historical sample 9180 body: random initialization and joint SLSQP constraints; descriptive hybrid text adds no computational change | Byte-identical extracted source to crossover | Both valid, identical coordinate set, 2.5338065697852596 |
| uniform-3 | Historical sample 12849 body: Halton initialization, Voronoi relaxation, Nelder-Mead refinement; missing `qmc` import | Model adds `from scipy.stats import qmc`, preserving computational body | Crossover NameError; mutation valid at 2.1392974801674187 |
| nbn_stratified-1 | Historical sample 3445 body: mirrored Voronoi centroids and nearest-neighbor radius limits | Byte-identical extracted source to crossover | Both valid, identical coordinate set, 1.8604153645199213 |
| nbn_stratified-2 | Historical sample 12852 body: Latin-hypercube initialization and SLSQP; missing `qmc` import | Model adds `from scipy.stats import qmc`, preserving computational body | Crossover NameError; mutation valid at 2.109107549240501 |
| nbn_stratified-3 | Historical sample 7918 body: Latin-hypercube initialization, per-circle Nelder-Mead and worst-circle resampling; missing `qmc` import | Adds a distance-based overlap adjustment but still omits `qmc` import | Both fail before optimization with NameError; new adjustment is not runtime-validated |

The import additions above were produced by the registered mutation requests, which received crossover source and docstring only. They were not researcher edits or evaluation-feedback repair calls. The protocol required mutation of static-eligible crossover outputs even after evaluation exceptions.

Eleven of twelve outputs match an eligible historical function body under the stated normalization; the remaining changed body fails at initialization. There are nine stripped-source fingerprints, nine full AST fingerprints, seven normalized function-body fingerprints and five exact valid coordinate-set fingerprints. None of the eight valid outputs exceeds the better observed parent in its chain. All valid outputs match one historical computational body under this diagnostic.

All twelve responses ended with `finish_reason=stop`; none hit the 1,800-token output cap. Thus these four observed exceptions are missing-import failures in complete returned code, not evidence of truncation. This does not exclude other latent defects in failed programs, which were not patched or executed again.

Uniform selection happened to draw both parents from branch 13793 in all three fixed seeds; stratification forces one parent from each of branches 11414 and 13793. Those policies therefore also change parent quality and mechanisms. The small observed validity difference is not evidence that one selection policy is generally superior or that NBN guidance is ineffective.

The next supported research question is whether an explicitly specified structural-combination prompt reduces parent-body copying while preserving complete imports and feasibility. That would require a separately registered matched prompt comparison using these frozen parent pairs, model and evaluator. It has not been run. This completed pilot should not be extended silently, and missing imports in its outputs must not be repaired retrospectively.
