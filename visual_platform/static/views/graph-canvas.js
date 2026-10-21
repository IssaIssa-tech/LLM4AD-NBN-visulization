import { clearElement, el } from "../core/dom.js";
import * as THREE from "three";
import { TrackballControls } from "three/addons/controls/TrackballControls.js";

// World-space half-extents for normalized node layout (centered at origin)
const WORLD_XY = 220;
const WORLD_Z = 130;

function numericValue(value) {
  const next = Number(value);
  return Number.isFinite(next) ? next : null;
}

function nodeScore(node) {
  // score/rawScore may be null for imported history; fall back to OFEC fitness.
  return numericValue(node?.rawScore) ?? numericValue(node?.score) ?? numericValue(node?.ofecFitness);
}

// Viridis colormap (matplotlib standard): perceptually uniform, colorblind-safe.
// Node color AND radius are both driven by dense score RANK, so a single monster
// outlier score (e.g. -1e208) can never flatten the whole gradient.
const VIRIDIS_STOPS = [
  [68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142],
  [31, 158, 137], [53, 183, 121], [110, 206, 88], [181, 222, 43], [253, 231, 37],
];

function viridisColor(ratio) {
  const t = Number.isFinite(ratio) ? Math.max(0, Math.min(1, ratio)) : 0;
  const pos = t * (VIRIDIS_STOPS.length - 1);
  const i = Math.min(VIRIDIS_STOPS.length - 2, Math.floor(pos));
  const u = pos - i;
  const a = VIRIDIS_STOPS[i];
  const b = VIRIDIS_STOPS[i + 1];
  return {
    r: Math.round(a[0] + (b[0] - a[0]) * u),
    g: Math.round(a[1] + (b[1] - a[1]) * u),
    b: Math.round(a[2] + (b[2] - a[2]) * u),
  };
}

// External expert nodes keep their score-driven viridis color and are marked
// with a yellow halo instead of a special node color (toggleable).
const EXPERT_HALO_COLOR = { r: 245, g: 197, b: 24 };
const NEIGHBORHOOD_COLOR = { r: 56, g: 189, b: 248 };
const NEIGHBORHOOD_ANCHOR_COLOR = { r: 192, g: 132, b: 252 };

// Transient selection overlay for task-basket members (bright white ring + scale).
const BASKET_HIGHLIGHT_COLOR = { r: 255, g: 255, b: 255 };

// Nodes without any usable score are painted slate gray so they never
// masquerade as mid-score solutions.
const UNSCORED_COLOR = { r: 100, g: 116, b: 139 };

// Z-axis mode cycle: score height -> score-rank height -> tree-depth height.
// (Coloring is always the viridis score gradient now, so the old fourth
// "tree + score color" mode became redundant and was merged into "tree".)
const Z_MODES = ["score", "rank", "tree"];
const Z_MODE_LABELS = {
  score: "Z轴：分数",
  rank: "Z轴：排名",
  tree: "Z轴：树形",
};

function isExternalNode(node) {
  return (
    node?.originKind === "external_expert" ||
    node?.sourceKind === "external_expert" ||
    node?.hasExternalExpert === true
  );
}

// Robust bounds for the low-score filter slider: 1st percentile .. true max.
// Garbage magnitudes (|score| > 1e6) are excluded so they cannot stretch it.
function computeHideSliderBounds(nodes) {
  const scores = nodes
    .map(nodeScore)
    .filter((s) => Number.isFinite(s) && Math.abs(s) <= 1e6)
    .sort((a, b) => a - b);
  if (!scores.length) return null;
  const min = scores[Math.floor(scores.length * 0.01)];
  const max = scores[scores.length - 1];
  if (!(max > min)) return null;
  return { min, max };
}

function radiusForRatio(ratio) {
  const t = Number.isFinite(ratio) ? Math.max(0, Math.min(1, ratio)) : 0.5;
  return 2.6 + t * 5.4;
}

// Dense score rank per node: distinct scores are evenly spaced in (0, 1] so
// clustered high scores get pulled apart instead of squeezing into one layer.
// Nodes without a usable score map to null (callers decide floor/gray).
function computeScoreRankMap(nodes) {
  const distinct = [...new Set(nodes.map(nodeScore).filter(Number.isFinite))].sort((a, b) => a - b);
  const rankOf = new Map(distinct.map((score, index) => [score, (index + 1) / distinct.length]));
  const map = new Map();
  for (const node of nodes) {
    const s = nodeScore(node);
    map.set(node.id, Number.isFinite(s) ? rankOf.get(s) : null);
  }
  return map;
}

// Node Z accessor: "score" uses the score-derived Z (default), "rank" uses the
// dense score rank, "tree" uses the cone-tree depth Z (zTree).
// Old artifacts without zTree fall back to z.
function nodeZValue(node, zMode, rankMap) {
  if (zMode === "tree") {
    const zt = numericValue(node.zTree);
    if (zt !== null) return zt;
  }
  if (zMode === "rank" && rankMap) {
    const rank = rankMap.get(node.id);
    return rank == null ? 0 : rank;
  }
  const z = numericValue(node.z);
  return z === null ? 0 : z;
}

