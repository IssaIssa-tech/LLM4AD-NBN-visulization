import { apiRequest } from "./api/client.js";
import { getArtifactContent, getNodeCode, listRevisionArtifacts } from "./api/artifacts.js";
import { cancelJob, getJob, submitJob } from "./api/jobs.js";
import { deleteRevision, getRevision, getRevisionEvents, renameRevision } from "./api/revisions.js";
import {
  createWorkspace,
  getWorkspace,
  listWorkspaceRevisions,
  listWorkspaces,
  updateWorkspace,
} from "./api/workspaces.js";
import { emit, EVENTS, on } from "./core/events.js";
import { clearElement, el } from "./core/dom.js";
import {
  getState,
  patchPage,
  patchPrefs,
  replaceServer,
  resetGraphState,
  subscribe,
} from "./core/state.js";
import {
  loadFavoriteNodeIds,
  saveFavoriteNodeIds,
  toggleFavoriteNodeId,
} from "./features/favorites.js";
import {
  clearTaskBasket,
  loadTaskBasketNodeIds,
  saveTaskBasketNodeIds,
  toggleTaskBasketNodeId,
} from "./features/task-basket.js";
import {
  clearRegionSelection,
  loadRegionSelection,
  saveRegionSelection,
} from "./features/region-selection.js";
import { selectGraphNode, syncGraphSelection } from "./features/selection.js";
import { createComposerView } from "./views/composer.js";
import { createGraphCanvasView } from "./views/graph-canvas.js";
import { createInspectorView } from "./views/inspector.js";
import { createJobStatusView } from "./views/job-status.js";
import { createRevisionPanelView } from "./views/revision-panel.js";
import { createWorkspaceListView } from "./views/workspace-list.js";

const PREFS_STORAGE_KEY = "llm4add.frontend.prefs.v2";

const elements = {
  topbarContext: document.getElementById("topbarContext"),
  workspaceListPanel: document.getElementById("workspaceListPanel"),
  revisionPanel: document.getElementById("revisionPanel"),
  graphPanel: document.getElementById("graphPanel"),
  inspectorPanel: document.getElementById("inspectorPanel"),
  composerPanel: document.getElementById("composerPanel"),
  jobStatusPanel: document.getElementById("jobStatusPanel"),
  themeToggleButton: document.getElementById("themeToggleButton"),
  openJobDrawer: document.getElementById("openJobDrawer"),
  openBasin3d: document.getElementById("openBasin3d"),
  openMds3d: document.getElementById("openMds3d"),
  openComposerDrawer: document.getElementById("openComposerDrawer"),
  jobDrawer: document.getElementById("jobDrawer"),
  composerDrawer: document.getElementById("composerDrawer"),
  jobDrawerDot: document.getElementById("jobDrawerDot"),
};

const refreshTracker = {
  workspacesAt: 0,
  workspaceContextAt: 0,
  revisionAt: 0,
  jobAt: 0,
  jobEventsAt: 0,
  graphAt: 0,
};

let pollInFlight = false;

const workspaceListView = createWorkspaceListView(elements.workspaceListPanel, {
  onSelectWorkspace: (workspaceId) => emit(EVENTS.WORKSPACE_SELECTED, { workspaceId }),
  onRefresh: () => emit(EVENTS.WORKSPACES_REFRESH_REQUESTED),
  onCreateWorkspace: () => emit(EVENTS.WORKSPACE_CREATED),
});

const revisionPanelView = createRevisionPanelView(elements.revisionPanel, {
  onSelectRevision: (revisionId) => emit(EVENTS.REVISION_SELECTED, { revisionId }),
  onDeleteRevision: (revisionId) => emit(EVENTS.REVISION_DELETE_REQUESTED, { revisionId }),
  onRenameRevision: (revisionId) => emit(EVENTS.REVISION_RENAME_REQUESTED, { revisionId }),
});

const graphCanvasView = createGraphCanvasView(elements.graphPanel, {
  onRequestGraph: () => emit(EVENTS.GRAPH_REQUESTED),
  onBuildGraph: () => emit(EVENTS.GRAPH_BUILD_SUBMITTED),
  onSelectArtifact: (artifactId) => emit(EVENTS.GRAPH_ARTIFACT_SELECTED, { artifactId }),
  onSelectNode: (nodeId) => emit(EVENTS.GRAPH_NODE_SELECTED, { nodeId }),
  onSelectRegion: (region) => emit(EVENTS.REGION_SELECTED, { region }),
});

const inspectorView = createInspectorView(elements.inspectorPanel, {
  onToggleFavorite: (nodeId) => emit(EVENTS.GRAPH_NODE_FAVORITE_TOGGLED, { nodeId }),
  onSelectNode: (nodeId) => emit(EVENTS.GRAPH_NODE_SELECTED, { nodeId }),
  onToggleTaskBasket: (nodeId) => emit(EVENTS.TASK_BASKET_TOGGLED, { nodeId }),
  onClearTaskBasket: () => emit(EVENTS.TASK_BASKET_CLEARED),
  onSetRegionAnchor: (nodeId) => emit(EVENTS.REGION_SELECTED, { region: { type: "expand", a: nodeId } }),
  onClearRegion: () => emit(EVENTS.REGION_CLEARED),
  onUseRecommendedRegion: (region) => emit(EVENTS.REGION_SELECTED, { region }),
  onRefreshRecommendations: (revisionId) => {
    void refreshRegionRecommendations(revisionId);
  },
  onFocusNode: (nodeId) => emit(EVENTS.GRAPH_NODE_SELECTED, { nodeId }),
});

const jobStatusView = createJobStatusView(elements.jobStatusPanel, {
  onCancelJob: (jobId) => emit(EVENTS.JOB_CANCEL_REQUESTED, { jobId }),
  onTogglePanel: (panelKey, open) => emit(EVENTS.PANEL_TOGGLED, { panelKey, open }),
  onHighlightNeighborhood: (ids, anchorId) => {
    patchPage({
      neighborhoodHighlightIds: Array.isArray(ids) ? ids : [],
      neighborhoodAnchorId: anchorId || null,
    });
  },
});

