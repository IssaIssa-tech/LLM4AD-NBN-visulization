import { clearElement, el } from "../core/dom.js";

function describeNode(node) {
  const scoreRaw = Number(node?.rawScore ?? node?.score ?? node?.ofecFitness);
  const score = Number.isFinite(scoreRaw) ? scoreRaw : null;
  return [
    ["节点 ID", node?.id || "-"],
    ["得分", score != null ? score.toFixed(5) : "-"],
    ["样本序号", node?.sampleOrder ?? "-"],
    ["代次", node?.generation ?? "-"],
    ["来源", node?.sourceKind || node?.originKind || "-"],
  ];
}

function cleanAlgorithmText(text) {
  let value = String(text || "").trim();
  // Imported summaries are frequently wrapped in a single pair of braces.
  if (value.startsWith("{") && value.endsWith("}")) {
    value = value.slice(1, -1).trim();
  }
  return value;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const PY_KEYWORDS = new Set([
  "def", "return", "if", "elif", "else", "for", "while", "in", "and", "or",
  "not", "is", "None", "True", "False", "import", "from", "as", "class",
  "try", "except", "finally", "with", "lambda", "yield", "break", "continue",
  "pass", "raise", "global", "nonlocal", "assert", "del", "await", "async",
]);

// Lightweight, dependency-free Python highlighter so the code block reads like
// an editor without pulling in an external syntax library.
function highlightPython(code) {
  const tokenRe = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b\d+\.?\d*\b)|([A-Za-z_]\w*)/g;
  let out = "";
  let last = 0;
  let match;
  while ((match = tokenRe.exec(code)) !== null) {
    out += escapeHtml(code.slice(last, match.index));
    if (match[1]) {
      out += `<span class="tok-comment">${escapeHtml(match[1])}</span>`;
    } else if (match[2]) {
      out += `<span class="tok-string">${escapeHtml(match[2])}</span>`;
    } else if (match[3]) {
      out += `<span class="tok-number">${escapeHtml(match[3])}</span>`;
    } else if (match[4]) {
      out += PY_KEYWORDS.has(match[4])
        ? `<span class="tok-keyword">${escapeHtml(match[4])}</span>`
        : escapeHtml(match[4]);
    }
    last = tokenRe.lastIndex;
  }
  out += escapeHtml(code.slice(last));
  return out;
}

function buildCollapsible(title, bodyEl, open = true) {
  const details = el("details", { className: "inspector-collapsible" });
  if (open) {
    details.setAttribute("open", "");
  }
  details.appendChild(el("summary", { className: "collapsible-summary" }, [
    el("span", { className: "collapsible-title", text: title }),
    el("span", { className: "collapsible-chevron", text: "›" }),
  ]));
  details.appendChild(el("div", { className: "collapsible-body" }, [bodyEl]));
  return details;
}

function buildCodeBlock(code) {
  const pre = el("pre", { className: "code-block" }, [
    el("code", { className: "language-python", html: highlightPython(String(code || "")) }),
  ]);
  return el("div", { className: "code-wrap" }, [
    el("div", { className: "code-toolbar" }, [
      el("span", { className: "code-lang", text: "Python" }),
      el("button", {
        className: "code-copy-btn",
        dataset: { action: "copy-code" },
        attrs: { type: "button" },
        text: "复制",
      }),
    ]),
    pre,
  ]);
}

function summarizeGraph(graphContent) {
  if (!graphContent || !Array.isArray(graphContent.nodes)) {
    return null;
  }
  const scores = graphContent.nodes
    .map((node) => Number(node?.rawScore ?? node?.score))
    .filter((value) => Number.isFinite(value));
  // 评测失败的样本会留下哨兵值（-inf，或 -1e8 以下/接近 -e308 的巨大负数）。
  // 平台以 score > 0 作为「有效解」的口径（与 3D 页「只看有效解（分数 > 0）」一致）。
  // 平均分必须只统计有效解，否则会被哨兵值拖成 -1e207 这种天文数字。
  const validScores = scores.filter((value) => value > 0);
  let bestScore = null, avgScore = null;
  if (scores.length) {
    let s = -Infinity;
    for (const v of scores) { if (v > s) s = v; }
    bestScore = s;
  }
  if (validScores.length) {
    let total = 0;
    for (const v of validScores) total += v;
    avgScore = total / validScores.length;
  }
  return {
    nodeCount: graphContent.nodes.length,
    edgeCount: Array.isArray(graphContent.edges) ? graphContent.edges.length : 0,
    scoredCount: scores.length,
    validCount: validScores.length,
    bestScore,
    avgScore,
  };
}

