import * as THREE from "three";
import { TrackballControls } from "https://unpkg.com/three@0.165.0/examples/jsm/controls/TrackballControls.js";

const FAVORITES_STORAGE_KEY = "llm4add.favorite-node-ids.v1";

const state = {
  activeRunId: null,
  activeSaveId: null,
  viewSaveId: null,
  viewRunId: null,
  expandedClusterId: null,
  saves: [],
  fullGraph: { nodes: [], edges: [], truncated: false },
  graph: { nodes: [], edges: [], truncated: false },
  graphSignature: null,
  selectedNodeIds: new Set(),
  favoriteNodeIds: new Set(loadFavoriteIds()),
  candidateNodeIds: new Set(),
  initialPopulationNodeIds: new Set(),
  nodeMeshes: [],
  nodeInstancedMesh: null,
  edgeObjects: [],
  nodeRenderMode: "mesh",
  nodePoints: null,
  selectedEdgeOverlay: null,
  nodeVisualPositions: new Map(),
  nodeIndexById: new Map(),
  nodeMap: new Map(),
  fullNodeMap: new Map(),
  algorithmTranslationCache: new Map(),
  algorithmTranslationPending: new Set(),
  isDraggingSelection: false,
  dragStart: null,
  autoRotate: false,
  showEdges: false,
  edgeVisibilityPinned: false,
  currentGraphKey: null,
  nodeSizeScale: 1,
  nodeOpacityScale: 1,
  edgeOpacityScale: 2.2,
  graphSpreadScale: 1,
  highScorePercent: 100,
  graphAbstractionMode: "full",
  clusterGroupSize: 20,
  openedClientClusterId: null,
  clusterGraphCacheKey: null,
  clusterGraphCache: null,
  backgroundTheme: "light",
  positionCenter: new THREE.Vector3(),
  currentStatus: "idle",
  pendingFocusNodeId: null,
  lastGraphRefreshAt: 0,
  lastGraphSampleCount: 0,
  lastGraphStatus: null,
  lastStatusSampleCount: 0,
  lastSavesRefreshAt: 0,
  lastSavesSignature: null,
  lastStatusPerf: null,
  lastGraphPerf: null,
  lastPerfRolling: null,
  lastRunSnapshot: null,
  nodeDetailCache: new Map(),
  nodeDetailPending: new Set(),
};

const elements = {
  host: document.getElementById("host"),
  key: document.getElementById("key"),
  model: document.getElementById("model"),
  distanceMetric: document.getElementById("distance_metric"),
  directAiPrompt: document.getElementById("directAiPrompt"),
  directAiMaxSampleNums: document.getElementById("directAiMaxSampleNums"),
  directAiPopSize: document.getElementById("directAiPopSize"),
  seededEohPrompt: document.getElementById("seededEohPrompt"),
  seededEohMaxGenerations: document.getElementById("seededEohMaxGenerations"),
  seededEohPopSize: document.getElementById("seededEohPopSize"),
  seededEohNumSamplers: document.getElementById("seededEohNumSamplers"),
  seededEohNumEvaluators: document.getElementById("seededEohNumEvaluators"),
  externalExpertTitle: document.getElementById("externalExpertTitle"),
  externalExpertDescription: document.getElementById("externalExpertDescription"),
  externalExpertFunction: document.getElementById("externalExpertFunction"),
  injectExpertSolutionButton: document.getElementById("injectExpertSolutionButton"),
  importHistoryButton: document.getElementById("importHistoryButton"),
  stopButton: document.getElementById("stopButton"),
  testLlmButton: document.getElementById("testLlmButton"),
  clearSelectionButton: document.getElementById("clearSelectionButton"),
  rotateToggleButton: document.getElementById("rotateToggleButton"),
  boxSelectMode: document.getElementById("boxSelectMode"),
  statusText: document.getElementById("statusText"),
  sampleCount: document.getElementById("sampleCount"),
  bestScore: document.getElementById("bestScore"),
  bestSample: document.getElementById("bestSample"),
  embeddingProgress: document.getElementById("embeddingProgress"),
  currentPhase: document.getElementById("currentPhase"),
  runProgress: document.getElementById("runProgress"),
  runnerTiming: document.getElementById("runnerTiming"),
  currentPrompt: document.getElementById("currentPrompt"),
  currentMode: document.getElementById("currentMode"),
  llmTestResult: document.getElementById("llmTestResult"),
  newSaveButton: document.getElementById("newSaveButton"),
  refreshRunsButton: document.getElementById("refreshRunsButton"),
  runHistoryList: document.getElementById("runHistoryList"),
  selectedNodes: document.getElementById("selectedNodes"),
  favoriteNodes: document.getElementById("favoriteNodes"),
  candidateCount: document.getElementById("candidateCount"),
  candidateNodes: document.getElementById("candidateNodes"),
  runCandidatesButton: document.getElementById("runCandidatesButton"),
  clearCandidatesButton: document.getElementById("clearCandidatesButton"),
  initialPopulationCount: document.getElementById("initialPopulationCount"),
  initialPopulationNodes: document.getElementById("initialPopulationNodes"),
  runInitialPopulationButton: document.getElementById("runInitialPopulationButton"),
  clearInitialPopulationButton: document.getElementById("clearInitialPopulationButton"),
  latestGeneratedCount: document.getElementById("latestGeneratedCount"),
  latestGeneratedBest: document.getElementById("latestGeneratedBest"),
  latestGeneratedCompare: document.getElementById("latestGeneratedCompare"),
  latestGeneratedNodes: document.getElementById("latestGeneratedNodes"),
  graphContainer: document.getElementById("graphContainer"),
  selectionRect: document.getElementById("selectionRect"),
  graphMeta: document.getElementById("graphMeta"),
  edgeToggle: document.getElementById("edgeToggle"),
  nodeSize: document.getElementById("nodeSize"),
  nodeSizeValue: document.getElementById("nodeSizeValue"),
  nodeOpacity: document.getElementById("nodeOpacity"),
  nodeOpacityValue: document.getElementById("nodeOpacityValue"),
  edgeOpacity: document.getElementById("edgeOpacity"),
  edgeOpacityValue: document.getElementById("edgeOpacityValue"),
  graphSpread: document.getElementById("graphSpread"),
  graphSpreadValue: document.getElementById("graphSpreadValue"),
  backgroundTheme: document.getElementById("backgroundTheme"),
  backgroundThemeValue: document.getElementById("backgroundThemeValue"),
  graphAbstractionMode: document.getElementById("graphAbstractionMode"),
  clusterGroupSize: document.getElementById("clusterGroupSize"),
  clusterGroupSizeValue: document.getElementById("clusterGroupSizeValue"),
  highScorePercent: document.getElementById("highScorePercent"),
  highScorePercentValue: document.getElementById("highScorePercentValue"),
  openClusterButton: document.getElementById("openClusterButton"),
  summaryViewButton: document.getElementById("summaryViewButton"),
  resetGraphViewButton: document.getElementById("resetGraphViewButton"),
  selectedCount: document.getElementById("selectedCount"),
  nodeDetails: document.getElementById("nodeDetails"),
};

function normalizePositiveInt(value, fallback, minimum = 1) {
  const numeric = Math.trunc(Number(value));
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.max(minimum, numeric);
}

// 不需要再同步全局参数了，分别在两个模式里配置

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(elements.graphContainer.clientWidth, elements.graphContainer.clientHeight);
elements.graphContainer.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = null;

const camera = new THREE.PerspectiveCamera(
  60,
  elements.graphContainer.clientWidth / elements.graphContainer.clientHeight,
  0.1,
  5000,
);
camera.position.set(0, 0, 360);

const controls = new TrackballControls(camera, renderer.domElement);
controls.rotateSpeed = 4.2;
controls.zoomSpeed = 1.2;
controls.panSpeed = 0.9;
controls.dynamicDampingFactor = 0.12;
controls.noRoll = false;

scene.add(new THREE.AmbientLight(0xffffff, 1.8));
scene.add(new THREE.HemisphereLight(0xdbeafe, 0x1e293b, 1.25));
const pointLight = new THREE.PointLight(0xffffff, 2.2);
pointLight.position.set(140, 180, 220);
scene.add(pointLight);
const fillLight = new THREE.DirectionalLight(0xcfe0ff, 1.1);
fillLight.position.set(-180, 120, 160);
scene.add(fillLight);

const graphGroup = new THREE.Group();
scene.add(graphGroup);

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function applyBackgroundTheme() {
  const isDark = state.backgroundTheme === "dark";
  elements.backgroundThemeValue.textContent = isDark ? "黑夜发光" : "浅色";
  elements.graphContainer.classList.toggle("theme-dark", isDark);
  scene.background = isDark ? new THREE.Color(0x020617) : null;
  pointLight.intensity = isDark ? 2.8 : 2.2;
  fillLight.intensity = isDark ? 1.55 : 1.1;
}

function createRoundPointTexture() {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  const center = size / 2;
  const radius = size * 0.34;
  context.clearRect(0, 0, size, size);
  context.beginPath();
  context.arc(center, center, radius, 0, Math.PI * 2);
  context.closePath();
  context.fillStyle = "rgba(255, 255, 255, 1)";
  context.fill();
  context.lineWidth = size * 0.055;
  context.strokeStyle = "rgba(255, 255, 255, 0.92)";
  context.stroke();
  const highlight = context.createRadialGradient(center - radius * 0.28, center - radius * 0.28, radius * 0.08, center, center, radius * 0.95);
  highlight.addColorStop(0, "rgba(255, 255, 255, 0.95)");
  highlight.addColorStop(0.6, "rgba(255, 255, 255, 0.18)");
  highlight.addColorStop(1, "rgba(255, 255, 255, 0)");
  context.beginPath();
  context.arc(center, center, radius, 0, Math.PI * 2);
  context.closePath();
  context.fillStyle = highlight;
  context.fill();
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

const roundPointTexture = createRoundPointTexture();

function scoreColor(score, maxScore) {
  if (score == null) {
    return new THREE.Color(0xcbd5e1);
  }
  const ratio = maxScore ? Math.max(0, Math.min(1, score / maxScore)) : 0.5;
  return new THREE.Color().setHSL(0.63 - ratio * 0.22, 0.85, 0.58);
}

function loadFavoriteIds() {
  try {
    const payload = JSON.parse(window.localStorage.getItem(FAVORITES_STORAGE_KEY) || "[]");
    if (!Array.isArray(payload)) {
      return [];
    }
    return payload.filter((item) => typeof item === "string" && item);
  } catch (_) {
    return [];
  }
}

function saveFavoriteIds() {
  window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify([...state.favoriteNodeIds]));
}

function clearGraph() {
  while (graphGroup.children.length) {
    const child = graphGroup.children.pop();
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (Array.isArray(child.material)) {
        child.material.forEach((material) => material.dispose());
      } else {
        child.material.dispose();
      }
    }
  }
  if (state.nodeInstancedMesh) {
    if (state.nodeInstancedMesh.geometry) state.nodeInstancedMesh.geometry.dispose();
    if (state.nodeInstancedMesh.material) state.nodeInstancedMesh.material.dispose();
    state.nodeInstancedMesh = null;
  }
  state.nodeMeshes = [];
  state.edgeObjects = [];
  state.nodeRenderMode = "mesh";
  state.nodePoints = null;
  state.selectedEdgeOverlay = null;
  state.nodeVisualPositions = new Map();
  state.nodeIndexById = new Map();
  state.nodeMap.clear();
  state.positionCenter = new THREE.Vector3();
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function adaptiveNodeRadius(nodeCount) {
  if (nodeCount > 5000) return 1.1;
  if (nodeCount > 2000) return 1.4;
  if (nodeCount > 800) return 1.8;
  if (nodeCount > 300) return 2.5;
  if (nodeCount > 120) return 3.2;
  return 4.5;
}

function adaptiveSegments(nodeCount) {
  if (nodeCount > 1500) return 8;
  if (nodeCount > 500) return 10;
  if (nodeCount > 200) return 12;
  return 18;
}

function adaptiveNodeOpacity(nodeCount) {
  if (nodeCount > 1500) return 0.52;
  if (nodeCount > 500) return 0.62;
  if (nodeCount > 200) return 0.72;
  return 0.84;
}

function adaptiveEdgeOpacity(nodeCount) {
  if (nodeCount > 1500) return 0.04;
  if (nodeCount > 500) return 0.06;
  if (nodeCount > 200) return 0.08;
  return 0.14;
}

function adaptivePointSize(nodeCount) {
  if (nodeCount > 10000) return 8.8;
  if (nodeCount > 5000) return 8.2;
  if (nodeCount > 2500) return 7.4;
  return Math.max(4.4, adaptiveNodeRadius(nodeCount) * 3.1);
}

function adaptivePointOpacity(nodeCount) {
  if (nodeCount > 10000) return 0.82;
  if (nodeCount > 5000) return 0.8;
  if (nodeCount > 2500) return 0.76;
  return adaptiveNodeOpacity(nodeCount);
}

function adaptivePointBackgroundEdgeOpacity(nodeCount) {
  if (nodeCount > 10000) return 0.08;
  if (nodeCount > 5000) return 0.072;
  if (nodeCount > 2500) return 0.06;
  return adaptiveEdgeOpacity(nodeCount);
}

function buildVisualPositions(nodes) {
  const positions = new Map();
  nodes.forEach((node) => {
    positions.set(
      node.id,
      new THREE.Vector3(Number(node.x) || 0, Number(node.y) || 0, Number(node.z) || 0),
    );
  });
  return positions;
}

function syncNodeSizeLabel() {
  elements.nodeSizeValue.textContent = `${state.nodeSizeScale.toFixed(1)}x`;
}

function syncNodeOpacityLabel() {
  elements.nodeOpacityValue.textContent = `${state.nodeOpacityScale.toFixed(1)}x`;
}

function syncEdgeOpacityLabel() {
  elements.edgeOpacityValue.textContent = `${state.edgeOpacityScale.toFixed(1)}x`;
}

function syncGraphSpreadLabel() {
  elements.graphSpreadValue.textContent = `${state.graphSpreadScale.toFixed(1)}x`;
}

function syncBackgroundThemeLabel() {
  elements.backgroundThemeValue.textContent = state.backgroundTheme === "dark" ? "黑夜发光" : "浅色";
}

function syncHighScoreLabel() {
  elements.highScorePercentValue.textContent = `${Math.round(state.highScorePercent)}%`;
}

function syncClusterGroupLabel() {
  elements.clusterGroupSizeValue.textContent = String(Math.round(state.clusterGroupSize));
  elements.clusterGroupSize.disabled = state.graphAbstractionMode !== "cluster";
}

function openedClientClusterSubgraph(graph, clusterId) {
  if (!clusterId) {
    return graph;
  }
  const clusteredGraph = spatialClusterGraph(graph, state.clusterGroupSize);
  const clusterNode = clusteredGraph.nodes.find((node) => node.id === clusterId && node.isClientCluster);
  if (!clusterNode?.memberNodeIds?.length) {
    return clusteredGraph;
  }
  const memberIds = new Set(clusterNode.memberNodeIds);
  const nodes = graph.nodes.filter((node) => memberIds.has(node.id));
  const validIds = new Set(nodes.map((node) => node.id));
  const edges = graph.edges.filter((edge) => validIds.has(edge.source) && validIds.has(edge.target));
  return {
    ...graph,
    nodes,
    edges,
    graphView: "opened_client_cluster",
    openedClientClusterId: clusterId,
    hiddenNodeCount: Math.max(0, graph.nodes.length - nodes.length),
    clusterGroupSize: state.clusterGroupSize,
  };
}

