import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";

const WORLD_XY = 220;
const WORLD_Z = 130;
// 数据来源：带 ?revision=<id> 时读该 revision 的数据（首次访问现场生成并缓存），
// 不带参数则读随仓库提供的**预实验快照**（只读演示）。
// 这两者是不同数据集——页面上会用 #source 明确标出来。
const SNAPSHOT_URL = "/static/data/mds3d_data.json";
const REVISION_ID = new URLSearchParams(location.search).get("revision") || "";
const DATA_URL = REVISION_ID
  ? `/api/revisions/${encodeURIComponent(REVISION_ID)}/mds3d`
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
const SOURCE_COLORS = {
  history: { r: 88, g: 166, b: 255 },
  run: { r: 63, g: 185, b: 80 },
  expert: { r: 210, g: 168, b: 255 },
  dig: { r: 240, g: 150, b: 60 },
  other: GRAY,
};
const SOURCE_LABELS = {
  history: "history（盲跑 EOH）",
  run: "run（区域/实验）",
  expert: "expert（专家解）",
  dig: "dig（爬山生成）",
  other: "其他",
};

// ---- 状态 ----
let data = null;
let nodeXs, nodeYs, nodeZs, nodeScores, nodeValid, nodeUnique;
let nodeIds, nodeOrigins, nodeOps, nodeRevs, nodeParents;
let nodeTrajOf = null;
let scoreRank = new Float32Array(0);

const state = {
  colorMode: "score",
  zMode: "score",
  scale: 1.0,  // 比例尺：整体均匀缩放
  onlyValid: false,
  onlyUnique: true,
  showTrajPaths: true,
  showChain: true,
  showRoots: true,
  showChainClimb: false,
  isolated: null, // 轨迹 index
  chainFrom: -1,  // 高亮父链的起点节点下标
  chainDropdown: "", // 下拉选中的入口 id
};

let scene, camera, renderer, controls, raycaster;
let pointsMesh = null;
let chainLineMesh = null;
let chainMarkersMesh = null;
let ccPointsMesh = null, ccLineMesh = null, ccAnchorGroup = null, ccParentGroup = null, ccLinkMesh = null;
let trajPathMesh = null;
let rootsMesh = null;
let renderNodeIndex = [];
let hoveredIndex = -1;
let lastDown = { x: 0, y: 0 };
let selectedNode = -1;

// ---- 场景 ----
function initScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d1117);
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 3000);
  camera.position.set(140, 90, 620);

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
    if (chainLineMesh?.material?.resolution) {
      chainLineMesh.material.resolution.set(window.innerWidth, window.innerHeight);
    }
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
  nodeScores = new Float64Array(n);
  nodeValid = new Uint8Array(n);
  nodeUnique = new Uint8Array(n);
  nodeIds = new Array(n);
  nodeOrigins = new Array(n);
  nodeOps = new Array(n);
  nodeRevs = new Array(n);
  nodeParents = new Int32Array(n);
  nodeTrajOf = data.trajectories.trajOf;

  for (let i = 0; i < n; i++) {
    const nd = nodes[i];
    nodeXs[i] = Number(nd.x) || 0;
    nodeYs[i] = Number(nd.y) || 0;
    nodeZs[i] = Number(nd.zScore) || 0;
    nodeScores[i] = Number(nd.score) || 0;
    nodeValid[i] = nd.valid ? 1 : 0;
    nodeUnique[i] = nd.unique ? 1 : 0;
    nodeIds[i] = nd.id;
    nodeOrigins[i] = nd.origin || "";
    nodeOps[i] = nd.op || "";
    nodeRevs[i] = nd.rev || "";
    nodeParents[i] = Number(nd.parent) || 0;
  }

  computeScoreRank();
  populateChainSelect();
  $("stats").textContent =
    `${data.nodeCount.toLocaleString()} 节点 · ${data.uniqueCount.toLocaleString()} 唯一码 · ` +
    `保真度 3D ρ=${data.fidelity.rho3.toFixed(2)} (stress ${data.fidelity.stress3.toFixed(2)}) · ` +
    `2D ρ=${data.fidelity.rho2.toFixed(2)}`;

  fitToView(); // 初始自动"适应画面"：均匀放大铺满，距离比例不变
  updateLegend();
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