const composerView = createComposerView(elements.composerPanel, {
  onSubmitEohEvolve: (payload) => emit(EVENTS.EOH_EVOLVE_SUBMITTED, { payload }),
  onSubmitPromptGen: (payload) => emit(EVENTS.PROMPT_GEN_SUBMITTED, { payload }),
  onSubmitRegionSearch: (payload) => emit(EVENTS.REGION_SEARCH_SUBMITTED, { payload }),
  onSubmitHistoryImport: (payload) => emit(EVENTS.HISTORY_IMPORT_SUBMITTED, { payload }),
  onSubmitExpertImport: (payload) => emit(EVENTS.EXPERT_IMPORT_SUBMITTED, { payload }),
  onAdaptExpert: (payload) => adaptExpertSolution(payload),
  onTogglePanel: (panelKey, open) => emit(EVENTS.PANEL_TOGGLED, { panelKey, open }),
});

function readStoredPrefs() {
  try {
    const payload = JSON.parse(window.localStorage.getItem(PREFS_STORAGE_KEY) || "{}");
    if (!payload || typeof payload !== "object") {
      return {};
    }
    return payload;
  } catch (_) {
    return {};
  }
}

function persistPrefs(prefs) {
  window.localStorage.setItem(
    PREFS_STORAGE_KEY,
    JSON.stringify({
      theme: prefs.theme,
      openPanels: prefs.openPanels,
    }),
  );
}

function applyTheme(theme) {
  document.body.classList.remove("theme-light", "theme-dark");
  document.body.classList.add(theme === "dark" ? "theme-dark" : "theme-light");
}

function renderTopbarContext(state) {
  const historyLink = document.getElementById("researchHistoryLink");
  if (historyLink) historyLink.href = "/static/research-history.html" + (state.page.selectedRevisionId ? "?revision=" + encodeURIComponent(state.page.selectedRevisionId) : "");
  if (!elements.topbarContext) {
    return;
  }
  clearElement(elements.topbarContext);
  const workspace = state.server.workspaceContext?.workspace || null;
  const revision = state.server.revisionDetail?.revision || state.server.workspaceContext?.selectedRevision || null;
  const graphArtifact = (state.server.graphArtifacts || []).find((artifact) => artifact.artifactId === state.page.selectedGraphArtifactId) || null;
  const job = state.server.currentJob?.job || state.server.currentJob || null;

  const chips = [
    ["工作台", workspace?.name || workspace?.workspaceId || "-"],
    ["Revision", revision?.revisionId || "-"],
    ["样本", String(revision?.sampleCount ?? 0)],
    ["最佳分", revision?.bestScore != null ? Number(revision.bestScore).toFixed(4) : "-"],
    ["图谱", graphArtifact?.status || (state.page.graphRequested ? "已请求" : "未加载")],
    ["Job", job?.status || "-"],
  ];

  chips.forEach(([label, value]) => {
    elements.topbarContext.appendChild(el("div", { className: "context-chip" }, [
      el("span", { className: "context-chip-label", text: label }),
      el("span", { className: "context-chip-value", text: value, attrs: { title: String(value) } }),
    ]));
  });

  if (elements.jobDrawerDot) {
    elements.jobDrawerDot.classList.remove("pulse", "warn", "danger");
    if (job) {
      if (["queued", "launch_requested", "running", "stop_requested"].includes(job.status)) {
        elements.jobDrawerDot.classList.add("pulse");
      } else if (["failed", "cancelled"].includes(job.status)) {
        elements.jobDrawerDot.classList.add("danger");
      } else if (["succeeded", "completed"].includes(job.status)) {
        elements.jobDrawerDot.classList.add("warn");
      }
    }
  }
}

function renderAll() {
  const state = getState();
  renderTopbarContext(state);
  workspaceListView.render(state);
  revisionPanelView.render(state);
  graphCanvasView.render(state);
  inspectorView.render(state);
  jobStatusView.render(state);
  composerView.render(state);
}

function markRefreshed(key) {
  refreshTracker[key] = Date.now();
}

function refreshedAgoMs(key) {
  return Date.now() - (refreshTracker[key] || 0);
}

function chooseWorkspaceId(workspacesPayload, preferredWorkspaceId) {
  const currentState = getState();
  const items = Array.isArray(workspacesPayload?.items) ? workspacesPayload.items : [];
  return preferredWorkspaceId
    || currentState.page.selectedWorkspaceId
    || workspacesPayload?.selectedWorkspaceId
    || items[0]?.workspaceId
    || null;
}

function chooseRevisionId(contextPayload, revisionsPayload, preferredRevisionId) {
  const items = Array.isArray(revisionsPayload?.items) ? revisionsPayload.items : [];
  const currentState = getState();
  return preferredRevisionId
    || currentState.page.selectedRevisionId
    || contextPayload?.workspace?.selectedRevisionId
    || contextPayload?.selectedRevision?.revisionId
    || contextPayload?.latestRevision?.revisionId
    || items[items.length - 1]?.revisionId
    || null;
}

function chooseCurrentJobId(revisionDetail) {
  const latestJobs = Array.isArray(revisionDetail?.latestJobs) ? revisionDetail.latestJobs : [];
  return revisionDetail?.currentJob?.jobId
    || latestJobs[0]?.jobId
    || null;
}

function chooseGraphArtifact(artifacts, currentArtifactId) {
  if (!Array.isArray(artifacts) || !artifacts.length) {
    return null;
  }
  const current = artifacts.find((artifact) => artifact.artifactId === currentArtifactId);
  if (current) {
    return current;
  }
  return (
    artifacts.find((artifact) => artifact.status === "ready" && artifact.artifactRole === "full")
    || artifacts.find((artifact) => artifact.status === "ready")
    || artifacts[0]
  );
}

