import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const WORLD_XY = 220;
const WORLD_Z = 130;
// 数据来源：带 ?revision=<id> 时读该 revision 的数据（首次访问现场生成并缓存），
// 不带参数则读随仓库提供的**预实验快照**（只读演示）。
// 这两者是不同数据集——页面上会用 #source 明确标出来。
const SNAPSHOT_URL = "/static/data/nbn_basins_3d.json";
const REVISION_ID = new URLSearchParams(location.search).get("revision") || "";
const DATA_URL = REVISION_ID
  ? `/api/revisions/${encodeURIComponent(REVISION_ID)}/basin3d`
  : SNAPSHOT_URL;
const CODE_API = (id) => `/api/nodes/${encodeURIComponent(id)}/code`;

const $ = (id) => document.getElementById(id);

// ---- 调色板 ----
function buildPalette(count = 30) {
  const colors = [];
  for (let i = 0; i < count; i++) {
    const hue = (i * 137.508) % 360;
    const sat = 78 + (i % 3) * 8;
    const light = 50 + (i % 4) * 7;
    const rgb = hslToRgb(hue, sat / 100, light / 100);
    colors.push({ r: Math.round(rgb[0] * 255), g: Math.round(rgb[1] * 255), b: Math.round(rgb[2] * 255) });
  }
  return colors;
}

function hslToRgb(h, s, l) {
  h = ((h % 360) + 360) % 360 / 360;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h * 12) % 12;
    return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [f(0), f(8), f(4)];
}

const VIRIDIS_STOPS = [
  [68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142],
  [31, 158, 137], [53, 183, 121], [110, 206, 88], [181, 222, 43], [253, 231, 37],
];
function viridisColor(t) {
  t = Math.max(0, Math.min(1, t));
  const pos = t * (VIRIDIS_STOPS.length - 1);
  const i = Math.min(VIRIDIS_STOPS.length - 2, Math.floor(pos));
  const u = pos - i;
  const a = VIRIDIS_STOPS[i], b = VIRIDIS_STOPS[i + 1];
  return { r: Math.round(a[0] + (b[0] - a[0]) * u), g: Math.round(a[1] + (b[1] - a[1]) * u), b: Math.round(a[2] + (b[2] - a[2]) * u) };
}

const GRAY = { r: 122, g: 124, b: 130 };
const DIM_GRAY = { r: 68, g: 72, b: 80 };

// ---- 状态 ----
let data = null;
let nodeXs, nodeYs, nodeZs, nodeZsTree, nodeScores, nodeValid;
let nodeIds, nodeOrigins, nodeOps, nodeRevs;
let nodeIndexById = new Map();
let scoreRank = new Float32Array(0);

const PARTITION_DEFAULT_THRESHOLD = { nbn: "0.04", ball: "0.05" };
const state = {
  partition: "nbn",
  threshold: "0.04",
  colorMode: "basin",
  pathMode: "best",
  zMode: "score",
  onlyValid: false,
  minSize: 1,
  showEdges: false,
  showRoots: true,
  showChainClimb: false,
  isolated: null, // nbn/ball: basin id；traj: trajectory index
};

let scene, camera, renderer, controls, raycaster;
let pointsMesh = null;
let edgesMesh = null;
let rootsMesh = null;
let ccPointsMesh = null, ccLineMesh = null, ccAnchorMesh = null, ccParentMesh = null, ccLinkMesh = null;
let pathMesh = null;
let renderNodeIndex = []; // geometry 顶点 -> 数据节点下标
let hoveredIndex = -1;
let lastDown = { x: 0, y: 0 };
let selectedNode = -1;

// 轨迹动画状态
let anim = { traj: -1, step: 0, playing: false, timer: null, seq: [] };
let animTrailMesh = null;
let animMarkerMesh = null;

// ---- 场景 ----
function initScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d1117);
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 3000);
  camera.position.set(0, 140, 620);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  $("scene").appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 0, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.8));
  scene.add(new THREE.DirectionalLight(0xffffff, 0.5));
  const grid = new THREE.GridHelper(900, 36, 0x30363d, 0x21262d);
  grid.position.y = -WORLD_XY - 2;
  scene.add(grid);

  raycaster = new THREE.Raycaster();
  raycaster.params.Points.threshold = 4.0;

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  renderer.domElement.addEventListener("pointermove", onPointerMove);
  renderer.domElement.addEventListener("pointerdown", (ev) => {
    lastDown = { x: ev.clientX, y: ev.clientY };
  });
  renderer.domElement.addEventListener("pointerup", onPointerUp);
  renderer.domElement.addEventListener("dblclick", onDoubleClick);
  animate();
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

