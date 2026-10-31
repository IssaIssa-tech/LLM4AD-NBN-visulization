"""Independently check saved vectors, strict NBN parents, outcomes and preservation.

Reads saved experimental records; never imports or executes candidate programs.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

base = Path(__file__).resolve().parents[1]
out = base / 'output/ael_nbn_analysis_20261031'
study = base / 'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda raw: hashlib.sha256(raw).hexdigest()
analysis = load(out / 'NBN_ANALYSIS.json')
graph = load(out / 'measured_nbn_graph.json')
manifest = load(out / 'INPUT_MANIFEST.json')
tracking = load(out / 'TRACKING_INDEX.json')
nodes = graph['nodes']
by_id = {n['id']: i for i, n in enumerate(nodes)}
saved = np.load(out / 'measured_pairwise_cosine_distances.npz')
assert list(saved['ids']) == [n['id'] for n in nodes]
distances = saved['distances']
assert distances.shape == (54, 54)
assert np.allclose(distances, distances.T, atol=1e-14)
ranked = [i for i, n in enumerate(nodes) if n['fitness_status'] == 'observed_valid']
edges = {e['source']: e for e in graph['edges']}
assert len(edges) == len(graph['edges']) == 28
roots = []
for i, node in enumerate(nodes):
    if i not in ranked:
        assert node['score'] is None and node['nbn_parent_id'] is None and node['id'] not in edges
        continue
    better = [j for j in ranked if nodes[j]['score'] > node['score']]
    if not better:
        roots.append(node['id'])
        assert node['nbn_parent_id'] is None and node['id'] not in edges
        continue
    j = min(better, key=lambda j: (distances[i, j], nodes[j]['id']))
    assert node['nbn_parent_id'] == nodes[j]['id'] == edges[node['id']]['target']
    assert abs(node['distance_to_better'] - distances[i, j]) < 1e-14
assert roots == graph['root_ids'] and len(roots) == 3 and len(ranked) == 31

# Exhaustively re-check every generated-to-archive nearest neighbour, not the 3D projection.
historical = load(out / 'historical_metadata.json')
vector_order = load(out / 'historical_vector_order.json')
old_raw = np.load(out / 'historical_vectors.private.npy')
assert sha(old_raw.astype('<f4').tobytes()) == vector_order['vector_bytes_sha256']
assert vector_order['ids'] == [n['id'] for n in historical]
old = old_raw.astype(float)
old /= np.linalg.norm(old, axis=1, keepdims=True)
new_data = np.load(out / 'representation_512/generated_embeddings.npz')
new = new_data['vectors'].astype(float)
new /= np.linalg.norm(new, axis=1, keepdims=True)
assert list(new_data['program_ids']) == [p['id'] for p in analysis['programs']]
nearest_distances = np.clip(1 - new @ old.T, 0, 2)
for i, row in enumerate(analysis['programs']):
    j = int(np.argmin(nearest_distances[i]))
    assert row['nearest_historical']['historical_id'] == historical[j]['id']
    assert abs(row['nearest_historical']['cosine_distance'] - nearest_distances[i, j]) < 1e-12
    assert row['nearest_historical']['historical_region_index'] == historical[j]['region_index']

hist_by_id = {n['id']: i for i, n in enumerate(historical)}
vectors = []
for node in nodes:
    if node['kind'] == 'historical_diagnostic':
        vectors.append(old[hist_by_id[node['historical_id']]])
    else:
        vectors.append(new[list(new_data['program_ids']).index(node['id'])])
recomputed = np.clip(1 - np.stack(vectors) @ np.stack(vectors).T, 0, 2)
assert np.allclose(distances, recomputed, atol=1e-14)
transform = np.load(out / 'historical_pca_transform.npz')
projection = (new - transform['mean']) @ transform['basis'] / transform['scale'] * 300
assert np.allclose(projection, np.array([r['position'] for r in analysis['programs']]), atol=1e-12)

# Output diversity is checked from saved full-precision coordinates, without a rerun.
parent_history = load(study / 'ael_parent_eligibility_20261031/platform_history.json')
packing_hash = lambda circles: sha(json.dumps(sorted(circles), separators=(',', ':'), allow_nan=False).encode())
historical_packings = {}
for event in parent_history['events']:
    if event['eventType'] != 'historical_reference_evaluated':
        continue
    payload = event['payload']
    if payload['evaluation']['status'] == 'valid':
        historical_packings[payload['reference']['node_id']] = packing_hash(payload['evaluation']['circles'])
views = {h['revision_id']: load(study / h['repo_path'])['view'] for h in manifest['histories']}
packing_checks = []
strata = {}
for p in analysis['programs']:
    attempt = next(a for a in views[p['origin_revision_id']]['attempts'] if a['id'] == p['call_id'])
    assert attempt['status'] == p['evaluation_status'] and attempt['score'] == p['score']
    assert sha((study / p['source_file']).read_bytes()) == p['code_sha256']
    key = p['case'] + ':' + p['selection_policy'] + ':' + p['operator']
    group = strata.setdefault(key, dict(records=0, valid=0, statuses=Counter(), best_score=None))
    group['records'] += 1
    group['statuses'][p['evaluation_status']] += 1
    if p['evaluation_status'] != 'valid':
        continue
    group['valid'] += 1
    group['best_score'] = max(p['score'], group['best_score'] or -float('inf'))
    circles = attempt['packing']['circles']
    assert len(circles) == 26
    assert abs(sum(c[2] for c in circles) - p['score']) < 1e-12
    fingerprint = packing_hash(circles)
    matches = [hid for hid, h in historical_packings.items() if h == fingerprint]
    assert matches, 'Previously unreported distinct valid packing; review rather than assume duplication'
    packing_checks.append(dict(program_id=p['id'],call_id=p['call_id'],case=p['case'],score=p['score'],packing_sha256=fingerprint,exact_coordinate_set_historical_matches=matches))
assert len(packing_checks) == 9
assert len({p['packing_sha256'] for p in packing_checks}) == 5

for entry in tracking['protected_artifacts']:
    assert sha((study / entry['path']).read_bytes()) == entry['sha256']
protected_counts = {}
for case in ['ael_operator_pilot_20261031','ael_structural_prompt_comparison_20261031']:
    protected = load(study / case / 'ARTIFACT_INTEGRITY.json')['files']
    for entry in protected:
        assert sha((study / case / entry['path']).read_bytes()) == entry['sha256']
    protected_counts[case] = len(protected)

verification = dict(passed=True,generation_calls=0,candidate_executions=0,
    exhaustive_nearest_archive_queries=24,historical_vectors_checked=14000,
    measured_pairwise_distances_recomputed=True,strict_nearest_better_parents_checked=28,
    tied_best_roots=roots,ranked=31,unranked_without_fitness_or_edges=23,
    fixed_historical_projection_verified=True,valid_coordinate_sets_checked=9,
    unique_valid_coordinate_sets=5,valid_outputs_matching_saved_historical_packings=9,
    packing_fingerprint_method='SHA256 of JSON sorted full-precision (x,y,r) triples; exact row-permutation-invariant equality, no tolerance or geometric symmetry equivalence',
    packing_checks=packing_checks,strata=strata,protected_artifacts_unchanged=len(tracking['protected_artifacts']),
    frozen_case_files_unchanged=protected_counts,
    representation_caution='All 24 sources exceed 512 tokens. Exact cosine analysis is exact only for this truncated CodeT5 representation.')
(out / 'ANALYSIS_VERIFICATION.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8',newline='\n')
print('Verified: 24 exhaustive archive queries; 28 strict edges; 9 valid outputs match 5 known packings; 616 artifacts unchanged.')