function effectiveNodeOpacity(baseOpacity, isSelected = false) {
  const scaled = clamp((baseOpacity || 0.8) * state.nodeOpacityScale, 0.18, 0.98);
  return isSelected ? Math.max(scaled, 0.95) : scaled;
}

function effectiveEdgeOpacity(baseOpacity) {
  return clamp((baseOpacity || 0.08) * state.edgeOpacityScale, 0.02, 0.95);
}

function nodeById(nodeId) {
  return state.nodeMap.get(nodeId) || state.fullNodeMap.get(nodeId) || null;
}

function currentDetailRunId() {
  return state.fullGraph?.runId || state.viewRunId || "";
}

function detailTargetNodeId(node) {
  return node?.clusterRepresentativeNodeId || node?.clusterRepresentativeId || node?.id || "";
}

function nodeDetailCacheKey(runId, nodeId) {
  return `${runId || ""}:${nodeId || ""}`;
}

function mergeNodeDetails(node) {
  if (!node) {
    return null;
  }
  const runId = currentDetailRunId();
  const targetNodeId = detailTargetNodeId(node);
  const cacheKey = nodeDetailCacheKey(runId, targetNodeId);
  const details = state.nodeDetailCache.get(cacheKey);
  return details ? { ...node, ...details } : node;
}

async function fetchNodeDetails(node) {
  const targetNodeId = detailTargetNodeId(node);
  const runId = currentDetailRunId();
  if (!runId || !targetNodeId || !node?.hasDetailPayload) {
    return null;
  }
  const cacheKey = nodeDetailCacheKey(runId, targetNodeId);
  if (state.nodeDetailCache.has(cacheKey)) {
    return state.nodeDetailCache.get(cacheKey);
  }
  if (state.nodeDetailPending.has(cacheKey)) {
    return null;
  }
  state.nodeDetailPending.add(cacheKey);
  try {
    const result = await fetchJson(buildApiUrl("/api/node-details", {
      run_id: runId,
      node_id: targetNodeId,
      cluster_id: state.expandedClusterId || undefined,
    }));
    const details = {
      algorithm: String(result?.details?.algorithm || ""),
      algorithmSummary: String(result?.details?.algorithmSummary || ""),
      functionPreview: String(result?.details?.functionPreview || ""),
    };
    state.nodeDetailCache.set(cacheKey, details);
    return details;
  } catch (_) {
    return null;
  } finally {
    state.nodeDetailPending.delete(cacheKey);
  }
}

async function ensureNodeDetails(nodes) {
  const tasks = [];
  for (const node of nodes) {
    if (!node || node.isClusterSummary || !node.hasDetailPayload) {
      continue;
    }
    const runId = currentDetailRunId();
    const targetNodeId = detailTargetNodeId(node);
    const cacheKey = nodeDetailCacheKey(runId, targetNodeId);
    if (!runId || !targetNodeId || state.nodeDetailCache.has(cacheKey) || state.nodeDetailPending.has(cacheKey)) {
      continue;
    }
    tasks.push(fetchNodeDetails(node));
  }
  if (tasks.length) {
    await Promise.allSettled(tasks);
    renderSelectedNodes();
  }
}

function highlightedScoreThreshold(nodes) {
  const scores = nodes
    .map((node) => rawScoreForNode(node))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b);
  if (!scores.length) {
    return null;
  }
  const percentileIndex = Math.max(0, Math.floor(scores.length * 0.985) - 1);
  return scores[percentileIndex];
}

function topScoreSubgraph(graph, percent) {
  const nodeCount = Array.isArray(graph?.nodes) ? graph.nodes.length : 0;
  if (!nodeCount || percent >= 100) {
    return graph;
  }
  const keepCount = Math.max(1, Math.ceil(nodeCount * (percent / 100)));
  const rankedNodes = [...graph.nodes].sort((a, b) => (rawScoreForNode(b) ?? -Infinity) - (rawScoreForNode(a) ?? -Infinity));
  const keepIds = new Set(rankedNodes.slice(0, keepCount).map((node) => node.id));
  state.selectedNodeIds.forEach((id) => keepIds.add(id));
  state.favoriteNodeIds.forEach((id) => keepIds.add(id));
  const nodes = graph.nodes.filter((node) => keepIds.has(node.id));
  const validIds = new Set(nodes.map((node) => node.id));
  const edges = graph.edges.filter((edge) => validIds.has(edge.source) && validIds.has(edge.target));
  return {
    ...graph,
    nodes,
    edges,
    graphView: "top_score_filter",
    highScorePercent: percent,
    hiddenNodeCount: Math.max(0, graph.nodes.length - nodes.length),
  };
}

function spatialClusterCacheKey(graph, groupSize) {
  return [
    graph?.runId || state.viewRunId || "",
    graph?.graphCachedAt || "",
    graph?.nodes?.length || 0,
    graph?.edges?.length || 0,
    Math.round(groupSize),
  ].join("|");
}

function spatialBucketKey(ix, iy, iz) {
  return `${ix}:${iy}:${iz}`;
}

function collectNearbyUnassignedCandidates(records, buckets, unassigned, seedRecord, bucketSize, targetCount) {
  const seedCellX = Math.floor(seedRecord.x / bucketSize);
  const seedCellY = Math.floor(seedRecord.y / bucketSize);
  const seedCellZ = Math.floor(seedRecord.z / bucketSize);
  const candidateIds = new Set();
  let radius = 0;
  const radiusLimit = Math.max(2, Math.ceil(Math.cbrt(records.length)));
  while (candidateIds.size < targetCount && radius <= radiusLimit) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dz = -radius; dz <= radius; dz += 1) {
          if (radius > 0 && Math.max(Math.abs(dx), Math.abs(dy), Math.abs(dz)) !== radius) {
            continue;
          }
          const bucketMembers = buckets.get(spatialBucketKey(seedCellX + dx, seedCellY + dy, seedCellZ + dz));
          if (!bucketMembers?.length) {
            continue;
          }
          bucketMembers.forEach((candidateIndex) => {
            if (unassigned.has(candidateIndex)) {
              candidateIds.add(candidateIndex);
            }
          });
        }
      }
    }
    radius += 1;
  }
  if (candidateIds.size < targetCount) {
    unassigned.forEach((candidateIndex) => candidateIds.add(candidateIndex));
  }
  return [...candidateIds]
    .map((candidateIndex) => {
      const candidate = records[candidateIndex];
      const dx = candidate.x - seedRecord.x;
      const dy = candidate.y - seedRecord.y;
      const dz = candidate.z - seedRecord.z;
      return {
        index: candidateIndex,
        distance2: dx * dx + dy * dy + dz * dz,
      };
    })
    .sort((a, b) => a.distance2 - b.distance2)
    .slice(0, targetCount)
    .map((entry) => entry.index);
}

function nearestMemberToCentroid(members, centroidX, centroidY, centroidZ) {
  let bestMember = members[0] || null;
  let bestDistance2 = Number.POSITIVE_INFINITY;
  members.forEach((member) => {
    const dx = (Number(member.x) || 0) - centroidX;
    const dy = (Number(member.y) || 0) - centroidY;
    const dz = (Number(member.z) || 0) - centroidZ;
    const distance2 = dx * dx + dy * dy + dz * dz;
    if (distance2 < bestDistance2) {
      bestDistance2 = distance2;
      bestMember = member;
    }
  });
  return bestMember;
}

function spatialClusterGraph(graph, groupSize) {
  const sourceNodes = Array.isArray(graph?.nodes) ? graph.nodes.filter((node) => !node.isClusterSummary) : [];
  if (!sourceNodes.length || groupSize <= 1 || sourceNodes.length <= Math.max(60, groupSize * 2)) {
    return graph;
  }
  const cacheKey = spatialClusterCacheKey(graph, groupSize);
  if (state.clusterGraphCacheKey === cacheKey && state.clusterGraphCache) {
    return state.clusterGraphCache;
  }

  const bounds = {
    minX: Infinity, minY: Infinity, minZ: Infinity,
    maxX: -Infinity, maxY: -Infinity, maxZ: -Infinity,
  };
  const records = sourceNodes.map((node, index) => {
    const x = Number(node.x) || 0;
    const y = Number(node.y) || 0;
    const z = Number(node.z) || 0;
    bounds.minX = Math.min(bounds.minX, x);
    bounds.minY = Math.min(bounds.minY, y);
    bounds.minZ = Math.min(bounds.minZ, z);
    bounds.maxX = Math.max(bounds.maxX, x);
    bounds.maxY = Math.max(bounds.maxY, y);
    bounds.maxZ = Math.max(bounds.maxZ, z);
    return { index, node, x, y, z };
  });

  const targetClusterCount = Math.max(1, Math.ceil(sourceNodes.length / Math.max(2, groupSize)));
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const spanZ = Math.max(1, bounds.maxZ - bounds.minZ);
  const estimatedCellSize = Math.cbrt((spanX * spanY * spanZ) / targetClusterCount);
  const bucketSize = Math.max(8, Number.isFinite(estimatedCellSize) ? estimatedCellSize : 8);
  const buckets = new Map();
  records.forEach((record) => {
    const ix = Math.floor(record.x / bucketSize);
    const iy = Math.floor(record.y / bucketSize);
    const iz = Math.floor(record.z / bucketSize);
    const key = spatialBucketKey(ix, iy, iz);
    if (!buckets.has(key)) {
      buckets.set(key, []);
    }
    buckets.get(key).push(record.index);
  });

  const orderedSeedIndices = [...records]
    .sort((a, b) => {
      const scoreDelta = (rawScoreForNode(b.node) ?? -Infinity) - (rawScoreForNode(a.node) ?? -Infinity);
      if (scoreDelta) return scoreDelta;
      if (b.z !== a.z) return b.z - a.z;
      if (b.y !== a.y) return b.y - a.y;
      return a.x - b.x;
    })
    .map((record) => record.index);

  const unassigned = new Set(records.map((record) => record.index));
  const groups = [];
  orderedSeedIndices.forEach((seedIndex) => {
    if (!unassigned.has(seedIndex)) {
      return;
    }
    const seedRecord = records[seedIndex];
    const memberIndices = [seedIndex];
    unassigned.delete(seedIndex);
    const additionalIndices = collectNearbyUnassignedCandidates(
      records,
      buckets,
      unassigned,
      seedRecord,
      bucketSize,
      Math.max(0, groupSize - 1),
    );
    additionalIndices.forEach((candidateIndex) => {
      if (!unassigned.has(candidateIndex)) {
        return;
      }
      memberIndices.push(candidateIndex);
      unassigned.delete(candidateIndex);
    });
    groups.push(memberIndices.map((memberIndex) => sourceNodes[memberIndex]));
  });

  const clusterNodes = [];
  const clusterByMemberId = new Map();
  groups.forEach((members, index) => {
    if (!members.length) {
      return;
    }
    let sumX = 0;
    let sumY = 0;
    let sumZ = 0;
    let historyCount = 0;
    let currentCount = 0;
    let latestCount = 0;
    let bestMember = members[0];
    let bestScore = rawScoreForNode(bestMember) ?? -Infinity;
    members.forEach((member) => {
      sumX += Number(member.x) || 0;
      sumY += Number(member.y) || 0;
      sumZ += Number(member.z) || 0;
      if (member.sourceKind === "history") {
        historyCount += 1;
      } else {
        currentCount += 1;
      }
      if (member.isLatestRound) {
        latestCount += 1;
      }
      const memberScore = rawScoreForNode(member);
      if ((memberScore ?? -Infinity) > bestScore) {
        bestScore = memberScore ?? -Infinity;
        bestMember = member;
      }
    });
    const clusterId = `spatial-cluster:${index}`;
    members.forEach((member) => clusterByMemberId.set(member.id, clusterId));
    const averageScore = members.reduce((acc, member) => acc + (rawScoreForNode(member) ?? 0), 0) / members.length;
    const centroidX = sumX / members.length;
    const centroidY = sumY / members.length;
    const centroidZ = sumZ / members.length;
    const anchorMember = nearestMemberToCentroid(members, centroidX, centroidY, centroidZ);
    clusterNodes.push({
      ...bestMember,
      id: clusterId,
      clusterId,
      isClusterSummary: true,
      isClientCluster: true,
      clusterSampleCount: members.length,
      clusterSourceCount: historyCount,
      clusterCurrentCount: currentCount,
      clusterLatestCount: latestCount,
      clusterRepresentativeNodeId: bestMember.id,
      memberNodeIds: members.map((member) => member.id),
      sourceLabel: "空间簇",
      algorithmSummary: `该空间簇包含 ${members.length} 个相邻节点，位置保持和全量图一致。代表点为 ${bestMember.id}。`,
      functionPreview: bestMember.functionPreview || "可切回全图查看簇内原始节点。",
      rawScore: Number.isFinite(bestScore) ? bestScore : averageScore,
      score: Number.isFinite(bestScore) ? bestScore : averageScore,
      x: Number(anchorMember?.x) || centroidX,
      y: Number(anchorMember?.y) || centroidY,
      z: Number(anchorMember?.z) || centroidZ,
    });
  });

  const aggregatedEdges = new Map();
  (graph.edges || []).forEach((edge) => {
    const sourceClusterId = clusterByMemberId.get(edge.source);
    const targetClusterId = clusterByMemberId.get(edge.target);
    if (!sourceClusterId || !targetClusterId || sourceClusterId === targetClusterId) {
      return;
    }
    const edgeKey = `${sourceClusterId}->${targetClusterId}`;
    const existing = aggregatedEdges.get(edgeKey);
    if (existing) {
      existing.weight += 1;
      return;
    }
    aggregatedEdges.set(edgeKey, {
      source: sourceClusterId,
      target: targetClusterId,
      weight: 1,
    });
  });

  const limitedEdges = [];
  const incidentCounts = new Map();
  [...aggregatedEdges.values()]
    .sort((a, b) => (b.weight || 0) - (a.weight || 0))
    .forEach((edge) => {
      const sourceCount = incidentCounts.get(edge.source) || 0;
      const targetCount = incidentCounts.get(edge.target) || 0;
      if (sourceCount >= 2 && targetCount >= 2) {
        return;
      }
      limitedEdges.push(edge);
      incidentCounts.set(edge.source, sourceCount + 1);
      incidentCounts.set(edge.target, targetCount + 1);
    });

  const clustered = {
    ...graph,
    nodes: clusterNodes,
    edges: limitedEdges,
    graphView: "spatial_cluster",
    clusterGroupSize: Math.round(groupSize),
    hiddenNodeCount: Math.max(0, sourceNodes.length - clusterNodes.length),
  };
  state.clusterGraphCacheKey = cacheKey;
  state.clusterGraphCache = clustered;
  return clustered;
}

function deriveDisplayGraph(graph) {
  if (!graph || graph.error || graph.buildPending) {
    return graph;
  }
  let derived = graph;
  if (state.graphAbstractionMode === "cluster") {
    derived = state.openedClientClusterId
      ? openedClientClusterSubgraph(graph, state.openedClientClusterId)
      : spatialClusterGraph(graph, state.clusterGroupSize);
  }
  derived = topScoreSubgraph(derived, state.highScorePercent);
  return derived;
}

function computeStretchedPositions() {
  const stretched = new Map();
  const spreadScale = Math.max(1, state.graphSpreadScale);
  state.graph.nodes.forEach((node) => {
    const basePosition = node.__visualBasePosition || new THREE.Vector3();
    const stretchedPosition = basePosition
      .clone()
      .sub(state.positionCenter)
      .multiplyScalar(spreadScale)
      .add(state.positionCenter);
    stretched.set(node.id, stretchedPosition);
  });
  return stretched;
}