// ---- 数据 ----
async function loadData() {
  const res = await fetch(DATA_URL);
  if (!res.ok) {
    // 后端失败时返回 {"ok":false,"error":{"message":"…下一步怎么办…"}}
    let detail = `HTTP ${res.status}`;
    try {
      const payload = await res.json();
      if (payload && payload.error && payload.error.message) detail = payload.error.message;
    } catch (_) { /* 非 JSON 响应，用状态码 */ }
    throw new Error(detail);
  }
  data = await res.json();
  const sourceEl = $("source");
  if (sourceEl) {
    sourceEl.textContent = REVISION_ID
      ? `工作区数据 · revision ${REVISION_ID}`
      : `预实验快照 · ${data.generatedAt || "—"} · 只读，与工作区数据无关`;
  }

  const nodes = data.nodes;
  const n = nodes.length;
  nodeXs = new Float32Array(n);
  nodeYs = new Float32Array(n);
  nodeZs = new Float32Array(n);
  nodeZsTree = new Float32Array(n);
  nodeScores = new Float64Array(n);
  nodeValid = new Uint8Array(n);
  nodeIds = new Array(n);
  nodeOrigins = new Array(n);
  nodeOps = new Array(n);
  nodeRevs = new Array(n);

  for (let i = 0; i < n; i++) {
    const nd = nodes[i];
    nodeXs[i] = Number(nd.x) || 0;
    nodeYs[i] = Number(nd.y) || 0;
    nodeZs[i] = Number(nd.z) || 0;
    nodeZsTree[i] = Number(nd.zTree) || 0;
    nodeScores[i] = Number(nd.score) || 0;
    nodeValid[i] = nd.valid ? 1 : 0;
    nodeIds[i] = nd.id;
    nodeOrigins[i] = nd.origin || "";
    nodeOps[i] = nd.op || "";
    nodeRevs[i] = nd.rev || "";
    nodeIndexById.set(nd.id, i);
  }

  normalizeCoords();
  computeScoreRank();
  populateThresholds();
  $("stats").textContent = `${data.nodeCount.toLocaleString()} 个节点 · ${data.edgeCount.toLocaleString()} 条 NBN 边 · ${data.validCount.toLocaleString()} 个有效解（${data.uniqueValidCount.toLocaleString()} 唯一）`;

  rebuildAll();
  updateLegend();
}

function normalizeCoords() {
  const n = nodeXs.length;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  let minZ = Infinity, maxZ = -Infinity, minT = Infinity, maxT = -Infinity;
  for (let i = 0; i < n; i++) {
    const x = nodeXs[i], y = nodeYs[i], z = nodeZs[i], t = nodeZsTree[i];
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
    if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    if (t < minT) minT = t; if (t > maxT) maxT = t;
  }
  const sx = Math.max(1, maxX - minX), sy = Math.max(1, maxY - minY);
  const sz = Math.max(1, maxZ - minZ), st = Math.max(1, maxT - minT);
  for (let i = 0; i < n; i++) {
    nodeXs[i] = ((nodeXs[i] - minX) / sx - 0.5) * 2 * WORLD_XY;
    nodeYs[i] = -((nodeYs[i] - minY) / sy - 0.5) * 2 * WORLD_XY;
    nodeZs[i] = ((nodeZs[i] - minZ) / sz - 0.5) * 2 * WORLD_Z;
    nodeZsTree[i] = ((nodeZsTree[i] - minT) / st - 0.5) * 2 * WORLD_Z;
  }
}

function computeScoreRank() {
  const n = nodeScores.length;
  const distinct = [...new Set(Array.from(nodeScores).filter((s) => Number.isFinite(s) && s > 0))].sort((a, b) => a - b);
  const rankOf = new Map(distinct.map((s, i) => [s, (i + 1) / distinct.length]));
  scoreRank = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const s = nodeScores[i];
    scoreRank[i] = s > 0 && rankOf.has(s) ? rankOf.get(s) : 0;
  }
}

// ---- 划分数据 ----
function currentData() {
  if (state.partition === "nbn") {
    return { kind: "nbn", basinOf: data.nbn[state.threshold].basinOf, basins: data.nbn[state.threshold].basins };
  }
  if (state.partition === "ball") {
    return { kind: "ball", basinOf: data.ball.thresholds[state.threshold].basinOf, basins: data.ball.thresholds[state.threshold].basins };
  }
  return { kind: "traj", trajOf: data.trajectories.trajOf, orderInTraj: data.trajectories.orderInTraj, trajs: data.trajectories.list };
}

