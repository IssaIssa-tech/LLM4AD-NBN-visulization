import { clearElement, el } from "../core/dom.js";

function formatScore(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(5) : "-";
}

function asText(value, fallback = "-") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function buildRevisionRow(revision, selectedRevisionId) {
  const isActive = revision.revisionId === selectedRevisionId;
  const customName = typeof revision.displayName === "string" ? revision.displayName.trim() : "";
  const hasName = customName.length > 0;
  return el("div", { className: `revision-row${isActive ? " active" : ""}` }, [
    el("div", {}, [
      el("div", {
        className: hasName ? "revision-name" : "revision-name mono",
        text: hasName ? customName : revision.revisionId,
      }),
      el("div", {
        className: "revision-meta",
        text: hasName
          ? `${revision.revisionId} · 状态 ${asText(revision.status)} / 样本 ${asText(revision.sampleCount, "0")}`
          : `状态 ${asText(revision.status)} / 模式 ${asText(revision.mode)} / 样本 ${asText(revision.sampleCount, "0")}`,
      }),
    ]),
    el("div", { className: "revision-row-actions" }, [
      el("button", {
        className: "secondary-button",
        text: isActive ? "当前版本" : "切换",
        dataset: { revisionId: revision.revisionId, action: "select-revision" },
        attrs: { type: "button", disabled: isActive },
      }),
      el("button", {
        className: "secondary-button",
        text: "重命名",
        dataset: { revisionId: revision.revisionId, action: "rename-revision" },
        attrs: { type: "button" },
      }),
      el("button", {
        className: "danger-button",
        text: "删除",
        dataset: { revisionId: revision.revisionId, action: "delete-revision" },
        attrs: { type: "button" },
      }),
    ]),
  ]);
}

export function createRevisionPanelView(container, callbacks) {
  container.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-action='delete-revision']");
    if (deleteButton) {
      callbacks.onDeleteRevision(deleteButton.dataset.revisionId);
      return;
    }

    const renameButton = event.target.closest("[data-action='rename-revision']");
    if (renameButton) {
      callbacks.onRenameRevision(renameButton.dataset.revisionId);
      return;
    }

    const revisionButton = event.target.closest("[data-action='select-revision']");
    if (revisionButton) {
      callbacks.onSelectRevision(revisionButton.dataset.revisionId);
    }
  });

  function renderSummaryCards(state) {
    const workspace = state.server.workspaceContext?.workspace || null;
    const revision = state.server.revisionDetail?.revision || state.server.workspaceContext?.selectedRevision || null;
    const runningJobs = state.server.workspaceContext?.runningJobs || [];
    const graphArtifacts = (state.server.revisionDetail?.artifacts || []).filter((artifact) => artifact.artifactType === "graph");

    return el("div", { className: "meta-grid" }, [
      el("div", { className: "meta-item" }, [
        el("span", { text: "当前工作台" }),
        el("strong", { text: workspace?.name || "-" }),
        el("div", { className: "muted-text mono", text: workspace?.workspaceId || "-" }),
      ]),
      el("div", { className: "meta-item" }, [
        el("span", { text: "当前 revision" }),
        el("strong", { className: "mono", text: revision?.revisionId || "-" }),
        el("div", { className: "muted-text", text: `状态 ${asText(revision?.status)} / 模式 ${asText(revision?.mode)}` }),
      ]),
      el("div", { className: "meta-item" }, [
        el("span", { text: "样本摘要" }),
        el("strong", { text: `${asText(revision?.sampleCount, "0")} 个样本` }),
        el("div", { className: "muted-text", text: `最佳分 ${formatScore(revision?.bestScore)}` }),
      ]),
      el("div", { className: "meta-item" }, [
        el("span", { text: "任务与图产物" }),
        el("strong", { text: `${runningJobs.length} 个运行中任务` }),
        el("div", { className: "muted-text", text: `${graphArtifacts.length} 个 graph artifact` }),
      ]),
    ]);
  }

  return {
    render(state) {
      clearElement(container);

      const workspace = state.server.workspaceContext?.workspace || null;
      const revisions = Array.isArray(state.server.workspaceRevisions) ? state.server.workspaceRevisions : [];
      const graphArtifacts = (state.server.revisionDetail?.artifacts || []).filter((artifact) => artifact.artifactType === "graph");

      container.appendChild(el("div", { className: "panel-header" }, [
        el("div", {}, [
          el("h2", { className: "panel-title", text: "Workspace 与 Revision" }),
          el("p", {
            className: "panel-subtitle",
            text: "这里承载服务端摘要，不在渲染时顺手打图接口。revision 切换会先切摘要，再由图面板决定是否加载 graph artifact。",
          }),
        ]),
      ]));

      if (state.page.errors.boot) {
        container.appendChild(el("div", {
          className: "error-box",
          text: state.page.errors.boot,
        }));
      }

      if (state.page.errors.submit) {
        container.appendChild(el("div", {
          className: "error-box",
          text: state.page.errors.submit,
        }));
      }

      if (!workspace) {
        container.appendChild(el("div", {
          className: "empty-state",
          text: "请选择一个工作台，或先创建新的工作台。",
        }));
        return;
      }

      container.appendChild(renderSummaryCards(state));

      container.appendChild(el("div", { className: "section-block" }, [
        el("h3", { text: "Revision 列表" }),
        revisions.length
          ? el("div", { className: "revision-list" }, revisions.map((revision) => (
            buildRevisionRow(revision, state.page.selectedRevisionId)
          )))
          : el("div", { className: "empty-state", text: "当前工作台还没有 revision。" }),
      ]));

      container.appendChild(el("div", { className: "section-block" }, [
        el("h3", { text: "Graph Artifact 摘要" }),
        graphArtifacts.length
          ? el("div", { className: "artifact-list" }, graphArtifacts.map((artifact) => (
            el("div", { className: "artifact-card" }, [
              el("div", { className: "artifact-top" }, [
                el("div", { className: "artifact-name mono", text: artifact.artifactId }),
                el("span", {
                  className: `status-pill${artifact.status === "ready" ? " success" : artifact.status === "failed" ? " danger" : " warning"}`,
                  text: artifact.status,
                }),
              ]),
              el("div", {
                className: "muted-text",
                text: `role ${asText(artifact.artifactRole)} / updated ${asText(artifact.updatedAt)}`,
              }),
            ])
          )))
          : el("div", { className: "empty-state", text: "当前 revision 还没有 graph artifact。" }),
      ]));
    },
  };
}
