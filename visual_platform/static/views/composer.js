import { clearElement, el } from "../core/dom.js";

function formGroup(labelText, inputEl) {
  return el("label", { className: "form-group" }, [
    el("span", { className: "form-label", text: labelText }),
    inputEl,
  ]);
}

function textInput(name, placeholder, value = "") {
  return el("input", {
    className: "form-input",
    attrs: { type: "text", name, placeholder, value },
  });
}

function numberInput(name, placeholder, value = "") {
  return el("input", {
    className: "form-input",
    attrs: { type: "number", name, placeholder, value: String(value) },
  });
}

function textareaInput(name, placeholder, value = "", rows = 4) {
  return el("textarea", {
    className: "form-input",
    attrs: { name, placeholder, rows },
    text: value,
  });
}

function selectInput(name, options, value = "") {
  const select = el("select", { className: "form-input", attrs: { name } });
  options.forEach(([optValue, optLabel]) => {
    const option = el("option", { attrs: { value: optValue }, text: optLabel });
    if (optValue === value) {
      option.setAttribute("selected", "selected");
    }
    select.appendChild(option);
  });
  return select;
}

function collectFormData(form) {
  const data = {};
  form.querySelectorAll("[name]").forEach((field) => {
    data[field.name] = field.value;
  });
  return data;
}

// Read-only display of the shared task-basket for the EoH / prompt-gen forms.
// The basket itself is edited from the inspector / graph; here it only shows
// how many nodes are queued and lets the user eyeball their ids.
function basketDisplay(basketNodeIds) {
  const ids = Array.isArray(basketNodeIds) ? basketNodeIds : [];
  if (!ids.length) {
    return el("div", {
      className: "error-box",
      text: "任务篮为空。请先在图上选中节点并「加入任务篮」，再发起本任务。",
    });
  }
  return el("div", {}, [
    el("div", { className: "section-hint", text: `已选 ${ids.length} 个节点：` }),
    el("div", { className: "chip-list" }, ids.map((nodeId) => (
      el("span", { className: "chip-button", text: nodeId })
    ))),
  ]);
}

function regionLabel(region) {
  if (!region) {
    return "未选择";
  }
  if (region.type === "edge") {
    return `边 A→B（A=${region.a}，B=${region.b}${region.distance != null ? `，d=${Number(region.distance).toFixed(4)}` : ""}）`;
  }
  return `扩张邻域（锚点 A=${region.a}）`;
}

function regionDisplay(region, graphContent) {
  if (!region) {
    return el("div", {
      className: "error-box",
      text: "尚未选择搜索区域。请在图上点击一条连边，或在检查器里把节点设为扩张区域锚点。",
    });
  }
  const nodes = Array.isArray(graphContent?.nodes) ? graphContent.nodes : [];
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const describe = (nodeId, role) => {
    const node = nodeById.get(nodeId);
    const scoreRaw = Number(node?.rawScore ?? node?.score);
    const score = Number.isFinite(scoreRaw) ? scoreRaw.toFixed(5) : "-";
    return el("div", { className: "section-hint" }, [
      el("strong", { text: `${role} ` }),
      el("span", { className: "mono", text: nodeId }),
      el("span", { text: ` · score=${score}` }),
    ]);
  };
  const items = [describe(region.a, region.type === "edge" ? "端点 A" : "锚点 A")];
  if (region.type === "edge") {
    items.push(describe(region.b, "端点 B"));
  }
  return el("div", { className: "region-display" }, [
    el("div", { className: "section-hint", text: regionLabel(region) }),
    ...items,
  ]);
}

function renderAdaptResult(box, result) {
  clearElement(box);
  const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
  box.appendChild(el("div", {
    className: "section-hint",
    text: "已用 LLM 改写为 pack_circles(n) 并回填到上方代码框，请检查确认后再提交导入。",
  }));
  if (result?.notes) {
    box.appendChild(el("div", { className: "muted-text", text: `改动说明：${result.notes}` }));
  }
  warnings.forEach((warning) => {
    box.appendChild(el("div", { className: "error-box", text: `⚠ ${warning}` }));
  });
}

function renderAdaptError(box, error) {
  clearElement(box);
  box.appendChild(el("div", { className: "error-box", text: `适配失败：${error?.message || error}` }));
}

function renderAdaptPending(box) {
  clearElement(box);
  box.appendChild(el("div", {
    className: "section-hint",
    text: "正在用 LLM 改写外部解……脚本较大时可能需要 1-3 分钟，请保持页面打开并耐心等待。",
  }));
}