export function createInspectorView(container, callbacks) {
  container.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]");
    if (!action) {
      return;
    }
    if (action.dataset.action === "toggle-favorite") {
      callbacks.onToggleFavorite(action.dataset.nodeId);
      return;
    }
    if (action.dataset.action === "focus-favorite") {
      callbacks.onSelectNode(action.dataset.nodeId);
      return;
    }
    if (action.dataset.action === "toggle-basket" || action.dataset.action === "remove-basket") {
      callbacks.onToggleTaskBasket(action.dataset.nodeId);
      return;
    }
    if (action.dataset.action === "focus-basket") {
      callbacks.onSelectNode(action.dataset.nodeId);
      return;
    }
    if (action.dataset.action === "clear-basket") {
      callbacks.onClearTaskBasket();
      return;
    }
    if (action.dataset.action === "set-region-anchor") {
      callbacks.onSetRegionAnchor(action.dataset.nodeId);
      return;
    }
    if (action.dataset.action === "clear-region") {
      callbacks.onClearRegion();
      return;
    }
    if (action.dataset.action === "use-recommended-region") {
      try {
        const region = JSON.parse(action.dataset.region || "{}");
        callbacks.onUseRecommendedRegion(region);
      } catch (_) {
        // ignore malformed payloads
      }
      return;
    }
    if (action.dataset.action === "refresh-region-recommendations") {
      callbacks.onRefreshRecommendations(action.dataset.revisionId);
      return;
    }
    if (action.dataset.action === "focus-region-node") {
      callbacks.onFocusNode(action.dataset.nodeId);
      return;
    }
    if (action.dataset.action === "copy-code") {
      const card = action.closest(".inspector-card");
      const codeEl = card ? card.querySelector(".code-block code") : null;
      const text = codeEl ? codeEl.textContent : "";
      if (text && navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          action.textContent = "已复制";
          setTimeout(() => { action.textContent = "复制"; }, 1500);
        }).catch(() => {});
      }
    }
  });

  return {
    render(state) {
      clearElement(container);

      const graphContent = state.server.graphContent || null;
      const selectedNodeId = state.page.selectedGraphNodeId;
      const favoriteNodeIds = new Set(state.prefs.favoriteNodeIds || []);
      const taskBasketNodeIds = new Set(state.prefs.taskBasketNodeIds || []);
      const regionSelection = state.prefs.regionSelection || null;
      const summary = summarizeGraph(graphContent);
      const selectedNode = Array.isArray(graphContent?.nodes)
        ? graphContent.nodes.find((node) => node.id === selectedNodeId) || null
        : null;

      container.appendChild(el("div", { className: "panel-header" }, [
        el("div", {}, [
          el("h2", { className: "panel-title", text: "检查器" }),
          el("p", {
            className: "panel-subtitle",
            text: "查看节点详情、图谱统计和收藏节点。",
          }),
        ]),
      ]));

      if (summary) {
        const stat = el("div", { className: "inspector-card" });
        stat.appendChild(el("div", { className: "inspector-title", text: "图谱统计" }));
        stat.appendChild(el("dl", { className: "inspector-detail" }, [
          el("dt", { text: "节点" }),
          el("dd", { text: String(summary.nodeCount) }),
          el("dt", { text: "边" }),
          el("dd", { text: String(summary.edgeCount) }),
          el("dt", { text: "最佳分" }),
          el("dd", { text: summary.bestScore != null ? summary.bestScore.toFixed(4) : "-" }),
          el("dt", { text: "有效解" }),
          el("dd", {
            text: summary.validCount != null
              ? `${summary.validCount} / ${summary.scoredCount}`
              : "-",
          }),
          el("dt", { text: "平均分（有效解）" }),
          el("dd", { text: summary.avgScore != null ? summary.avgScore.toFixed(4) : "-" }),
        ]));
        container.appendChild(stat);
      }

      const inspector = el("div", { className: "inspector-card" });
      inspector.appendChild(el("div", { className: "inspector-title", text: "选中节点" }));
      if (!selectedNode) {
        inspector.appendChild(el("div", {
          className: "inspector-empty",
          text: state.page.graphRequested
            ? "尚未选中节点。在图上点选节点即可查看详情。"
            : "请先加载图谱，再选择节点。",
        }));
      } else {
        const list = el("dl", { className: "inspector-detail" });
        describeNode(selectedNode).forEach(([label, value]) => {
          list.appendChild(el("dt", { text: label }));
          list.appendChild(el("dd", { className: label === "节点 ID" ? "mono" : "", text: String(value) }));
        });
        inspector.appendChild(list);

        const isExpertNode = selectedNode.originKind === "external_expert"
          || selectedNode.sourceKind === "external_expert"
          || selectedNode.hasExternalExpert === true;
        const nodeScoreRaw = Number(selectedNode.rawScore ?? selectedNode.score ?? selectedNode.ofecFitness);
        if (isExpertNode && !Number.isFinite(nodeScoreRaw)) {
          inspector.appendChild(el("div", {
            className: "error-box",
            text: "⚠ 该外部专家解未通过有效评估（无有效分数），已按最差解处理。导入虽已完成，但它并未成功求解，请检查代码是否满足 pack_circles(n) 契约。",
          }));
        }

        const nodeDetail = (state.page.nodeCodeCache || {})[selectedNode.id] || null;

        const algorithmText = cleanAlgorithmText(
          selectedNode.algorithm
          || selectedNode.algorithmSummary
          || (nodeDetail && nodeDetail.algorithm)
          || "",
        );
        if (algorithmText) {
          inspector.appendChild(buildCollapsible(
            "算法说明",
            el("p", { className: "algo-desc", text: algorithmText }),
            true,
          ));
        }

        // Older artifacts embedded the code directly; new (slim) artifacts carry
        // no code and we fetch it on demand into state.page.nodeCodeCache.
        const embeddedCode = String(
          selectedNode.programPreview
          || selectedNode.functionPreview
          || selectedNode.program
          || selectedNode.function
          || "",
        ).trim();
        if (embeddedCode) {
          inspector.appendChild(buildCollapsible("算法代码（完整程序）", buildCodeBlock(embeddedCode), true));
        } else if (!nodeDetail || nodeDetail.status === "loading") {
          inspector.appendChild(el("div", {
            className: "inspector-empty",
            text: "正在加载该节点的算法代码…",
          }));
        } else if (nodeDetail.status === "error") {
          inspector.appendChild(el("div", {
            className: "error-box",
            text: `加载节点代码失败：${nodeDetail.error || "未知错误"}`,
          }));
        } else {
          const codeText = String(nodeDetail.program || nodeDetail.function || "").trim();
          if (codeText) {
            inspector.appendChild(buildCollapsible("算法代码（完整程序）", buildCodeBlock(codeText), true));
          } else {
            inspector.appendChild(el("div", {
              className: "inspector-empty",
              text: "该节点未携带可展示的算法代码。",
            }));
          }
        }

        inspector.appendChild(el("div", { className: "button-row" }, [
          el("button", {
            className: favoriteNodeIds.has(selectedNode.id) ? "secondary-button" : "primary-button",
            text: favoriteNodeIds.has(selectedNode.id) ? "取消收藏" : "收藏节点",
            dataset: { action: "toggle-favorite", nodeId: selectedNode.id },
            attrs: { type: "button" },
          }),
          el("button", {
            className: taskBasketNodeIds.has(selectedNode.id) ? "secondary-button" : "primary-button",
            text: taskBasketNodeIds.has(selectedNode.id) ? "移出任务篮" : "加入任务篮",
            dataset: { action: "toggle-basket", nodeId: selectedNode.id },
            attrs: { type: "button" },
          }),
          el("button", {
            className: "secondary-button",
            text: "设为扩张区域锚点",
            dataset: { action: "set-region-anchor", nodeId: selectedNode.id },
            attrs: { type: "button", title: "以该节点为锚点生成“扩张邻域”搜索区域（0.02 < d < 0.30）" },
          }),
        ]));
      }
      container.appendChild(inspector);

      const favoritesCard = el("div", { className: "inspector-card" });
      favoritesCard.appendChild(el("div", { className: "inspector-title", text: "收藏节点" }));
      const favorites = (state.prefs.favoriteNodeIds || [])
        .map((nodeId) => Array.isArray(graphContent?.nodes) ? graphContent.nodes.find((node) => node.id === nodeId) : null)
        .filter(Boolean);
      if (!favorites.length) {
        favoritesCard.appendChild(el("div", { className: "inspector-empty", text: "当前图里还没有收藏节点。" }));
      } else {
        favoritesCard.appendChild(el("div", { className: "chip-list" }, favorites.map((node) => (
          el("button", {
            className: `chip-button${node.id === selectedNodeId ? " active" : ""}`,
            text: node.id,
            dataset: { action: "focus-favorite", nodeId: node.id },
            attrs: { type: "button" },
          })
        ))));
      }
      container.appendChild(favoritesCard);

      const basketCard = el("div", { className: "inspector-card" });
      basketCard.appendChild(el("div", { className: "inspector-title", text: "任务篮" }));
      basketCard.appendChild(el("div", {
        className: "section-hint",
        text: "任务篮里的节点会作为“EoH 进化”的初始种群，或“多解+提示词生成”的参考代码。",
      }));
      const basketNodes = (state.prefs.taskBasketNodeIds || [])
        .map((nodeId) => Array.isArray(graphContent?.nodes) ? graphContent.nodes.find((node) => node.id === nodeId) : null)
        .filter(Boolean);
      if (!basketNodes.length) {
        basketCard.appendChild(el("div", { className: "inspector-empty", text: "任务篮为空。选中节点后点击“加入任务篮”。" }));
      } else {
        basketCard.appendChild(el("div", { className: "chip-list" }, basketNodes.map((node) => (
          el("button", {
            className: `chip-button${node.id === selectedNodeId ? " active" : ""}`,
            text: node.id,
            dataset: { action: "focus-basket", nodeId: node.id },
            attrs: { type: "button", title: "点击定位该节点" },
          })
        ))));
        basketCard.appendChild(el("div", { className: "button-row" }, [
          el("button", {
            className: "secondary-button",
            text: `清空任务篮（${basketNodes.length}）`,
            dataset: { action: "clear-basket" },
            attrs: { type: "button" },
          }),
        ]));
      }
      container.appendChild(basketCard);

      const regionCard = el("div", { className: "inspector-card" });
      regionCard.appendChild(el("div", { className: "inspector-title", text: "当前搜索区域" }));
      regionCard.appendChild(el("div", {
        className: "section-hint",
        text: "区域是区域搜索的输入：在图上点一条连边选 A—B 区域，或把节点设为扩张锚点。",
      }));
      if (!regionSelection) {
        regionCard.appendChild(el("div", { className: "inspector-empty", text: "尚未选择区域。点一条连边试试。" }));
      } else {
        const list = el("dl", { className: "inspector-detail" });
        const nodeById = new Map((Array.isArray(graphContent?.nodes) ? graphContent.nodes : []).map((node) => [node.id, node]));
        const describeNode = (nodeId) => {
          const node = nodeById.get(nodeId);
          const scoreRaw = Number(node?.rawScore ?? node?.score);
          return node ? `score=${Number.isFinite(scoreRaw) ? scoreRaw.toFixed(5) : "-"}` : "（不在当前图中）";
        };
        list.appendChild(el("dt", { text: "类型" }));
        list.appendChild(el("dd", { text: regionSelection.type === "edge" ? "边（A—B 填缝）" : "扩张邻域（锚点 A）" }));
        list.appendChild(el("dt", { text: "端点 A" }));
        list.appendChild(el("dd", { className: "mono", text: `${regionSelection.a} · ${describeNode(regionSelection.a)}` }));
        if (regionSelection.type === "edge") {
          list.appendChild(el("dt", { text: "端点 B" }));
          list.appendChild(el("dd", { className: "mono", text: `${regionSelection.b} · ${describeNode(regionSelection.b)}` }));
          if (regionSelection.distance != null) {
            list.appendChild(el("dt", { text: "语义距离" }));
            list.appendChild(el("dd", { text: Number(regionSelection.distance).toFixed(4) }));
          }
        }
        regionCard.appendChild(list);
        regionCard.appendChild(el("div", { className: "button-row" }, [
          el("button", {
            className: "secondary-button",
            text: "定位端点 A",
            dataset: { action: "focus-region-node", nodeId: regionSelection.a },
            attrs: { type: "button", title: "把相机飞到端点 A" },
          }),
          ...(regionSelection.type === "edge"
            ? [
                el("button", {
                  className: "secondary-button",
                  text: "定位端点 B",
                  dataset: { action: "focus-region-node", nodeId: regionSelection.b },
                  attrs: { type: "button", title: "把相机飞到端点 B" },
                }),
              ]
            : []),
          el("button", {
            className: "secondary-button",
            text: "清除区域",
            dataset: { action: "clear-region" },
            attrs: { type: "button" },
          }),
          el("span", { className: "section-hint", text: "发起任务请在右侧「区域搜索」表单。" }),
        ]));
      }
      container.appendChild(regionCard);

      const recommendationCard = el("div", { className: "inspector-card" });
      recommendationCard.appendChild(el("div", { className: "inspector-title", text: "值得搜索的区域" }));
      recommendationCard.appendChild(el("div", {
        className: "section-hint",
        text: "系统按“异族高分家族”和“长边空带”给出候选区域；点「设为区域」即可在图上高亮并提交搜索。",
      }));
      const recommendations = state.server.regionRecommendations || null;
      const revisionId = state.page.selectedRevisionId || "";
      recommendationCard.appendChild(el("div", { className: "button-row" }, [
        el("button", {
          className: "secondary-button",
          text: recommendations ? "刷新推荐" : "获取区域推荐",
          dataset: { action: "refresh-region-recommendations", revisionId },
          attrs: { type: "button", disabled: !revisionId },
        }),
      ]));
      if (recommendations && recommendations.ok === false) {
        recommendationCard.appendChild(el("div", { className: "error-box", text: `推荐失败：${recommendations.error || "未知错误"}` }));
      } else if (recommendations && recommendations.data) {
        const data = recommendations.data;
        const champion = data.champion;
        if (champion) {
          recommendationCard.appendChild(el("div", {
            className: "section-hint",
            text: `冠军家族 ${champion.family_id}：代表 ${champion.rep_id}，规模 ${champion.size}，代表分 ${Number(champion.rep_score).toFixed(6)}。`,
          }));
        }
        const renderItem = (item, label) => {
          const region = item.type === "edge"
            ? { type: "edge", a: item.a, b: item.b, distance: item.distance }
            : { type: "expand", a: item.anchor };
          const focusId = item.type === "edge" ? item.a : item.anchor;
          return el("div", { className: "inspector-item" }, [
            el("div", { className: "section-hint", text: label }),
            el("div", { className: "muted-text", text: item.reason || "" }),
            el("div", { className: "button-row" }, [
              el("button", {
                className: "secondary-button",
                text: "设为区域",
                dataset: { action: "use-recommended-region", region: JSON.stringify(region) },
                attrs: { type: "button" },
              }),
              el("button", {
                className: "ghost-button",
                text: "定位",
                dataset: { action: "focus-region-node", nodeId: focusId },
                attrs: { type: "button" },
              }),
            ]),
          ]);
        };
        if (Array.isArray(data.highScoreList) && data.highScoreList.length) {
          recommendationCard.appendChild(el("div", { className: "inspector-title", text: `异族高分榜（前 ${data.highScoreList.length}）` }));
          data.highScoreList.forEach((item) => recommendationCard.appendChild(renderItem(item, `expand · 分位 P${Math.round((item.percentile || 0) * 100)}%`)));
        }
        if (Array.isArray(data.longEdgeList) && data.longEdgeList.length) {
          recommendationCard.appendChild(el("div", { className: "inspector-title", text: `长边榜（前 ${data.longEdgeList.length}）` }));
          data.longEdgeList.forEach((item) => recommendationCard.appendChild(renderItem(item, `edge · d=${Number(item.distance).toFixed(4)}`)));
        }
        if (!Array.isArray(data.highScoreList) && !Array.isArray(data.longEdgeList)) {
          recommendationCard.appendChild(el("div", { className: "inspector-empty", text: "暂无可推荐的区域。" }));
        }
      } else {
        recommendationCard.appendChild(el("div", {
          className: "inspector-empty",
          text: "点击「获取区域推荐」生成候选榜（需要当前 revision 已有全量 NBN 图）。",
        }));
      }
      container.appendChild(recommendationCard);
    },
  };
}
