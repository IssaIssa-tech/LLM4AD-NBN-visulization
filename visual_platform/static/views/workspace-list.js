import { clearElement, el } from "../core/dom.js";

function formatDate(value) {
  return value || "-";
}

export function createWorkspaceListView(container, callbacks) {
  container.addEventListener("click", (event) => {
    const workspaceButton = event.target.closest("[data-workspace-id]");
    if (workspaceButton) {
      callbacks.onSelectWorkspace(workspaceButton.dataset.workspaceId);
      return;
    }
    if (event.target.closest("[data-action='refresh-workspaces']")) {
      callbacks.onRefresh();
      return;
    }
    if (event.target.closest("[data-action='create-workspace']")) {
      callbacks.onCreateWorkspace();
    }
  });

  function renderWorkspaceCard(workspace, selectedWorkspaceId) {
    const isActive = workspace.workspaceId === selectedWorkspaceId;
    return el("article", { className: `workspace-card${isActive ? " active" : ""}` }, [
      el("div", { className: "workspace-title-row" }, [
        el("div", {}, [
          el("div", { className: "workspace-name", text: workspace.name || workspace.workspaceId }),
          el("div", { className: "muted-text mono", text: workspace.workspaceId }),
        ]),
        el("button", {
          className: "workspace-button",
          text: isActive ? "当前工作台" : "进入",
          dataset: { workspaceId: workspace.workspaceId },
          attrs: { type: "button" },
        }),
      ]),
      el("div", { className: "muted-text" }, [
        `当前版本: ${workspace.selectedRevisionId || "-"}`,
        el("br"),
        `最新版本: ${workspace.latestRevisionId || "-"}`,
        el("br"),
        `更新时间: ${formatDate(workspace.updatedAt)}`,
      ]),
    ]);
  }

  return {
    render(state) {
      clearElement(container);

      const header = el("div", { className: "panel-header" }, [
        el("div", {}, [
          el("h2", { className: "panel-title", text: "工作台列表" }),
          el("p", {
            className: "panel-subtitle",
            text: "首屏只拉 workspace 摘要。进入具体工作台后，再加载 revision 上下文。",
          }),
        ]),
        el("div", { className: "inline-actions" }, [
          el("button", {
            className: "secondary-button",
            text: "刷新",
            dataset: { action: "refresh-workspaces" },
            attrs: { type: "button" },
          }),
          el("button", {
            text: "新建",
            dataset: { action: "create-workspace" },
            attrs: { type: "button" },
          }),
        ]),
      ]);

      const workspaceItems = Array.isArray(state.server.workspaces) ? state.server.workspaces : [];
      const body = workspaceItems.length
        ? el("div", { className: "workspace-list" }, workspaceItems.map((workspace) => (
          renderWorkspaceCard(workspace, state.page.selectedWorkspaceId)
        )))
        : el("div", {
          className: "empty-state",
          text: state.page.loading.workspaces ? "正在加载工作台..." : "当前还没有工作台。",
        });

      container.appendChild(header);
      container.appendChild(body);
    },
  };
}
