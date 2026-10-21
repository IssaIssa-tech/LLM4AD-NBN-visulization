/* English-first display localization for the browser UI.
 *
 * The API preserves its original messages and research records.  This layer
 * translates only rendered interface text, including panels added after the
 * initial page load, so saved data and experiment payloads remain unchanged.
 */
(() => {
  "use strict";

  const exact = new Map([
    ["LLM4ADD 可视化平台", "LLM4ADD Visual Platform"],
    ["LLM4AD 可视化平台", "LLM4AD Visual Platform"],
    ["3D 搜索空间", "3D Search Space"],
    ["MDS 语义空间", "MDS Semantic Space"],
    ["任务监控", "Job Monitor"],
    ["发起任务", "Start Task"],
    ["切换主题", "Toggle theme"],
    ["关闭", "Close"],
    ["工作台列表", "Workspaces"],
    ["刷新", "Refresh"],
    ["新建", "New"],
    ["当前工作台", "Current workspace"],
    ["当前版本", "Current revision"],
    ["当前 revision", "Current revision"],
    ["当前还没有工作台。", "No workspaces yet."],
    ["正在加载工作台...", "Loading workspaces..."],
    ["请选择一个工作台，或先创建新的工作台。", "Select a workspace or create a new one."],
    ["Revision 列表", "Revisions"],
    ["Graph Artifact 摘要", "Graph Artifact Summary"],
    ["当前工作台还没有 revision。", "This workspace has no revisions yet."],
    ["当前 revision 还没有 graph artifact。", "This revision has no graph artifact yet."],
    ["任务状态与事件账本独立渲染。图失败不会拖垮这里，这里的失败也不会拖垮其他面板。", "Job status and event history render independently. A graph failure does not block this panel or the rest of the workspace."],
    ["当前 revision 还没有可显示的 job。", "This revision has no jobs to display yet."],
    ["当前关注的 Job", "Selected Job"],
    ["任务时间线", "Job Timeline"],
    ["事件账本", "Event History"],
    ["暂无任务消息。", "No job message yet."],
    ["暂无消息。", "No message yet."],
    ["当前还没有事件账本。", "No event history yet."],
    ["取消任务", "Cancel Job"],
    ["区域搜索结论", "Regional Search Result"],
    ["区域搜索报告", "Regional Search Report"],
    ["预实验演示", "Preview Demo"],
    ["这是只读快照，不是你的数据。", "This is a read-only snapshot, not your data."],
    ["打开 3D 搜索空间 →", "Open 3D Search Space →"],
    ["打开 MDS 语义空间 →", "Open MDS Semantic Space →"],
    ["正在加载...", "Loading..."],
    ["加载图谱", "Load Graph"],
    ["提交构图", "Build Graph"],
    ["构图中", "Building Graph"],
    ["已完成", "Completed"],
    ["失败", "Failed"],
    ["运行中", "Running"],
    ["排队中", "Queued"],
    ["空闲", "Idle"],
    ["未开始", "Not started"],
    ["已停止", "Stopped"],
    ["正在测试连接...", "Testing connection..."],
    ["连接成功", "Connection successful"],
    ["连接失败", "Connection failed"],
    ["未知错误", "Unknown error"],
    ["暂无", "None"],
    ["删除", "Delete"],
    ["重命名", "Rename"],
    ["切换", "Switch"],
    ["进入", "Open"],
    ["收藏", "Favorite"],
    ["取消收藏", "Remove favorite"],
    ["进度", "Progress"],
    ["结果 revision", "Result revision"],
    ["排队时间", "Queued at"],
    ["开始时间", "Started at"],
    ["更新时间", "Updated at"],
    ["完成时间", "Completed at"],
    ["样本摘要", "Sample Summary"],
    ["任务与图产物", "Jobs and Graph Artifacts"],
    ["最佳分", "Best score"],
    ["状态", "Status"],
    ["模式", "Mode"],
    ["样本", "Samples"],
    ["节点", "nodes"],
    ["个节点", " nodes"],
    ["个样本", " samples"],
    ["个运行中任务", " running jobs"],
    ["个 graph artifact", " graph artifacts"],
    ["当前版本", "Current revision"],
    ["最新版本", "Latest revision"],
    ["更新时间", "Updated"],
  ]);

  // Longer phrases must precede their component labels.
  const fragments = [
    ["首屏只拉 workspace 摘要。进入具体工作台后，再加载 revision 上下文。", "The initial page loads workspace summaries only. Revision details load after you enter a workspace."],
    ["这里承载服务端摘要，不在渲染时顺手打图接口。revision 切换会先切摘要，再由图面板决定是否加载 graph artifact。", "This panel shows server summaries. It does not build graphs while rendering; the graph panel decides whether to load the selected revision's artifact."],
    ["在 3D 视图中打开当前 revision 的数据", "Open the selected revision in the 3D view"],
    ["在 MDS 语义空间中打开当前 revision 的数据", "Open the selected revision in the MDS semantic view"],
    ["正在生成完整 NBN 图", "Building the full NBN graph"],
    ["正在导入固定目录历史样本", "Importing history samples from the configured directory"],
    ["历史样本已导入", "History samples imported"],
    ["历史样本导入", "History Import"],
    ["外部专家解", "External Expert Solution"],
    ["区域搜索", "Regional Search"],
    ["版本生成", "Revision Generation"],
    ["NBN 图构建", "NBN Graph Build"],
    ["图构建", "Graph Build"],
    ["加载图谱", "Load Graph"],
    ["当前工作台", "Current workspace"],
    ["当前 revision", "Current revision"],
    ["最新版本", "Latest revision"],
    ["样本序号", "Sample order"],
    ["原始评估分", "Raw evaluation score"],
    ["父节点距离", "Parent distance"],
    ["父节点", "Parent"],
    ["节点来源", "Node source"],
    ["节点", "node"],
    ["操作符", "Operator"],
    ["轮次", "Generation"],
    ["算法说明", "Algorithm description"],
    ["函数预览", "Function preview"],
    ["查看原节点", "View source node"],
    ["展开区域", "Expand region"],
    ["加入参考解", "Add as reference"],
    ["移出参考解", "Remove reference"],
    ["加入种群", "Add to population"],
    ["移出种群", "Remove from population"],
    ["正在加载函数预览", "Loading function preview"],
    ["暂无函数预览", "No function preview available"],
    ["暂无算法摘要", "No algorithm summary available"],
    ["暂无算法说明", "No algorithm description available"],
    ["只读快照", "read-only snapshot"],
    ["预实验", "Preview experiment"],
    ["搜索空间", "Search Space"],
    ["语义空间", "Semantic Space"],
    ["工作台", "Workspace"],
    ["图产物", "Graph Artifact"],
    ["当前", "Current"],
    ["最新", "Latest"],
    ["时间", "time"],
  ];

  const skipTags = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA"]);
  const translate = (value) => {
    if (!value || !/[\u3400-\u9fff]/.test(value)) return value;
    let result = exact.get(value.trim());
    if (result) return value.replace(value.trim(), result);
    result = value;
    for (const [source, target] of fragments) result = result.replaceAll(source, target);
    return result;
  };

  const translateElement = (element) => {
    if (!(element instanceof Element) || skipTags.has(element.tagName)) return;
    for (const name of ["title", "aria-label", "placeholder", "value"]) {
      if (element.hasAttribute(name)) element.setAttribute(name, translate(element.getAttribute(name)));
    }
    for (const child of element.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) child.nodeValue = translate(child.nodeValue);
    }
  };

  const translateTree = (root) => {
    if (!(root instanceof Element || root instanceof Document)) return;
    if (root instanceof Element) translateElement(root);
    root.querySelectorAll?.("*").forEach(translateElement);
  };

  const install = () => {
    document.documentElement.lang = "en";
    translateTree(document);
    new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === "characterData") {
          const translated = translate(record.target.nodeValue);
          if (translated !== record.target.nodeValue) record.target.nodeValue = translated;
        }
        record.addedNodes.forEach((node) => {
          if (node.nodeType === Node.TEXT_NODE) {
            const translated = translate(node.nodeValue);
            if (translated !== node.nodeValue) node.nodeValue = translated;
          }
          else translateTree(node);
        });
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