function updateGraphLayout() {
  const stretchedPositions = computeStretchedPositions();
  state.nodeVisualPositions = stretchedPositions;
  
  if (state.nodeRenderMode === "points" && state.nodePoints) {
    const attribute = state.nodePoints.geometry.getAttribute("position");
    state.graph.nodes.forEach((node, index) => {
      const position = stretchedPositions.get(node.id);
      if (!position) return;
      attribute.setXYZ(index, position.x, position.y, position.z);
    });
    attribute.needsUpdate = true;
    state.nodePoints.geometry.computeBoundingSphere();
    
    const edgeSegments = state.edgeObjects[0];
    if (edgeSegments?.geometry) {
      const edgeAttribute = edgeSegments.geometry.getAttribute("position");
      state.graph.edges.forEach((edge, index) => {
        const source = stretchedPositions.get(edge.source);
        const target = stretchedPositions.get(edge.target);
        if (!source || !target) return;
        edgeAttribute.setXYZ(index * 2, source.x, source.y, source.z);
        edgeAttribute.setXYZ(index * 2 + 1, target.x, target.y, target.z);
      });
      edgeAttribute.needsUpdate = true;
      edgeSegments.geometry.computeBoundingSphere();
    }
    updatePointSelectionEdges();
    return;
  }

  if (state.nodeInstancedMesh) {
    const dummy = new THREE.Object3D();
    const maxScore = Math.max(...state.graph.nodes.map((node) => rawScoreForNode(node) ?? -Infinity).filter(Number.isFinite), 0);
    
    state.graph.nodes.forEach((node, index) => {
      const pos = stretchedPositions.get(node.id);
      if (!pos) return;

      const isSelected = state.selectedNodeIds.has(node.id);
      const isFavorite = state.favoriteNodeIds.has(node.id);
      const isExternalExpert = isExternalExpertNode(node);
      const isBest = rawScoreForNode(node) === maxScore && rawScoreForNode(node) != null;
      const isLatestRun = Boolean(node.isLatestRun);
      const isLatestRound = Boolean(node.isLatestRound);

      const emphasisScale = isSelected ? 1.32 : isFavorite ? 1.18 : isExternalExpert ? 1.16 : isLatestRun ? 1.18 : isLatestRound ? 1.12 : isBest ? 1.1 : 1;
      const scale = state.nodeSizeScale * emphasisScale;

      dummy.position.copy(pos);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      state.nodeInstancedMesh.setMatrixAt(index, dummy.matrix);
    });
    state.nodeInstancedMesh.instanceMatrix.needsUpdate = true;
    state.nodeInstancedMesh.geometry.computeBoundingSphere();
  }

  // 更新连边
  state.edgeObjects.forEach((edgeObj) => {
    if (edgeObj.geometry && edgeObj.geometry.getAttribute("position")) {
      const edgeAttribute = edgeObj.geometry.getAttribute("position");
      state.graph.edges.forEach((edge, index) => {
        const source = stretchedPositions.get(edge.source);
        const target = stretchedPositions.get(edge.target);
        if (!source || !target) return;
        edgeAttribute.setXYZ(index * 2, source.x, source.y, source.z);
        edgeAttribute.setXYZ(index * 2 + 1, target.x, target.y, target.z);
      });
      edgeAttribute.needsUpdate = true;
      edgeObj.geometry.computeBoundingSphere();
    }
  });
}

function updateEdgeAppearance() {
  state.edgeObjects.forEach((line) => {
    line.material.opacity = effectiveEdgeOpacity(line.userData.baseOpacity);
  });
  if (state.nodeRenderMode === "points" && state.nodePoints) {
    state.nodePoints.material.opacity = effectiveNodeOpacity(adaptivePointOpacity(state.graph.nodes.length), false);
    state.nodePoints.material.size = Math.max(5.2, adaptivePointSize(state.graph.nodes.length) * state.nodeSizeScale);
  }
  if (state.selectedEdgeOverlay?.material) {
    state.selectedEdgeOverlay.material.opacity = clamp(0.42 * state.edgeOpacityScale, 0.18, 0.9);
  }
}

function applyEdgeVisibilityPreset(graph) {
  const graphKey = `${state.viewRunId || "none"}:${graph.graphSource || "graph"}:${graph.nodes.length}`;
  if (state.currentGraphKey !== graphKey) {
    state.currentGraphKey = graphKey;
    state.edgeVisibilityPinned = false;
  }
  if (!state.edgeVisibilityPinned) {
    state.showEdges = false;
    elements.edgeToggle.checked = state.showEdges;
  }
}

function updateEdgeVisibility() {
  state.edgeObjects.forEach((line) => {
    line.visible = state.showEdges;
  });
  if (state.selectedEdgeOverlay) {
    state.selectedEdgeOverlay.visible = state.showEdges && state.selectedNodeIds.size > 0;
  }
}

function updateGraphMeta() {
  const graph = state.graph || { nodes: [], edges: [] };
  if (!state.viewRunId) {
    const currentSave = currentSaveEntry();
    elements.graphMeta.textContent = currentSave
      ? `当前存档“${currentSave.name}”还没有进度，可先导入历史样本或直接开始 Run`
      : "请先选择或新建一个存档";
    return;
  }
  if (graph.error) {
    elements.graphMeta.textContent = `OFEC-NBN 未就绪: ${graph.error}`;
    return;
  }
  if (!graph.nodes?.length && !graph.edges?.length) {
    elements.graphMeta.textContent = "图尚未生成";
    return;
  }
  const sourceLabel = graph.graphSource === "exact_nbn_cached"
    ? "完整NBN"
    : graph.graphSource === "ofec_nbn"
      ? "OFEC-NBN"
    : graph.graphSource === "summary_clusters"
      ? "摘要图"
      : "未知数据源";
  const viewLabel = graph.graphView === "summary"
    ? " / 摘要视图"
    : graph.graphView === "local_cluster"
      ? ` / 局部展开 ${graph.expandedClusterId || ""}`.trimEnd()
      : graph.graphView === "top_score_filter"
          ? ` / 高分前 ${graph.highScorePercent || state.highScorePercent}%`
          : graph.graphView === "spatial_cluster"
            ? ` / 空间簇 约${graph.clusterGroupSize || state.clusterGroupSize}点/簇`
            : graph.graphView === "opened_client_cluster"
              ? ` / 已打开簇 ${graph.openedClientClusterId || ""}`.trimEnd()
      : "";
  let metricLabel = "";
  if (graph.distanceMetricRequested && graph.distanceMetric && graph.distanceMetricRequested !== graph.distanceMetric) {
    metricLabel = ` / 距离 ${graph.distanceMetricRequested} -> ${graph.distanceMetric}`;
  } else if (graph.distanceMetric) {
    metricLabel = ` / 距离 ${graph.distanceMetric}`;
  }
  const fallbackLabel = graph.distanceMetricFallbackReason ? " / 已自动回退" : "";
  const truncatedLabel = graph.truncated ? " / 已截断显示" : "";
  const edgeLabel = graph.edges?.length ? ` / 连边${state.showEdges ? "显示" : "隐藏"}` : "";
  const mergedLabel = graph.sourceSampleCount || graph.currentSampleCount
    ? ` / 祖先链${graph.sourceSampleCount || 0} + 当前${graph.currentSampleCount || 0}${graph.mergedRunCount ? ` / 共${graph.mergedRunCount}轮` : ""}`
    : "";
  const latestRunLabel = graph.latestRunSampleCount
    ? ` / 最新运行 ${graph.latestRunSampleCount || 0}`
    : "";
  const latestLabel = graph.latestGeneration
    ? `${latestRunLabel} / 最新一代 G${graph.latestGeneration} (${graph.latestRoundSampleCount || 0})`
    : latestRunLabel;
  const hiddenLabel = graph.hiddenNodeCount ? ` / 已隐藏${graph.hiddenNodeCount}点` : "";
  let cacheLabel = "";
  const hasUsableGraph = (graph.nodes?.length || 0) > 0;
  if (hasUsableGraph && graph.graphCache === "disk") {
    cacheLabel = " / 已复用历史图缓存";
  } else if (hasUsableGraph && graph.graphCache === "built") {
    cacheLabel = " / 已新生成图缓存";
  }
  const renderLabel = state.nodeRenderMode === "points" ? " / 点云渲染" : "";
  const pickLabel = state.nodeRenderMode === "points" ? " / 圆点吸附选点" : "";
  const localEdgeLabel = state.nodeRenderMode !== "mesh" ? " / 选中局部连边" : "";
  const statusPerf = state.lastStatusPerf || {};
  const graphPerf = state.lastGraphPerf || {};
  const rollingPerf = state.lastPerfRolling || {};
  const snapshot = state.lastRunSnapshot || null;
  const perfParts = [];
  if (snapshot?.phaseLabel) {
    const progressText = formatRunProgress(snapshot);
    perfParts.push(`运行阶段 ${snapshot.phaseLabel}${progressText && progressText !== "-" ? ` (${progressText})` : ""}`);
  }
  if (statusPerf.apiStatusMs != null) {
    perfParts.push(`状态接口 ${formatDurationMs(statusPerf.apiStatusMs)}`);
  }
  if (graphPerf.graphLoadMs != null) {
    perfParts.push(`图加载 ${formatDurationMs(graphPerf.graphLoadMs)}`);
  }
  if (graphPerf.graphBuildMs != null) {
    perfParts.push(`最近构图 ${formatDurationMs(graphPerf.graphBuildMs)}`);
  }
  if (rollingPerf.apiStatusMs?.avgMs != null) {
    perfParts.push(`状态均/峰 ${formatRollingDuration(rollingPerf.apiStatusMs)}`);
  }
  if (rollingPerf.graphLoadMs?.avgMs != null) {
    perfParts.push(`图加载均/峰 ${formatRollingDuration(rollingPerf.graphLoadMs)}`);
  }
  if (rollingPerf.graphBuildMs?.avgMs != null) {
    perfParts.push(`构图均/峰 ${formatRollingDuration(rollingPerf.graphBuildMs)}`);
  }
  const perfLabel = perfParts.length ? ` / ${perfParts.join(" / ")}` : "";
  elements.graphMeta.textContent = `节点 ${graph.nodes.length} / 边 ${graph.edges.length} / ${sourceLabel}${viewLabel}${mergedLabel}${latestLabel}${hiddenLabel}${metricLabel}${fallbackLabel}${truncatedLabel}${edgeLabel}${cacheLabel}${renderLabel}${pickLabel}${localEdgeLabel}${perfLabel}`;
}

function syncGraphViewControls() {
  const [selectedNodeId] = [...state.selectedNodeIds];
  const selectedNode = selectedNodeId ? state.nodeMap.get(selectedNodeId) : null;
  elements.openClusterButton.disabled = !(state.graphAbstractionMode === "cluster" && selectedNode?.isClientCluster);
  elements.resetGraphViewButton.hidden = !(state.highScorePercent < 100 || state.openedClientClusterId);
  elements.clusterGroupSize.disabled = state.graphAbstractionMode !== "cluster";
  elements.runCandidatesButton.disabled = state.candidateNodeIds.size === 0;
  elements.clearCandidatesButton.disabled = state.candidateNodeIds.size === 0;
  elements.runInitialPopulationButton.disabled = state.initialPopulationNodeIds.size === 0;
  elements.clearInitialPopulationButton.disabled = state.initialPopulationNodeIds.size === 0;
}