// Normalize node coordinates into a centered world-space box [-WORLD_XY, WORLD_XY] etc.
function computePositions3D(nodes, zMode = "score", rankMap = null) {
  const withCoordinates = nodes.filter((node) => numericValue(node.x) !== null && numericValue(node.y) !== null);
  if (withCoordinates.length >= 2) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (const node of withCoordinates) {
      const x = Number(node.x), y = Number(node.y), z = nodeZValue(node, zMode, rankMap);
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const spanZ = Math.max(1, maxZ - minZ);
    const map = new Map();
    for (const node of nodes) {
      const x = numericValue(node.x), y = numericValue(node.y);
      if (x === null || y === null) { map.set(node.id, null); continue; }
      const z = nodeZValue(node, zMode, rankMap);
      map.set(node.id, {
        x: ((x - minX) / spanX - 0.5) * 2 * WORLD_XY,
        y: -((y - minY) / spanY - 0.5) * 2 * WORLD_XY,
        z: ((z - minZ) / spanZ - 0.5) * 2 * WORLD_Z,
      });
    }
    return map;
  }
  const radius = WORLD_XY * 0.8;
  return new Map(nodes.map((node, i) => {
    const a = (Math.PI * 2 * i) / Math.max(nodes.length, 1);
    return [node.id, { x: Math.cos(a) * radius, y: Math.sin(a) * radius, z: 0 }];
  }));
}

function buildGraphSignature(nodes, edges) {
  const nodePart = nodes
    .map((node) => {
      const x = numericValue(node.x);
      const y = numericValue(node.y);
      const z = numericValue(node.z);
      const score = nodeScore(node);
      return [
        node.id,
        x === null ? "" : x,
        y === null ? "" : y,
        z === null ? "" : z,
        Number.isFinite(score) ? score : "",
      ].join(":");
    })
    .join("|");
  const edgePart = edges
    .map((edge) => `${edge.source}->${edge.target}`)
    .join("|");
  return `${nodes.length}#${edges.length}#${nodePart}#${edgePart}`;
}

function favoriteIdsKey(favoriteNodeIds) {
  return [...favoriteNodeIds].sort().join(",");
}