function populateThresholds() {
  const sel = $("threshold");
  sel.innerHTML = "";
  const keys = state.partition === "ball"
    ? Object.keys(data.ball.thresholds)
    : Object.keys(data.nbn);
  keys.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  });
  state.threshold = PARTITION_DEFAULT_THRESHOLD[state.partition] || keys[0];
  sel.value = state.threshold;
}

// ---- 重建 ----
function rebuildAll() {
  const info = currentData();
  if (info.kind === "traj") {
    rebuildTraj(info);
  } else {
    rebuildBasins(info);
  }
  rebuildChainClimb();
  $("stats").textContent = `${data.nodeCount.toLocaleString()} 个节点 · ${renderNodeIndex.length.toLocaleString()} 个可见 · ${data.validCount.toLocaleString()} 个有效解（${data.uniqueValidCount.toLocaleString()} 唯一）`;
}

function visibleMask(info) {
  const n = data.nodeCount;
  const visible = [];
  if (info.kind === "traj") {
    for (let i = 0; i < n; i++) {
      if (state.onlyValid && !nodeValid[i]) continue;
      const t = info.trajOf[i];
      if (t < 0) continue;
      if (state.isolated !== null && t !== state.isolated) continue;
      visible.push(i);
    }
    return visible;
  }
  const sizeOf = new Map(info.basins.map((b, idx) => [b.basin, { size: b.size, rank: idx }]));
  for (let i = 0; i < n; i++) {
    if (state.onlyValid && !nodeValid[i]) continue;
    const basin = info.basinOf[i];
    const meta = sizeOf.get(basin);
    if (!meta || meta.size < state.minSize) continue;
    if (state.isolated !== null && basin !== state.isolated) continue;
    visible.push(i);
  }
  return visible;
}

function nodeColor(info, i, palette) {
  if (state.partition === "traj" || state.colorMode === "basin") {
    if (info.kind === "traj") {
      const t = info.trajOf[i];
      return t >= 0 && t < palette.length ? palette[t] : DIM_GRAY;
    }
    const basin = info.basinOf[i];
    const rank = info.rankOf?.get(basin) ?? 9999;
    return rank < palette.length ? palette[rank] : GRAY;
  }
  return viridisColor(scoreRank[i]);
}

function rebuildBasins(info) {
  const n = data.nodeCount;
  info.rankOf = new Map(info.basins.map((b, idx) => [b.basin, idx]));
  const visible = visibleMask(info);
  const palette = buildPalette();
  const positions = new Float32Array(visible.length * 3);
  const colors = new Float32Array(visible.length * 3);
  renderNodeIndex = new Array(visible.length);
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;

  for (let k = 0; k < visible.length; k++) {
    const i = visible[k];
    positions[k * 3] = nodeXs[i];
    positions[k * 3 + 1] = zArr[i];
    positions[k * 3 + 2] = nodeYs[i];
    const c = nodeColor(info, i, palette);
    colors[k * 3] = c.r / 255;
    colors[k * 3 + 1] = c.g / 255;
    colors[k * 3 + 2] = c.b / 255;
    renderNodeIndex[k] = i;
  }
  setPoints(positions, colors);
  rebuildEdges(visible, info);
  rebuildRoots(visible, info, palette);
  removePathMesh();
}

function rebuildTraj(info) {
  const visible = visibleMask(info);
  const palette = buildPalette();
  const positions = new Float32Array(visible.length * 3);
  const colors = new Float32Array(visible.length * 3);
  renderNodeIndex = new Array(visible.length);
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;

  for (let k = 0; k < visible.length; k++) {
    const i = visible[k];
    positions[k * 3] = nodeXs[i];
    positions[k * 3 + 1] = zArr[i];
    positions[k * 3 + 2] = nodeYs[i];
    const c = nodeColor(info, i, palette);
    colors[k * 3] = c.r / 255;
    colors[k * 3 + 1] = c.g / 255;
    colors[k * 3 + 2] = c.b / 255;
    renderNodeIndex[k] = i;
  }
  setPoints(positions, colors);
  rebuildEdges(visible, info);
  rebuildPaths(info, palette);
  rebuildRoots(visible, info, palette);
}