async function hydrateWorkspaceList(preferredWorkspaceId = null) {
  patchPage({
    loading: { workspaces: true },
    errors: { workspace: "" },
  });
  const payload = await listWorkspaces();
  replaceServer({ workspaces: payload.items || [] });
  const workspaceId = chooseWorkspaceId(payload, preferredWorkspaceId);
  patchPage({
    selectedWorkspaceId: workspaceId,
    loading: { workspaces: false },
  });
  markRefreshed("workspacesAt");
  return workspaceId;
}

async function hydrateWorkspaceContext(workspaceId) {
  patchPage({
    loading: { workspace: true },
    errors: { workspace: "" },
  });
  const contextPayload = await getWorkspace(workspaceId);
  const revisionsPayload = await listWorkspaceRevisions(workspaceId);
  const revisions = [...(revisionsPayload.items || [])].sort((a, b) => {
    const left = String(a.createdAt || a.revisionId || "");
    const right = String(b.createdAt || b.revisionId || "");
    return right.localeCompare(left);
  });
  replaceServer({
    workspaceContext: contextPayload,
    workspaceRevisions: revisions,
  });
  patchPage({
    loading: { workspace: false },
  });
  markRefreshed("workspaceContextAt");
  return { contextPayload, revisionsPayload };
}

async function hydrateRevision(revisionId) {
  patchPage({
    loading: { revision: true },
    errors: { revision: "" },
  });
  const payload = await getRevision(revisionId);
  replaceServer({
    revisionDetail: payload,
    graphArtifacts: (payload.artifacts || []).filter((artifact) => artifact.artifactType === "graph"),
  });
  patchPage({
    loading: { revision: false },
  });
  markRefreshed("revisionAt");
  return payload;
}

async function hydrateRevisionEvents(revisionId) {
  if (!revisionId) {
    replaceServer({ currentJobEvents: [] });
    return;
  }
  try {
    const eventPayload = await getRevisionEvents(revisionId, { limit: 100 });
    replaceServer({ currentJobEvents: eventPayload.items || [] });
  } catch (error) {
    // If revision-level events fail, keep existing events rather than clearing.
  }
}

async function hydrateRegionReport(revisionId) {
  if (!revisionId) {
    replaceServer({ regionReport: null });
    return;
  }
  try {
    const payload = await apiRequest(`/api/revisions/${revisionId}/region`);
    replaceServer({
      regionReport: payload && payload.ok ? payload.data : null,
    });
  } catch (_) {
    replaceServer({ regionReport: null });
  }
}

async function refreshRegionRecommendations(revisionId) {
  if (!revisionId) {
    replaceServer({ regionRecommendations: null });
    return;
  }
  try {
    const payload = await apiRequest("/api/regions/recommend", {
      method: "POST",
      body: JSON.stringify({ revisionId }),
    });
    replaceServer({ regionRecommendations: payload });
  } catch (error) {
    replaceServer({
      regionRecommendations: {
        ok: false,
        error: String(error?.message || error || "获取区域推荐失败。"),
      },
    });
  }
}

async function hydrateJob(jobId) {
  if (!jobId) {
    replaceServer({
      currentJob: null,
    });
    return null;
  }
  patchPage({
    loading: { job: true },
    errors: { job: "" },
  });
  const jobPayload = await getJob(jobId);
  replaceServer({
    currentJob: jobPayload.job,
  });
  patchPage({
    loading: { job: false },
  });
  markRefreshed("jobAt");
  return jobPayload.job;
}

async function ensureGraphLoaded(forceRefreshArtifacts = false) {
  console.log("[ensureGraphLoaded] called, forceRefresh:", forceRefreshArtifacts);
  const state = getState();
  const revisionId = state.page.selectedRevisionId;
  console.log("[ensureGraphLoaded] revisionId:", revisionId);
  if (!revisionId) {
    console.log("[ensureGraphLoaded] no revisionId, returning");
    return;
  }
  patchPage({
    graphRequested: true,
    loading: { graph: true },
    errors: { graph: "" },
  });

  let artifacts = state.server.graphArtifacts || [];
  try {
    if (forceRefreshArtifacts || !artifacts.length) {
      const payload = await listRevisionArtifacts(revisionId, { artifactType: "graph" });
      artifacts = payload.items || [];
      console.log("[ensureGraphLoaded] fetched artifacts:", artifacts.length);
      replaceServer({ graphArtifacts: artifacts });
    }

    const artifact = chooseGraphArtifact(artifacts, state.page.selectedGraphArtifactId);
    console.log("[ensureGraphLoaded] chosen artifact:", artifact?.artifactId, "status:", artifact?.status);
    patchPage({
      selectedGraphArtifactId: artifact?.artifactId || null,
    });

    if (!artifact) {
      replaceServer({ graphContent: null });
      patchPage({
        loading: { graph: false },
        errors: { graph: "当前 revision 还没有 graph artifact。" },
      });
      return;
    }
    if (artifact.status !== "ready") {
      replaceServer({ graphContent: null });
      patchPage({
        loading: { graph: false },
        errors: { graph: `graph artifact 当前状态为 ${artifact.status}，暂时不可读取。` },
      });
      return;
    }

    console.log("[ensureGraphLoaded] fetching content for:", artifact.artifactId);
    const payload = await getArtifactContent(artifact.artifactId);
    console.log("[ensureGraphLoaded] got payload, keys:", Object.keys(payload), "has content:", !!payload.content, "nodes:", payload.content?.nodes?.length);
    const graphData = payload.content || null;
    console.log("[ensureGraphLoaded] graphData type:", typeof graphData, "is null:", graphData === null, "nodes:", graphData?.nodes?.length);
    replaceServer({
      graphContent: graphData,
    });
    console.log("[ensureGraphLoaded] after replaceServer, state.server.graphContent:", !!getState().server.graphContent, "nodes:", getState().server.graphContent?.nodes?.length);
    syncGraphSelection(graphData, getState().page.selectedGraphNodeId);
    patchPage({
      loading: { graph: false },
      errors: { graph: "" },
    });
    markRefreshed("graphAt");
  } catch (error) {
    console.error("[ensureGraphLoaded] failed:", error);
    replaceServer({ graphContent: null });
    patchPage({
      loading: { graph: false },
      errors: { graph: `图谱加载失败：${String(error?.message || error || "未知错误")}` },
    });
  }
}