function formatNumber(value, digits = 6) {
  if (value == null) {
    return "-";
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return numeric.toFixed(digits);
}

function formatDurationMs(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return numeric >= 1000 ? `${(numeric / 1000).toFixed(2)}s` : `${numeric.toFixed(1)}ms`;
}

function formatRollingDuration(metric) {
  if (!metric || metric.avgMs == null) {
    return "-";
  }
  return `${formatDurationMs(metric.avgMs)} / ${formatDurationMs(metric.maxMs)}`;
}

function formatCompactTiming(metric, label = "") {
  if (!metric || metric.lastMs == null) {
    return "";
  }
  const prefix = label ? `${label} ` : "";
  if (metric.avgMs == null) {
    return `${prefix}${formatDurationMs(metric.lastMs)}`;
  }
  return `${prefix}${formatDurationMs(metric.lastMs)} / ${formatDurationMs(metric.avgMs)}`;
}

function formatRunPhase(snapshot, status = null) {
  if (snapshot?.phaseLabel) {
    return snapshot.phaseLabel;
  }
  if (status?.status === "building_graph") {
    return "完整图生成中";
  }
  return "-";
}

function formatRunProgress(snapshot) {
  if (!snapshot) {
    return "-";
  }
  if (snapshot.phase === "initial_population") {
    const completed = Number(snapshot.completedSeedCount || 0);
    const total = Number(snapshot.initialPopulationCount || 0);
    const accepted = Number(snapshot.acceptedSeedCount || 0);
    const currentSeed = snapshot.currentSeedSampleOrder != null ? ` / 当前 seed ${snapshot.currentSeedSampleOrder}` : "";
    return `${completed}/${total || "?"} / 通过 ${accepted}${currentSeed}`;
  }
  if (snapshot.phase === "direct_ai_sampling") {
    const completed = Number(snapshot.completedAttempts || 0);
    const total = Number(snapshot.totalAttempts || 0);
    const currentAttempt = snapshot.currentAttempt != null ? ` / 当前 ${snapshot.currentAttempt}` : "";
    return `${completed}/${total || "?"}${currentAttempt}`;
  }
  if (snapshot.phase === "sampling" || snapshot.phase === "eoh_running") {
    const parts = [];
    if (snapshot.currentGeneration != null) {
      parts.push(`G${snapshot.currentGeneration}`);
    }
    if (snapshot.populationSize != null) {
      parts.push(`种群 ${snapshot.populationSize}`);
    }
    if (snapshot.sampleCount != null) {
      parts.push(`样本 ${snapshot.sampleCount}`);
    } else if (snapshot.lastSampleOrder != null) {
      parts.push(`样本 ${snapshot.lastSampleOrder}`);
    }
    return parts.length ? parts.join(" / ") : "-";
  }
  if (snapshot.phase === "stopped") {
    return "运行已手动停止";
  }
  if (snapshot.phase === "finished") {
    return "运行完成";
  }
  return "-";
}

function formatRunnerTiming(snapshot, perf = null) {
  const timings = perf?.runnerTimings || {};
  if (snapshot?.phase === "initial_population" || snapshot?.phase === "stopped") {
    return formatCompactTiming(timings.seedEvaluationMs, "seed") || "-";
  }
  if (snapshot?.phase === "direct_ai_sampling") {
    return formatCompactTiming(timings.directAiAttemptMs, "单次") || "-";
  }
  if (snapshot?.phase === "sampling" || snapshot?.phase === "eoh_running" || snapshot?.phase === "finished") {
    const parts = [];
    const sampleGen = formatCompactTiming(timings.sampleGenerationMs, "采样");
    const sampleEval = formatCompactTiming(timings.sampleEvaluationMs, "评估");
    if (sampleGen) {
      parts.push(sampleGen);
    }
    if (sampleEval) {
      parts.push(sampleEval);
    }
    if (parts.length) {
      return parts.join(" / ");
    }
  }
  if (perf?.graphBuildMs != null) {
    return `构图 ${formatDurationMs(perf.graphBuildMs)}`;
  }
  return "-";
}

function rawScoreForNode(node) {
  return node?.rawScore ?? node?.score ?? null;
}

function ofecFitnessForNode(node) {
  return node?.ofecFitness ?? null;
}

function summarizeText(text, fallback, maxLength = 180) {
  const source = String(text || "").trim();
  if (!source) {
    return fallback;
  }
  return source.length > maxLength ? `${source.slice(0, maxLength)}...` : source;
}

function normalizeAlgorithmText(text, fallback = "") {
  const source = String(text || "").trim();
  if (!source) {
    return fallback;
  }
  if (/[\u4e00-\u9fff]/.test(source)) {
    return source;
  }

  if (source.startsWith("{") && source.endsWith("}")) {
    return source.slice(1, -1).trim();
  }
  return source;
}

function localAlgorithmFallback(text, fallback = "") {
  const source = normalizeAlgorithmText(text, fallback);
  if (!source) {
    return fallback;
  }
  if (/[\u4e00-\u9fff]/.test(source)) {
    return source;
  }

  const exactReplacements = new Map([
    ["No high-level summary provided by the model.", "模型未提供高层摘要。"],
    ["Fallback deterministic grid baseline injected by the visual platform to guarantee a feasible initializer.", "由可视化平台注入的确定性网格保底基线，用于保证初始化阶段至少存在一个可行解。"],
    ["LLM response could not be parsed into a valid function.", "LLM 响应无法解析为有效函数。"],
    ["Generated function could not be converted into an executable program.", "生成的函数无法转换为可执行程序。"],
  ]);
  return exactReplacements.get(source) || "";
}

function algorithmTextForNode(node) {
  const detailedNode = mergeNodeDetails(node) || node;
  return normalizeAlgorithmText(detailedNode?.algorithm || detailedNode?.algorithmSummary || "", "");
}

function algorithmTranslationKey(node) {
  return `${node.id}::${algorithmTextForNode(node)}`;
}

function displayAlgorithmText(node, fallback = "") {
  const source = algorithmTextForNode(node);
  if (!source) {
    return fallback;
  }
  if (/[\u4e00-\u9fff]/.test(source)) {
    return source;
  }
  const localFallback = localAlgorithmFallback(source, "");
  if (localFallback) {
    return localFallback;
  }
  const cacheKey = algorithmTranslationKey(node);
  return state.algorithmTranslationCache.get(cacheKey) || "正在调用 AI 翻译这条算法说明...";
}

async function ensureAlgorithmTranslations(nodes) {
  const tasks = [];
  for (const node of nodes) {
    const source = algorithmTextForNode(node);
    if (!source || /[\u4e00-\u9fff]/.test(source)) {
      continue;
    }
    if (localAlgorithmFallback(source, "")) {
      continue;
    }
    const cacheKey = algorithmTranslationKey(node);
    if (state.algorithmTranslationCache.has(cacheKey) || state.algorithmTranslationPending.has(cacheKey)) {
      continue;
    }

    state.algorithmTranslationPending.add(cacheKey);
    const task = fetchJson("/api/translate-algorithm", {
      method: "POST",
      body: JSON.stringify({
        text: source,
        llm: llmPayload(),
      }),
    })
      .then((result) => {
        const translated = String(result?.translatedText || "").trim();
        if (translated) {
          state.algorithmTranslationCache.set(cacheKey, translated);
        }
      })
      .catch(() => {})
      .finally(() => {
        state.algorithmTranslationPending.delete(cacheKey);
        if (state.selectedNodeIds.has(node.id)) {
          renderSelectedNodes();
        }
      });
    tasks.push(task);
  }
  if (tasks.length) {
    await Promise.allSettled(tasks);
  }
}

function setAutoRotate(enabled) {
  state.autoRotate = Boolean(enabled);
  elements.rotateToggleButton.textContent = `自动旋转：${state.autoRotate ? "开" : "关"}`;
  elements.rotateToggleButton.classList.toggle("active", state.autoRotate);
}

function syncControlState() {
  controls.enabled = !elements.boxSelectMode.checked && !state.isDraggingSelection;
}

function isExternalExpertNode(node) {
  return Boolean(node?.hasExternalExpert) || node?.originKind === "external_expert";
}

function colorForNode(node, maxScore) {
  const nodeScore = rawScoreForNode(node);
  const isSelected = state.selectedNodeIds.has(node.id);
  const isFavorite = state.favoriteNodeIds.has(node.id);
  const isExternalExpert = isExternalExpertNode(node);
  const isBest = nodeScore === maxScore && nodeScore != null;
  const isLatestRun = Boolean(node.isLatestRun);
  const isLatestRound = Boolean(node.isLatestRound);
  return isSelected
    ? new THREE.Color(0xf472b6)
    : isFavorite
      ? new THREE.Color(0x22d3ee)
      : isExternalExpert
        ? new THREE.Color(0x6d28d9)
      : isLatestRun
        ? new THREE.Color(0xef4444)
        : isLatestRound
          ? new THREE.Color(0xf97316)
        : isBest
          ? new THREE.Color(0xfbbf24)
          : scoreColor(nodeScore, maxScore);
}

function pointColorForNode(node, maxScore, threshold) {
  const base = colorForNode(node, maxScore);
  const nodeScore = rawScoreForNode(node);
  const isSelected = state.selectedNodeIds.has(node.id);
  const isFavorite = state.favoriteNodeIds.has(node.id);
  const isExternalExpert = isExternalExpertNode(node);
  const isLatestRun = Boolean(node.isLatestRun);
  const isLatestRound = Boolean(node.isLatestRound);
  const isBest = nodeScore === maxScore && nodeScore != null;
  const isHighScore = threshold != null && nodeScore != null && nodeScore >= threshold;
  if (isSelected || isFavorite || isExternalExpert || isLatestRun || isLatestRound || isBest || isHighScore) {
    return base;
  }
  return new THREE.Color(0x8ea0c9).lerp(base, 0.22);
}

function nodeEmphasisScale(node, maxScore) {
  const nodeScore = rawScoreForNode(node);
  const isSelected = state.selectedNodeIds.has(node.id);
  const isFavorite = state.favoriteNodeIds.has(node.id);
  const isExternalExpert = isExternalExpertNode(node);
  const isBest = nodeScore === maxScore && nodeScore != null;
  const isLatestRun = Boolean(node.isLatestRun);
  const isLatestRound = Boolean(node.isLatestRound);
  return isSelected ? 1.34 : isFavorite ? 1.2 : isExternalExpert ? 1.18 : isLatestRun ? 1.18 : isLatestRound ? 1.14 : isBest ? 1.12 : 1;
}

function updatePointSelectionEdges() {
  if (state.selectedEdgeOverlay) {
    graphGroup.remove(state.selectedEdgeOverlay);
    if (state.selectedEdgeOverlay.geometry) {
      state.selectedEdgeOverlay.geometry.dispose();
    }
    if (state.selectedEdgeOverlay.material) {
      state.selectedEdgeOverlay.material.dispose();
    }
    state.selectedEdgeOverlay = null;
  }
  if (state.nodeRenderMode !== "points" || !state.selectedNodeIds.size) {
    return;
  }
  const selectedIds = state.selectedNodeIds;
  const localEdges = state.graph.edges.filter((edge) => selectedIds.has(edge.source) || selectedIds.has(edge.target)).slice(0, 1600);
  if (!localEdges.length) {
    return;
  }
  const edgePositions = new Float32Array(localEdges.length * 6);
  localEdges.forEach((edge, index) => {
    const source = state.nodeVisualPositions.get(edge.source);
    const target = state.nodeVisualPositions.get(edge.target);
    if (!source || !target) {
      return;
    }
    const offset = index * 6;
    edgePositions[offset] = source.x;
    edgePositions[offset + 1] = source.y;
    edgePositions[offset + 2] = source.z;
    edgePositions[offset + 3] = target.x;
    edgePositions[offset + 4] = target.y;
    edgePositions[offset + 5] = target.z;
  });
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
  const edgeMaterial = new THREE.LineBasicMaterial({
    color: 0xf8fafc,
    transparent: true,
    opacity: clamp(0.42 * state.edgeOpacityScale, 0.18, 0.9),
  });
  const edgeSegments = new THREE.LineSegments(edgeGeometry, edgeMaterial);
  edgeSegments.visible = state.showEdges;
  graphGroup.add(edgeSegments);
  state.selectedEdgeOverlay = edgeSegments;
}

function buildMeshGraph(graph, visualPositions, maxScore, nodeRadius, nodeSegments, nodeOpacity, edgeOpacity) {
  // 1. 批量渲染连边 (LineSegments)
  if (graph.edges.length > 0) {
    const edgePositions = new Float32Array(graph.edges.length * 6);
    graph.edges.forEach((edge, index) => {
      const source = visualPositions.get(edge.source);
      const target = visualPositions.get(edge.target);
      if (!source || !target) return;
      const offset = index * 6;
      edgePositions[offset] = source.x;
      edgePositions[offset + 1] = source.y;
      edgePositions[offset + 2] = source.z;
      edgePositions[offset + 3] = target.x;
      edgePositions[offset + 4] = target.y;
      edgePositions[offset + 5] = target.z;
    });

    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0x6b7cff,
      transparent: true,
      opacity: effectiveEdgeOpacity(edgeOpacity),
    });
    const edgeSegments = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeSegments.userData.baseOpacity = edgeOpacity;
    graphGroup.add(edgeSegments);
    state.edgeObjects.push(edgeSegments);
  }

  // 2. 批量渲染节点 (InstancedMesh)
  const nodeCount = graph.nodes.length;
  if (nodeCount === 0) return;

  const geometry = new THREE.SphereGeometry(nodeRadius, nodeSegments, nodeSegments);
  const material = new THREE.MeshStandardMaterial({
    emissive: state.backgroundTheme === "dark" ? new THREE.Color(0x172554) : new THREE.Color(0x243244),
    emissiveIntensity: state.backgroundTheme === "dark" ? 0.46 : 0.2,
    roughness: 0.18,
    metalness: 0.16,
    transparent: true,
    opacity: effectiveNodeOpacity(nodeOpacity, false),
  });

  const instancedMesh = new THREE.InstancedMesh(geometry, material, nodeCount);
  instancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  instancedMesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(nodeCount * 3), 3);

  const dummy = new THREE.Object3D();
  graph.nodes.forEach((node, index) => {
    const position = visualPositions.get(node.id) || new THREE.Vector3(node.x || 0, node.y || 0, node.z || 0);
    dummy.position.copy(position);
    dummy.scale.setScalar(1);
    dummy.updateMatrix();
    instancedMesh.setMatrixAt(index, dummy.matrix);

    const color = colorForNode(node, maxScore);
    instancedMesh.setColorAt(index, color);

    node.__visualBasePosition = position.clone();
  });

  instancedMesh.instanceMatrix.needsUpdate = true;
  if (instancedMesh.instanceColor) instancedMesh.instanceColor.needsUpdate = true;

  graphGroup.add(instancedMesh);
  state.nodeInstancedMesh = instancedMesh;
}

function buildPointGraph(graph, visualPositions, maxScore, nodeRadius, nodeOpacity, edgeOpacity) {
  state.nodeRenderMode = "points";
  const pointOpacity = adaptivePointOpacity(graph.nodes.length);
  const pointSize = adaptivePointSize(graph.nodes.length);
  const pointEdgeOpacity = adaptivePointBackgroundEdgeOpacity(graph.nodes.length);
  if (graph.edges.length) {
    const edgePositions = new Float32Array(graph.edges.length * 6);
    graph.edges.forEach((edge, index) => {
      const source = visualPositions.get(edge.source);
      const target = visualPositions.get(edge.target);
      if (!source || !target) {
        return;
      }
      const offset = index * 6;
      edgePositions[offset] = source.x;
      edgePositions[offset + 1] = source.y;
      edgePositions[offset + 2] = source.z;
      edgePositions[offset + 3] = target.x;
      edgePositions[offset + 4] = target.y;
      edgePositions[offset + 5] = target.z;
    });
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0x7282ff,
      transparent: true,
      opacity: clamp(effectiveEdgeOpacity(pointEdgeOpacity), 0.03, 0.18),
    });
    const edgeSegments = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeSegments.userData.baseOpacity = pointEdgeOpacity;
    graphGroup.add(edgeSegments);
    state.edgeObjects.push(edgeSegments);
  }
  const nodePositions = new Float32Array(graph.nodes.length * 3);
  const nodeColors = new Float32Array(graph.nodes.length * 3);
  const scoreThreshold = highlightedScoreThreshold(graph.nodes);
  graph.nodes.forEach((node, index) => {
    const position = visualPositions.get(node.id) || new THREE.Vector3(node.x || 0, node.y || 0, node.z || 0);
    const offset = index * 3;
    nodePositions[offset] = position.x;
    nodePositions[offset + 1] = position.y;
    nodePositions[offset + 2] = position.z;
    const color = pointColorForNode(node, maxScore, scoreThreshold);
    nodeColors[offset] = color.r;
    nodeColors[offset + 1] = color.g;
    nodeColors[offset + 2] = color.b;
    node.__visualBasePosition = position.clone();
  });
  const nodeGeometry = new THREE.BufferGeometry();
  nodeGeometry.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
  nodeGeometry.setAttribute("color", new THREE.BufferAttribute(nodeColors, 3));
  const nodeMaterial = new THREE.PointsMaterial({
    size: Math.max(5.2, pointSize * state.nodeSizeScale),
    vertexColors: true,
    transparent: true,
    opacity: effectiveNodeOpacity(pointOpacity, false),
    sizeAttenuation: true,
    alphaMap: roundPointTexture,
    map: roundPointTexture,
    depthWrite: false,
    depthTest: true,
    alphaTest: 0.48,
  });
  const points = new THREE.Points(nodeGeometry, nodeMaterial);
  graphGroup.add(points);
  state.nodePoints = points;
  raycaster.params.Points.threshold = Math.max(10, nodeRadius * 5.4);
  updatePointSelectionEdges();
}

function buildGraph(graph) {
  clearGraph();
  state.graph = graph;
  state.expandedClusterId = graph.expandedClusterId || null;
  state.graphSignature = graphSignature(graph);
  state.favoriteNodeIds = new Set([...state.favoriteNodeIds].filter((id) => graph.nodes.some((node) => node.id === id) || id.includes("-")));
  const validNodeIds = new Set(graph.nodes.map((node) => node.id));
  state.selectedNodeIds = new Set([...state.selectedNodeIds].filter((id) => validNodeIds.has(id)));
  graphGroup.rotation.y = 0;
  applyEdgeVisibilityPreset(graph);
  if (graph.error) {
    updateGraphMeta();
    renderSelectedNodes();
    return;
  }
  const visualPositions = buildVisualPositions(graph.nodes);
  const positionValues = [...visualPositions.values()];
  if (positionValues.length) {
    const center = new THREE.Vector3();
    positionValues.forEach((position) => center.add(position));
    state.positionCenter = center.multiplyScalar(1 / positionValues.length);
  } else {
    state.positionCenter = new THREE.Vector3();
  }
  const nodeCount = graph.nodes.length;
  const maxScore = Math.max(...graph.nodes.map((node) => rawScoreForNode(node) ?? -Infinity).filter(Number.isFinite), 0);
  const nodeRadius = adaptiveNodeRadius(nodeCount);
  const nodeSegments = adaptiveSegments(nodeCount);
  const nodeOpacity = adaptiveNodeOpacity(nodeCount);
  const edgeOpacity = adaptiveEdgeOpacity(nodeCount);
  graph.nodes.forEach((node) => {
    const position = visualPositions.get(node.id) || new THREE.Vector3(node.x || 0, node.y || 0, node.z || 0);
    node.__visualBasePosition = position.clone();
    state.nodeMap.set(node.id, node);
    state.nodeVisualPositions.set(node.id, position.clone());
    state.nodeIndexById.set(node.id, state.nodeIndexById.size);
  });

  buildMeshGraph(graph, visualPositions, maxScore, nodeRadius, nodeSegments, nodeOpacity, edgeOpacity);

  updateGraphLayout();
  updateEdgeAppearance();
  updateEdgeVisibility();
  syncSummaryViewButton();
  updateGraphMeta();
  renderFavoriteNodes();
  syncGraphViewControls();
}