// Polling-driven re-renders call render() and rebuild every form from scratch,
// which would otherwise wipe whatever the user is typing. Snapshot the current
// field values / adapt-result content / focus before clearing, then restore.
function captureComposerState(container) {
  const values = {};
  container.querySelectorAll("[data-form-type]").forEach((form) => {
    const type = form.dataset.formType;
    form.querySelectorAll("[name]").forEach((field) => {
      values[`${type}::${field.name}`] = field.value;
    });
  });
  const box = container.querySelector("[data-role='adapt-result']");
  const adaptHtml = box ? box.innerHTML : null;
  let focus = null;
  const active = document.activeElement;
  if (active && container.contains(active) && active.name) {
    const form = active.closest("[data-form-type]");
    focus = {
      key: form ? `${form.dataset.formType}::${active.name}` : null,
      start: active.selectionStart,
      end: active.selectionEnd,
    };
  }
  return { values, adaptHtml, focus };
}

function restoreComposerState(container, snapshot) {
  if (!snapshot) return;
  const { values, adaptHtml, focus } = snapshot;
  container.querySelectorAll("[data-form-type]").forEach((form) => {
    const type = form.dataset.formType;
    form.querySelectorAll("[name]").forEach((field) => {
      const key = `${type}::${field.name}`;
      // Only restore fields the user actually filled, so async-loaded defaults
      // (e.g. llm host/model) still populate empty fields on later renders.
      if (Object.prototype.hasOwnProperty.call(values, key) && values[key] !== "") {
        field.value = values[key];
      }
    });
  });
  if (adaptHtml != null) {
    const box = container.querySelector("[data-role='adapt-result']");
    if (box) box.innerHTML = adaptHtml;
  }
  if (focus && focus.key) {
    const target = findFieldByKey(container, focus.key);
    if (target) {
      target.focus();
      if (typeof target.setSelectionRange === "function" && focus.start != null) {
        try {
          target.setSelectionRange(focus.start, focus.end);
        } catch (_) {
          /* number inputs etc. don't support selection range */
        }
      }
    }
  }
}

function findFieldByKey(container, key) {
  const [type, name] = key.split("::");
  const form = container.querySelector(`[data-form-type='${type}']`);
  return form ? form.querySelector(`[name='${name}']`) : null;
}