function populateChainSelect() {
  const sel = $("chainSelect");
  sel.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = "（不显示）";
  sel.appendChild(opt0);
  for (const ec of data.entryChains) {
    const short = ec.entry.length > 52 ? ec.entry.slice(0, 52) + "…" : ec.entry;
    const opt = document.createElement("option");
    opt.value = ec.entry;
    opt.textContent = `${short} · 链 ${ec.chain.length} 步`;
    sel.appendChild(opt);
  }
}

// ---- Z 高度 ----
function zHeight(i) {
  if (state.zMode === "rank") return scoreRank[i];
  if (state.zMode === "flat") return 0.5;
  return nodeZs[i];
}

function percentileOf(arr, p) {
  const s = Float32Array.from(arr).sort();
  const idx = (p / 100) * (s.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return s[lo] + (s[hi] - s[lo]) * (idx - lo);
}

function normalizeCoords() {
  const n = nodeXs.length;
  const xyz = new Float32Array(n * 3);

  // x,y 用 P1–P99 铺满（少数离群点会被撑爆 min-max，把主体压扁在中间一小块）；
  // z（分数高度）用 min-max，保证冠军在顶部。
  const xLo = percentileOf(nodeXs, 1), xHi = percentileOf(nodeXs, 99);
  const yLo = percentileOf(nodeYs, 1), yHi = percentileOf(nodeYs, 99);
  let zMin = Infinity, zMax = -Infinity;
  for (let i = 0; i < n; i++) {
    const z = zHeight(i);
    if (z < zMin) zMin = z; if (z > zMax) zMax = z;
  }
  const sx = Math.max(1e-9, xHi - xLo), sy = Math.max(1e-9, yHi - yLo), sz = Math.max(1e-9, zMax - zMin);
  for (let i = 0; i < n; i++) {
    xyz[i * 3] = ((nodeXs[i] - xLo) / sx - 0.5) * 2 * WORLD_XY;
    xyz[i * 3 + 1] = ((zHeight(i) - zMin) / sz - 0.5) * 2 * WORLD_Z;
    xyz[i * 3 + 2] = -((nodeYs[i] - yLo) / sy - 0.5) * 2 * WORLD_XY;
  }

  // 比例尺：整体均匀缩放（围绕质心），不改变任何距离比例，保真度零损失。
  if (state.scale !== 1.0) {
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < n; i++) {
      cx += xyz[i * 3]; cy += xyz[i * 3 + 1]; cz += xyz[i * 3 + 2];
    }
    cx /= n; cy /= n; cz /= n;
    for (let i = 0; i < n; i++) {
      xyz[i * 3] = cx + (xyz[i * 3] - cx) * state.scale;
      xyz[i * 3 + 1] = cy + (xyz[i * 3 + 1] - cy) * state.scale;
      xyz[i * 3 + 2] = cz + (xyz[i * 3 + 2] - cz) * state.scale;
    }
  }
  return xyz;
}

// 适应画面：按"90% 分位半径"把点云均匀放大到占满视野（全部点仍可见，距离比例不变）
function fitToView() {
  const xyz = normalizeCoords();
  const n = xyz.length / 3;
  let cx = 0, cy = 0, cz = 0;
  for (let i = 0; i < n; i++) {
    cx += xyz[i * 3]; cy += xyz[i * 3 + 1]; cz += xyz[i * 3 + 2];
  }
  cx /= n; cy /= n; cz /= n;
  const rs = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    rs[i] = Math.hypot(xyz[i * 3] - cx, xyz[i * 3 + 1] - cy, xyz[i * 3 + 2] - cz);
  }
  rs.sort();
  const r90 = rs[Math.floor(n * 0.9)] || 1;
  const camDist = camera.position.distanceTo(controls.target);
  const halfView = camDist * Math.tan((camera.fov * Math.PI) / 360); // 垂直半视野
  state.scale = Math.min(5, (0.85 * halfView) / r90);
  $("spread").value = String(state.scale.toFixed(2));
  $("spreadLabel").textContent = state.scale.toFixed(2) + "×";
  rebuildAll();
}