// Graph nodes are transported without their (large) code so the payload stays
// small; the full code/algorithm for a node is fetched on demand the first time
// it is selected. Results are cached per node id (== individuals.id).
async function ensureNodeCodeLoaded(nodeId) {
  const id = String(nodeId || "").trim();
  if (!id) {
    return;
  }
  const cache = getState().page.nodeCodeCache || {};
  const existing = cache[id];
  if (existing && (existing.status === "loading" || existing.status === "ready")) {
    return;
  }
  patchPage({
    nodeCodeCache: { ...(getState().page.nodeCodeCache || {}), [id]: { status: "loading" } },
  });
  try {
    const artifactId = getState().page.selectedGraphArtifactId || undefined;
    const detail = await getNodeCode(id, artifactId);
    patchPage({
      nodeCodeCache: {
        ...(getState().page.nodeCodeCache || {}),
        [id]: {
          status: "ready",
          function: detail.function || "",
          program: detail.program || "",
          algorithm: detail.algorithm || "",
        },
      },
    });
  } catch (error) {
    patchPage({
      nodeCodeCache: {
        ...(getState().page.nodeCodeCache || {}),
        [id]: { status: "error", error: String(error?.message || error || "加载失败") },
      },
    });
  }
}

async function refreshCurrentSelection({
  preferredWorkspaceId = null,
  preferredRevisionId = null,
  preferredJobId = null,
  resetGraph = false,
} = {}) {
  try {
    patchPage({ errors: { boot: "", workspace: "", revision: "", job: "" } });
    const previousRevisionId = getState().page.selectedRevisionId;
    const workspaceId = await hydrateWorkspaceList(preferredWorkspaceId);
    if (!workspaceId) {
      replaceServer({
        workspaceContext: null,
        workspaceRevisions: [],
        revisionDetail: null,
        currentJob: null,
        currentJobEvents: [],
        graphArtifacts: [],
        graphContent: null,
      });
      patchPage({
        selectedRevisionId: null,
        selectedJobId: null,
        loading: { boot: false },
      });
      return;
    }

    const { contextPayload, revisionsPayload } = await hydrateWorkspaceContext(workspaceId);
    const revisionId = chooseRevisionId(contextPayload, revisionsPayload, preferredRevisionId);
    patchPage({ selectedRevisionId: revisionId });

    if (resetGraph || revisionId !== previousRevisionId) {
      resetGraphState();
      patchPage({ selectedRevisionId: revisionId });
    }

    if (!revisionId) {
      replaceServer({
        revisionDetail: null,
        currentJob: null,
        currentJobEvents: [],
        graphArtifacts: [],
        graphContent: null,
      });
      patchPage({
        selectedJobId: null,
        loading: { boot: false },
      });
      return;
    }

    const revisionPayload = await hydrateRevision(revisionId);
    await hydrateRevisionEvents(revisionId);
    markRefreshed("jobEventsAt");
    if (revisionPayload?.mode === "region_search") {
      await hydrateRegionReport(revisionId);
    } else {
      replaceServer({ regionReport: null });
    }
    const jobId = preferredJobId || chooseCurrentJobId(revisionPayload);
    patchPage({ selectedJobId: jobId });
    await hydrateJob(jobId);

    if (getState().page.graphRequested) {
      await ensureGraphLoaded(true);
    }

    patchPage({
      loading: { boot: false },
    });
  } catch (error) {
    patchPage({
      loading: {
        boot: false,
        workspaces: false,
        workspace: false,
        revision: false,
        graph: false,
        job: false,
      },
      errors: {
        boot: error.message || "前端初始化失败。",
      },
    });
  }
}

async function withSubmit(action) {
  patchPage({
    loading: { submit: true },
    errors: { submit: "" },
  });
  try {
    await action();
  } catch (error) {
    patchPage({
      errors: { submit: error.message || "提交失败。" },
    });
    window.alert(error.message || "提交失败。");
  } finally {
    patchPage({
      loading: { submit: false },
    });
  }
}

function llmPayloadFromForm(payload, defaults) {
  return {
    host: String(payload.host || defaults.llm?.host || ""),
    key: String(payload.key || ""),
    model: String(payload.model || defaults.llm?.model || ""),
    thinking: String(payload.thinking || defaults.llm?.thinking || "disabled"),
    timeout: Number(defaults.llm?.timeout || 120),
    max_tokens: Number(defaults.llm?.max_tokens || 4096),
  };
}

// Snapshot every revision that makes up the graph currently on screen (each node carries its
// own sourceRevisionId), plus the displayed revision itself. The backend records this set so a
// seeded run's merged graph reproduces exactly "the graph I evolved from", even if some of those
// revisions are deleted later.
function collectDisplayedSourceRevisionIds() {
  const state = getState();
  const ids = [];
  const push = (rid) => {
    const value = String(rid || "").trim();
    if (value && !ids.includes(value)) {
      ids.push(value);
    }
  };
  push(state.page.selectedRevisionId);
  const nodes = state.server.graphContent?.nodes;
  if (Array.isArray(nodes)) {
    for (const node of nodes) {
      push(node?.sourceRevisionId);
    }
  }
  return ids;
}