export function createComposerView(container, callbacks) {
  // Guards against duplicate adapt requests: a polling re-render rebuilds the
  // button (dropping its disabled state) while the LLM call is still running.
  let adaptInFlight = false;
  container.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.target.closest("[data-form-type]");
    if (!form) return;

    const payload = collectFormData(form);
    const type = form.dataset.formType;

    if (type === "eoh-evolve") {
      callbacks.onSubmitEohEvolve(payload);
    } else if (type === "prompt-gen") {
      callbacks.onSubmitPromptGen(payload);
    } else if (type === "region-search") {
      callbacks.onSubmitRegionSearch(payload);
    } else if (type === "history-import") {
      callbacks.onSubmitHistoryImport(payload);
    } else if (type === "expert-import") {
      callbacks.onSubmitExpertImport(payload);
    }
  });

  container.addEventListener("click", async (event) => {
    const adaptButton = event.target.closest("[data-action='adapt-expert']");
    if (!adaptButton) return;
    event.preventDefault();
    const form = adaptButton.closest("[data-form-type='expert-import']");
    if (!form || typeof callbacks.onAdaptExpert !== "function") return;
    if (adaptInFlight) return;

    const payload = collectFormData(form);
    const originalLabel = adaptButton.textContent;
    adaptInFlight = true;
    adaptButton.disabled = true;
    adaptButton.textContent = "改写中...";
    const pendingBox = form.querySelector("[data-role='adapt-result']");
    if (pendingBox) renderAdaptPending(pendingBox);
    try {
      const result = await callbacks.onAdaptExpert(payload);
      // A polling re-render may have replaced the form while the request was in
      // flight, so re-query the live nodes instead of using stale references.
      const liveForm = container.querySelector("[data-form-type='expert-import']") || form;
      const textarea = liveForm.querySelector("[name='functionText']");
      if (textarea && result?.adaptedCode) {
        textarea.value = result.adaptedCode;
      }
      const resultBox = liveForm.querySelector("[data-role='adapt-result']");
      if (resultBox) renderAdaptResult(resultBox, result);
    } catch (error) {
      const liveForm = container.querySelector("[data-form-type='expert-import']") || form;
      const resultBox = liveForm.querySelector("[data-role='adapt-result']");
      if (resultBox) renderAdaptError(resultBox, error);
    } finally {
      adaptInFlight = false;
      const liveButton = container.querySelector("[data-action='adapt-expert']") || adaptButton;
      liveButton.disabled = false;
      liveButton.textContent = originalLabel;
    }
  });

  return {
    render(state) {
      const snapshot = captureComposerState(container);
      clearElement(container);

      const defaults = state.server.defaults || {};
      const isLoading = state.page.loading?.composer;
      const basketNodeIds = Array.isArray(state.prefs.taskBasketNodeIds) ? state.prefs.taskBasketNodeIds : [];
      const basketCount = basketNodeIds.length;
      const regionSelection = state.prefs.regionSelection || null;
      const defaultPopSize = Math.max(basketCount, 5);
      const defaultMaxGenerations = 10;

      container.appendChild(
        el("div", { className: "composer-body" }, [
          el("div", { className: "panel-header" }, [
            el("div", {}, [
              el("h2", { className: "panel-title", text: "发起任务" }),
              el("p", { className: "panel-subtitle", text: "选择任务类型并填写参数，提交后自动进入任务监控。" }),
            ]),
          ]),

          /* ---------- EoH Evolve ---------- */
          el("section", { className: "section-block" }, [
            el("h3", { className: "section-title", text: "EoH 进化 — 以任务篮为初始种群" }),
            el("p", { className: "section-hint" }, [
              "把任务篮里的节点作为 EoH 进化的初始种群，多代进化后把新解写回图中生成新版本。本次生成的节点会显示为",
              el("strong", { text: "紫色" }),
              "，以前 EoH 生成的节点会回落为普通分数色。",
            ]),
            el("form", { dataset: { formType: "eoh-evolve" } }, [
              basketDisplay(basketNodeIds),
              formGroup("引导提示词（可选）", textareaInput("prompt", "附加给每次 LLM 采样的引导信息，例如结构提示、重组方向；留空则为原生 EoH...", "", 4)),
              el("p", { className: "section-hint", text: "引导提示词会追加到任务描述末尾，随 i1/e1/e2/m1/m2 每一次采样发给 LLM；对照实验请留空。" }),
              el("div", { className: "form-row" }, [
                formGroup("种群规模", numberInput("popSize", "每代存活的算法数量上限", defaultPopSize)),
                formGroup("生成代数", numberInput("maxGenerations", "进化多少代后停止", defaultMaxGenerations)),
              ]),
              el("p", { className: "section-hint", text: "种群规模：每代存活的算法数量上限，系统会自动保证 ≥ 你选中的节点数；初始成员就是任务篮里的这些解。生成代数：最多进化多少代（主要的“跑多久”旋钮）。" }),
              el("details", { className: "inspector-collapsible" }, [
                el("summary", { className: "collapsible-summary" }, [
                  el("span", { className: "collapsible-title", text: "高级设置" }),
                  el("span", { className: "collapsible-chevron", text: "›" }),
                ]),
                el("div", { className: "collapsible-body" }, [
                  el("div", { className: "form-row" }, [
                    formGroup("交叉选择数", numberInput("selectionNum", "每次交叉选几个父代", 2)),
                    formGroup("采样并发数", numberInput("numSamplers", "同时发几个LLM请求", 2)),
                  ]),
                  el("div", { className: "form-row" }, [
                    formGroup("评估并发数", numberInput("numEvaluators", "同时跑几个评测", 4)),
                  ]),
                  el("p", { className: "section-hint", text: "本次样本总量由 种群规模 × 生成代数 自动决定，无需单独设置。交叉选择数：仅影响 e1/e2，每次交叉从种群中挑几个父代。采样并发数：同时向 LLM 发起多少个请求，值越大生成越快但越容易触发 API 限流（HTTP 429），限流时请调低为 1-2；这是主要的提速旋钮，建议 6-8。评估并发数：同时跑几个算法评测进程，评估很快不是瓶颈，4-6 足够。" }),
                ]),
              ]),
              el("p", { className: "section-hint" }, [
                el("strong", { text: "算子权重" }),
                "（相对概率）：每生成一个新个体时，按下面的权重随机选一个算子；父代由种群适应度选择产生。",
                el("br", {}),
                "e1=多父交叉、e2=同思路交叉、m1=参数微调变异、m2=结构变异。",
              ]),
              el("div", { className: "form-row" }, [
                formGroup("e1 多父交叉", numberInput("wE1", "默认 1", 1)),
                formGroup("e2 同思路交叉", numberInput("wE2", "默认 1", 1)),
              ]),
              el("div", { className: "form-row" }, [
                formGroup("m1 参数微调变异", numberInput("wM1", "默认 1", 1)),
                formGroup("m2 结构变异", numberInput("wM2", "默认 1", 1)),
              ]),
              formGroup("API Base URL", textInput("host", "https://api.openai.com/v1", defaults.llm?.host || "")),
              formGroup("模型名称", textInput("model", "如 gpt-4o-mini、deepseek-chat、glm-4", defaults.llm?.model || "")),
              formGroup("API Key", el("input", { className: "form-input", attrs: { type: "password", name: "key", placeholder: "sk-...（留空则读取环境变量 OPENAI_API_KEY / API_KEY）" } })),
              el("div", { className: "form-actions" }, [
                el("button", {
                  className: "primary-button",
                  attrs: { type: "submit", disabled: basketCount === 0 },
                  text: isLoading ? "提交中..." : "发起 EoH 进化",
                }),
              ]),
            ]),
          ]),

          /* ---------- Prompt Generate ---------- */
          el("section", { className: "section-block" }, [
            el("h3", { className: "section-title", text: "多解 + 提示词生成" }),
            el("p", { className: "section-hint" }, [
              "把任务篮里节点的代码 + 你的提示词一起发给 AI，生成新解写回图中生成新版本。本次生成的节点会显示为",
              el("strong", { text: "橙色" }),
              "。",
            ]),
            el("form", { dataset: { formType: "prompt-gen" } }, [
              basketDisplay(basketNodeIds),
              formGroup("提示词", textareaInput("prompt", "描述你希望 AI 如何改进或重写这些解...", "", 4)),
              formGroup("生成数量", numberInput("count", "生成多少个新解", 8)),
              formGroup("API Base URL", textInput("host", "https://api.openai.com/v1", defaults.llm?.host || "")),
              formGroup("模型名称", textInput("model", "如 gpt-4o-mini、deepseek-chat、glm-4", defaults.llm?.model || "")),
              formGroup("API Key", el("input", { className: "form-input", attrs: { type: "password", name: "key", placeholder: "sk-...（留空则读取环境变量 OPENAI_API_KEY / API_KEY）" } })),
              el("p", { className: "section-hint", text: "平台会自动附加固定适配约束（pack_circles(n) 单入口、返回 (n,3) 数组、无顶层执行/print），以保证生成解可被评测。" }),
              el("div", { className: "form-actions" }, [
                el("button", {
                  className: "primary-button",
                  attrs: { type: "submit", disabled: basketCount === 0 },
                  text: isLoading ? "提交中..." : "发起提示词生成",
                }),
              ]),
            ]),
          ]),

          /* ---------- Region Search ---------- */
          el("section", { className: "section-block" }, [
            el("h3", { className: "section-title", text: "区域搜索 — 在选定的边/邻域内搜索" }),
            el("p", { className: "section-hint" }, [
              "把 NBN 图上一条边（A—B 之间的语义空带）或一个节点邻域作为搜索区域：",
              el("strong", { text: "区域端点做种子 + 区域引导 prompt 跑多段 EOH" }),
              "，逐段检测漂移并拉回。一个区域任务生成一个新 revision，完成后自动重构图，可对比“长边被切分/走廊加密”。",
            ]),
            el("form", { dataset: { formType: "region-search" } }, [
              regionDisplay(regionSelection, state.server.graphContent),
              el("div", { className: "form-row" }, [
                formGroup("段数", numberInput("regionSegments", "默认 5", defaults.method?.region_segments || 5)),
                formGroup("每段样本数", numberInput("samplesPerSegment", "默认 30", defaults.method?.samples_per_segment || 30)),
              ]),
              el("p", { className: "section-hint", text: "预算 = 段数 × 每段样本数（默认 5×30=150）。连续两段零命中且零新颖会提前判定 FRACTURE。" }),
              formGroup("引导提示词（可选）", textareaInput("prompt", "附加给区域 EOH 的引导信息，例如想探索的具体结构方向；留空则使用默认区域目标。", "", 3)),
              el("details", { className: "inspector-collapsible" }, [
                el("summary", { className: "collapsible-summary" }, [
                  el("span", { className: "collapsible-title", text: "高级设置" }),
                  el("span", { className: "collapsible-chevron", text: "›" }),
                ]),
                el("div", { className: "collapsible-body" }, [
                el("div", { className: "form-row" }, [
                    formGroup("采样并发数", numberInput("numSamplers", "同时发几个LLM请求", defaults.method?.num_samplers || 4)),
                    formGroup("评估并发数", numberInput("numEvaluators", "同时跑几个评测", defaults.method?.num_evaluators || 4)),
                  ]),
                  formGroup("高分融合模式", selectInput("fusionMode", [
                    ["none", "纯锚点（默认）"],
                    ["auto", "无提升时融合"],
                    ["always", "始终融合"],
                  ], defaults.method?.fusion_mode || "none")),
                  el("p", { className: "section-hint", text: "融合模式：把“离锚点最近的更高分解”作为交叉父代引入高分元素。none=纯锚点家族；auto=连续两段无提升才融合；always=每段融合。实验用。" }),
                ]),
              ]),
              formGroup("API Base URL", textInput("host", "https://api.openai.com/v1", defaults.llm?.host || "")),
              formGroup("模型名称", textInput("model", "如 gpt-4o-mini、deepseek-chat", defaults.llm?.model || "")),
              formGroup("API Key", el("input", { className: "form-input", attrs: { type: "password", name: "key", placeholder: "sk-...（留空则读取环境变量）" } })),
              el("p", { className: "section-hint", text: "生成的新解会持续写入该区域对应的 revision；有效率为首要指标，解析失败的解也会被记录但不计入命中。" }),
              el("div", { className: "form-actions" }, [
                el("button", {
                  className: "primary-button",
                  attrs: { type: "submit", disabled: !regionSelection },
                  text: isLoading ? "提交中..." : "发起区域搜索",
                }),
              ]),
            ]),
          ]),

          /* ---------- History Import ---------- */
          el("section", { className: "section-block" }, [
            el("h3", { className: "section-title", text: "History Import — 历史导入" }),
            el("form", { dataset: { formType: "history-import" } }, [
              formGroup("数据源", selectInput("source", [
                ["circle_packing_history", "Circle Packing 历史"],
                ["tsp_history", "TSP 历史"],
              ], "circle_packing_history")),
              el("div", { className: "form-actions" }, [
                el("button", {
                  className: "secondary-button",
                  attrs: { type: "submit" },
                  text: isLoading ? "导入中..." : "提交历史导入",
                }),
              ]),
            ]),
          ]),

          /* ---------- Expert Import ---------- */
          el("section", { className: "section-block" }, [
            el("h3", { className: "section-title", text: "Expert Import — 专家导入" }),
            el("p", { className: "section-hint" }, [
              "评测器要求单入口函数 ",
              el("strong", { text: "pack_circles(n)" }),
              "：返回形状 (n,3) 的 numpy 数组，每行 (x, y, radius)，取值在 [0,1]、圆不重叠。",
              el("br", {}),
              el("strong", { text: "① 预览适配（可选）" }),
              "：调用 LLM 把多函数脚本改写成上述格式，结果回填到下方代码框。这只是本地预览，",
              el("strong", { text: "不会产生任务、刷新页面会丢失。" }),
              el("br", {}),
              el("strong", { text: "② 提交专家导入" }),
              "：确认代码无误后点此按钮，才会真正评估并导入图中，并在「任务监控」生成一条任务（此时才会持久化）。",
              el("br", {}),
              "（脚本较大时预览适配可能需要 1-3 分钟，请等「改写中…」完成，其间不要刷新页面。）",
            ]),
            el("form", { dataset: { formType: "expert-import" } }, [
              formGroup("标题", textInput("title", "专家算法标题", "")),
              formGroup("描述", textareaInput("description", "简短描述...", "", 2)),
              el("div", { className: "form-row" }, [
                formGroup("API Base URL", textInput("host", "https://api.openai.com/v1", defaults.llm?.host || "")),
                formGroup("模型名称", textInput("model", "如 gpt-4o-mini、deepseek-chat", defaults.llm?.model || "")),
              ]),
              formGroup("API Key（仅改写用）", el("input", { className: "form-input", attrs: { type: "password", name: "key", placeholder: "sk-...（留空则读取环境变量 OPENAI_API_KEY / API_KEY）" } })),
              formGroup("函数代码 (Python)", textareaInput("functionText", "粘贴外部解代码，可先「预览适配」再导入", "", 10)),
              el("div", { className: "adapt-result", dataset: { role: "adapt-result" } }),
              el("div", { className: "form-actions" }, [
                el("button", {
                  className: "secondary-button",
                  attrs: { type: "button", disabled: adaptInFlight },
                  dataset: { action: "adapt-expert" },
                  text: adaptInFlight ? "改写中..." : "预览适配 (LLM 改写)",
                }),
                el("button", {
                  className: "secondary-button",
                  attrs: { type: "submit" },
                  text: isLoading ? "导入中..." : "提交专家导入",
                }),
              ]),
            ]),
          ]),
        ]),
      );

      restoreComposerState(container, snapshot);
    },
  };
}