function graphSignature(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const firstNodeId = nodes[0]?.id || "";
  const lastNodeId = nodes[nodes.length - 1]?.id || "";
  return [
    graph?.runId || state.viewRunId || "",
    graph?.graphCachedAt || "",
    graph?.graphNodeLimit || "",
    graph?.distanceMetric || "",
    graph?.graphView || "",
    graph?.expandedClusterId || "",
    graph?.highScorePercent || "",
    state.graphAbstractionMode || "",
    state.clusterGroupSize || "",
    state.openedClientClusterId || "",
    graph?.hiddenNodeCount || 0,
    nodes.length,
    edges.length,
    firstNodeId,
    lastNodeId,
    graph?.error || "",
  ].join("|");
}

function setWaitingGraphMessage(message) {
  elements.graphMeta.textContent = message;
}

function showNoRunSelectedState() {
  state.viewRunId = null;
  state.currentStatus = "idle";
  state.expandedClusterId = null;
  state.openedClientClusterId = null;
  state.clusterGraphCacheKey = null;
  state.clusterGraphCache = null;
  state.fullGraph = { nodes: [], edges: [], truncated: false };
  state.graph = { nodes: [], edges: [], truncated: false };
  state.graphSignature = null;
  state.pendingFocusNodeId = null;
  state.fullNodeMap.clear();
  state.candidateNodeIds.clear();
    state.initialPopulationNodeIds.clear();
  state.selectedNodeIds.clear();
  state.selectedNodeIds.clear();
  state.lastStatusPerf = null;
  state.lastGraphPerf = null;
  state.lastPerfRolling = null;
  state.nodeDetailCache.clear();
  state.nodeDetailPending.clear();
  elements.statusText.textContent = "空闲";
  elements.sampleCount.textContent = "0";
  elements.bestScore.textContent = "-";
  elements.bestSample.textContent = "-";
  elements.embeddingProgress.textContent = "-";
  elements.currentPrompt.textContent = "-";
  elements.currentMode.textContent = "-";
  clearGraph();
  renderRunHistory();
  syncSummaryViewButton();
  updateGraphMeta();
  renderSelectedNodes();
  renderCandidateNodes();
    renderInitialPopulationNodes();
  renderLatestGeneratedNodes();
  syncGraphViewControls();
}

function syncSummaryViewButton() {
  const show = Boolean(state.viewRunId && state.expandedClusterId);
  elements.summaryViewButton.hidden = !show;
}

function renderActiveGraph(force = false) {
  const graph = deriveDisplayGraph(state.fullGraph);
  const signature = graphSignature(graph);
  if (force || signature !== state.graphSignature) {
    buildGraph(graph);
  } else {
    state.graph = graph;
    updateGraphMeta();
    syncGraphViewControls();
  }
  if (graph.error) {
    renderSelectedNodes();
    return;
  }
  refreshNodeColors();
  renderSelectedNodes();
}

function openClientCluster(nodeId) {
  const clusterNode = state.nodeMap.get(nodeId);
  if (!clusterNode?.isClientCluster) {
    return;
  }
  state.openedClientClusterId = clusterNode.id;
  state.selectedNodeIds.clear();
  syncClusterGroupLabel();
  renderActiveGraph(true);
  const representativeId = clusterNode.clusterRepresentativeNodeId || clusterNode.memberNodeIds?.[0] || null;
  if (representativeId) {
    updateSelection([representativeId]);
  }
}

function currentSaveEntry() {
  return state.saves.find((save) => save.saveId === state.activeSaveId) || null;
}

function render() {
  controls.update();
  if (state.autoRotate && !state.isDraggingSelection) {
    graphGroup.rotation.y += 0.0018;
  }
  renderer.render(scene, camera);
  requestAnimationFrame(render);
}