async function handleEohEvolveSubmit(payload) {
  const state = getState();
  const workspaceId = state.page.selectedWorkspaceId;
  if (!workspaceId) {
    throw new Error("请先选择工作台。");
  }
  const basketNodeIds = Array.isArray(state.prefs.taskBasketNodeIds) ? state.prefs.taskBasketNodeIds : [];
  if (!basketNodeIds.length) {
    throw new Error("任务篮为空。请先把节点加入任务篮，再发起 EoH 进化。");
  }
  const defaults = state.server.defaults || {};
  const popSize = Math.max(1, Number(payload.popSize) || Math.max(basketNodeIds.length, 5));
  const maxGenerations = Math.max(1, Number(payload.maxGenerations) || 10);
  const maxSampleNums = Math.max(1, Number(payload.maxSampleNums) || popSize * maxGenerations);
  const selectionNum = Math.max(1, Number(payload.selectionNum) || 2);
  const numSamplers = Math.max(1, Number(payload.numSamplers) || 2);
  const numEvaluators = Math.max(1, Number(payload.numEvaluators) || 4);
  await withSubmit(async () => {
    const submitted = await submitJob({
      workspaceId,
      jobType: "revision_generation",
      request: {
        mode: "seeded_eoh",
        prompt: String(payload.prompt || "").trim(),
        initialPopulationNodeIds: basketNodeIds,
        sourceRevisionIds: collectDisplayedSourceRevisionIds(),
        llm: llmPayloadFromForm(payload, defaults),
        method: {
          pop_size: popSize,
          max_generations: maxGenerations,
          max_sample_nums: maxSampleNums,
          selection_num: selectionNum,
          num_samplers: numSamplers,
          num_evaluators: numEvaluators,
          operator_weights: {
            e1: Number(payload.wE1) || 0,
            e2: Number(payload.wE2) || 0,
            m1: Number(payload.wM1) || 0,
            m2: Number(payload.wM2) || 0,
          },
          distance_metric: String(payload.distanceMetric || defaults.method?.distance_metric || "codet5p_embedding_cosine"),
        },
      },
    });
    patchPrefs({ taskBasketNodeIds: clearTaskBasket() });
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: submitted?.job?.resultRevisionId || null,
      preferredJobId: submitted?.job?.jobId || null,
      resetGraph: true,
    });
    closeDrawer("composerDrawer");
    openDrawer("jobDrawer");
  });
}

async function handlePromptGenSubmit(payload) {
  const state = getState();
  const workspaceId = state.page.selectedWorkspaceId;
  if (!workspaceId) {
    throw new Error("请先选择工作台。");
  }
  const basketNodeIds = Array.isArray(state.prefs.taskBasketNodeIds) ? state.prefs.taskBasketNodeIds : [];
  if (!basketNodeIds.length) {
    throw new Error("任务篮为空。请先把节点加入任务篮，再发起提示词生成。");
  }
  const prompt = String(payload.prompt || "").trim();
  if (!prompt) {
    throw new Error("请先填写提示词。");
  }
  const defaults = state.server.defaults || {};
  const count = Math.max(1, Number(payload.count) || 8);
  await withSubmit(async () => {
    const submitted = await submitJob({
      workspaceId,
      jobType: "revision_generation",
      request: {
        mode: "prompt_gen",
        referenceNodeIds: basketNodeIds,
        sourceRevisionIds: collectDisplayedSourceRevisionIds(),
        prompt,
        llm: llmPayloadFromForm(payload, defaults),
        method: {
          max_sample_nums: count,
          distance_metric: String(payload.distanceMetric || defaults.method?.distance_metric || "codet5p_embedding_cosine"),
        },
      },
    });
    patchPrefs({ taskBasketNodeIds: clearTaskBasket() });
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: submitted?.job?.resultRevisionId || null,
      preferredJobId: submitted?.job?.jobId || null,
      resetGraph: true,
    });
    closeDrawer("composerDrawer");
    openDrawer("jobDrawer");
  });
}

async function handleRegionSearchSubmit(payload) {
  const state = getState();
  const workspaceId = state.page.selectedWorkspaceId;
  if (!workspaceId) {
    throw new Error("请先选择工作台。");
  }
  const region = state.prefs.regionSelection || null;
  if (!region) {
    throw new Error("尚未选择搜索区域。请先在图上点一条连边，或在检查器里把节点设为扩张区域锚点。");
  }
  const defaults = state.server.defaults || {};
  const regionSegments = Math.max(1, Number(payload.regionSegments) || defaults.method?.region_segments || 3);
  const samplesPerSegment = Math.max(1, Number(payload.samplesPerSegment) || defaults.method?.samples_per_segment || 24);
  const numSamplers = Math.max(1, Number(payload.numSamplers) || defaults.method?.num_samplers || 4);
  const numEvaluators = Math.max(1, Number(payload.numEvaluators) || defaults.method?.num_evaluators || 4);
  await withSubmit(async () => {
    const submitted = await submitJob({
      workspaceId,
      jobType: "region_search",
      request: {
        region,
        prompt: String(payload.prompt || "").trim(),
        sourceRevisionIds: collectDisplayedSourceRevisionIds(),
        llm: llmPayloadFromForm(payload, defaults),
        method: {
          region_segments: regionSegments,
          samples_per_segment: samplesPerSegment,
          max_sample_nums: regionSegments * samplesPerSegment,
          num_samplers: numSamplers,
          num_evaluators: numEvaluators,
          timeout_seconds: Number(defaults.method?.timeout_seconds || 120),
          distance_metric: String(payload.distanceMetric || defaults.method?.distance_metric || "codet5p_embedding_cosine"),
          fusion_mode: String(payload.fusionMode || defaults.method?.fusion_mode || "none"),
        },
      },
    });
    patchPrefs({ regionSelection: clearRegionSelection() });
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: submitted?.job?.resultRevisionId || null,
      preferredJobId: submitted?.job?.jobId || null,
      resetGraph: true,
    });
    closeDrawer("composerDrawer");
    openDrawer("jobDrawer");
  });
}

async function handleHistoryImportSubmit(payload) {
  const workspaceId = getState().page.selectedWorkspaceId;
  if (!workspaceId) {
    throw new Error("请先选择工作台。");
  }
  await withSubmit(async () => {
    const submitted = await submitJob({
      workspaceId,
      jobType: "history_import",
      request: {
        source: String(payload.source || "circle_packing_history"),
      },
    });
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: submitted?.job?.resultRevisionId || null,
      preferredJobId: submitted?.job?.jobId || null,
      resetGraph: true,
    });
    closeDrawer("composerDrawer");
    openDrawer("jobDrawer");
  });
}

