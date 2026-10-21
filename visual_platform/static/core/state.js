const listeners = new Set();

const initialState = {
  server: {
    defaults: null,
    workspaces: [],
    workspaceContext: null,
    workspaceRevisions: [],
    revisionDetail: null,
    currentJob: null,
    currentJobEvents: [],
    graphArtifacts: [],
    graphContent: null,
    regionRecommendations: null,
    regionReport: null,
  },
  page: {
    selectedWorkspaceId: null,
    selectedRevisionId: null,
    selectedJobId: null,
    selectedGraphArtifactId: null,
    selectedGraphNodeId: null,
    neighborhoodHighlightIds: [],
    neighborhoodAnchorId: null,
    nodeCodeCache: {},
    graphRequested: false,
    loading: {
      boot: true,
      workspaces: false,
      workspace: false,
      revision: false,
      graph: false,
      job: false,
      submit: false,
    },
    errors: {
      boot: "",
      workspace: "",
      revision: "",
      graph: "",
      job: "",
      submit: "",
    },
  },
  prefs: {
    theme: "light",
    favoriteNodeIds: [],
    taskBasketNodeIds: [],
    regionSelection: null,
    openPanels: {
      eohEvolve: true,
      promptGen: false,
      historyImport: false,
      expertImport: false,
      jobEvents: true,
      graphInspector: true,
    },
  },
};

const state = structuredClone(initialState);

function notify(slice) {
  listeners.forEach((listener) => listener(state, slice));
}

export function getState() {
  return state;
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function replaceServer(nextServer) {
  state.server = {
    ...state.server,
    ...nextServer,
  };
  notify("server");
}

export function patchPage(nextPage) {
  state.page = {
    ...state.page,
    ...nextPage,
    loading: {
      ...state.page.loading,
      ...(nextPage.loading || {}),
    },
    errors: {
      ...state.page.errors,
      ...(nextPage.errors || {}),
    },
  };
  notify("page");
}

export function patchPrefs(nextPrefs) {
  state.prefs = {
    ...state.prefs,
    ...nextPrefs,
    openPanels: {
      ...state.prefs.openPanels,
      ...(nextPrefs.openPanels || {}),
    },
  };
  notify("prefs");
}

export function resetGraphState() {
  patchPage({
    selectedGraphArtifactId: null,
    selectedGraphNodeId: null,
    nodeCodeCache: {},
    graphRequested: false,
    errors: {
      graph: "",
    },
  });
  replaceServer({
    graphArtifacts: [],
    graphContent: null,
  });
}

export function resetSelectionState() {
  patchPage({
    selectedGraphNodeId: null,
  });
}
