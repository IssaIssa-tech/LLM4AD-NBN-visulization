import { clearElement, el } from "../core/dom.js";

function formatProgress(job) {
  if (Number.isFinite(Number(job?.percent))) {
    return `${Math.round(Number(job.percent))}%`;
  }
  if (job?.current !== null && job?.current !== undefined && job?.total) {
    return `${job.current}/${job.total}`;
  }
  return "-";
}

function pillClass(status) {
  if (["succeeded", "completed", "ready"].includes(status)) {
    return "status-pill success";
  }
  if (["failed", "cancelled"].includes(status)) {
    return "status-pill danger";
  }
  if (["queued", "launch_requested", "running", "stop_requested"].includes(status)) {
    return "status-pill warning";
  }
  return "status-pill";
}

function formatTimestamp(ts) {
  if (!ts) return "-";
  const text = String(ts);
  // Try to parse as ISO; if it has no timezone info, assume local.
  let date;
  try {
    if (text.includes("T") || text.includes("Z")) {
      date = new Date(text);
    } else {
      // SQLite-style "YYYY-MM-DD HH:MM:SS" — treat as local time.
      date = new Date(text.replace(" ", "T"));
    }
  } catch (_) {
    return text;
  }
  if (isNaN(date.getTime())) {
    return text;
  }
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

const JOB_TYPE_LABELS = {
  revision_generation: "版本生成",
  region_search: "区域搜索",
  history_import: "历史样本导入",
  expert_import: "外部专家解导入",
  graph_build: "NBN 图构建",
};

function jobTypeLabel(jobType) {
  return JOB_TYPE_LABELS[jobType] || jobType || "-";
}

export function createJobStatusView(container, callbacks) {
  container.addEventListener("click", (event) => {
    const summary = event.target.closest("summary");
    if (summary) {
      const panel = summary.parentElement;
      if (panel instanceof HTMLDetailsElement && panel.dataset.panelKey) {
        event.preventDefault();
        callbacks.onTogglePanel(panel.dataset.panelKey, !panel.open);
        return;
      }
    }

    const cancelButton = event.target.closest("[data-action='cancel-job']");
    if (cancelButton) {
      callbacks.onCancelJob(cancelButton.dataset.jobId);
      return;
    }
    const highlightButton = event.target.closest("[data-action='highlight-neighborhood']");
    if (highlightButton) {
      try {
        const ids = JSON.parse(highlightButton.dataset.ids || "[]");
        callbacks.onHighlightNeighborhood(ids, highlightButton.dataset.anchorId);
      } catch (_) {
        // ignore malformed payloads
      }
    }
  });

  return {
    render(state) {
      clearElement(container);

      const revisionDetail = state.server.revisionDetail || null;
      const currentJob = state.server.currentJob?.job || state.server.currentJob || null;
      const events = Array.isArray(state.server.currentJobEvents) ? state.server.currentJobEvents : [];
      const timeline = Array.isArray(revisionDetail?.timeline) ? revisionDetail.timeline : [];

      container.appendChild(el("div", { className: "panel-header" }, [
        el("div", {}, [
          el("h2", { className: "panel-title", text: "任务监控" }),
          el("p", {
            className: "panel-subtitle",
            text: "任务状态与事件账本独立渲染。图失败不会拖垮这里，这里的失败也不会拖垮其他面板。",
          }),
        ]),
      ]));

      if (state.page.errors.job) {
        container.appendChild(el("div", {
          className: "error-box",
          text: state.page.errors.job,
        }));
      }

      if (!currentJob && !timeline.length) {
        container.appendChild(el("div", {
          className: "empty-state",
          text: "当前 revision 还没有可显示的 job。",
        }));
        return;
      }

      if (currentJob) {
        container.appendChild(el("div", { className: "section-block" }, [
          el("h3", { text: "当前关注的 Job" }),
          el("div", { className: "job-card" }, [
            el("div", { className: "job-top" }, [
              el("div", {}, [
                el("div", { className: "job-name mono", text: currentJob.jobId }),
                el("div", { className: "muted-text", text: `${jobTypeLabel(currentJob.jobType)} / ${currentJob.stageLabel || currentJob.stage || "-"}` }),
              ]),
              el("span", {
                className: pillClass(currentJob.status),
                text: currentJob.statusLabel || currentJob.status || "-",
              }),
            ]),
            el("div", { className: "meta-grid section-block" }, [
              el("div", { className: "meta-item" }, [
                el("span", { text: "进度" }),
                el("strong", { text: formatProgress(currentJob) }),
              ]),
              el("div", { className: "meta-item" }, [
                el("span", { text: "结果 revision" }),
                el("strong", { className: "mono", text: currentJob.resultRevisionId || "-" }),
              ]),
              el("div", { className: "meta-item" }, [
                el("span", { text: "排队时间" }),
                el("strong", { text: formatTimestamp(currentJob.queuedAt) }),
              ]),
              el("div", { className: "meta-item" }, [
                el("span", { text: "开始时间" }),
                el("strong", { text: formatTimestamp(currentJob.startedAt) }),
              ]),
              el("div", { className: "meta-item" }, [
                el("span", { text: "更新时间" }),
                el("strong", { text: formatTimestamp(currentJob.updatedAt) }),
              ]),
              el("div", { className: "meta-item" }, [
                el("span", { text: "完成时间" }),
                el("strong", { text: formatTimestamp(currentJob.finishedAt) }),
              ]),
            ]),
            ...(currentJob.jobType === "region_search" && currentJob.result
              ? [
                  el("div", { className: "region-verdict section-block" }, [
                    el("div", { className: "inspector-title", text: "区域搜索结论" }),
                    el("div", { className: "meta-grid" }, [
                      el("div", { className: "meta-item" }, [
                        el("span", { text: "verdict" }),
                        el("strong", { className: "mono", text: currentJob.result.verdict || "-" }),
                      ]),
                      el("div", { className: "meta-item" }, [
                        el("span", { text: "generated / valid" }),
                        el("strong", { text: `${currentJob.result.generated ?? "-"} / ${currentJob.result.valid ?? "-"}` }),
                      ]),
                      el("div", { className: "meta-item" }, [
                        el("span", { text: "hits / novel / ships" }),
                        el("strong", { text: `${currentJob.result.hits ?? "-"} / ${currentJob.result.novel ?? "-"} / ${currentJob.result.ships ?? "-"}` }),
                      ]),
                      el("div", { className: "meta-item" }, [
                        el("span", { text: "候选子节点" }),
                        el("strong", { text: `${currentJob.result.candidateChildCount ?? "-"}` }),
                      ]),
                      el("div", { className: "meta-item" }, [
                        el("span", { text: "区域 best" }),
                        el("strong", { text: currentJob.result.bestScore != null ? Number(currentJob.result.bestScore).toFixed(5) : "-" }),
                      ]),
                      ...(currentJob.result.coverage
                        ? [
                            el("div", { className: "meta-item" }, [
                              el("span", { text: "邻域覆盖" }),
                              el("strong", { text: `${currentJob.result.coverage.covered ?? "-"}/${currentJob.result.coverage.total ?? "-"} 桶` }),
                            ]),
                          ]
                        : []),
                      ...(currentJob.result.novelRate !== undefined
                        ? [
                            el("div", { className: "meta-item" }, [
                              el("span", { text: "新颖率" }),
                              el("strong", { text: `${(Number(currentJob.result.novelRate) * 100).toFixed(1)}%` }),
                            ]),
                          ]
                        : []),
                      ...(currentJob.result.conclusion
                        ? [
                            el("div", { className: "meta-item" }, [
                              el("span", { text: "探索结论" }),
                              el("strong", { text: currentJob.result.conclusion.conclusion || "-" }),
                            ]),
                          ]
                        : []),
                      ...(currentJob.result.fusionMode
                        ? [
                            el("div", { className: "meta-item" }, [
                              el("span", { text: "融合模式" }),
                              el("strong", { text: `${currentJob.result.fusionMode}${Array.isArray(currentJob.result.fusionUsedSegments) && currentJob.result.fusionUsedSegments.length ? `（段 ${currentJob.result.fusionUsedSegments.join(",")}）` : ""}` }),
                            ]),
                          ]
                        : []),
                      ...(Array.isArray(currentJob.result.anchorTrail) && currentJob.result.anchorTrail.length > 1
                        ? [
                            el("div", { className: "meta-item" }, [
                              el("span", { text: "锚点漂移" }),
                              el("strong", { className: "mono", text: currentJob.result.anchorTrail.map((t) => `${t.id}(${Number(t.score).toFixed(4)})`).join(" → ") }),
                            ]),
                          ]
                        : []),
                    ]),
                  ]),
                ]
              : []),
            el("div", { className: "event-message", text: currentJob.message || "暂无任务消息。" }),
            ["queued", "launch_requested", "running"].includes(currentJob.status || "")
              ? el("div", { className: "button-row section-block" }, [
                el("button", {
                  className: "danger-button",
                  text: "取消任务",
                  dataset: { action: "cancel-job", jobId: currentJob.jobId },
                  attrs: { type: "button" },
                }),
              ])
              : null,
          ]),
        ]));
      }

      const timelineNodes = timeline.map((job) =>
        el("div", { className: "job-card" }, [
          el("div", { className: "job-top" }, [
            el("div", {}, [
              el("div", { className: "job-name mono", text: job.jobId }),
              el("div", { className: "muted-text", text: `${jobTypeLabel(job.jobType)} / ${job.stageLabel || job.stage || "-"}` }),
            ]),
            el("span", { className: pillClass(job.status), text: job.statusLabel || job.status || "-" }),
          ]),
          el("div", { className: "muted-text", text: `${formatTimestamp(job.updatedAt || job.queuedAt)} / ${job.statusLabel || job.status || "-"}` }),
          el("div", { className: "event-message", text: job.message || "暂无消息。" }),
        ])
      );

      container.appendChild(el("div", { className: "section-block" }, [
        el("h3", { text: "任务时间线" }),
        el("div", { className: "job-list" }, timelineNodes),
      ]));

      const detailsNode = el("details", {
        className: "composer",
        attrs: { open: state.prefs.openPanels.jobEvents || undefined },
        dataset: { panelKey: "jobEvents" },
      }, [
        el("summary", { text: `事件账本 (${events.length})` }),
        el("div", { className: "composer-body" }, [
          events.length
            ? el("div", { className: "event-list" }, events.map((item) =>
              el("div", { className: "event-card" }, [
                el("div", { className: "event-top" }, [
                  el("div", { className: "mono", text: `#${item.seq ?? "-"}` }),
                  el("span", { className: pillClass(item.status), text: item.statusLabel || item.status || "-" }),
                ]),
                el("div", {
                  className: "muted-text",
                  text: `${item.stageLabel || item.stage || "-"} / ${formatTimestamp(item.createdAt)}`,
                }),
                el("div", { className: "event-message", text: item.message || "暂无消息。" }),
              ])
            ))
            : el("div", { className: "empty-state", text: "当前还没有事件账本。" }),
        ]),
      ]);

      container.appendChild(detailsNode);

      const regionReport = state.server.regionReport || null;
      if (regionReport && regionReport.reportMarkdown) {
        container.appendChild(el("details", {
          className: "composer",
          attrs: { open: true },
        }, [
          el("summary", { text: "区域搜索报告" }),
          el("div", { className: "composer-body" }, [
            el("pre", { className: "code-block report-block", text: regionReport.reportMarkdown }),
            ...(Array.isArray(regionReport.neighborhood) && regionReport.neighborhood.length
              ? [
                  el("div", { className: "button-row section-block" }, [
                    el("button", {
                      className: "primary-button",
                      text: `在图上标亮锚点邻域（${regionReport.neighborhood.length} 个）`,
                      dataset: {
                        action: "highlight-neighborhood",
                        ids: JSON.stringify(regionReport.neighborhood.map((item) => item.id)),
                        anchorId: String(regionReport.region?.a || ""),
                      },
                      attrs: { type: "button" },
                    }),
                  ]),
                ]
              : []),
            ...(regionReport.corridor && regionReport.corridor.directChildrenBefore !== undefined
              ? [
                  el("div", { className: "section-hint", text:
                    `锚点群密度：NBN 直接子节点 ${regionReport.corridor.directChildrenBefore ?? "-"} → ${regionReport.corridor.directChildrenAfter ?? "-"}；最佳子节点分=${regionReport.corridor.bestChildScore != null ? Number(regionReport.corridor.bestChildScore).toFixed(5) : "-"}。`,
                  }),
                ]
              : []),
            ...(regionReport.corridor
              && regionReport.corridor.edgeBefore !== undefined
              ? [
                  el("div", { className: "section-hint", text:
                    `走廊对比：原边 d=${regionReport.corridor.edgeBefore != null ? Number(regionReport.corridor.edgeBefore).toFixed(4) : "-"} → 新图 d=${regionReport.corridor.edgeAfter != null ? Number(regionReport.corridor.edgeAfter).toFixed(4) : "-"}；走廊节点数=${regionReport.corridor.corridorNodeCount ?? "-"}。`,
                  }),
                ]
              : []),
          ]),
        ]));
      }
    },
  };
}