async function adaptExpertSolution(payload) {
  const functionText = String(payload.functionText || "").trim();
  if (!functionText) {
    throw new Error("请先粘贴需要改写的外部解代码。");
  }
  return apiRequest("/api/expert/adapt", {
    method: "POST",
    body: JSON.stringify({
      functionText,
      llm: {
        host: String(payload.host || ""),
        model: String(payload.model || ""),
        key: String(payload.key || ""),
      },
      timeBudgetSeconds: Number(payload.timeBudgetSeconds || 300),
    }),
  });
}

async function handleExpertImportSubmit(payload) {
  const workspaceId = getState().page.selectedWorkspaceId;
  if (!workspaceId) {
    throw new Error("请先选择工作台。");
  }
  const functionText = String(payload.functionText || "").trim();
  if (!functionText) {
    throw new Error("请先提供可评估的 pack_circles 函数。");
  }
  await withSubmit(async () => {
    const submitted = await submitJob({
      workspaceId,
      jobType: "expert_import",
      request: {
        title: String(payload.title || ""),
        description: String(payload.description || ""),
        functionText,
      },
    });
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: submitted?.job?.resultRevisionId || null,
      preferredJobId: submitted?.job?.jobId || null,
      resetGraph: true,
    });
    closeDrawer("composerDrawer");
    openDrawer("jobDrawer");
  });
}

async function handleWorkspaceSelected(workspaceId) {
  await refreshCurrentSelection({
    preferredWorkspaceId: workspaceId,
    preferredRevisionId: null,
    preferredJobId: null,
    resetGraph: true,
  });
}

async function handleRevisionSelected(revisionId) {
  const workspaceId = getState().page.selectedWorkspaceId;
  if (!workspaceId || !revisionId) {
    return;
  }
  await updateWorkspace(workspaceId, {
    selectedRevisionId: revisionId,
  });
  await refreshCurrentSelection({
    preferredWorkspaceId: workspaceId,
    preferredRevisionId: revisionId,
    preferredJobId: null,
    resetGraph: true,
  });
}

async function handleRevisionDeleted(revisionId) {
  if (!revisionId) {
    return;
  }
  const confirmed = window.confirm(
    `确定删除 revision ${revisionId} 吗？该操作会一并删除其样本、任务与图产物，且不可撤销。`,
  );
  if (!confirmed) {
    return;
  }
  const workspaceId = getState().page.selectedWorkspaceId;
  const deletingCurrent = getState().page.selectedRevisionId === revisionId;
  await withSubmit(async () => {
    let result;
    try {
      result = await deleteRevision(revisionId);
    } catch (err) {
      // The backend refuses to delete a revision that uniquely holds solutions
      // (not referenced by any other version) unless deletion is explicitly
      // forced. Ask the user to confirm the permanent loss, then retry with force.
      if (err?.code === "revision_deletes_unique_solutions") {
        const uniqueCount = err?.details?.uniqueCount;
        const forced = window.confirm(
          `该版本独占${uniqueCount ? ` ${uniqueCount} 个` : ""}解（未被其它版本引用），删除后将永久丢失且无法恢复。\n确定仍要删除吗？`,
        );
        if (!forced) {
          return;
        }
        result = await deleteRevision(revisionId, { force: true });
      } else {
        throw err;
      }
    }
    if (deletingCurrent) {
      // Drop the stale selection so the refresh does not try to hydrate a deleted revision.
      resetGraphState();
      patchPage({ selectedRevisionId: null, selectedJobId: null });
    }
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: deletingCurrent
        ? (result?.selectedRevisionId || null)
        : getState().page.selectedRevisionId,
      preferredJobId: null,
      resetGraph: deletingCurrent,
    });
  });
}

async function handleRevisionRenamed(revisionId) {
  if (!revisionId) {
    return;
  }
  const revisions = getState().server.workspaceRevisions || [];
  const current = revisions.find((item) => item.revisionId === revisionId) || null;
  const currentName = typeof current?.displayName === "string" ? current.displayName : "";
  const input = window.prompt(
    `为 revision ${revisionId} 设置显示名称（留空则恢复显示原始 ID）：`,
    currentName,
  );
  if (input === null) {
    return;
  }
  const nextName = input.trim();
  if (nextName === currentName.trim()) {
    return;
  }
  await withSubmit(async () => {
    await renameRevision(revisionId, nextName);
    await refreshCurrentSelection({
      preferredWorkspaceId: getState().page.selectedWorkspaceId,
      preferredRevisionId: getState().page.selectedRevisionId,
      preferredJobId: getState().page.selectedJobId,
    });
  });
}

async function handleCreateWorkspace() {
  const name = window.prompt("输入工作台名称，可留空自动命名：", "") ?? "";
  await withSubmit(async () => {
    const payload = await createWorkspace(name || "New Workspace");
    const workspaceId = payload.workspace?.workspaceId;
    if (workspaceId) {
      await refreshCurrentSelection({
        preferredWorkspaceId: workspaceId,
        resetGraph: true,
      });
      return;
    }
    await refreshCurrentSelection({ resetGraph: true });
  });
}

async function handleGraphBuild() {
  const state = getState();
  const workspaceId = state.page.selectedWorkspaceId;
  const revisionId = state.page.selectedRevisionId;
  if (!workspaceId || !revisionId) {
    return;
  }
  await withSubmit(async () => {
    await submitJob({
      workspaceId,
      jobType: "graph_build",
      request: {
        revisionId,
      },
    });
    patchPage({
      graphRequested: true,
      selectedGraphArtifactId: null,
      errors: { graph: "" },
    });
    replaceServer({ graphContent: null });
    await refreshCurrentSelection({
      preferredWorkspaceId: workspaceId,
      preferredRevisionId: revisionId,
    });
    openDrawer("jobDrawer");
  });
}