function setPoints(positions, colors) {
  if (pointsMesh) {
    scene.remove(pointsMesh);
    pointsMesh.geometry.dispose();
    pointsMesh.material.dispose();
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.PointsMaterial({
    size: 2.6,
    vertexColors: true,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.95,
    depthWrite: false,
  });
  pointsMesh = new THREE.Points(geo, mat);
  pointsMesh.frustumCulled = false;
  scene.add(pointsMesh);
}

function rebuildEdges(visible, info) {
  if (edgesMesh) {
    scene.remove(edgesMesh);
    edgesMesh.geometry.dispose();
    edgesMesh.material.dispose();
    edgesMesh = null;
  }
  if (!state.showEdges) return;
  const visibleSet = new Set(visible);
  const segs = [];
  const basinOf = info.kind === "traj" ? null : info.basinOf;
  for (const [s, t] of data.edges) {
    if (!visibleSet.has(s) || !visibleSet.has(t)) continue;
    if (basinOf && state.isolated !== null && basinOf[s] !== basinOf[t]) continue;
    if (info.kind === "traj" && state.isolated !== null && info.trajOf[s] !== info.trajOf[t]) continue;
    segs.push(s, t);
  }
  if (!segs.length) return;
  const positions = new Float32Array(segs.length * 3);
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;
  for (let k = 0; k < segs.length; k++) {
    const i = segs[k];
    positions[k * 3] = nodeXs[i];
    positions[k * 3 + 1] = zArr[i];
    positions[k * 3 + 2] = nodeYs[i];
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.LineBasicMaterial({ color: 0x7d8590, transparent: true, opacity: state.isolated !== null ? 0.7 : 0.28 });
  edgesMesh = new THREE.LineSegments(geo, mat);
  edgesMesh.frustumCulled = false;
  scene.add(edgesMesh);
}

function rebuildPaths(info, palette) {
  removePathMesh();
  if (info.kind !== "traj") return;
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;
  const pts = [];
  const cols = [];
  for (const tr of info.trajs) {
    if (state.isolated !== null && tr.index !== state.isolated) continue;
    const path = state.pathMode === "chain"
      ? (tr.chainPath || tr.bestPath)
      : state.pathMode === "best" ? tr.bestPath : tr.path;
    for (let k = 0; k + 1 < path.length; k++) {
      const a = path[k], b = path[k + 1];
      const c = tr.index < palette.length ? palette[tr.index] : { r: 255, g: 255, b: 255 };
      for (const idx of [a, b]) {
        pts.push(nodeXs[idx], zArr[idx], nodeYs[idx]);
        cols.push(c.r / 255, c.g / 255, c.b / 255);
      }
    }
  }
  if (!pts.length) return;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(cols), 3));
  const mat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 });
  pathMesh = new THREE.LineSegments(geo, mat);
  pathMesh.frustumCulled = false;
  scene.add(pathMesh);
}

function removePathMesh() {
  if (pathMesh) {
    scene.remove(pathMesh);
    pathMesh.geometry.dispose();
    pathMesh.material.dispose();
    pathMesh = null;
  }
}

// ---- 轨迹动画 ----
function currentAnimSeq() {
  if (state.partition !== "traj" || state.isolated === null) return null;
  const info = currentData();
  const tr = info.trajs.find((t) => t.index === state.isolated);
  if (!tr) return null;
  if (state.pathMode === "chain") return tr.chainPath || null;
  return state.pathMode === "best" ? tr.bestPath : tr.path;
}

function stopAnimation() {
  if (anim.timer) {
    clearInterval(anim.timer);
    anim.timer = null;
  }
  anim.playing = false;
  anim.traj = -1;
  anim.step = 0;
  anim.seq = [];
  removeAnimMeshes();
  const btn = $("animToggle");
  if (btn) btn.textContent = "▶ 播放轨迹";
  const st = $("animStatus");
  if (st) st.textContent = "";
}

function removeAnimMeshes() {
  for (const key of ["animTrailMesh", "animMarkerMesh"]) {
    if (animTrailMesh) {
      scene.remove(animTrailMesh);
      animTrailMesh.geometry?.dispose();
      animTrailMesh.material?.dispose();
      animTrailMesh = null;
    }
    if (animMarkerMesh) {
      scene.remove(animMarkerMesh);
      animMarkerMesh.geometry?.dispose();
      animMarkerMesh.material?.dispose();
      animMarkerMesh = null;
    }
  }
}