function createHaloTexture() {
  const size = 128;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  // Softer, capped alpha so close-up zoom never washes out to solid white
  grad.addColorStop(0, "rgba(255,255,255,0.5)");
  grad.addColorStop(0.35, "rgba(255,255,255,0.18)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

export function createGraphCanvasView(container, callbacks) {
  let _legendClosed = false;
  let _spread = 1;
  let _showEdges = true;
  let _zMode = "score"; // "score" | "rank" | "tree" （见 Z_MODE_LABELS）
  let _hideBelow = null; // 低分过滤阈值；null=不过滤。生效时 score=None 也一并隐藏
  let _hideBounds = null; // 当前图的滑条范围 { min, max }（随图数据刷新）
  let _showExpertHalo = true; // 给外部专家解叠加黄色光环标记
  let lastNodesRef = null;
  let lastEdgesRef = null;

  // --- Persistent Three.js state (survives across render() calls, created lazily once) ---
  let renderer = null, scene = null, camera = null, controls = null, canvasEl = null;
  let contentGroup = null, nodesMesh = null, edgesLines = null, haloGroup = null;
  let resizeObserver = null;
  let observedViewportEl = null;
  let nodeIndexList = [];
  let nodeBase = []; // { id, x, y, z, radius, color:{r,g,b} }
  let edgeBasePositions = null;
  let lastSelectedNodeId = null;
  let lastFavoriteNodeIds = new Set();
  let lastBasketNodeIds = new Set();
  let lastRegionSelection = null;
  let lastNeighborhoodIds = new Set();
  let lastNeighborhoodAnchorId = null;
  let lastFocusedNeighborhoodAnchor = null;
  let lastVisualKey = null;
  let pointerDownPos = null;
  let dragMoved = false;
  const raycaster = new THREE.Raycaster();
  const pointerNdc = new THREE.Vector2();

  const sphereGeometry = new THREE.SphereGeometry(1, 14, 10);
  // NOTE: do NOT enable vertexColors here. The sphere geometry has no per-vertex
  // color attribute, so vertexColors:true makes the shader read a (0,0,0) color
  // and multiplies every instance to black. Per-instance colors are supplied via
  // InstancedMesh.setColorAt (instanceColor), which works without vertexColors.
  const sphereMaterial = new THREE.MeshStandardMaterial({
    roughness: 0.5,
    metalness: 0.05,
  });
  const edgeMaterial = new THREE.LineBasicMaterial({
    color: 0x8fb1ff, transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const regionEdgeMaterial = new THREE.LineBasicMaterial({
    color: 0xff4d8d, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  let haloTexture = null;
  let regionEdgeLine = null;
  let lastRendererSize = { w: 0, h: 0 };
  let lastGraphSignature = null;
  let lastDataSignature = null; // 仅图数据部分的签名：变化时才允许重置相机
  let shellEl = null;
  let headerCaptionEl = null;
  let headerActionsEl = null;
  let viewportEl = null;
  let overlayHostEl = null;
  let legendEl = null;
  let hintEl = null;
  let spreadControlEl = null;
  let spreadSliderEl = null;
  let spreadValueEl = null;
  let hideSliderEl = null;
  let hideValueEl = null;
  let expertHaloCheckboxEl = null;

  // View-option signature: same graph data + different z-mode / low-score filter
  // must be treated as a different scene (structural rebuild without camera reset).
  function viewSignature(dataSignature) {
    return `${_zMode}|hb:${_hideBelow === null ? "off" : _hideBelow.toFixed(4)}@${dataSignature}`;
  }

  // Coalesce slider-drag rebuilds to one per animation frame (16k nodes each).
  let viewRebuildScheduled = false;
  function scheduleViewRebuild() {
    if (viewRebuildScheduled) return;
    viewRebuildScheduled = true;
    requestAnimationFrame(() => {
      viewRebuildScheduled = false;
      if (!lastNodesRef) return;
      rebuildGraph(lastNodesRef, lastEdgesRef || [], { resetCamera: false });
      lastGraphSignature = viewSignature(buildGraphSignature(lastNodesRef, lastEdgesRef || []));
      applyVisualState(lastSelectedNodeId, lastFavoriteNodeIds, lastBasketNodeIds);
    });
  }

  function projectToScreen(v, rect) {
    const projected = v.clone().project(camera);
    return {
      x: ((projected.x + 1) / 2) * rect.width,
      y: ((-projected.y + 1) / 2) * rect.height,
    };
  }

  function pointSegmentDistance(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    let t = 0;
    if (lenSq > 1e-9) {
      t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
    }
    const cx = ax + t * dx, cy = ay + t * dy;
    return Math.hypot(px - cx, py - cy);
  }

  function pickEdge(event) {
    if (!camera || !lastEdgesRef || !lastEdgesRef.length || !nodeBase.length) {
      return null;
    }
    const rect = canvasEl.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      return null;
    }
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    const spread = Math.max(0.15, _spread);
    const byId = new Map(nodeBase.map((base) => [base.id, { x: base.x * spread, y: base.y * spread, z: base.z * spread }]));
    const va = new THREE.Vector3();
    const vb = new THREE.Vector3();
    let best = null;
    let bestDistance = Infinity;
    for (const edge of lastEdgesRef) {
      const a = byId.get(edge.source);
      const b = byId.get(edge.target);
      if (!a || !b) {
        continue;
      }
      const pa = projectToScreen(va.set(a.x, a.y, a.z), rect);
      const pb = projectToScreen(vb.set(b.x, b.y, b.z), rect);
      const length = Math.hypot(pb.x - pa.x, pb.y - pa.y);
      // Extremely short on-screen segments are effectively a single node; do
      // not let them hijack node clicks.
      if (length < 8) {
        continue;
      }
      const distance = pointSegmentDistance(mx, my, pa.x, pa.y, pb.x, pb.y);
      if (distance <= 10 && distance < bestDistance) {
        bestDistance = distance;
        best = { source: edge.source, target: edge.target, distance: edge.distance };
      }
    }
    return best;
  }

  function handlePick(event) {
    if (!nodesMesh || !camera) return;
    const rect = canvasEl.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    pointerNdc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointerNdc.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointerNdc, camera);
    const hits = raycaster.intersectObject(nodesMesh);
    if (hits.length && hits[0].instanceId != null) {
      const node = nodeIndexList[hits[0].instanceId];
      if (node) {
        callbacks.onSelectNode(node.id);
      }
      return;
    }
    const edge = pickEdge(event);
    if (edge && typeof callbacks.onSelectRegion === "function") {
      callbacks.onSelectRegion({
        type: "edge",
        a: edge.source,
        b: edge.target,
        distance: edge.distance,
      });
    }
  }

  function ensureScene() {
    if (renderer) return;

    const bgColor = 0x161f36;
    scene = new THREE.Scene();
    scene.background = new THREE.Color(bgColor);
    // Gentle linear fog that only kicks in well beyond the default framing distance
    // (default distance ~490, maxDistance 2400) so normal zoom/pan never gets obscured.
    scene.fog = new THREE.Fog(bgColor, 1400, 2800);

    camera = new THREE.PerspectiveCamera(50, 1, 1, 6000);
    camera.position.set(0, 90, 480);

    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(bgColor, 1);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    canvasEl = renderer.domElement;
    canvasEl.className = "graph-canvas";
    canvasEl.style.cursor = "grab";

    scene.add(new THREE.HemisphereLight(0xdbe8ff, 0x223052, 0.82));
    scene.add(new THREE.AmbientLight(0xb6cbef, 1.05));
    const key = new THREE.DirectionalLight(0xffffff, 1.45);
    key.position.set(180, 260, 220);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x8fb1ff, 0.7);
    fill.position.set(-220, -140, -180);
    scene.add(fill);

    contentGroup = new THREE.Group();
    scene.add(contentGroup);

    // TrackballControls gives an arcball / "grab the ball and spin it" rotation:
    // left-right drag always rotates around the screen vertical axis and up-down
    // around the screen horizontal axis, tracking the cursor 1:1. Unlike
    // OrbitControls it has no fixed world "up" axis, so the view never flips over
    // when combining horizontal and vertical rotation.
    controls = new TrackballControls(camera, canvasEl);
    controls.rotateSpeed = 2.2;
    controls.zoomSpeed = 1.1;
    controls.panSpeed = 0.8;
    // Light inertial damping so the view keeps following instead of stopping dead.
    controls.staticMoving = false;
    controls.dynamicDampingFactor = 0.12;
    controls.minDistance = 40;
    controls.maxDistance = 2400;
    controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    // Disable the A/S/D keyboard mode shortcuts so they never swallow key presses
    // meant for the rest of the page.
    controls.keys = [];

    haloTexture = createHaloTexture();

    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });

    canvasEl.addEventListener("pointerdown", (e) => {
      pointerDownPos = { x: e.clientX, y: e.clientY };
      dragMoved = false;
      canvasEl.style.cursor = "grabbing";
    });
    canvasEl.addEventListener("pointermove", (e) => {
      if (!pointerDownPos) return;
      if (Math.abs(e.clientX - pointerDownPos.x) > 3 || Math.abs(e.clientY - pointerDownPos.y) > 3) {
        dragMoved = true;
      }
    });
    window.addEventListener("pointerup", (e) => {
      if (pointerDownPos && !dragMoved) {
        handlePick(e);
      }
      pointerDownPos = null;
      canvasEl.style.cursor = "grab";
    });
    canvasEl.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  function attachResize(viewportEl) {
    if (!renderer || !camera || !viewportEl) {
      return;
    }
    if (resizeObserver && observedViewportEl === viewportEl) {
      return;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
    observedViewportEl = viewportEl;
    const sync = () => {
      const w = Math.max(1, viewportEl.clientWidth);
      const h = Math.max(1, viewportEl.clientHeight);
      if (w === lastRendererSize.w && h === lastRendererSize.h) {
        return;
      }
      lastRendererSize = { w, h };
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      // TrackballControls caches the canvas screen rect for its pointer math;
      // it must be refreshed whenever the viewport resizes or rotation drifts.
      if (controls && typeof controls.handleResize === "function") {
        controls.handleResize();
      }
    };
    resizeObserver = new ResizeObserver(sync);
    resizeObserver.observe(viewportEl);
    sync();
  }

  function buildOverlayCard(title, message, buttonText = null, actionName = null, disabled = false) {
    const overlay = el("div", { className: "graph-empty-overlay" });
    const children = [
      el("h3", { text: title }),
      el("p", { text: message }),
    ];
    if (buttonText && actionName) {
      children.push(el("button", {
        className: "primary-button",
        text: buttonText,
        dataset: { action: actionName },
        attrs: { type: "button", disabled },
      }));
    }
    overlay.appendChild(el("div", { className: "graph-empty-card" }, children));
    return overlay;
  }

  function ensureDom() {
    if (shellEl) {
      return;
    }
    clearElement(container);

    headerCaptionEl = el("div", { className: "graph-header-caption" });
    headerActionsEl = el("div", { className: "graph-header-actions" });
    const header = el("div", { className: "graph-header" }, [
      el("div", { className: "graph-header-left" }, [
        el("div", { className: "graph-header-title" }, [
          el("h2", { text: "历史解nbn图" }),
          headerCaptionEl,
        ]),
      ]),
      headerActionsEl,
    ]);

    overlayHostEl = el("div");
    legendEl = el("div", { className: `graph-legend${_legendClosed ? " collapsed" : ""}` }, [
      el("h4", {}, [
        el("span", { text: "图例" }),
        el("button", {
          className: "legend-close",
          dataset: { action: "close-legend" },
          attrs: { type: "button", "aria-label": "关闭图例" },
          text: "✕",
        }),
      ]),
      el("div", { className: "legend-grid" }, [
        el("div", { className: "legend-item legend-item--wide" }, [
          el("span", { className: "legend-bar", attrs: { style: "background:linear-gradient(90deg,#440154,#31688e,#26828e,#35b779,#fde725)" } }),
          el("span", { text: "颜色/大小 = 分数排名 低→高" }),
        ]),
        el("div", { className: "legend-item" }, [
          el("span", { className: "legend-dot", attrs: { style: "background:#64748b" } }),
          el("span", { text: "无分数" }),
        ]),
        el("div", { className: "legend-item" }, [
          el("span", { className: "legend-dot", attrs: { style: "background:transparent;border:2px solid #f5c518;box-shadow:0 0 6px rgba(245,197,24,0.8)" } }),
          el("span", { text: "外部专家（光环）" }),
        ]),
        el("div", { className: "legend-item" }, [
          el("span", { className: "legend-dot", attrs: { style: "background:#13b8c8" } }),
          el("span", { text: "收藏" }),
        ]),
        el("div", { className: "legend-item" }, [
          el("span", { className: "legend-dot", attrs: { style: "background:#ffffff;border:1px solid #94a3b8" } }),
          el("span", { text: "任务篮" }),
        ]),
        el("div", { className: "legend-item" }, [
          el("span", { className: "legend-dot", attrs: { style: "background:#ff4d8d" } }),
          el("span", { text: "选中" }),
        ]),
      ]),
    ]);

    hintEl = el("div", { className: "graph-controls-hint" }, [
      el("span", { text: "左键拖拽=旋转  右键拖拽=平移  滚轮=缩放  点节点=选中  点连边=选区域" }),
    ]);

    spreadValueEl = el("strong", { className: "spread-value", text: `${_spread.toFixed(1)}x` });
    spreadSliderEl = el("input", {
      type: "range",
      value: String(_spread),
      attrs: { min: "0.5", max: "6", step: "0.1" },
      on: {
        input: (event) => {
          const next = Number(event.target.value);
          if (!Number.isFinite(next)) {
            return;
          }
          _spread = next;
          spreadValueEl.textContent = `${_spread.toFixed(1)}x`;
          lastVisualKey = null;
          applyVisualState(lastSelectedNodeId, lastFavoriteNodeIds, lastBasketNodeIds, lastRegionSelection);
        },
      },
    });
    const spreadRow = el("div", { className: "spread-row" }, [
      el("span", { className: "spread-label", text: "节点间距" }),
      spreadSliderEl,
      spreadValueEl,
    ]);

    // Low-score filter: slider leftmost = show everything (incl. unscored);
    // any position to the right hides unscored nodes plus score < threshold.
    hideValueEl = el("strong", { className: "spread-value", text: "关" });
    hideSliderEl = el("input", {
      type: "range",
      value: "0",
      attrs: { min: "0", max: "1", step: "0.01" },
      on: {
        input: (event) => {
          const raw = Number(event.target.value);
          if (!Number.isFinite(raw) || !_hideBounds) return;
          _hideBelow = raw <= _hideBounds.min ? null : raw;
          hideValueEl.textContent = _hideBelow === null ? "关" : `<${_hideBelow.toFixed(2)}`;
          scheduleViewRebuild();
        },
      },
    });
    expertHaloCheckboxEl = el("input", {
      type: "checkbox",
      on: {
        change: (event) => {
          _showExpertHalo = Boolean(event.target.checked);
          lastVisualKey = null;
          applyVisualState(lastSelectedNodeId, lastFavoriteNodeIds, lastBasketNodeIds, lastRegionSelection);
        },
      },
    });
    expertHaloCheckboxEl.checked = _showExpertHalo;
    const hideRow = el("div", { className: "spread-row" }, [
      el("span", { className: "spread-label", text: "隐藏低分" }),
      hideSliderEl,
      hideValueEl,
      el("label", { className: "hide-unscored-toggle", attrs: { title: "给外部专家解叠加黄色光环标记" } }, [
        expertHaloCheckboxEl,
        el("span", { text: "专家光环" }),
      ]),
    ]);
    const locateInputEl = el("input", {
      className: "graph-locate-input",
      attrs: { type: "text", placeholder: "节点 ID（回车定位）", spellcheck: "false" },
    });
    const locateButtonEl = el("button", {
      className: "ghost-button",
      text: "定位",
      dataset: { action: "locate-node" },
      attrs: { type: "button" },
    });
    const locateRow = el("div", { className: "spread-row locate-row" }, [
      el("span", { className: "spread-label", text: "定位节点" }),
      locateInputEl,
      locateButtonEl,
    ]);
    locateInputEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        locateNodeById(locateInputEl.value, locateButtonEl);
      }
    });
    spreadControlEl = el("div", { className: "graph-spread-control" }, [spreadRow, hideRow, locateRow]);

    viewportEl = el("div", { className: "graph-viewport" }, [
      legendEl,
      hintEl,
      spreadControlEl,
      overlayHostEl,
    ]);

    const viewportWrap = el("div", { className: "graph-viewport-wrap" }, [viewportEl]);
    shellEl = el("div", { className: "graph-shell" }, [header, viewportWrap]);
    container.appendChild(shellEl);
  }

  function renderHeader(state, graphArtifacts, currentRevisionId, selectedArtifactId) {
    headerCaptionEl.textContent = currentRevisionId
      ? `revision ${currentRevisionId} · artifact ${selectedArtifactId || "未选择"}`
      : "请先选择 revision 来加载图谱";

    clearElement(headerActionsEl);
    if (graphArtifacts.length) {
      headerActionsEl.appendChild(el("div", { className: "chip-list" }, graphArtifacts.map((artifact) => (
        el("button", {
          className: `chip-button${artifact.artifactId === selectedArtifactId ? " active" : ""}`,
          text: `${artifact.artifactRole || "graph"} · ${artifact.status}`,
          dataset: { action: "select-artifact", artifactId: artifact.artifactId },
          attrs: { type: "button" },
        })
      ))));
    } else {
      headerActionsEl.appendChild(el("span", { className: "muted-text", text: "无 artifact" }));
    }
    headerActionsEl.appendChild(el("button", {
      className: "secondary-button",
      text: state.page.loading.graph ? "加载中..." : "加载图谱",
      dataset: { action: "request-graph" },
      attrs: { type: "button", disabled: !currentRevisionId || state.page.loading.graph },
    }));
    headerActionsEl.appendChild(el("button", {
      className: "ghost-button",
      text: _showEdges ? "隐藏连边" : "显示连边",
      dataset: { action: "toggle-edges" },
      attrs: { type: "button" },
    }));
    headerActionsEl.appendChild(el("button", {
      className: "ghost-button",
      text: Z_MODE_LABELS[_zMode] || Z_MODE_LABELS.score,
      dataset: { action: "toggle-zmode" },
      attrs: { type: "button", title: "循环切换高度语义：分数 / 排名 / 树形（旧图无树深度数据时退回分数高度）" },
    }));
    headerActionsEl.appendChild(el("button", {
      className: "ghost-button",
      text: "定位最高分",
      dataset: { action: "locate-best" },
      attrs: { type: "button", title: "选中全图分数最高的节点并把相机飞过去" },
    }));
    headerActionsEl.appendChild(el("button", {
      className: "ghost-button",
      text: "提交构图",
      dataset: { action: "build-graph" },
      attrs: { type: "button", disabled: !currentRevisionId },
    }));
  }

  function setOverlay(overlayNode = null) {
    clearElement(overlayHostEl);
    if (overlayNode) {
      overlayHostEl.appendChild(overlayNode);
    }
  }

  function setGraphVisible(visible) {
    hintEl.hidden = !visible;
    spreadControlEl.hidden = !visible;
    if (canvasEl) {
      if (canvasEl.parentNode !== viewportEl) {
        viewportEl.insertBefore(canvasEl, overlayHostEl);
        // TrackballControls caches the canvas rect in its constructor, when the
        // canvas is still detached (size 0). Refresh it now that the canvas is in
        // the DOM, otherwise its rotation math divides by a zero width and the
        // view cannot be dragged at all.
        if (controls && typeof controls.handleResize === "function") {
          controls.handleResize();
        }
      }
      canvasEl.style.visibility = visible ? "visible" : "hidden";
    }
  }

  function syncLegendState() {
    if (legendEl) {
      legendEl.classList.toggle("collapsed", _legendClosed);
    }
  }

  function syncEdgeVisibility() {
    if (edgesLines) {
      edgesLines.visible = _showEdges;
    }
  }

  // Structural rebuild: called only when the graph payload or view options change.
  // resetCamera=false keeps the current viewpoint (z-mode switch / filter drag).
  function rebuildGraph(allNodes, allEdges, { resetCamera = true } = {}) {
    if (nodesMesh) { contentGroup.remove(nodesMesh); nodesMesh.dispose(); nodesMesh = null; }
    if (edgesLines) { contentGroup.remove(edgesLines); edgesLines.geometry.dispose(); edgesLines = null; }
    if (regionEdgeLine) { contentGroup.remove(regionEdgeLine); regionEdgeLine.geometry.dispose(); regionEdgeLine = null; }
    if (haloGroup) {
      haloGroup.children.forEach((sprite) => sprite.material.dispose());
      contentGroup.remove(haloGroup);
      haloGroup = null;
    }
    edgeBasePositions = null;

    let nodes = allNodes;
    let edges = allEdges;
    if (_hideBelow !== null) {
      nodes = allNodes.filter((node) => {
        const s = nodeScore(node);
        return Number.isFinite(s) && s >= _hideBelow;
      });
      const visibleIds = new Set(nodes.map((node) => node.id));
      edges = allEdges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
    }

    // Rank drives color, radius and the "rank" z-mode; outlier-proof by design.
    const rankMap = computeScoreRankMap(nodes);
    const positions = computePositions3D(nodes, _zMode, rankMap);

    nodeIndexList = nodes.slice();
    nodeBase = nodes.map((node) => {
      const p = positions.get(node.id) || { x: 0, y: 0, z: 0 };
      const rank = rankMap.get(node.id);
      return {
        id: node.id,
        x: p.x, y: p.y, z: p.z,
        radius: radiusForRatio(rank == null ? 0 : rank),
        color: rank == null ? UNSCORED_COLOR : viridisColor(rank),
        isExpert: isExternalNode(node),
      };
    });

    const count = nodeBase.length;
    nodesMesh = new THREE.InstancedMesh(sphereGeometry, sphereMaterial, count);
    contentGroup.add(nodesMesh);
    for (let i = 0; i < count; i++) {
      const base = nodeBase[i];
      nodesMesh.setColorAt(i, new THREE.Color(base.color.r / 255, base.color.g / 255, base.color.b / 255));
    }
    if (nodesMesh.instanceColor) {
      nodesMesh.instanceColor.needsUpdate = true;
    }

    if (edges.length) {
      const posArr = new Float32Array(edges.length * 6);
      let w = 0;
      for (const edge of edges) {
        const s = positions.get(edge.source), t = positions.get(edge.target);
        if (!s || !t) continue;
        posArr[w++] = s.x; posArr[w++] = s.y; posArr[w++] = s.z;
        posArr[w++] = t.x; posArr[w++] = t.y; posArr[w++] = t.z;
      }
      edgeBasePositions = new Float32Array(posArr.subarray(0, w));
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(edgeBasePositions), 3));
      edgesLines = new THREE.LineSegments(geom, edgeMaterial);
      contentGroup.add(edgesLines);
      syncEdgeVisibility();
    }

    if (resetCamera) {
      camera.position.set(0, 90, 480);
      controls.target.set(0, 0, 0);
      controls.update();
    }
  }

  // Move the camera close to one node, keeping the current viewing direction.
  function focusNodeById(nodeId) {
    if (!nodesMesh || !camera || !controls) return;
    const base = nodeBase.find((b) => b.id === nodeId);
    if (!base) return;
    const spread = Math.max(0.15, _spread);
    const target = new THREE.Vector3(base.x * spread, base.y * spread, base.z * spread);
    const dir = new THREE.Vector3().subVectors(camera.position, controls.target);
    if (dir.lengthSq() < 1e-6) dir.set(0, 0.3, 1);
    dir.setLength(Math.max(controls.minDistance * 3, 160));
    controls.target.copy(target);
    camera.position.copy(target).add(dir);
    controls.update();
  }

  // Locate a node by id (exact match, then case-insensitive / suffix match) and
  // fly the camera to it. Returns true when found.
  function locateNodeById(query, locateButton) {
    if (!nodeBase.length) {
      return false;
    }
    const text = String(query || "").trim();
    if (!text) {
      return false;
    }
    const lower = text.toLowerCase();
    let base = nodeBase.find((b) => b.id === text)
      || nodeBase.find((b) => b.id.toLowerCase() === lower)
      || nodeBase.find((b) => b.id.toLowerCase().includes(lower));
    if (!base && locateButton) {
      const original = locateButton.textContent;
      locateButton.textContent = "未找到";
      locateButton.disabled = true;
      setTimeout(() => {
        locateButton.textContent = original;
        locateButton.disabled = false;
      }, 1500);
      return false;
    }
    if (!base) {
      return false;
    }
    callbacks.onSelectNode(base.id);
    applyVisualState(base.id, lastFavoriteNodeIds, lastBasketNodeIds, lastRegionSelection);
    focusNodeById(base.id);
    return true;
  }

  // Cheap visual update for selection / favorites / task-basket / node spacing (no graph rebuild)
  function applyVisualState(selectedNodeId, favoriteNodeIds, basketNodeIds, regionSelection = null) {
    if (!nodesMesh) return;
    lastSelectedNodeId = selectedNodeId || null;
    lastFavoriteNodeIds = new Set(favoriteNodeIds);
    lastBasketNodeIds = new Set(basketNodeIds);
    lastRegionSelection = regionSelection || null;

    const dummy = new THREE.Object3D();
    const color = new THREE.Color();
    const haloEntries = [];
    const spread = Math.max(0.15, _spread);
    const posById = new Map(nodeBase.map((base) => [base.id, base]));

    for (let i = 0; i < nodeBase.length; i++) {
      const base = nodeBase[i];
      const isSel = base.id === selectedNodeId;
      const isBasket = basketNodeIds.has(base.id);
      const isFav = favoriteNodeIds.has(base.id);
      const scale = base.radius * (isSel ? 1.4 : isBasket ? 1.25 : isFav ? 1.2 : 1);
      const x = base.x * spread;
      const y = base.y * spread;
      const z = base.z * spread;
      dummy.position.set(x, y, z);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      nodesMesh.setMatrixAt(i, dummy.matrix);

      // Overlay priority: selected (pink) > task-basket (white) > favorite (cyan) > base color.
      const rgb = isSel
        ? { r: 255, g: 77, b: 141 }
        : isBasket
        ? BASKET_HIGHLIGHT_COLOR
        : isFav
        ? { r: 19, g: 184, b: 200 }
        : base.color;
      color.setRGB(rgb.r / 255, rgb.g / 255, rgb.b / 255);
      nodesMesh.setColorAt(i, color);

      if (isSel || isBasket || isFav) {
        haloEntries.push({ x, y, z, radius: scale, rgb });
      } else if (lastNeighborhoodIds.has(base.id)) {
        haloEntries.push({ x, y, z, radius: scale, rgb: NEIGHBORHOOD_COLOR });
      } else if (_showExpertHalo && base.isExpert) {
        // Expert marker: yellow halo around the score-colored node.
        haloEntries.push({ x, y, z, radius: scale, rgb: EXPERT_HALO_COLOR });
      }
      if (base.id === lastNeighborhoodAnchorId) {
        haloEntries.push({ x, y, z, radius: scale * 1.6, rgb: NEIGHBORHOOD_ANCHOR_COLOR });
      }
    }
    nodesMesh.instanceMatrix.needsUpdate = true;
    if (nodesMesh.instanceColor) nodesMesh.instanceColor.needsUpdate = true;
    // InstancedMesh.raycast() uses this.boundingSphere as a broad-phase reject test
    // and only auto-computes it when it is null. Since we moved instances (spread /
    // selection scaling) the cached sphere goes stale and far nodes silently stop
    // being pickable. Recompute it every visual update so clicks always hit.
    nodesMesh.computeBoundingSphere();

    if (edgesLines && edgeBasePositions) {
      const positionAttr = edgesLines.geometry.getAttribute("position");
      const arr = positionAttr.array;
      for (let i = 0; i < edgeBasePositions.length; i += 3) {
        arr[i] = edgeBasePositions[i] * spread;
        arr[i + 1] = edgeBasePositions[i + 1] * spread;
        arr[i + 2] = edgeBasePositions[i + 2] * spread;
      }
      positionAttr.needsUpdate = true;
      edgesLines.geometry.computeBoundingSphere();
    }
    syncEdgeVisibility();

    // Region highlight: bright pink line for an edge region, halo on the anchor
    // node for both edge and expand regions.
    if (regionEdgeLine) {
      contentGroup.remove(regionEdgeLine);
      regionEdgeLine.geometry.dispose();
      regionEdgeLine = null;
    }
    const region = lastRegionSelection;
    if (region && region.type === "edge") {
      const regionA = posById.get(region.a);
      const regionB = posById.get(region.b);
      if (regionA && regionB) {
        const geom = new THREE.BufferGeometry();
        geom.setAttribute(
          "position",
          new THREE.BufferAttribute(
            new Float32Array([
              regionA.x * spread, regionA.y * spread, regionA.z * spread,
              regionB.x * spread, regionB.y * spread, regionB.z * spread,
            ]),
            3,
          ),
        );
        regionEdgeLine = new THREE.Line(geom, regionEdgeMaterial);
        contentGroup.add(regionEdgeLine);
      }
    }
    if (region && posById.has(region.a)) {
      const base = posById.get(region.a);
      const scale = base.radius * 1.45;
      haloEntries.push({
        x: base.x * spread,
        y: base.y * spread,
        z: base.z * spread,
        radius: scale,
        rgb: { r: 255, g: 77, b: 141 },
      });
    }

    if (haloGroup) {
      haloGroup.children.forEach((sprite) => sprite.material.dispose());
      contentGroup.remove(haloGroup);
      haloGroup = null;
    }
    if (haloEntries.length) {
      haloGroup = new THREE.Group();
      for (const entryData of haloEntries) {
        const material = new THREE.SpriteMaterial({
          map: haloTexture, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        });
        material.color.setRGB(entryData.rgb.r / 255, entryData.rgb.g / 255, entryData.rgb.b / 255);
        const sprite = new THREE.Sprite(material);
        sprite.position.set(entryData.x, entryData.y, entryData.z);
        const s = entryData.radius * 4.4;
        sprite.scale.set(s, s, 1);
        haloGroup.add(sprite);
      }
      contentGroup.add(haloGroup);
    }
  }

  container.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]");
    if (!action) {
      return;
    }
    const actionName = action.dataset.action;
    if (actionName === "request-graph") {
      callbacks.onRequestGraph();
      return;
    }
    if (actionName === "build-graph") {
      callbacks.onBuildGraph();
      return;
    }
    if (actionName === "toggle-edges") {
      _showEdges = !_showEdges;
      syncEdgeVisibility();
      return;
    }
    if (actionName === "toggle-zmode") {
      _zMode = Z_MODES[(Z_MODES.indexOf(_zMode) + 1) % Z_MODES.length];
      action.textContent = Z_MODE_LABELS[_zMode];
      if (lastNodesRef) {
        rebuildGraph(lastNodesRef, lastEdgesRef || [], { resetCamera: false });
        lastGraphSignature = viewSignature(buildGraphSignature(lastNodesRef, lastEdgesRef || []));
        applyVisualState(lastSelectedNodeId, lastFavoriteNodeIds, lastBasketNodeIds, lastRegionSelection);
      }
      return;
    }
    if (actionName === "locate-best") {
      if (!lastNodesRef || !lastNodesRef.length) return;
      let best = null;
      let bestScore = -Infinity;
      for (const node of lastNodesRef) {
        const s = nodeScore(node);
        if (Number.isFinite(s) && s > bestScore) {
          bestScore = s;
          best = node;
        }
      }
      if (!best) return;
      callbacks.onSelectNode(best.id);
      // Apply the pink selection highlight immediately; the state-driven re-render
      // will confirm the same selection afterwards.
      applyVisualState(best.id, lastFavoriteNodeIds, lastBasketNodeIds, lastRegionSelection);
      focusNodeById(best.id);
      return;
    }
    if (actionName === "locate-node") {
      const row = action.closest(".locate-row");
      const input = row ? row.querySelector(".graph-locate-input") : null;
      locateNodeById(input ? input.value : "", action);
      return;
    }
    if (actionName === "select-artifact") {
      callbacks.onSelectArtifact(action.dataset.artifactId);
      return;
    }
    if (actionName === "close-legend") {
      _legendClosed = true;
      const legend = event.target.closest(".graph-legend");
      if (legend) {
        legend.classList.add("collapsed");
      }
      return;
    }
  });

  return {
    render(state) {
      ensureDom();

      const graphArtifacts = Array.isArray(state.server.graphArtifacts) ? state.server.graphArtifacts : [];
      const graphContent = state.server.graphContent || null;
      const selectedNodeId = state.page.selectedGraphNodeId;
      const favoriteNodeIds = new Set(state.prefs.favoriteNodeIds || []);
      const basketNodeIds = new Set(state.prefs.taskBasketNodeIds || []);
      const regionSelection = state.prefs.regionSelection || null;
      const neighborhoodIds = new Set(state.page.neighborhoodHighlightIds || []);
      const neighborhoodAnchorId = state.page.neighborhoodAnchorId || null;
      const currentRevisionId = state.page.selectedRevisionId;
      const selectedArtifactId = state.page.selectedGraphArtifactId;
      renderHeader(state, graphArtifacts, currentRevisionId, selectedArtifactId);
      syncLegendState();
      spreadSliderEl.value = String(_spread);
      spreadValueEl.textContent = `${_spread.toFixed(1)}x`;
      if (expertHaloCheckboxEl) {
        expertHaloCheckboxEl.checked = _showExpertHalo;
      }

      // Render states
      if (state.page.errors.graph) {
        setGraphVisible(false);
        setOverlay(buildOverlayCard("图谱加载失败", state.page.errors.graph, "重试", "request-graph"));
      } else if (!state.page.graphRequested) {
        setGraphVisible(false);
        setOverlay(buildOverlayCard(
          "图谱尚未加载",
          "先确认左侧的 revision 目标，再点击“加载图谱”读取数据。",
          state.page.loading.graph ? "加载中..." : "立即加载",
          "request-graph",
          !currentRevisionId || state.page.loading.graph,
        ));
      } else if (!graphContent || !Array.isArray(graphContent.nodes) || !graphContent.nodes.length) {
        setGraphVisible(false);
        setOverlay(buildOverlayCard("当前 artifact 无节点数据", "可切换 artifact 或提交新的构图任务。"));
      } else {
        const nodes = graphContent.nodes;
        const edges = Array.isArray(graphContent.edges) ? graphContent.edges : [];
        lastNodesRef = nodes;
        lastEdgesRef = edges;

        ensureScene();
        setGraphVisible(true);
        attachResize(viewportEl);
        setOverlay(null);

        const dataSignature = buildGraphSignature(nodes, edges);
        const dataChanged = dataSignature !== lastDataSignature;
        if (dataChanged) {
          // New graph payload: refresh the low-score slider range and reset the filter.
          _hideBounds = computeHideSliderBounds(nodes);
          _hideBelow = null;
          if (_hideBounds) {
            hideSliderEl.min = String(_hideBounds.min);
            hideSliderEl.max = String(_hideBounds.max);
            hideSliderEl.step = String((_hideBounds.max - _hideBounds.min) / 100);
            hideSliderEl.disabled = false;
          } else {
            hideSliderEl.disabled = true;
          }
          hideSliderEl.value = hideSliderEl.min;
          hideValueEl.textContent = "关";
        }
        const graphSignature = viewSignature(dataSignature);
        const graphChanged = graphSignature !== lastGraphSignature;
        const regionKey = regionSelection
          ? `${regionSelection.type}:${regionSelection.a}:${regionSelection.b || ""}`
          : "";
        lastNeighborhoodIds = neighborhoodIds;
        lastNeighborhoodAnchorId = neighborhoodAnchorId;
        const neighborhoodKey = `${neighborhoodIds.size}|${neighborhoodAnchorId || ""}`;
        const visualKey = `${selectedNodeId || ""}|${favoriteIdsKey(favoriteNodeIds)}|${favoriteIdsKey(basketNodeIds)}|${regionKey}|${neighborhoodKey}|${_spread.toFixed(2)}|xh:${_showExpertHalo ? 1 : 0}`;

        if (graphChanged) {
          // Only a brand-new graph payload recenters the camera; z-mode / filter
          // rebuilds keep the current viewpoint.
          rebuildGraph(nodes, edges, { resetCamera: dataChanged });
          lastGraphSignature = graphSignature;
          lastDataSignature = dataSignature;
        }
        if (graphChanged || visualKey !== lastVisualKey) {
          applyVisualState(selectedNodeId, favoriteNodeIds, basketNodeIds, regionSelection);
          lastVisualKey = visualKey;
        }
        if (neighborhoodAnchorId && neighborhoodAnchorId !== lastFocusedNeighborhoodAnchor) {
          lastFocusedNeighborhoodAnchor = neighborhoodAnchorId;
          focusNodeById(neighborhoodAnchorId);
        }
      }
    },
  };
}