async function handleJobCancel(jobId) {
  if (!jobId) {
    return;
  }
  await cancelJob(jobId);
  await refreshCurrentSelection({
    preferredWorkspaceId: getState().page.selectedWorkspaceId,
    preferredRevisionId: getState().page.selectedRevisionId,
    preferredJobId: jobId,
  });
}

function nextPollDelayMs() {
  const state = getState();
  const currentJob = state.server.currentJob?.job || state.server.currentJob || null;
  const waitingGraph = state.page.graphRequested
    && (state.server.graphArtifacts || []).some((artifact) => artifact.status !== "ready");
  if (["queued", "launch_requested", "running", "stop_requested"].includes(currentJob?.status || "") || waitingGraph) {
    return 4000;
  }
  return 15000;
}

function shouldRefreshWorkspaces() {
  return refreshedAgoMs("workspacesAt") >= 30000;
}

function shouldRefreshWorkspaceContext() {
  return refreshedAgoMs("workspaceContextAt") >= 30000;
}

function shouldRefreshRevision(currentJob) {
  if (!getState().server.revisionDetail) {
    return true;
  }
  if (["queued", "launch_requested", "running", "stop_requested"].includes(currentJob?.status || "")) {
    return refreshedAgoMs("revisionAt") >= 6000;
  }
  return refreshedAgoMs("revisionAt") >= 15000;
}

function shouldRefreshJob(currentJob) {
  if (!currentJob) {
    return false;
  }
  if (["queued", "launch_requested", "running", "stop_requested"].includes(currentJob?.status || "")) {
    return refreshedAgoMs("jobAt") >= 4000;
  }
  return refreshedAgoMs("jobAt") >= 15000;
}

function shouldRefreshJobEvents(currentJob) {
  if (["queued", "launch_requested", "running", "stop_requested"].includes(currentJob?.status || "")) {
    return refreshedAgoMs("jobEventsAt") >= 4000;
  }
  return refreshedAgoMs("jobEventsAt") >= 15000;
}

function shouldRefreshGraphArtifacts(currentJob, graphArtifacts) {
  if (!getState().page.graphRequested) {
    return false;
  }
  const waitingGraph = Array.isArray(graphArtifacts)
    && graphArtifacts.some((artifact) => artifact.status !== "ready" && artifact.status !== "failed");
  if (waitingGraph) {
    return refreshedAgoMs("graphAt") >= 6000;
  }
  if (["queued", "launch_requested", "running", "stop_requested"].includes(currentJob?.status || "")) {
    return refreshedAgoMs("graphAt") >= 10000;
  }
  return refreshedAgoMs("graphAt") >= 20000;
}

async function pollCurrentSelection() {
  if (pollInFlight) {
    return;
  }
  pollInFlight = true;
  try {
    const state = getState();
    if (!state.page.selectedWorkspaceId) {
      await refreshCurrentSelection();
      return;
    }

    if (shouldRefreshWorkspaces()) {
      await hydrateWorkspaceList(state.page.selectedWorkspaceId);
    }

    if (shouldRefreshWorkspaceContext()) {
      await hydrateWorkspaceContext(state.page.selectedWorkspaceId);
    }

    const currentJob = state.server.currentJob?.job || state.server.currentJob || null;
    if (state.page.selectedRevisionId && shouldRefreshRevision(currentJob)) {
      const revisionPayload = await hydrateRevision(state.page.selectedRevisionId);
      await hydrateRevisionEvents(state.page.selectedRevisionId);
      markRefreshed("jobEventsAt");
      const nextJobId = chooseCurrentJobId(revisionPayload);
      const currentJobId = getState().server.currentJob?.jobId || getState().server.currentJob?.job?.jobId || null;
      patchPage({ selectedJobId: nextJobId });
      if (!getState().server.currentJob || currentJobId !== nextJobId) {
        await hydrateJob(nextJobId);
      }
    }

    const latestJob = getState().server.currentJob?.job || getState().server.currentJob || null;
    if (shouldRefreshJob(latestJob)) {
      await hydrateJob(getState().page.selectedJobId);
    }

    if (state.page.selectedRevisionId && shouldRefreshJobEvents(latestJob)) {
      await hydrateRevisionEvents(state.page.selectedRevisionId);
      markRefreshed("jobEventsAt");
    }

    if (shouldRefreshGraphArtifacts(latestJob, getState().server.graphArtifacts)) {
      await ensureGraphLoaded(true);
    }
  } catch (error) {
    patchPage({
      errors: {
        boot: error.message || "轮询刷新失败。",
      },
    });
  } finally {
    pollInFlight = false;
  }
}

function startPolling() {
  async function loop() {
    await pollCurrentSelection();
    window.setTimeout(loop, nextPollDelayMs());
  }
  window.setTimeout(loop, nextPollDelayMs());
}

function openDrawer(drawerId) {
  const drawer = document.getElementById(drawerId);
  if (drawer) {
    drawer.setAttribute("aria-hidden", "false");
  }
}

function closeDrawer(drawerId) {
  const drawer = document.getElementById(drawerId);
  if (drawer) {
    drawer.setAttribute("aria-hidden", "true");
  }
}