function renderAnimStep() {
  const seq = anim.seq;
  if (!seq.length) return;
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;
  removeAnimMeshes();

  // 已走过的轨迹段
  const trailPts = [];
  const upto = seq.slice(0, anim.step + 1);
  for (let k = 0; k + 1 < upto.length; k++) {
    const a = upto[k], b = upto[k + 1];
    trailPts.push(nodeXs[a], zArr[a], nodeYs[a], nodeXs[b], zArr[b], nodeYs[b]);
  }
  if (trailPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(trailPts), 3));
    const m = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95 });
    animTrailMesh = new THREE.LineSegments(g, m);
    animTrailMesh.frustumCulled = false;
    scene.add(animTrailMesh);
  }

  // 当前点
  const cur = upto[upto.length - 1];
  const pg = new THREE.BufferGeometry();
  pg.setAttribute("position", new THREE.BufferAttribute(new Float32Array([nodeXs[cur], zArr[cur], nodeYs[cur]]), 3));
  pg.setAttribute("color", new THREE.BufferAttribute(new Float32Array([1, 1, 1]), 3));
  const pm = new THREE.PointsMaterial({ size: 16, vertexColors: true, sizeAttenuation: true, depthWrite: false });
  animMarkerMesh = new THREE.Points(pg, pm);
  animMarkerMesh.frustumCulled = false;
  scene.add(animMarkerMesh);

  $("animStatus").textContent = `轨迹 #${anim.traj}：第 ${anim.step}/${seq.length - 1} 步 · 分数 ${nodeScores[cur].toFixed(5)}`;
}

function startAnimation() {
  stopAnimation();
  const seq = currentAnimSeq();
  if (!seq || seq.length < 2) {
    $("animStatus").textContent = seq && seq.length < 2 ? "该轨迹没有可画路径" : "请先在图例点选一条轨迹";
    return;
  }
  anim.traj = state.isolated;
  anim.seq = seq;
  anim.step = 0;
  anim.playing = true;
  $("animToggle").textContent = "⏸ 暂停";
  renderAnimStep();
  const delay = seq.length <= 8 ? 400 : 180;
  anim.timer = setInterval(animTick, delay);
}

function animTick() {
  if (!anim.seq.length) return;
  anim.step += 1;
  if (anim.step >= anim.seq.length - 1) {
    const trajLabel = anim.traj;
    anim.step = anim.seq.length - 1;
    renderAnimStep();
    $("animStatus").textContent = `轨迹 #${trajLabel}：到达终点 · 分数 ${nodeScores[anim.seq[anim.step]].toFixed(5)}`;
    stopAnimation();
    $("animStatus").textContent = `轨迹 #${trajLabel}：播放完成`;
    return;
  }
  renderAnimStep();
}

function removeChainClimb() {
  for (const key of ["ccPointsMesh", "ccLineMesh", "ccAnchorMesh", "ccParentMesh", "ccLinkMesh"]) {
    const m = eval(key);
    if (m) {
      scene.remove(m);
      if (m.geometry) m.geometry.dispose();
      if (m.material) m.material.dispose();
      eval(key + " = null");
    }
  }
}

// 链爬过程图层（本次实验）：橙=全部生成节点，红=锚点链，紫=每个锚点的父（目标）
function rebuildChainClimb() {
  removeChainClimb();
  if (!state.showChainClimb) return;
  const tr = data.trajectories.list.find((t) => Array.isArray(t.chainPath) && t.chainPath.length);
  if (!tr) return;
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;
  const chain = tr.chainPath;
  const parents = tr.chainParents || [];

  // 橙点：本次全部生成节点
  const runPts = [];
  for (const i of tr.path) {
    if (nodeIndexById.get(nodeIds[i]) === undefined) continue;
    runPts.push(nodeXs[i], zArr[i], nodeYs[i]);
  }
  if (runPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(runPts), 3));
    const m = new THREE.PointsMaterial({ color: 0xf0883e, size: 4.5, sizeAttenuation: true, transparent: true, opacity: 0.95, depthWrite: false });
    ccPointsMesh = new THREE.Points(g, m);
    ccPointsMesh.frustumCulled = false;
    scene.add(ccPointsMesh);
  }

  // 红线：锚点链
  const chainPts = [];
  for (const i of chain) {
    chainPts.push(nodeXs[i], zArr[i], nodeYs[i]);
  }
  if (chainPts.length >= 6) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(chainPts), 3));
    const m = new THREE.LineBasicMaterial({ color: 0xff4444, transparent: true, opacity: 0.95 });
    ccLineMesh = new THREE.Line(g, m);
    ccLineMesh.frustumCulled = false;
    scene.add(ccLineMesh);
  }

  // 红星：锚点
  const aPts = [];
  for (const i of chain) aPts.push(nodeXs[i], zArr[i], nodeYs[i]);
  if (aPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(aPts), 3));
    const m = new THREE.PointsMaterial({ color: 0xff2222, size: 13, sizeAttenuation: true, transparent: true, depthWrite: false });
    ccAnchorMesh = new THREE.Points(g, m);
    ccAnchorMesh.frustumCulled = false;
    scene.add(ccAnchorMesh);
  }

  // 紫菱 + 虚线：每个锚点的父（目标）
  const pPts = [], linkPts = [];
  for (let k = 0; k < chain.length; k++) {
    const pi = parents[k];
    if (pi === undefined || pi === null || pi < 0) continue;
    pPts.push(nodeXs[pi], zArr[pi], nodeYs[pi]);
    const a = chain[k];
    linkPts.push(nodeXs[a], zArr[a], nodeYs[a], nodeXs[pi], zArr[pi], nodeYs[pi]);
  }
  if (pPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pPts), 3));
    const m = new THREE.PointsMaterial({ color: 0xa371f7, size: 11, sizeAttenuation: true, transparent: true, depthWrite: false });
    ccParentMesh = new THREE.Points(g, m);
    ccParentMesh.frustumCulled = false;
    scene.add(ccParentMesh);
  }
  if (linkPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(linkPts), 3));
    const m = new THREE.LineBasicMaterial({ color: 0xa371f7, transparent: true, opacity: 0.55 });
    ccLinkMesh = new THREE.LineSegments(g, m);
    ccLinkMesh.frustumCulled = false;
    scene.add(ccLinkMesh);
  }
}