function normalizePointer(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function refreshNodeColors() {
  const maxScore = Math.max(...state.graph.nodes.map((node) => rawScoreForNode(node) ?? -Infinity).filter(Number.isFinite), 0);
  
  if (state.nodeRenderMode === "points" && state.nodePoints) {
    const colorAttribute = state.nodePoints.geometry.getAttribute("color");
    const scoreThreshold = highlightedScoreThreshold(state.graph.nodes);
    state.graph.nodes.forEach((node, index) => {
      const color = pointColorForNode(node, maxScore, scoreThreshold);
      colorAttribute.setXYZ(index, color.r, color.g, color.b);
    });
    colorAttribute.needsUpdate = true;
    state.nodePoints.material.opacity = effectiveNodeOpacity(adaptiveNodeOpacity(state.graph.nodes.length), false);
    state.nodePoints.material.size = Math.max(3.2, adaptiveNodeRadius(state.graph.nodes.length) * 3.2 * state.nodeSizeScale);
    updatePointSelectionEdges();
    updateEdgeVisibility();
    return;
  }

  if (state.nodeInstancedMesh) {
    const dummy = new THREE.Object3D();
    const stretchedPositions = computeStretchedPositions();
    
    state.graph.nodes.forEach((node, index) => {
      const nodeScore = rawScoreForNode(node);
      const isSelected = state.selectedNodeIds.has(node.id);
      const isFavorite = state.favoriteNodeIds.has(node.id);
      const isExternalExpert = isExternalExpertNode(node);
      const isBest = nodeScore === maxScore && nodeScore != null;
      const isLatestRun = Boolean(node.isLatestRun);
      const isLatestRound = Boolean(node.isLatestRound);

      // 颜色更新
      const color = colorForNode(node, maxScore);
      state.nodeInstancedMesh.setColorAt(index, color);

      // 缩放更新 (针对选中/高分等进行强调)
      const emphasisScale = isSelected ? 1.32 : isFavorite ? 1.18 : isExternalExpert ? 1.16 : isLatestRun ? 1.18 : isLatestRound ? 1.12 : isBest ? 1.1 : 1;
      const scale = state.nodeSizeScale * emphasisScale;
      
      const pos = stretchedPositions.get(node.id) || node.__visualBasePosition || new THREE.Vector3();
      dummy.position.copy(pos);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      state.nodeInstancedMesh.setMatrixAt(index, dummy.matrix);
    });

    state.nodeInstancedMesh.instanceMatrix.needsUpdate = true;
    if (state.nodeInstancedMesh.instanceColor) state.nodeInstancedMesh.instanceColor.needsUpdate = true;
    
    // 更新整体材质透明度
    state.nodeInstancedMesh.material.opacity = effectiveNodeOpacity(adaptiveNodeOpacity(state.graph.nodes.length), false);
  }
}

function renderFavoriteNodes() {
  const favorites = [...state.favoriteNodeIds]
    .map((id) => nodeById(id))
    .filter(Boolean)
    .sort((a, b) => (b.generation || 0) - (a.generation || 0) || (b.sampleOrder || 0) - (a.sampleOrder || 0));

  if (!favorites.length) {
    elements.favoriteNodes.textContent = "暂无";
    return;
  }

  elements.favoriteNodes.innerHTML = favorites
    .map(
      (node) => `
        <div class="selected-chip favorite-chip">
          <strong>${escapeHtml(node.id)}</strong> | G${node.generation ?? "-"} | ${escapeHtml(node.sourceLabel || "-")}
          <div class="chip-meta">原始评估分: ${formatNumber(rawScoreForNode(node), 5)} | 操作符: ${escapeHtml(node.operator || "-")}</div>
          <div class="chip-actions">
            <button class="secondary chip-button" data-action="focus-node" data-node-id="${escapeHtml(node.id)}">定位</button>
            <button class="secondary chip-button" data-action="toggle-candidate" data-node-id="${escapeHtml(node.id)}">${state.candidateNodeIds.has(node.id) ? "移出参考解" : "加入参考解"}</button>
            <button class="secondary chip-button" data-action="toggle-initial-population" data-node-id="${escapeHtml(node.id)}">${state.initialPopulationNodeIds.has(node.id) ? "移出种群" : "加入种群"}</button>
            <button class="secondary chip-button" data-action="toggle-favorite" data-node-id="${escapeHtml(node.id)}">取消收藏</button>
          </div>
        </div>
      `,
    )
    .join("");
}

function renderCandidateNodes() {
  const candidates = [...state.candidateNodeIds]
    .map((id) => nodeById(id))
    .filter((node) => node && !node.isClusterSummary)
    .sort((a, b) => (b.generation || 0) - (a.generation || 0) || (b.sampleOrder || 0) - (a.sampleOrder || 0));
  elements.candidateCount.textContent = String(candidates.length);
  if (!candidates.length) {
    elements.candidateNodes.textContent = "暂无";
    syncGraphViewControls();
    return;
  }
  elements.candidateNodes.innerHTML = candidates
    .map(
      (node) => `
        <div class="selected-chip">
          <strong>${escapeHtml(node.id)}</strong> | G${node.generation ?? "-"} | ${escapeHtml(node.sourceLabel || "-")}
          <div class="chip-meta">原始评估分: ${formatNumber(rawScoreForNode(node), 5)} | 操作符: ${escapeHtml(node.operator || "-")}</div>
          <div class="chip-summary">${escapeHtml(summarizeText(displayAlgorithmText(node, "暂无算法摘要"), "暂无算法摘要", 100))}</div>
          <div class="chip-actions">
            <button class="secondary chip-button" data-action="focus-node" data-node-id="${escapeHtml(node.id)}">定位</button>
            <button class="secondary chip-button" data-action="toggle-candidate" data-node-id="${escapeHtml(node.id)}">移出参考解</button>
            <button class="secondary chip-button" data-action="toggle-initial-population" data-node-id="${escapeHtml(node.id)}">${state.initialPopulationNodeIds.has(node.id) ? "移出种群" : "加入种群"}</button>
          </div>
        </div>
      `,
    )
    .join("");
  syncGraphViewControls();
}

function renderInitialPopulationNodes() {
  const nodes = [...state.initialPopulationNodeIds]
    .map((id) => nodeById(id))
    .filter((node) => node && !node.isClusterSummary)
    .sort((a, b) => (b.generation || 0) - (a.generation || 0) || (b.sampleOrder || 0) - (a.sampleOrder || 0));
  elements.initialPopulationCount.textContent = String(nodes.length);
  if (!nodes.length) {
    elements.initialPopulationNodes.textContent = "暂无";
    syncGraphViewControls();
    return;
  }
  elements.initialPopulationNodes.innerHTML = nodes
    .map(
      (node) => `
        <div class="selected-chip">
          <strong>${escapeHtml(node.id)}</strong> | G${node.generation ?? "-"} | ${escapeHtml(node.sourceLabel || "-")}
          <div class="chip-meta">原始评估分: ${formatNumber(rawScoreForNode(node), 5)} | 操作符: ${escapeHtml(node.operator || "-")}</div>
          <div class="chip-summary">${escapeHtml(summarizeText(displayAlgorithmText(node, "暂无算法摘要"), "暂无算法摘要", 100))}</div>
          <div class="chip-actions">
            <button class="secondary chip-button" data-action="focus-node" data-node-id="${escapeHtml(node.id)}">定位</button>
            <button class="secondary chip-button" data-action="toggle-initial-population" data-node-id="${escapeHtml(node.id)}">移出种群</button>
          </div>
        </div>
      `,
    )
    .join("");
  syncGraphViewControls();
}

function latestGeneratedNodes() {
  const fullNodes = Array.isArray(state.fullGraph?.nodes) ? state.fullGraph.nodes : [];
  return fullNodes
    .filter((node) => !node.isClusterSummary && node.isLatestRun && !isExternalExpertNode(node))
    .sort((a, b) => (rawScoreForNode(b) ?? -Infinity) - (rawScoreForNode(a) ?? -Infinity) || (b.sampleOrder || 0) - (a.sampleOrder || 0));
}

function renderLatestGeneratedNodes() {
  const latestNodes = latestGeneratedNodes();
  const latestBestScore = state.fullGraph?.latestRunBestScore ?? null;
  const historicalBestScore = state.fullGraph?.historicalBestScore ?? null;
  const exceedsHistory = Boolean(state.fullGraph?.latestRunExceededHistoryBest);
  elements.latestGeneratedCount.textContent = String(latestNodes.length);
  elements.latestGeneratedBest.textContent = formatNumber(latestBestScore, 5);
  elements.latestGeneratedCompare.textContent = latestBestScore == null
    ? "-"
    : historicalBestScore == null
      ? "无历史基线"
      : exceedsHistory
        ? `超过历史 ${formatNumber(historicalBestScore, 5)}`
        : `未超过历史 ${formatNumber(historicalBestScore, 5)}`;
  if (!latestNodes.length) {
    elements.latestGeneratedNodes.textContent = "暂无";
    return;
  }
  elements.latestGeneratedNodes.innerHTML = latestNodes
    .map(
      (node) => `
        <div class="selected-chip">
          <strong>${escapeHtml(node.id)}</strong> | G${node.generation ?? "-"} | 原始评估分 ${formatNumber(rawScoreForNode(node), 5)}
          <div class="chip-meta">来源: ${escapeHtml(node.sourceLabel || "-")} | 最新一次运行 | 操作符: ${escapeHtml(node.operator || "-")}</div>
          <div class="chip-summary">${escapeHtml(summarizeText(displayAlgorithmText(node, "暂无算法摘要"), "暂无算法摘要", 100))}</div>
          <div class="chip-actions">
            <button class="secondary chip-button" data-action="focus-node" data-node-id="${escapeHtml(node.id)}">定位</button>
            <button class="secondary chip-button" data-action="toggle-candidate" data-node-id="${escapeHtml(node.id)}">${state.candidateNodeIds.has(node.id) ? "移出参考解" : "加入参考解"}</button>
            <button class="secondary chip-button" data-action="toggle-initial-population" data-node-id="${escapeHtml(node.id)}">${state.initialPopulationNodeIds.has(node.id) ? "移出种群" : "加入种群"}</button>
            <button class="secondary chip-button" data-action="toggle-favorite" data-node-id="${escapeHtml(node.id)}">${state.favoriteNodeIds.has(node.id) ? "取消收藏" : "收藏"}</button>
          </div>
        </div>
      `,
    )
    .join("");
}

function renderSelectedNodes() {
  const selectedNodes = [...state.selectedNodeIds]
    .map((id) => mergeNodeDetails(nodeById(id)))
    .filter(Boolean)
    .sort((a, b) => a.sampleOrder - b.sampleOrder);

  elements.selectedCount.textContent = String(selectedNodes.length);

  if (!selectedNodes.length) {
    elements.selectedNodes.textContent = "暂无";
    elements.nodeDetails.innerHTML = `<div class="empty-state">点击或框选节点后，这里会显示算法说明、父节点信息和函数预览。</div>`;
    syncGraphViewControls();
    return;
  }

  elements.selectedNodes.innerHTML = selectedNodes
    .map(
      (node) => `
        <div class="selected-chip">
          <strong>${escapeHtml(node.id)}</strong> | ${node.isClusterSummary ? `区域 ${escapeHtml(String(node.clusterSampleCount || 0))} 个解` : `样本 ${node.sampleOrder}`} | 原始评估分 ${formatNumber(rawScoreForNode(node), 5)}
          <div class="chip-meta">来源: ${escapeHtml(node.sourceLabel || "-")} | ${node.isClusterSummary ? `历史 ${node.clusterSourceCount || 0} / 本轮 ${node.clusterCurrentCount || 0}` : `轮次: G${node.generation ?? "-"}${node.isLatestRun ? " / 最新一次运行" : node.isLatestRound ? " / 最新一代" : ""} | OFEC fitness: ${formatNumber(ofecFitnessForNode(node), 5)}`} | 操作符: ${escapeHtml(node.operator || "-")} | 父节点: ${node.ofecParentIndex ?? "-"}</div>
          <div class="chip-summary">${escapeHtml(summarizeText(displayAlgorithmText(node, "暂无算法摘要"), "暂无算法摘要", 110))}</div>
          <div class="chip-actions">
            ${node.isClientCluster
              ? `<button class="secondary chip-button" data-action="open-client-cluster" data-node-id="${escapeHtml(node.id)}">查看原节点</button>`
              : node.isClusterSummary
                ? `<button class="secondary chip-button" data-action="expand-cluster" data-cluster-id="${escapeHtml(node.clusterId || node.id)}">展开区域</button>`
                : ""}
            ${!node.isClusterSummary
              ? `<button class="secondary chip-button" data-action="toggle-candidate" data-node-id="${escapeHtml(node.id)}">${state.candidateNodeIds.has(node.id) ? "移出参考解" : "加入参考解"}</button>`
              : ""}
            ${!node.isClusterSummary
              ? `<button class="secondary chip-button" data-action="toggle-initial-population" data-node-id="${escapeHtml(node.id)}">${state.initialPopulationNodeIds.has(node.id) ? "移出种群" : "加入种群"}</button>`
              : ""}
            <button class="secondary chip-button" data-action="toggle-favorite" data-node-id="${escapeHtml(node.id)}">${state.favoriteNodeIds.has(node.id) ? "取消收藏" : "收藏"}</button>
          </div>
        </div>
      `,
    )
    .join("");

  elements.nodeDetails.innerHTML = selectedNodes
    .map(
      (node) => `
        <article class="node-detail-card">
          <div class="node-detail-head">
            <strong>${escapeHtml(node.id)}</strong>
            <span class="node-score">原始评估分 ${formatNumber(rawScoreForNode(node), 5)}</span>
          </div>
          <div class="node-detail-grid">
            <div class="detail-item">
              <span>样本序号</span>
              <strong>${node.isClusterSummary ? "-" : node.sampleOrder ?? "-"}</strong>
            </div>
            <div class="detail-item">
              <span>操作符</span>
              <strong>${escapeHtml(node.operator || "-")}</strong>
            </div>
            <div class="detail-item">
              <span>节点来源</span>
              <strong>${escapeHtml(node.sourceLabel || "-")}</strong>
            </div>
            <div class="detail-item">
              <span>轮次</span>
              <strong>${node.isClusterSummary ? `区域内最新 ${node.clusterLatestCount || 0}` : `G${node.generation ?? "-"}`}</strong>
            </div>
            <div class="detail-item">
              <span>OFEC fitness</span>
              <strong>${formatNumber(ofecFitnessForNode(node), 5)}</strong>
            </div>
            <div class="detail-item">
              <span>父节点</span>
              <strong>${node.isClusterSummary ? "-" : node.ofecParentIndex ?? "-"}</strong>
            </div>
            <div class="detail-item">
              <span>原始评估分</span>
              <strong>${formatNumber(rawScoreForNode(node), 5)}</strong>
            </div>
            <div class="detail-item">
              <span>父节点距离</span>
              <strong>${node.isClusterSummary ? "-" : formatNumber(node.distanceToParent, 6)}</strong>
            </div>
            <div class="detail-item">
              <span>区域样本数</span>
              <strong>${node.isClusterSummary ? (node.clusterSampleCount || 0) : "-"}</strong>
            </div>
            <div class="detail-item">
              <span>区域来源</span>
              <strong>${node.isClusterSummary ? `历史 ${node.clusterSourceCount || 0} / 本轮 ${node.clusterCurrentCount || 0}` : "-"}</strong>
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-section-title">算法说明</div>
            <p>${escapeHtml(summarizeText(displayAlgorithmText(node, "暂无算法说明"), "暂无算法说明", 800))}</p>
          </div>
          <div class="chip-actions">
            ${node.isClientCluster
              ? `<button class="secondary chip-button" data-action="open-client-cluster" data-node-id="${escapeHtml(node.id)}">查看原节点</button>`
              : node.isClusterSummary
                ? `<button class="secondary chip-button" data-action="expand-cluster" data-cluster-id="${escapeHtml(node.clusterId || node.id)}">展开区域</button>`
                : ""}
            ${!node.isClusterSummary
              ? `<button class="secondary chip-button" data-action="toggle-candidate" data-node-id="${escapeHtml(node.id)}">${state.candidateNodeIds.has(node.id) ? "移出参考解" : "加入参考解"}</button>`
              : ""}
            ${!node.isClusterSummary
              ? `<button class="secondary chip-button" data-action="toggle-initial-population" data-node-id="${escapeHtml(node.id)}">${state.initialPopulationNodeIds.has(node.id) ? "移出种群" : "加入种群"}</button>`
              : ""}
            <button class="secondary chip-button" data-action="toggle-favorite" data-node-id="${escapeHtml(node.id)}">${state.favoriteNodeIds.has(node.id) ? "取消收藏" : "收藏节点"}</button>
          </div>
          <div class="detail-section">
            <div class="detail-section-title">${node.isClusterSummary ? "代表函数预览" : "函数预览"}</div>
            <pre>${escapeHtml(node.functionPreview || (node.hasDetailPayload ? "正在加载函数预览..." : "暂无函数预览"))}</pre>
          </div>
        </article>
      `,
    )
    .join("");

  void ensureNodeDetails(selectedNodes);
  void ensureAlgorithmTranslations(selectedNodes);
  renderFavoriteNodes();
  renderCandidateNodes();
  renderInitialPopulationNodes();
  renderLatestGeneratedNodes();
  syncGraphViewControls();
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function updateSelection(ids, additive = false) {
  if (!additive) {
    state.selectedNodeIds.clear();
  }
  ids.forEach((id) => state.selectedNodeIds.add(id));
  refreshNodeColors();
  renderSelectedNodes();
  syncGraphViewControls();
}

function toggleFavorite(nodeId) {
  if (!nodeId) {
    return;
  }
  if (state.favoriteNodeIds.has(nodeId)) {
    state.favoriteNodeIds.delete(nodeId);
  } else {
    state.favoriteNodeIds.add(nodeId);
  }
  saveFavoriteIds();
  refreshNodeColors();
  renderSelectedNodes();
  renderFavoriteNodes();
  renderLatestGeneratedNodes();
}

function toggleCandidate(nodeId) {
  const node = nodeById(nodeId);
  if (!node || node.isClusterSummary) {
    return;
  }
  if (state.candidateNodeIds.has(nodeId)) {
    state.candidateNodeIds.delete(nodeId);
  } else {
    state.candidateNodeIds.add(nodeId);
  }
  renderCandidateNodes();
  renderSelectedNodes();
  renderFavoriteNodes();
  renderLatestGeneratedNodes();
}

function toggleInitialPopulation(nodeId) {
  const node = nodeById(nodeId);
  if (!node || node.isClusterSummary) {
    return;
  }
  if (state.initialPopulationNodeIds.has(nodeId)) {
    state.initialPopulationNodeIds.delete(nodeId);
  } else {
    state.initialPopulationNodeIds.add(nodeId);
  }
  renderInitialPopulationNodes();
  renderSelectedNodes();
  renderFavoriteNodes();
  renderLatestGeneratedNodes();
}

function focusNode(nodeId) {
  const node = nodeById(nodeId);
  if (!nodeId || !node) {
    return;
  }
  if (!state.nodeMap.has(nodeId)) {
    state.graphAbstractionMode = "full";
    state.openedClientClusterId = null;
    state.highScorePercent = 100;
    elements.graphAbstractionMode.value = "full";
    elements.highScorePercent.value = "100";
    syncHighScoreLabel();
    syncClusterGroupLabel();
    renderActiveGraph(true);
  }
  updateSelection([nodeId]);
  const position = state.nodeVisualPositions.get(nodeId);
  if (!position) {
    return;
  }
  controls.target.copy(position);
}

function resetDerivedGraphView() {
  state.openedClientClusterId = null;
  state.highScorePercent = 100;
  elements.highScorePercent.value = "100";
  syncHighScoreLabel();
  renderActiveGraph(true);
}

function handleNodeActionClick(event) {
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) {
    return;
  }
  const nodeId = actionButton.dataset.nodeId;
  if (actionButton.dataset.action === "toggle-favorite") {
    toggleFavorite(nodeId);
  } else if (actionButton.dataset.action === "toggle-candidate") {
    toggleCandidate(nodeId);
  } else if (actionButton.dataset.action === "toggle-initial-population") {
    toggleInitialPopulation(nodeId);
  } else if (actionButton.dataset.action === "focus-node") {
    focusNode(nodeId);
  } else if (actionButton.dataset.action === "open-client-cluster") {
    openClientCluster(nodeId);
  } else if (actionButton.dataset.action === "expand-cluster") {
    void openClusterView(actionButton.dataset.clusterId);
  }
}

async function openClusterView(clusterId) {
  if (!state.viewRunId || !clusterId) {
    return;
  }
  state.expandedClusterId = clusterId;
  syncSummaryViewButton();
  setWaitingGraphMessage(`正在展开区域 ${clusterId} 的局部 NBN...`);
  await refreshGraph(state.viewRunId);
}

async function openSummaryView() {
  state.expandedClusterId = null;
  syncSummaryViewButton();
  if (!state.viewRunId) {
    updateGraphMeta();
    return;
  }
  setWaitingGraphMessage("正在返回完整图...");
  await refreshGraph(state.viewRunId);
}

function pickNode(event) {
  normalizePointer(event);
  raycaster.setFromCamera(pointer, camera);
  
  let hits = [];
  if (state.nodeRenderMode === "points" && state.nodePoints) {
    hits = raycaster.intersectObject(state.nodePoints);
  } else if (state.nodeInstancedMesh) {
    hits = raycaster.intersectObject(state.nodeInstancedMesh);
  } else {
    hits = raycaster.intersectObjects(state.nodeMeshes);
  }

  const fallbackNode = nearestPointNode(event);
  if (!hits.length && !fallbackNode) {
    if (!event.ctrlKey) {
      updateSelection([]);
    }
    return;
  }

  let node = null;
  if (state.nodeRenderMode === "points" && state.nodePoints) {
    node = fallbackNode || state.graph.nodes[hits[0]?.index];
  } else if (state.nodeInstancedMesh) {
    const instanceId = hits[0]?.instanceId;
    if (instanceId != null) {
      node = state.graph.nodes[instanceId];
    } else {
      node = fallbackNode;
    }
  } else {
    node = hits[0]?.object?.userData?.node || null;
  }

  if (!node) return;

  if (event.ctrlKey) {
    if (state.selectedNodeIds.has(node.id)) {
      state.selectedNodeIds.delete(node.id);
      refreshNodeColors();
      renderSelectedNodes();
      return;
    }
    updateSelection([node.id], true);
    return;
  }
  updateSelection([node.id]);
}

function pointerInGraph(event) {
  const rect = elements.graphContainer.getBoundingClientRect();
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  return {
    rect,
    x: clamp(event.clientX - rect.left, 0, rect.width),
    y: clamp(event.clientY - rect.top, 0, rect.height),
  };
}

function screenPositionOfNodeId(nodeId) {
  graphGroup.updateMatrixWorld(true);
  const vector = state.nodeVisualPositions.get(nodeId)?.clone();
  if (!vector) {
    return null;
  }
  vector.project(camera);
  const rect = renderer.domElement.getBoundingClientRect();
  return {
    x: ((vector.x + 1) / 2) * rect.width,
    y: ((-vector.y + 1) / 2) * rect.height,
  };
}

function nearestPointNode(event) {
  if (state.nodeRenderMode === "mesh" || !state.graph.nodes.length) {
    return null;
  }
  const target = pointerInGraph(event);
  graphGroup.updateMatrixWorld(true);
  const rect = renderer.domElement.getBoundingClientRect();
  const searchRadius = Math.max(16, 12 + state.nodeSizeScale * 8);
  let bestNode = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  state.graph.nodes.forEach((node) => {
    const vector = state.nodeVisualPositions.get(node.id)?.clone();
    if (!vector) {
      return;
    }
    vector.project(camera);
    if (vector.z < -1 || vector.z > 1) {
      return;
    }
    const x = ((vector.x + 1) / 2) * rect.width;
    const y = ((-vector.y + 1) / 2) * rect.height;
    const distance = Math.hypot(x - target.x, y - target.y);
    if (distance <= searchRadius && distance < bestDistance) {
      bestDistance = distance;
      bestNode = node;
    }
  });
  return bestNode;
}

function beginSelection(event) {
  if (!elements.boxSelectMode.checked || event.button !== 0) {
    return;
  }
  const { x, y } = pointerInGraph(event);
  state.isDraggingSelection = true;
  state.dragStart = { x, y };
  syncControlState();
  elements.selectionRect.style.display = "block";
  elements.selectionRect.style.left = `${state.dragStart.x}px`;
  elements.selectionRect.style.top = `${state.dragStart.y}px`;
  elements.selectionRect.style.width = "0px";
  elements.selectionRect.style.height = "0px";
  event.preventDefault();
}

function moveSelection(event) {
  if (!state.isDraggingSelection || !state.dragStart) {
    return;
  }
  const current = pointerInGraph(event);
  const left = Math.min(state.dragStart.x, current.x);
  const top = Math.min(state.dragStart.y, current.y);
  const width = Math.abs(state.dragStart.x - current.x);
  const height = Math.abs(state.dragStart.y - current.y);
  elements.selectionRect.style.left = `${left}px`;
  elements.selectionRect.style.top = `${top}px`;
  elements.selectionRect.style.width = `${width}px`;
  elements.selectionRect.style.height = `${height}px`;
}

function endSelection(event) {
  if (!state.isDraggingSelection || !state.dragStart) {
    return;
  }
  const end = pointerInGraph(event);
  const left = Math.min(state.dragStart.x, end.x);
  const right = Math.max(state.dragStart.x, end.x);
  const top = Math.min(state.dragStart.y, end.y);
  const bottom = Math.max(state.dragStart.y, end.y);

  const selectedIds = state.graph.nodes
    .filter((node) => {
      const position = screenPositionOfNodeId(node.id);
      return position && position.x >= left && position.x <= right && position.y >= top && position.y <= bottom;
    })
    .map((node) => node.id);

  updateSelection(selectedIds, event.ctrlKey);

  state.isDraggingSelection = false;
  state.dragStart = null;
  syncControlState();
  elements.selectionRect.style.display = "none";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`请求失败 (${response.status}): ${url} 未返回有效 JSON，请查看服务日志。`);
  }
  if (!response.ok) {
    throw new Error(payload.error || `请求失败: ${response.status}`);
  }
  return payload;
}