// ---- 重建 ----
function rebuildAll() {
  const n = data.nodeCount;
  const xyz = normalizeCoords();
  const visible = [];
  for (let i = 0; i < n; i++) {
    if (state.onlyValid && !nodeValid[i]) continue;
    if (state.onlyUnique && !nodeUnique[i]) continue;
    if (state.isolated !== null && nodeTrajOf[i] !== state.isolated) continue;
    visible.push(i);
  }
  renderNodeIndex = visible;

  const positions = new Float32Array(visible.length * 3);
  const colors = new Float32Array(visible.length * 3);
  const palette = buildPalette();
  for (let k = 0; k < visible.length; k++) {
    const i = visible[k];
    positions[k * 3] = xyz[i * 3];
    positions[k * 3 + 1] = xyz[i * 3 + 1];
    positions[k * 3 + 2] = xyz[i * 3 + 2];
    const c = nodeColor(i, palette);
    colors[k * 3] = c.r / 255;
    colors[k * 3 + 1] = c.g / 255;
    colors[k * 3 + 2] = c.b / 255;
  }
  setPoints(positions, colors);

  rebuildTrajPaths(xyz);
  rebuildChain(xyz);
  rebuildRoots(xyz);
  rebuildChainClimb(xyz);
  $("stats").textContent =
    `${data.nodeCount.toLocaleString()} 节点 · ${renderNodeIndex.length.toLocaleString()} 可见 · ` +
    `保真度 3D ρ=${data.fidelity.rho3.toFixed(2)} · 2D ρ=${data.fidelity.rho2.toFixed(2)}`;
}

function nodeColor(i, palette) {
  if (state.colorMode === "source") {
    const c = SOURCE_COLORS[nodeOrigins[i]] || GRAY;
    return c;
  }
  if (state.colorMode === "traj") {
    const t = nodeTrajOf[i];
    return t >= 0 && t < palette.length ? palette[t] : DIM_GRAY;
  }
  return viridisColor(scoreRank[i]);
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
    size: 2.4,
    vertexColors: true,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
  });
  pointsMesh = new THREE.Points(geo, mat);
  pointsMesh.frustumCulled = false;
  scene.add(pointsMesh);
}

// ---- 爬山轨迹链（新高点）----
function rebuildTrajPaths(xyz) {
  if (trajPathMesh) {
    scene.remove(trajPathMesh);
    trajPathMesh.geometry.dispose();
    trajPathMesh.material.dispose();
    trajPathMesh = null;
  }
  if (!state.showTrajPaths) return;
  const palette = buildPalette();
  const visibleSet = new Set(renderNodeIndex);
  const pts = [];
  const cols = [];
  for (const tr of data.trajectories.list) {
    if (state.isolated !== null && tr.index !== state.isolated) continue;
    if (state.pathMode === "chain" && !tr.chainPath) continue; // 只有链爬行轨迹
    const path = state.pathMode === "chain"
      ? tr.chainPath
      : (tr.bestPath || tr.path);
    for (let k = 0; k + 1 < path.length; k++) {
      const a = path[k], b = path[k + 1];
      if (!visibleSet.has(a) || !visibleSet.has(b)) continue;
      const c = tr.index < palette.length ? palette[tr.index] : { r: 255, g: 255, b: 255 };
      for (const idx of [a, b]) {
        pts.push(xyz[idx * 3], xyz[idx * 3 + 1], xyz[idx * 3 + 2]);
        cols.push(c.r / 255, c.g / 255, c.b / 255);
      }
    }
  }
  if (!pts.length) return;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(cols), 3));
  const mat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85 });
  trajPathMesh = new THREE.LineSegments(geo, mat);
  trajPathMesh.frustumCulled = false;
  scene.add(trajPathMesh);
}

// ---- NBN 父链 ----
function chainOf(startIdx) {
  const chain = [];
  let cur = startIdx;
  const seen = new Set();
  while (cur >= 0 && cur < nodeParents.length && !seen.has(cur) && chain.length < 80) {
    seen.add(cur);
    chain.push(cur);
    const p = nodeParents[cur];
    if (p < 0 || p === cur) break;
    cur = p;
  }
  return chain;
}