function rebuildRoots(visible, info, palette) {
  if (rootsMesh) {
    scene.remove(rootsMesh);
    rootsMesh.geometry.dispose();
    rootsMesh.material.dispose();
    rootsMesh = null;
  }
  if (!state.showRoots) return;
  const visibleSet = new Set(visible);
  const zArr = state.zMode === "tree" ? nodeZsTree : nodeZs;
  const pts = [];
  const cols = [];
  if (info.kind === "traj") {
    for (const tr of info.trajs) {
      if (state.isolated !== null && tr.index !== state.isolated) continue;
      if (state.pathMode === "chain" && !tr.chainPath) continue; // 新父链模式只留链爬行入口
      const idx = tr.path[0];
      if (idx === undefined || !visibleSet.has(idx)) continue;
      const c = tr.index < palette.length ? palette[tr.index] : { r: 255, g: 255, b: 255 };
      pts.push(nodeXs[idx], zArr[idx], nodeYs[idx]);
      cols.push(c.r / 255, c.g / 255, c.b / 255);
    }
  } else {
    for (const b of info.basins) {
      if (b.size < state.minSize) continue;
      if (state.isolated !== null && b.basin !== state.isolated) continue;
      const idx = nodeIndexById.get(b.rootId ?? b.leaderId);
      if (idx === undefined || !visibleSet.has(idx)) continue;
      const rank = info.rankOf?.get(b.basin) ?? 9999;
      const c = rank < palette.length ? palette[rank] : { r: 230, g: 230, b: 230 };
      pts.push(nodeXs[idx], zArr[idx], nodeYs[idx]);
      cols.push(c.r / 255, c.g / 255, c.b / 255);
    }
  }
  if (!pts.length) return;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(cols), 3));
  const mat = new THREE.PointsMaterial({
    size: 9,
    vertexColors: true,
    sizeAttenuation: true,
    transparent: true,
    opacity: 1,
    depthWrite: false,
  });
  rootsMesh = new THREE.Points(geo, mat);
  rootsMesh.frustumCulled = false;
  scene.add(rootsMesh);
}