function installEventHandlers() {
  on(EVENTS.WORKSPACE_SELECTED, ({ workspaceId }) => {
    void handleWorkspaceSelected(workspaceId);
  });
  on(EVENTS.REVISION_SELECTED, ({ revisionId }) => {
    void handleRevisionSelected(revisionId);
  });
  on(EVENTS.REVISION_DELETE_REQUESTED, ({ revisionId }) => {
    void handleRevisionDeleted(revisionId);
  });
  on(EVENTS.REVISION_RENAME_REQUESTED, ({ revisionId }) => {
    void handleRevisionRenamed(revisionId);
  });
  on(EVENTS.WORKSPACES_REFRESH_REQUESTED, () => {
    void refreshCurrentSelection({
      preferredWorkspaceId: getState().page.selectedWorkspaceId,
      preferredRevisionId: getState().page.selectedRevisionId,
      preferredJobId: getState().page.selectedJobId,
    });
  });
  on(EVENTS.WORKSPACE_CREATED, () => {
    void handleCreateWorkspace();
  });
  on(EVENTS.EOH_EVOLVE_SUBMITTED, ({ payload }) => {
    void handleEohEvolveSubmit(payload);
  });
  on(EVENTS.PROMPT_GEN_SUBMITTED, ({ payload }) => {
    void handlePromptGenSubmit(payload);
  });
  on(EVENTS.REGION_SEARCH_SUBMITTED, ({ payload }) => {
    void handleRegionSearchSubmit(payload);
  });
  on(EVENTS.HISTORY_IMPORT_SUBMITTED, ({ payload }) => {
    void handleHistoryImportSubmit(payload);
  });
  on(EVENTS.EXPERT_IMPORT_SUBMITTED, ({ payload }) => {
    void handleExpertImportSubmit(payload);
  });
  on(EVENTS.JOB_CANCEL_REQUESTED, ({ jobId }) => {
    void handleJobCancel(jobId);
  });
  on(EVENTS.GRAPH_REQUESTED, () => {
    void ensureGraphLoaded(true);
  });
  on(EVENTS.GRAPH_BUILD_SUBMITTED, () => {
    void handleGraphBuild();
  });
  on(EVENTS.GRAPH_ARTIFACT_SELECTED, ({ artifactId }) => {
    patchPage({
      selectedGraphArtifactId: artifactId,
      graphRequested: true,
    });
    void ensureGraphLoaded(false);
  });
  on(EVENTS.GRAPH_NODE_SELECTED, ({ nodeId }) => {
    selectGraphNode(nodeId);
    if (nodeId) {
      void ensureNodeCodeLoaded(nodeId);
    }
  });
  on(EVENTS.GRAPH_NODE_FAVORITE_TOGGLED, ({ nodeId }) => {
    const nextFavorites = toggleFavoriteNodeId(getState().prefs.favoriteNodeIds, nodeId);
    patchPrefs({ favoriteNodeIds: nextFavorites });
  });
  on(EVENTS.TASK_BASKET_TOGGLED, ({ nodeId }) => {
    const nextBasket = toggleTaskBasketNodeId(getState().prefs.taskBasketNodeIds, nodeId);
    patchPrefs({ taskBasketNodeIds: nextBasket });
  });
  on(EVENTS.TASK_BASKET_CLEARED, () => {
    patchPrefs({ taskBasketNodeIds: clearTaskBasket() });
  });
  on(EVENTS.REGION_SELECTED, ({ region }) => {
    patchPrefs({ regionSelection: saveRegionSelection(region) });
    if (region && region.a) {
      emit(EVENTS.GRAPH_NODE_SELECTED, { nodeId: region.a });
    }
  });
  on(EVENTS.REGION_CLEARED, () => {
    patchPrefs({ regionSelection: clearRegionSelection() });
  });
  on(EVENTS.THEME_TOGGLED, () => {
    patchPrefs({
      theme: getState().prefs.theme === "dark" ? "light" : "dark",
    });
  });
  on(EVENTS.PANEL_TOGGLED, ({ panelKey, open }) => {
    patchPrefs({
      openPanels: {
        [panelKey]: open,
      },
    });
  });
  elements.themeToggleButton.addEventListener("click", () => {
    emit(EVENTS.THEME_TOGGLED);
  });
  elements.openJobDrawer.addEventListener("click", () => {
    openDrawer("jobDrawer");
  });
  // 3D 视图打开的是**当前 revision 自己的数据**（后端按 revision 现场生成并缓存）。
  // 预实验快照演示已移到独立入口 /demo.html，不再混在工作台主流程里。
  const openRevision3d = (base) => {
    const revisionId = getState().page.selectedRevisionId;
    if (!revisionId) {
      window.alert("请先在工作台列表里选择一个 revision，再打开 3D 视图。");
      return;
    }
    window.open(`${base}?revision=${encodeURIComponent(revisionId)}`, "_blank", "noopener");
  };
  if (elements.openBasin3d) {
    elements.openBasin3d.addEventListener("click", () => openRevision3d("/basins3d.html"));
  }
  if (elements.openMds3d) {
    elements.openMds3d.addEventListener("click", () => openRevision3d("/mds3d.html"));
  }
  elements.openComposerDrawer.addEventListener("click", () => {
    openDrawer("composerDrawer");
  });
  document.addEventListener("click", (event) => {
    const closeTarget = event.target.closest("[data-drawer-close]");
    if (closeTarget) {
      closeDrawer(closeTarget.dataset.drawerClose);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer("jobDrawer");
      closeDrawer("composerDrawer");
    }
  });
}

subscribe((state, slice) => {
  const scrollX = slice === "prefs" ? window.scrollX : null;
  const scrollY = slice === "prefs" ? window.scrollY : null;
  applyTheme(state.prefs.theme);
  persistPrefs(state.prefs);
  saveFavoriteNodeIds(state.prefs.favoriteNodeIds || []);
  saveTaskBasketNodeIds(state.prefs.taskBasketNodeIds || []);
  saveRegionSelection(state.prefs.regionSelection);
  renderAll();
  if (scrollX !== null && scrollY !== null) {
    window.requestAnimationFrame(() => {
      window.scrollTo(scrollX, scrollY);
    });
  }
});

async function boot() {
  const storedPrefs = readStoredPrefs();
  patchPrefs({
    theme: storedPrefs.theme || "light",
    favoriteNodeIds: loadFavoriteNodeIds(),
    taskBasketNodeIds: loadTaskBasketNodeIds(),
    regionSelection: loadRegionSelection(),
    openPanels: storedPrefs.openPanels || {},
  });

  applyTheme(getState().prefs.theme);
  installEventHandlers();

  try {
    const defaults = await apiRequest("/api/defaults");
    replaceServer({ defaults });
  } catch (_) {
    replaceServer({ defaults: null });
  }

  await refreshCurrentSelection();
  startPolling();
}

boot();