function rebuildChain(xyz) {
  if (chainLineMesh) {
    scene.remove(chainLineMesh);
    chainLineMesh.geometry.dispose();
    chainLineMesh.material.dispose();
    chainLineMesh = null;
  }
  if (chainMarkersMesh) {
    scene.remove(chainMarkersMesh);
    chainMarkersMesh.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) obj.material.dispose();
    });
    chainMarkersMesh = null;
  }
  if (!state.showChain) return;

  let startIdx = -1;
  if (state.chainDropdown) {
    const idx = data.nodes.findIndex((nd) => nd.id === state.chainDropdown);
    if (idx >= 0) startIdx = idx;
  } else if (state.chainFrom >= 0) {
    startIdx = state.chainFrom;
  }
  if (startIdx < 0) return;

  const chain = chainOf(startIdx);

  // 粗红线：Line2（真线宽）—— 标注层，不受"只看唯一/有效"过滤影响
  const linePts = [];
  for (const idx of chain) {
    linePts.push(xyz[idx * 3], xyz[idx * 3 + 1], xyz[idx * 3 + 2]);
  }
  if (linePts.length >= 2) {
    const geo = new LineGeometry();
    geo.setPositions(linePts);
    const mat = new LineMaterial({
      color: 0xff4444,
      linewidth: 4,
      transparent: true,
      opacity: 0.95,
      depthTest: false,
    });
    mat.resolution.set(window.innerWidth, window.innerHeight);
    chainLineMesh = new Line2(geo, mat);
    chainLineMesh.frustumCulled = false;
    scene.add(chainLineMesh);
  }

  // 实体小球标记：起点白，中间红，终点（冠军）亮黄
  const group = new THREE.Group();
  for (let k = 0; k < chain.length; k++) {
    const idx = chain[k];
    const isStart = k === 0;
    const isEnd = k === chain.length - 1;
    const color = isStart ? 0xffffff : isEnd ? 0xffd700 : 0xff4444;
    const radius = isStart ? 4.5 : isEnd ? 6.0 : 3.2;
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 16, 12),
      new THREE.MeshBasicMaterial({ color, depthTest: false }),
    );
    sphere.position.set(xyz[idx * 3], xyz[idx * 3 + 1], xyz[idx * 3 + 2]);
    group.add(sphere);
  }
  chainMarkersMesh = group;
  scene.add(group);
  const endIdx = chain[chain.length - 1];
  const startScore = nodeScores[chain[0]];
  const endScore = nodeScores[endIdx];
  const endName = endIdx === data.nodes.findIndex((nd) => nd.id === data.champion) ? "（冠军）" : "";
  const chainInfo = `父链 ${chain.length} 步：${nodeIds[chain[0]].split("-").pop()} ${startScore.toFixed(4)} → ${nodeIds[endIdx].split("-").pop()} ${endScore.toFixed(4)}${endName}`;
  $("chainInfoEl")?.remove();
  const info = document.createElement("div");
  info.id = "chainInfoEl";
  info.className = "muted";
  info.textContent = chainInfo;
  $("controls").appendChild(info);
}

// ---- 入口星标 ----
function removeChainClimb() {
  for (const key of ["ccPointsMesh", "ccLineMesh", "ccAnchorGroup", "ccParentGroup", "ccLinkMesh"]) {
    const m = eval(key);
    if (m) {
      scene.remove(m);
      if (m.geometry) m.geometry.dispose();
      if (m.material) m.material.dispose();
      if (m.traverse) m.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
      eval(key + " = null");
    }
  }
}

// 链爬过程图层（本次实验）：橙=全部生成节点，红=锚点链，紫=每个锚点的父（目标）
function rebuildChainClimb(xyz) {
  removeChainClimb();
  if (!state.showChainClimb) return;
  const tr = data.trajectories.list.find((t) => Array.isArray(t.chainPath) && t.chainPath.length);
  if (!tr) return;
  const chain = tr.chainPath;
  const parents = tr.chainParents || [];

  // 橙点：本次全部生成节点
  const runPts = [];
  for (const i of tr.path) {
    runPts.push(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
  }
  if (runPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(runPts), 3));
    const m = new THREE.PointsMaterial({ color: 0xf0883e, size: 5, sizeAttenuation: true, transparent: true, opacity: 0.95, depthWrite: false });
    ccPointsMesh = new THREE.Points(g, m);
    ccPointsMesh.frustumCulled = false;
    scene.add(ccPointsMesh);
  }

  // 红线：锚点链（Line2 粗线）
  const chainPts = [];
  for (const i of chain) chainPts.push(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
  if (chainPts.length >= 6) {
    const g = new LineGeometry();
    g.setPositions(chainPts);
    const m = new LineMaterial({ color: 0xff4444, linewidth: 4, transparent: true, opacity: 0.95, depthTest: false });
    m.resolution.set(window.innerWidth, window.innerHeight);
    ccLineMesh = new Line2(g, m);
    ccLineMesh.frustumCulled = false;
    scene.add(ccLineMesh);
  }

  // 红星：锚点（实体球）
  const anchorGroup = new THREE.Group();
  for (const i of chain) {
    const sph = new THREE.Mesh(new THREE.SphereGeometry(4.0, 16, 12), new THREE.MeshBasicMaterial({ color: 0xff2222, depthTest: false }));
    sph.position.set(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
    anchorGroup.add(sph);
  }
  ccAnchorGroup = anchorGroup;
  scene.add(anchorGroup);

  // 紫菱 + 虚线：每个锚点的父（目标）
  const parentGroup = new THREE.Group();
  const linkPts = [];
  for (let k = 0; k < chain.length; k++) {
    const pi = parents[k];
    if (pi === undefined || pi === null || pi < 0) continue;
    const sph = new THREE.Mesh(new THREE.SphereGeometry(3.2, 16, 12), new THREE.MeshBasicMaterial({ color: 0xa371f7, depthTest: false }));
    sph.position.set(xyz[pi * 3], xyz[pi * 3 + 1], xyz[pi * 3 + 2]);
    parentGroup.add(sph);
    const a = chain[k];
    linkPts.push(xyz[a * 3], xyz[a * 3 + 1], xyz[a * 3 + 2], xyz[pi * 3], xyz[pi * 3 + 1], xyz[pi * 3 + 2]);
  }
  ccParentGroup = parentGroup;
  scene.add(parentGroup);
  if (linkPts.length) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(linkPts), 3));
    const m = new THREE.LineBasicMaterial({ color: 0xa371f7, transparent: true, opacity: 0.6 });
    ccLinkMesh = new THREE.LineSegments(g, m);
    ccLinkMesh.frustumCulled = false;
    scene.add(ccLinkMesh);
  }
}