// ---- 图例 ----
function updateLegend() {
  const info = currentData();
  const listEl = $("legendList");
  listEl.innerHTML = "";
  const palette = buildPalette();

  if (info.kind === "traj") {
    $("legendTitle").textContent = "爬山轨迹";
    for (const tr of info.trajs) {
      const c = tr.index < palette.length ? palette[tr.index] : { r: 255, g: 255, b: 255 };
      const item = document.createElement("div");
      item.className = "legend-item" + (state.isolated === tr.index ? " active" : "") + (state.isolated !== null && state.isolated !== tr.index ? " dim" : "");
      const shortEntry = tr.entry.length > 42 ? tr.entry.slice(0, 42) + "…" : tr.entry;
      item.innerHTML = `
        <span class="swatch" style="background: rgb(${c.r},${c.g},${c.b})"></span>
        <span class="legend-main">#${String(tr.index).padStart(2, "0")} ${tr.session}</span>
        <span class="legend-sub">${shortEntry} · ${tr.nodeCount} 节点 · best ${tr.best != null ? Number(tr.best).toFixed(4) : "—"}${tr.completed ? "" : " · 未判死"}</span>
      `;
      item.title = `入口: ${tr.entry}\n评测: ${tr.evaluated ?? "—"}\n判定: ${tr.verdict ?? "—"}`;
      item.addEventListener("click", () => {
        state.isolated = state.isolated === tr.index ? null : tr.index;
        stopAnimation();
        rebuildAll();
        updateLegend();
      });
      listEl.appendChild(item);
    }
    return;
  }

  $("legendTitle").textContent = info.kind === "ball" ? "球（按规模排序）" : "山（按规模排序）";
  const show = info.basins.filter((b) => b.size >= state.minSize).slice(0, 24);
  for (const b of show) {
    const rank = info.basins.indexOf(b);
    const c = rank < palette.length ? palette[rank] : GRAY;
    const rootScore = b.rootScore != null ? b.rootScore : b.leaderScore;
    const item = document.createElement("div");
    item.className = "legend-item" + (state.isolated === b.basin ? " active" : "") + (state.isolated !== null && state.isolated !== b.basin ? " dim" : "");
    item.innerHTML = `
      <span class="swatch" style="background: rgb(${c.r},${c.g},${c.b})"></span>
      <span class="legend-main">${info.kind === "ball" ? "球" : "山"} #${b.basin} · ${b.size.toLocaleString()} 个解</span>
      <span class="legend-sub">根分 ${rootScore != null ? Number(rootScore).toFixed(4) : "—"}</span>
    `;
    item.title = `根: ${b.rootId ?? b.leaderId}`;
    item.addEventListener("click", () => {
      state.isolated = state.isolated === b.basin ? null : b.basin;
      stopAnimation();
      rebuildAll();
      updateLegend();
    });
    listEl.appendChild(item);
  }
  if (info.basins.length > show.length) {
    const more = document.createElement("div");
    more.className = "muted";
    more.textContent = `… 其余 ${info.basins.length - show.length} 个小规模${info.kind === "ball" ? "球" : "山"}未列出`;
    listEl.appendChild(more);
  }
}

// ---- 交互 ----
function onPointerMove(ev) {
  if (!pointsMesh) return;
  const rect = renderer.domElement.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((ev.clientX - rect.left) / rect.width) * 2 - 1,
    -((ev.clientY - rect.top) / rect.height) * 2 + 1,
  );
  raycaster.setFromCamera(ndc, camera);
  const hits = raycaster.intersectObject(pointsMesh, false);
  const tip = $("tooltip");
  if (!hits.length) {
    hoveredIndex = -1;
    tip.style.display = "none";
    return;
  }
  const nodeIdx = renderNodeIndex[hits[0].index];
  hoveredIndex = nodeIdx;
  const info = currentData();
  let groupInfo = "";
  if (info.kind === "traj") {
    const t = info.trajOf[nodeIdx];
    groupInfo = t >= 0 ? `轨迹 #${t}` : "非轨迹";
  } else {
    const basin = info.basinOf[nodeIdx];
    const meta = info.basins.find((b) => b.basin === basin);
    groupInfo = `${info.kind === "ball" ? "球" : "山"} #${basin}（${(meta?.size ?? 0).toLocaleString()} 个解）`;
  }
  tip.innerHTML = `
    <div class="tt-id">${nodeIds[nodeIdx]}</div>
    <div class="tt-row">分数 <b>${nodeScores[nodeIdx].toFixed(6)}</b> · ${groupInfo}</div>
    <div class="tt-row">来源 ${nodeOrigins[nodeIdx] || "—"} · 算子 ${nodeOps[nodeIdx] || "—"}</div>
    <div class="tt-row">revision ${nodeRevs[nodeIdx] || "—"}</div>
  `;
  tip.style.display = "block";
  tip.style.left = Math.min(ev.clientX + 14, window.innerWidth - 360) + "px";
  tip.style.top = Math.min(ev.clientY + 14, window.innerHeight - 120) + "px";
}

function onPointerUp(ev) {
  if (ev.button !== 0) return;
  const moved = Math.hypot(ev.clientX - lastDown.x, ev.clientY - lastDown.y);
  if (moved > 6 || hoveredIndex < 0) return;
  selectNode(hoveredIndex);
}

function onDoubleClick() {
  if (hoveredIndex < 0) return;
  const info = currentData();
  const key = info.kind === "traj" ? info.trajOf[hoveredIndex] : info.basinOf[hoveredIndex];
  if (key < 0) return;
  state.isolated = state.isolated === key ? null : key;
  stopAnimation();
  rebuildAll();
  updateLegend();
}