function buildApiUrl(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value == null || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });
  return url.pathname + url.search;
}

function llmPayload() {
  return {
    host: elements.host.value,
    key: elements.key.value,
    model: elements.model.value,
    timeout: 60,
  };
}

function nodesPayloadFromIds(ids, lookupMap = state.nodeMap) {
  return [...ids]
    .map((id) => mergeNodeDetails(lookupMap.get(id)))
    .filter(Boolean)
    .filter((node) => !node.isClusterSummary)
    .map((node) => ({
      id: node.id,
      sampleOrder: node.sampleOrder,
      score: node.score,
      rawScore: rawScoreForNode(node),
      ofecFitness: ofecFitnessForNode(node),
      algorithm: node.algorithm,
      algorithmSummary: node.algorithmSummary,
      operator: node.operator,
      functionPreview: node.functionPreview,
      sourceRunId: node.sourceRunId,
      sourceKind: node.sourceKind,
    }));
}

function selectedNodesPayload() {
  return nodesPayloadFromIds(state.selectedNodeIds, state.nodeMap);
}

function candidateNodesPayload() {
  return nodesPayloadFromIds(state.candidateNodeIds, state.fullNodeMap);
}

async function selectedNodesPayloadAsync() {
  await ensureNodeDetails([...state.selectedNodeIds].map((id) => state.nodeMap.get(id)).filter(Boolean));
  return selectedNodesPayload();
}

function renderRunHistory() {
  if (!Array.isArray(state.saves) || !state.saves.length) {
    elements.runHistoryList.innerHTML = `<div class="empty-state">暂无存档。</div>`;
    return;
  }

  elements.runHistoryList.innerHTML = state.saves
    .map((save) => {
      const isActiveView = save.saveId === state.viewSaveId;
      const bestScore = save.bestScore == null ? "-" : Number(save.bestScore).toFixed(5);
      const sampleCount = save.sampleCount ?? "-";
      const graphCount = save.graphArtifactCount ?? 0;
      const modeLabel = save.currentRunId ? (save.mode || "run") : "空白";
      const statusLabel = save.currentRunId
        ? (save.isRunning ? `${statusText(save.status)} / 当前运行` : statusText(save.status))
        : "未开始";
      const updatedAt = save.updatedAt || "-";
      return `
        <div class="run-history-item ${isActiveView ? "active" : ""}" data-save-id="${escapeHtml(save.saveId)}">
          <div class="run-history-top">
            <strong class="run-history-title">${escapeHtml(save.name || save.saveId)}</strong>
            <div class="run-history-inline-actions">
              <span class="run-history-badge">${escapeHtml(modeLabel)}</span>
              <button class="secondary compact-button run-history-delete-button" data-action="delete-save" data-save-id="${escapeHtml(save.saveId)}">删除</button>
            </div>
          </div>
          <div class="run-history-meta">
            状态: ${escapeHtml(statusLabel)}<br>
            样本: ${escapeHtml(String(sampleCount))} / 最优分: ${escapeHtml(String(bestScore))}<br>
            图缓存: ${escapeHtml(String(graphCount))} / 更新时间: ${escapeHtml(updatedAt)}
          </div>
        </div>
      `;
    })
    .join("");
}

function savesPayloadSignature(payload) {
  const saves = Array.isArray(payload?.saves) ? payload.saves : [];
  return JSON.stringify({
    activeSaveId: payload?.activeSaveId || null,
    saves: saves.map((save) => ({
      saveId: save.saveId || "",
      currentRunId: save.currentRunId || null,
      status: save.status || "",
      sampleCount: save.sampleCount ?? null,
      bestScore: save.bestScore ?? null,
      graphArtifactCount: save.graphArtifactCount ?? null,
      updatedAt: save.updatedAt || "",
      isRunning: Boolean(save.isRunning),
    })),
  });
}

function applySavesPayload(payload) {
  state.saves = Array.isArray(payload?.saves) ? payload.saves : [];
  state.activeSaveId = payload?.activeSaveId || null;
  if (state.viewSaveId) {
    const viewedSave = state.saves.find((save) => save.saveId === state.viewSaveId) || null;
    state.viewRunId = viewedSave?.currentRunId || null;
  }
  const signature = savesPayloadSignature(payload);
  const changed = signature !== state.lastSavesSignature;
  state.lastSavesSignature = signature;
  state.lastSavesRefreshAt = Date.now();
  if (changed) {
    renderRunHistory();
  }
  return changed;
}

function nextSavesRefreshDelayMs(status = state.currentStatus) {
  if (status === "running") {
    return 10000;
  }
  if (status === "building_graph") {
    return 8000;
  }
  if (state.viewRunId) {
    return 12000;
  }
  return 5000;
}

function shouldRefreshRuns(force = false, status = state.currentStatus) {
  if (force) {
    return true;
  }
  return (Date.now() - state.lastSavesRefreshAt) >= nextSavesRefreshDelayMs(status);
}

async function refreshRuns(options = {}) {
  const force = Boolean(options?.force);
  const status = options?.status || state.currentStatus;
  if (!shouldRefreshRuns(force, status)) {
    return false;
  }
  const payload = await fetchJson("/api/saves");
  applySavesPayload(payload);
  return true;
}

async function refreshRunsSafe(options = {}) {
  try {
    await refreshRuns(options);
    return true;
  } catch (_) {
    return false;
  }
}

async function viewRun(saveId) {
  state.selectedNodeIds.clear();
  state.expandedClusterId = null;
  state.viewSaveId = saveId || null;
  await fetchJson("/api/saves/activate", {
    method: "POST",
    body: JSON.stringify({ save_id: saveId }),
  });
  await refreshRunsSafe({ force: true });
  if (state.viewRunId) {
    await refreshStatus(state.viewRunId);
    await refreshGraph(state.viewRunId);
  } else {
    showNoRunSelectedState();
  }
}