function rebuildRoots(xyz) {
  if (rootsMesh) {
    scene.remove(rootsMesh);
    rootsMesh.geometry.dispose();
    rootsMesh.material.dispose();
    rootsMesh = null;
  }
  if (!state.showRoots) return;
  const visibleSet = new Set(renderNodeIndex);
  const palette = buildPalette();
  const pts = [];
  const cols = [];
  for (const tr of data.trajectories.list) {
    if (state.isolated !== null && tr.index !== state.isolated) continue;
    const idx = tr.path[0];
    if (idx === undefined || !visibleSet.has(idx)) continue;
    const c = tr.index < palette.length ? palette[tr.index] : { r: 255, g: 255, b: 255 };
    pts.push(xyz[idx * 3], xyz[idx * 3 + 1], xyz[idx * 3 + 2]);
    cols.push(c.r / 255, c.g / 255, c.b / 255);
  }
  if (!pts.length) return;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(cols), 3));
  const mat = new THREE.PointsMaterial({
    size: 11, vertexColors: true, sizeAttenuation: true, transparent: true, depthWrite: false,
  });
  rootsMesh = new THREE.Points(geo, mat);
  rootsMesh.frustumCulled = false;
  scene.add(rootsMesh);
}

// ---- 图例 ----
function updateLegend() {
  const title = $("legendTitle");
  const listEl = $("legendList");
  listEl.innerHTML = "";
  const palette = buildPalette();

  if (state.colorMode === "source") {
    title.textContent = "按来源";
    $("scoreBar").classList.add("hidden");
    for (const [key, c] of Object.entries(SOURCE_COLORS)) {
      const count = data.nodes.filter((nd) => (nd.origin || "") === key).length;
      const item = document.createElement("div");
      item.className = "legend-item";
      item.innerHTML = `
        <span class="swatch" style="background: rgb(${c.r},${c.g},${c.b})"></span>
        <span class="legend-main">${SOURCE_LABELS[key] || key}</span>
        <span class="legend-sub">${count.toLocaleString()} 个</span>
      `;
      listEl.appendChild(item);
    }
    return;
  }

  if (state.colorMode === "traj") {
    title.textContent = "爬山轨迹（点击隔离）";
    $("scoreBar").classList.add("hidden");
    for (const tr of data.trajectories.list) {
      const c = tr.index < palette.length ? palette[tr.index] : { r: 255, g: 255, b: 255 };
      const item = document.createElement("div");
      item.className = "legend-item" + (state.isolated === tr.index ? " active" : "") + (state.isolated !== null && state.isolated !== tr.index ? " dim" : "");
      const shortEntry = tr.entry.length > 42 ? tr.entry.slice(0, 42) + "…" : tr.entry;
      item.innerHTML = `
        <span class="swatch" style="background: rgb(${c.r},${c.g},${c.b})"></span>
        <span class="legend-main">#${String(tr.index).padStart(2, "0")} ${tr.session}</span>
        <span class="legend-sub">${shortEntry} · ${tr.nodeCount} 节点 · best ${tr.best != null ? Number(tr.best).toFixed(4) : "—"}</span>
      `;
      item.title = `入口: ${tr.entry}\n判定: ${tr.verdict || "—"}`;
      item.addEventListener("click", () => {
        state.isolated = state.isolated === tr.index ? null : tr.index;
        state.colorMode = "traj";
        $("colorMode").value = "traj";
        rebuildAll();
        updateLegend();
      });
      listEl.appendChild(item);
    }
    return;
  }

  // score 模式
  title.textContent = "按分数";
  $("scoreBar").classList.remove("hidden");
  const grad = $("scoreGradient");
  grad.style.background =
    `linear-gradient(90deg, rgb(${VIRIDIS_STOPS[0].join(",")}), rgb(${VIRIDIS_STOPS[4].join(",")}), rgb(${VIRIDIS_STOPS[9].join(",")}))`;
  const stats = document.createElement("div");
  stats.className = "muted";
  stats.textContent =
    `有效解 ${data.fidelity ? "" : ""}分数范围：0.0000 – ${data.nodes.length ? Math.max(...data.nodes.map((nd) => Number(nd.score) || 0)).toFixed(4) : "—"}`;
  listEl.appendChild(stats);
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
  const t = nodeTrajOf[nodeIdx];
  const trajInfo = t >= 0 ? ` · 轨迹 #${t}` : "";
  tip.innerHTML = `
    <div class="tt-id">${nodeIds[nodeIdx]}</div>
    <div class="tt-row">分数 <b>${nodeScores[nodeIdx].toFixed(6)}</b> · 来源 ${nodeOrigins[nodeIdx] || "—"}${trajInfo}</div>
    <div class="tt-row">算子 ${nodeOps[nodeIdx] || "—"} · revision ${nodeRevs[nodeIdx] || "—"}</div>
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
  const t = nodeTrajOf[hoveredIndex];
  if (t < 0) return;
  state.isolated = state.isolated === t ? null : t;
  state.colorMode = "traj";
  $("colorMode").value = "traj";
  rebuildAll();
  updateLegend();
}

async function selectNode(nodeIdx) {
  selectedNode = nodeIdx;
  // 自动追父链
  state.chainFrom = nodeIdx;
  state.chainDropdown = "";
  $("chainSelect").value = "";
  rebuildChain(normalizeCoords());

  const t = nodeTrajOf[nodeIdx];
  const groupInfo = t >= 0 ? `轨迹 #${t}` : "非轨迹节点";
  const panel = $("detail");
  panel.style.display = "flex";
  $("detailTitle").textContent = nodeIds[nodeIdx];
  $("detailMeta").textContent = `分数 ${nodeScores[nodeIdx].toFixed(6)} · ${groupInfo} · 来源 ${nodeOrigins[nodeIdx] || "—"} · 算子 ${nodeOps[nodeIdx] || "—"} · revision ${nodeRevs[nodeIdx] || "—"}`;
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
  $("colorMode").addEventListener("change", (e) => {
    state.colorMode = e.target.value;
    state.isolated = null;
    rebuildAll();
    updateLegend();
  });
  $("chainSelect").addEventListener("change", (e) => {
    state.chainDropdown = e.target.value;
    state.chainFrom = -1;
    rebuildChain(normalizeCoords());
  });
  $("zMode").addEventListener("change", (e) => {
    state.zMode = e.target.value;
    rebuildAll();
  });
  $("spread").addEventListener("input", (e) => {
    state.scale = Number(e.target.value);
    $("spreadLabel").textContent = state.scale.toFixed(2) + "×";
    rebuildAll();
  });
  $("fitView").addEventListener("click", fitToView);
  $("onlyValid").addEventListener("change", (e) => {
    state.onlyValid = e.target.checked;
    rebuildAll();
  });
  $("onlyUnique").addEventListener("change", (e) => {
    state.onlyUnique = e.target.checked;
    rebuildAll();
  });
  $("showTrajPaths").addEventListener("change", (e) => {
    state.showTrajPaths = e.target.checked;
    rebuildAll();
  });
  $("pathMode").addEventListener("change", (e) => {
    state.pathMode = e.target.value;
    rebuildAll();
  });
  $("showChain").addEventListener("change", (e) => {
    state.showChain = e.target.checked;
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
    camera.position.set(140, 90, 620);
    controls.target.set(0, 0, 0);
    controls.update();
  });
  $("resetIsolation").addEventListener("click", () => {
    state.isolated = null;
    rebuildAll();
    updateLegend();
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