async function selectNode(nodeIdx) {
  selectedNode = nodeIdx;
  const info = currentData();
  let groupInfo = "";
  if (info.kind === "traj") {
    const t = info.trajOf[nodeIdx];
    groupInfo = t >= 0 ? `轨迹 #${t}` : "非轨迹";
  } else {
    const basin = info.basinOf[nodeIdx];
    const meta = info.basins.find((b) => b.basin === basin);
    groupInfo = `${info.kind === "ball" ? "球" : "山"} #${basin}（${(meta?.size ?? 0).toLocaleString()} 个解）`;
  }
  const panel = $("detail");
  panel.style.display = "flex";
  $("detailTitle").textContent = nodeIds[nodeIdx];
  $("detailMeta").textContent = `分数 ${nodeScores[nodeIdx].toFixed(6)} · ${groupInfo} · 来源 ${nodeOrigins[nodeIdx] || "—"} · 算子 ${nodeOps[nodeIdx] || "—"}`;
  $("detailAlgo").textContent = "";
  $("detailCode").textContent = "加载中…";
  $("detailLoading").classList.remove("hidden");
  $("detailError").classList.add("hidden");
  try {
    const res = await fetch(CODE_API(nodeIds[nodeIdx]));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    if (!payload?.ok || !payload.data) throw new Error("接口返回异常");
    const d = payload.data;
    $("detailAlgo").textContent = d.algorithm ? `算法摘要：${d.algorithm}` : "";
    $("detailCode").textContent = d.function || d.program || "（无代码）";
  } catch (err) {
    $("detailError").textContent = `加载代码失败：${err.message}`;
    $("detailError").classList.remove("hidden");
    $("detailCode").textContent = "—";
  } finally {
    $("detailLoading").classList.add("hidden");
  }
}

// ---- 控件 ----
function bindControls() {
  $("partition").addEventListener("change", (e) => {
    state.partition = e.target.value;
    state.isolated = null;
    stopAnimation();
    populateThresholds();
    const isTraj = state.partition === "traj";
    $("thresholdRow").classList.toggle("hidden", isTraj);
    $("colorModeRow").classList.toggle("hidden", isTraj);
    $("minSizeRow").classList.toggle("hidden", isTraj);
    $("pathModeRow").classList.toggle("hidden", !isTraj);
    $("animRow").classList.toggle("hidden", !isTraj);
    $("rootsLabel").textContent = isTraj ? "显示入口 ★" : "显示山根 ★";
    $("resetIsolation").textContent = "显示全部";
    rebuildAll();
    updateLegend();
  });
  $("pathMode").addEventListener("change", (e) => {
    state.pathMode = e.target.value;
    stopAnimation();
    rebuildAll();
  });
  $("threshold").addEventListener("change", (e) => {
    state.threshold = e.target.value;
    state.isolated = null;
    rebuildAll();
    updateLegend();
  });
  $("colorMode").addEventListener("change", (e) => {
    state.colorMode = e.target.value;
    state.isolated = null;
    rebuildAll();
    updateLegend();
  });
  $("zMode").addEventListener("change", (e) => {
    state.zMode = e.target.value;
    rebuildAll();
  });
  $("onlyValid").addEventListener("change", (e) => {
    state.onlyValid = e.target.checked;
    rebuildAll();
  });
  $("minSize").addEventListener("input", (e) => {
    state.minSize = Number(e.target.value);
    $("minSizeLabel").textContent = state.minSize;
    rebuildAll();
    updateLegend();
  });
  $("showEdges").addEventListener("change", (e) => {
    state.showEdges = e.target.checked;
    rebuildAll();
  });
  $("showRoots").addEventListener("change", (e) => {
    state.showRoots = e.target.checked;
    rebuildAll();
  });
  $("showChainClimb").addEventListener("change", (e) => {
    state.showChainClimb = e.target.checked;
    rebuildAll();
  });
  $("resetView").addEventListener("click", () => {
    camera.position.set(0, 140, 620);
    controls.target.set(0, 0, 0);
    controls.update();
  });
  $("resetIsolation").addEventListener("click", () => {
    state.isolated = null;
    stopAnimation();
    rebuildAll();
    updateLegend();
  });
  $("animToggle").addEventListener("click", () => {
    if (anim.playing) {
      clearInterval(anim.timer);
      anim.timer = null;
      anim.playing = false;
      $("animToggle").textContent = "▶ 继续";
      return;
    }
    if (anim.seq.length) {
      anim.playing = true;
      $("animToggle").textContent = "⏸ 暂停";
      const delay = anim.seq.length <= 8 ? 400 : 180;
      anim.timer = setInterval(animTick, delay);
      return;
    }
    startAnimation();
  });
  $("detailClose").addEventListener("click", () => {
    $("detail").style.display = "none";
    selectedNode = -1;
  });
}

// ---- 启动 ----
initScene();
bindControls();
loadData().catch((err) => {
  $("stats").textContent = "加载失败: " + err.message;
  console.error(err);
});