async function startDirectAiRun(referenceNodes = null) {
  if (!referenceNodes) {
    referenceNodes = state.selectedNodeIds.size ? await selectedNodesPayloadAsync() : selectedNodesPayload();
  }
  const payload = {
    mode: "direct_ai",
    prompt: elements.directAiPrompt.value,
    reference_nodes: referenceNodes,
    selected_nodes: referenceNodes,
    save_id: state.activeSaveId,
    llm: llmPayload(),
    method: {
      max_sample_nums: normalizePositiveInt(elements.directAiMaxSampleNums.value, 10, 1),
      max_generations: 1,
      pop_size: normalizePositiveInt(elements.directAiPopSize.value, 5, 1),
      num_samplers: 1,
      num_evaluators: 1,
      timeout_seconds: 120,
      distance_metric: elements.distanceMetric.value,
    },
  };
  const result = await fetchJson("/api/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedNodeIds.clear();
  state.expandedClusterId = null;
  state.activeRunId = result.runId || null;
  state.activeSaveId = result.saveId || state.activeSaveId;
  state.viewSaveId = result.saveId || state.viewSaveId;
  state.viewRunId = result.runId || null;
  await refreshRunsSafe({ force: true });
  await refreshStatus(state.viewRunId);
  await refreshGraph(state.viewRunId);
}

async function startSeededEohRun(initialPopulationNodes = null) {
  if (!initialPopulationNodes) {
    initialPopulationNodes = state.selectedNodeIds.size ? await selectedNodesPayloadAsync() : selectedNodesPayload();
  }
  const payload = {
    mode: "seeded_eoh",
    prompt: elements.seededEohPrompt.value,
    initial_population_nodes: initialPopulationNodes,
    selected_nodes: initialPopulationNodes,
    save_id: state.activeSaveId,
    llm: llmPayload(),
    method: {
      max_sample_nums: normalizePositiveInt(elements.seededEohPopSize.value, 8, 2) * normalizePositiveInt(elements.seededEohMaxGenerations.value, 8, 1),
      max_generations: normalizePositiveInt(elements.seededEohMaxGenerations.value, 8, 1),
      pop_size: normalizePositiveInt(elements.seededEohPopSize.value, 8, 2),
      num_samplers: normalizePositiveInt(elements.seededEohNumSamplers.value, 4, 1),
      num_evaluators: normalizePositiveInt(elements.seededEohNumEvaluators.value, 4, 1),
      timeout_seconds: 120,
      distance_metric: elements.distanceMetric.value,
    },
  };
  const result = await fetchJson("/api/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedNodeIds.clear();
  state.expandedClusterId = null;
  state.activeRunId = result.runId || null;
  state.activeSaveId = result.saveId || state.activeSaveId;
  state.viewSaveId = result.saveId || state.viewSaveId;
  state.viewRunId = result.runId || null;
  await refreshRunsSafe({ force: true });
  await refreshStatus(state.viewRunId);
  await refreshGraph(state.viewRunId);
}

async function startRunWithCandidates() {
  await ensureNodeDetails([...state.candidateNodeIds].map((id) => state.fullNodeMap.get(id)).filter(Boolean));
  const candidates = candidateNodesPayload();
  if (!candidates.length) {
    window.alert("请先把节点加入 AI 参考解区。");
    return;
  }
  await startDirectAiRun(candidates);
}

async function startRunWithInitialPopulation() {
  await ensureNodeDetails([...state.initialPopulationNodeIds].map((id) => state.fullNodeMap.get(id)).filter(Boolean));
  const nodes = nodesPayloadFromIds(state.initialPopulationNodeIds, state.fullNodeMap);
  if (!nodes.length) {
    window.alert("请先把节点加入初始种群区。");
    return;
  }
  await startSeededEohRun(nodes);
}

async function startRunWithUserFeedback(kind) {
  try {
    if (kind === "candidates") {
      await startRunWithCandidates();
      return;
    }
    if (kind === "initial_population") {
      await startRunWithInitialPopulation();
      return;
    }
  } catch (error) {
    const message = error?.message || "启动运行失败。";
    elements.llmTestResult.textContent = `启动失败\n${message}`;
    window.alert(message);
  }
}

async function importHistorySamples() {
  elements.importHistoryButton.disabled = true;
  setWaitingGraphMessage("正在导入固定目录历史样本...");
  try {
    const defaults = await fetchJson("/api/defaults");
    const source = defaults?.historyImport?.defaultSource || "circle_packing_history";
    const result = await fetchJson("/api/import-history", {
      method: "POST",
      body: JSON.stringify({
        source,
        save_id: state.activeSaveId,
        method: {
          distance_metric: elements.distanceMetric.value,
        },
      }),
    });
    state.selectedNodeIds.clear();
    state.expandedClusterId = null;
    state.activeRunId = result.runId || null;
    state.activeSaveId = result.saveId || state.activeSaveId;
    state.viewSaveId = result.saveId || state.viewSaveId;
    state.viewRunId = result.runId || null;
    await refreshRunsSafe({ force: true });
    await refreshStatus(state.viewRunId);
    setWaitingGraphMessage("历史样本已导入，正在生成完整 NBN 图...");
    await refreshGraph(state.viewRunId);
  } catch (error) {
    const message = `导入历史样本失败：${error.message || error}`;
    setWaitingGraphMessage(message);
    window.alert(message);
  } finally {
    elements.importHistoryButton.disabled = false;
  }
}

async function injectExternalExpertSolution() {
  const functionText = String(elements.externalExpertFunction.value || "").trim();
  if (!functionText) {
    window.alert("请先粘贴一个可评估的 `pack_circles` 函数。");
    return;
  }
  elements.injectExpertSolutionButton.disabled = true;
  setWaitingGraphMessage("正在评估并注入外部专家解...");
  try {
    const result = await fetchJson("/api/expert-solution", {
      method: "POST",
      body: JSON.stringify({
        save_id: state.activeSaveId,
        title: elements.externalExpertTitle.value,
        description: elements.externalExpertDescription.value,
        function_text: elements.externalExpertFunction.value,
        method: {
          distance_metric: elements.distanceMetric.value,
        },
      }),
    });
    state.selectedNodeIds.clear();
    state.expandedClusterId = null;
    state.activeRunId = result.runId || null;
    state.activeSaveId = result.saveId || state.activeSaveId;
    state.viewSaveId = result.saveId || state.viewSaveId;
    state.viewRunId = result.runId || null;
    state.pendingFocusNodeId = result.nodeId || null;
    await refreshRunsSafe({ force: true });
    await refreshStatus(state.viewRunId);
    setWaitingGraphMessage("外部专家解已入图，正在刷新当前图...");
    await refreshGraph(state.viewRunId);
    const scoreLabel = result.acceptedAsWorst
      ? "该解未通过有效评估，已按最差解放到底层"
      : `评估分数 ${formatNumber(result.score, 5)}`;
    window.alert(`外部专家解已注入当前图，${scoreLabel}。`);
    elements.externalExpertFunction.value = "";
  } catch (error) {
    window.alert(error.message || "注入外部专家解失败。");
  } finally {
    elements.injectExpertSolutionButton.disabled = false;
  }
}

async function createSave() {
  const name = window.prompt("输入存档名称（可留空自动命名）:", "");
  if (name == null) {
    return;
  }
  const result = await fetchJson("/api/saves", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  applySavesPayload(result);
  state.viewSaveId = result.save?.saveId || state.viewSaveId;
  state.viewRunId = null;
  showNoRunSelectedState();
}

async function deleteSave(saveId) {
  if (!saveId) {
    return;
  }
  const save = state.saves.find((item) => item.saveId === saveId);
  const label = save?.name || saveId;
  const confirmed = window.confirm(`确认删除存档“${label}”？`);
  if (!confirmed) {
    return;
  }
  try {
    const result = await fetchJson("/api/saves/delete", {
      method: "POST",
      body: JSON.stringify({ save_id: saveId }),
    });
    applySavesPayload(result);
    if (state.viewSaveId === saveId) {
      state.viewSaveId = null;
      state.viewRunId = null;
    } else if (state.viewSaveId) {
      const viewedSave = state.saves.find((item) => item.saveId === state.viewSaveId) || null;
      state.viewRunId = viewedSave?.currentRunId || null;
    }
    state.expandedClusterId = null;
    if (state.viewRunId) {
      await refreshStatus(state.viewRunId);
      await refreshGraph(state.viewRunId);
    } else {
      showNoRunSelectedState();
    }
    renderRunHistory();
  } catch (error) {
    window.alert(error.message || "删除存档失败。");
  }
}

async function testLlmConnection() {
  elements.testLlmButton.disabled = true;
  elements.llmTestResult.textContent = "正在测试连接...";
  try {
    const result = await fetchJson("/api/test-llm", {
      method: "POST",
      body: JSON.stringify({ llm: llmPayload() }),
    });
    if (!result.ok) {
      elements.llmTestResult.textContent = `连接失败\n${result.error || "未知错误"}`;
      return;
    }

    const modelLine = result.requestedModel === result.actualModel
      ? result.actualModel
      : `${result.requestedModel} -> ${result.actualModel}`;
    const keySourceMap = {
      form: "表单输入",
      env: "环境变量",
      code_default: "代码默认值",
      missing: "未找到",
    };
    elements.llmTestResult.textContent = [
      "连接成功",
      `模型: ${modelLine}`,
      `地址: ${result.baseUrl || "-"}`,
      `Key 来源: ${keySourceMap[result.keySource] || result.keySource}`,
      `超时: ${result.timeoutSeconds}s`,
      `响应预览: ${result.responsePreview || "-"}`,
    ].join("\n");
  } catch (error) {
    elements.llmTestResult.textContent = `连接失败\n${error.message}`;
  } finally {
    elements.testLlmButton.disabled = false;
  }
}

async function stopRun() {
  await fetchJson("/api/stop", { method: "POST" });
  await refreshRunsSafe({ force: true });
  await refreshStatus(state.viewRunId);
}

async function refreshStatus(runId = state.viewRunId) {
  if (!runId) {
    state.currentStatus = "idle";
    state.lastRunSnapshot = null;
    elements.statusText.textContent = "idle";
    elements.sampleCount.textContent = "0";
    elements.bestScore.textContent = "-";
    elements.bestSample.textContent = "-";
    elements.embeddingProgress.textContent = "-";
    elements.currentPhase.textContent = "-";
    elements.runProgress.textContent = "-";
    elements.runnerTiming.textContent = "-";
    elements.currentPrompt.textContent = "-";
    elements.currentMode.textContent = "-";
    updateGraphMeta();
    return null;
  }
  const status = await fetchJson(buildApiUrl("/api/status", { run_id: runId }));
  state.activeRunId = status.activeRunId || null;
  state.viewRunId = status.runId || state.viewRunId;
  state.currentStatus = status.status || "idle";
  state.lastStatusSampleCount = Number(status?.metrics?.sample_count || 0);
  state.lastStatusPerf = status?.perf || null;
  state.lastPerfRolling = status?.perf?.rolling || state.lastPerfRolling;
  state.lastRunSnapshot = status?.snapshot || null;
  elements.statusText.textContent = statusText(status.status);
  elements.sampleCount.textContent = status.metrics.sample_count;
  elements.bestScore.textContent = status.metrics.best_score == null ? "-" : status.metrics.best_score.toFixed(5);
  elements.bestSample.textContent = status.metrics.best_sample_order ?? "-";
  elements.currentPhase.textContent = formatRunPhase(state.lastRunSnapshot, status);
  elements.runProgress.textContent = formatRunProgress(state.lastRunSnapshot);
  elements.runnerTiming.textContent = formatRunnerTiming(state.lastRunSnapshot, status?.perf || null);
  elements.currentPrompt.textContent = status.prompt || "-";
  elements.currentMode.textContent = modeText(status.mode);
  if (status.graphStatus === "pending" && !status.error) {
    setWaitingGraphMessage("样本已就绪，正在生成完整 NBN 图...");
  }
  if (status.error) {
    elements.graphMeta.textContent = `运行失败: ${status.error}`;
  }
  if (!state.selectedNodeIds.size && Array.isArray(status.selectedNodes) && status.selectedNodes.length) {
    updateSelection(status.selectedNodes.map((node) => node.id));
  }
  await refreshEmbeddingProgress(runId, status);
  return status;
}

async function refreshEmbeddingProgress(runId = state.viewRunId, status = null) {
  if (!runId) {
    elements.embeddingProgress.textContent = "-";
    return null;
  }
  try {
    const payload = await fetchJson(buildApiUrl("/api/embedding-progress", { run_id: runId }));
    if (!payload.enabled) {
      elements.embeddingProgress.textContent = payload.message || "不适用";
      return payload;
    }
    const total = Number(payload.totalSamples || 0);
    const cached = Number(payload.cachedSamples || 0);
    const phaseMap = {
      embedding: "编码中",
      nbn: "构图中",
      ready: "已完成",
      idle: "未开始",
    };
    const phaseLabel = phaseMap[payload.phase] || payload.phase || "-";
    elements.embeddingProgress.textContent = `${cached}/${total} (${phaseLabel})`;
    if ((status?.status === "building_graph" || payload.phase === "embedding" || payload.phase === "nbn") && total > 0) {
      setWaitingGraphMessage(`正在生成完整 NBN 图... embedding ${cached}/${total}，阶段：${phaseLabel}`);
    }
    return payload;
  } catch (_) {
    elements.embeddingProgress.textContent = "读取失败";
    return null;
  }
}

function statusText(status) {
  const map = {
    idle: "空闲",
    running: "运行中",
    building_graph: "生成图中",
    finished: "已完成",
    stopped: "已停止",
    failed: "失败",
  };
  return map[status] || String(status || "-");
}

function modeText(mode) {
  const map = {
    direct_ai: "AI 直接生成",
    seeded_eoh: "指定初始种群运行 EOH",
    history_import: "导入历史样本",
    external_expert: "外部专家解注入",
  };
  return map[mode] || String(mode || "-");
}

function shouldRefreshGraphForStatus(status) {
  if (!status?.runId) {
    return false;
  }
  const now = Date.now();
  const sampleCount = Number(status?.metrics?.sample_count || 0);
  if (!state.graphSignature || state.fullGraph?.runId !== status.runId) {
    return true;
  }
  if (status.status !== state.lastGraphStatus) {
    return true;
  }
  if (status.status === "running") {
    return sampleCount !== state.lastGraphSampleCount && (now - state.lastGraphRefreshAt) >= 6000;
  }
  if (status.status === "building_graph") {
    return (now - state.lastGraphRefreshAt) >= 4000;
  }
  return false;
}

function nextPollDelayMs(status) {
  if (status?.status === "building_graph") {
    return 4000;
  }
  if (status?.status === "running") {
    return 3000;
  }
  return 2000;
}

const graphWorker = new Worker("/static/graphWorker.js");
let graphWorkerMsgId = 0;

function fetchGraphDataAsync(url) {
  return new Promise((resolve, reject) => {
    const id = ++graphWorkerMsgId;
    const handler = (event) => {
      const { type, payload, id: msgId } = event.data;
      if (msgId === id) {
        graphWorker.removeEventListener("message", handler);
        if (type === "FETCH_GRAPH_SUCCESS") {
          resolve(payload);
        } else if (type === "FETCH_GRAPH_ERROR") {
          reject(new Error(payload));
        }
      }
    };
    graphWorker.addEventListener("message", handler);
    graphWorker.postMessage({ type: "FETCH_GRAPH", id, payload: { url } });
  });
}

async function refreshGraph(runId = state.viewRunId) {
  if (!runId) {
    showNoRunSelectedState();
    return;
  }
  const previousRunId = state.fullGraph?.runId || null;
  const url = buildApiUrl("/api/graph", { run_id: runId, cluster_id: state.expandedClusterId || undefined });
  const graph = await fetchGraphDataAsync(url);
  state.fullGraph = graph;
  if (previousRunId !== graph?.runId) {
    state.nodeDetailCache.clear();
    state.nodeDetailPending.clear();
  }
  state.lastGraphPerf = graph?.perf || null;
  state.lastPerfRolling = graph?.perf?.rolling || state.lastPerfRolling;
  state.fullNodeMap = new Map((graph.nodes || []).map((node) => [node.id, node]));
  state.candidateNodeIds = new Set([...state.candidateNodeIds].filter((id) => state.fullNodeMap.has(id)));
  state.initialPopulationNodeIds = new Set([...state.initialPopulationNodeIds].filter((id) => state.fullNodeMap.has(id)));
  state.clusterGraphCacheKey = null;
  state.clusterGraphCache = null;
  state.lastGraphRefreshAt = Date.now();
  state.lastGraphSampleCount = Number(state.lastStatusSampleCount || 0);
  state.lastGraphStatus = state.currentStatus;
  renderActiveGraph();
  renderCandidateNodes();
  renderInitialPopulationNodes();
  renderLatestGeneratedNodes();
  if (state.pendingFocusNodeId && state.fullNodeMap.has(state.pendingFocusNodeId)) {
    const pendingNodeId = state.pendingFocusNodeId;
    state.pendingFocusNodeId = null;
    focusNode(pendingNodeId);
  }
}

async function loadDefaults() {
  const defaults = await fetchJson("/api/defaults");
  elements.host.value = defaults.llm.host;
  elements.model.value = defaults.llm.model;
  elements.directAiMaxSampleNums.value = "10";
  elements.directAiPopSize.value = "5";
  elements.seededEohMaxGenerations.value = defaults.method.max_generations ?? "8";
  elements.seededEohPopSize.value = defaults.method.pop_size ?? "8";
  elements.seededEohNumSamplers.value = defaults.method.num_samplers ?? defaults.method.num_evaluators ?? "4";
  elements.seededEohNumEvaluators.value = defaults.method.num_evaluators ?? "4";
  elements.distanceMetric.value = defaults.method.distance_metric || "codet5p_embedding_cosine";
  state.highScorePercent = Number(elements.highScorePercent.value) || 100;
  state.graphAbstractionMode = elements.graphAbstractionMode?.value || "full";
  state.clusterGroupSize = Number(elements.clusterGroupSize?.value) || 20;
  state.backgroundTheme = elements.backgroundTheme?.value || "light";
  syncHighScoreLabel();
  syncClusterGroupLabel();
  syncBackgroundThemeLabel();
  applyBackgroundTheme();
  await refreshRunsSafe({ force: true, status: "idle" });
  showNoRunSelectedState();
}

async function poll() {
  let nextDelay = 2000;
  try {
    await refreshRunsSafe({ status: state.currentStatus });
    if (state.viewRunId) {
      const status = await refreshStatus(state.viewRunId);
      await refreshRunsSafe({ status: status?.status || state.currentStatus });
      if (shouldRefreshGraphForStatus(status)) {
        await refreshGraph(state.viewRunId);
      }
      nextDelay = nextPollDelayMs(status);
    } else {
      showNoRunSelectedState();
    }
  } catch (error) {
    elements.graphMeta.textContent = `连接失败: ${error.message}`;
  } finally {
    setTimeout(poll, nextDelay);
  }
}

elements.runCandidatesButton.addEventListener("click", () => {
  void startRunWithUserFeedback("candidates");
});
elements.runInitialPopulationButton.addEventListener("click", () => {
  void startRunWithUserFeedback("initial_population");
});
elements.clearCandidatesButton.addEventListener("click", () => {
  state.candidateNodeIds.clear();
  renderCandidateNodes();
  renderSelectedNodes();
  renderFavoriteNodes();
  renderLatestGeneratedNodes();
});
elements.clearInitialPopulationButton.addEventListener("click", () => {
  state.initialPopulationNodeIds.clear();
  renderInitialPopulationNodes();
  renderSelectedNodes();
  renderFavoriteNodes();
  renderLatestGeneratedNodes();
});
elements.injectExpertSolutionButton.addEventListener("click", () => {
  void injectExternalExpertSolution();
});
elements.importHistoryButton.addEventListener("click", importHistorySamples);
elements.stopButton.addEventListener("click", stopRun);
elements.testLlmButton.addEventListener("click", testLlmConnection);
elements.summaryViewButton.addEventListener("click", () => {
  void openSummaryView();
});
elements.openClusterButton.addEventListener("click", () => {
  const [nodeId] = [...state.selectedNodeIds];
  if (nodeId) {
    openClientCluster(nodeId);
  }
});
elements.resetGraphViewButton.addEventListener("click", () => {
  resetDerivedGraphView();
});
elements.newSaveButton.addEventListener("click", createSave);
elements.refreshRunsButton.addEventListener("click", async () => {
  await refreshRunsSafe({ force: true });
  if (state.viewRunId) {
    await refreshStatus(state.viewRunId);
    await refreshGraph(state.viewRunId);
  } else {
    showNoRunSelectedState();
  }
});
elements.runHistoryList.addEventListener("click", async (event) => {
  const deleteButton = event.target.closest("[data-action='delete-save']");
  if (deleteButton) {
    event.stopPropagation();
    await deleteSave(deleteButton.dataset.saveId);
    return;
  }
  const item = event.target.closest(".run-history-item[data-save-id]");
  if (!item) {
    return;
  }
  await viewRun(item.dataset.saveId);
});
elements.selectedNodes.addEventListener("click", handleNodeActionClick);
elements.favoriteNodes.addEventListener("click", handleNodeActionClick);
elements.candidateNodes.addEventListener("click", handleNodeActionClick);
elements.initialPopulationNodes.addEventListener("click", handleNodeActionClick);
elements.latestGeneratedNodes.addEventListener("click", handleNodeActionClick);
elements.nodeDetails.addEventListener("click", handleNodeActionClick);
elements.clearSelectionButton.addEventListener("click", () => updateSelection([]));
elements.rotateToggleButton.addEventListener("click", () => setAutoRotate(!state.autoRotate));
elements.boxSelectMode.addEventListener("change", syncControlState);
elements.edgeToggle.addEventListener("change", () => {
  state.showEdges = elements.edgeToggle.checked;
  state.edgeVisibilityPinned = true;
  updateEdgeVisibility();
  updateGraphMeta();
});
elements.nodeSize.addEventListener("input", () => {
  state.nodeSizeScale = Number(elements.nodeSize.value) || 1;
  syncNodeSizeLabel();
  refreshNodeColors();
});
elements.nodeOpacity.addEventListener("input", () => {
  state.nodeOpacityScale = Number(elements.nodeOpacity.value) || 1;
  syncNodeOpacityLabel();
  refreshNodeColors();
});
elements.edgeOpacity.addEventListener("input", () => {
  state.edgeOpacityScale = Number(elements.edgeOpacity.value) || 1;
  syncEdgeOpacityLabel();
  updateEdgeAppearance();
});
elements.graphSpread.addEventListener("input", () => {
  state.graphSpreadScale = Number(elements.graphSpread.value) || 1;
  syncGraphSpreadLabel();
  updateGraphLayout();
});
elements.backgroundTheme.addEventListener("change", () => {
  state.backgroundTheme = elements.backgroundTheme.value || "light";
  syncBackgroundThemeLabel();
  applyBackgroundTheme();
  refreshNodeColors();
});
elements.highScorePercent.addEventListener("input", () => {
  state.highScorePercent = Number(elements.highScorePercent.value) || 100;
  syncHighScoreLabel();
  renderActiveGraph(true);
});
elements.graphAbstractionMode.addEventListener("change", () => {
  state.graphAbstractionMode = elements.graphAbstractionMode.value || "full";
  state.selectedNodeIds.clear();
  state.openedClientClusterId = null;
  syncClusterGroupLabel();
  renderActiveGraph(true);
});
elements.clusterGroupSize.addEventListener("input", () => {
  state.clusterGroupSize = Number(elements.clusterGroupSize.value) || 20;
  state.selectedNodeIds.clear();
  state.openedClientClusterId = null;
  syncClusterGroupLabel();
  if (state.graphAbstractionMode === "cluster") {
    renderActiveGraph(true);
  }
});

renderer.domElement.addEventListener("click", (event) => {
  if (elements.boxSelectMode.checked || state.isDraggingSelection) {
    return;
  }
  pickNode(event);
});

renderer.domElement.addEventListener("pointerdown", beginSelection);
window.addEventListener("pointermove", moveSelection);
window.addEventListener("pointerup", endSelection);

window.addEventListener("resize", () => {
  const width = elements.graphContainer.clientWidth;
  const height = elements.graphContainer.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
  if (typeof controls.handleResize === "function") {
    controls.handleResize();
  }
});

loadDefaults().then(() => {
  state.nodeSizeScale = Number(elements.nodeSize.value) || 1;
  state.nodeOpacityScale = Number(elements.nodeOpacity.value) || 1;
  state.edgeOpacityScale = Number(elements.edgeOpacity.value) || 1;
  state.graphSpreadScale = Number(elements.graphSpread.value) || 1;
  syncNodeSizeLabel();
  syncNodeOpacityLabel();
  syncEdgeOpacityLabel();
  syncGraphSpreadLabel();
  syncHighScoreLabel();
  syncClusterGroupLabel();
  setAutoRotate(false);
  syncControlState();
  renderSelectedNodes();
  syncGraphViewControls();
  render();
  poll();
});
