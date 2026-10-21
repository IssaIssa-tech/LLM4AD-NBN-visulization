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
    ["请先在工作台列表里选择一个 revision，再打开 3D 视图。", "Select a revision in the workspace before opening a 3D view."],
    ["请先选择工作台。", "Select a workspace first."],
    ["任务篮为空。请先把节点加入任务篮，再发起 EoH 进化。", "The task basket is empty. Add nodes before starting EoH evolution."],
    ["任务篮为空。请先把节点加入任务篮，再发起提示词生成。", "The task basket is empty. Add nodes before starting prompt generation."],
    ["请先填写提示词。", "Enter a prompt first."],
    ["尚未选择搜索区域。请先在图上点一条连边，或在检查器里把节点设为扩张区域锚点。", "No search region is selected. Select a graph edge or set a node as the expansion-region anchor in the inspector."],
    ["请先粘贴需要改写的外部解代码。", "Paste the external solution code to adapt first."],
    ["请先提供可评估的 pack_circles 函数。", "Provide an evaluable pack_circles function first."],
    ["获取区域推荐失败", "Could not obtain region recommendations"],
    ["前端初始化失败", "Frontend initialization failed"],
    ["轮询刷新失败", "Polling refresh failed"],
    ["提交失败", "Submission failed"],
    ["当前 revision 还没有 graph artifact。", "This revision has no graph artifact yet."],
    ["图谱加载失败", "Graph loading failed"],
    ["图谱", "Graph"],
    ["工作区数据", "Workspace data"],
    ["预实验快照", "Preview snapshot"],
    ["只读，与工作区数据无关", "read-only and separate from workspace data"],
    ["只读演示", "read-only demo"],
    ["正在加载代码", "Loading code"],
    ["加载代码失败", "Could not load code"],
    ["接口返回异常", "Unexpected API response"],
    ["加载失败", "Loading failed"],
    ["加载中", "Loading"],
    ["播放轨迹", "Play trajectory"],
    ["继续", "Resume"],
    ["暂停", "Pause"],
    ["播放完成", "Playback complete"],
    ["到达终点", "Reached endpoint"],
    ["该轨迹没有可画路径", "This trajectory has no drawable path"],
    ["请先在图例点选一条轨迹", "Select a trajectory in the legend first"],
    ["爬山轨迹", "Hill-climbing trajectories"],
    ["链爬过程（本次实验）", "Chain-climbing process (this experiment)"],
    ["新父链（锚点）", "New parent chain (anchors)"],
    ["新高点（干净）", "New best (clean)"],
    ["新高点", "New best"],
    ["全部节点（完整）", "All nodes (full)"],
    ["按山/轨迹", "By basin / trajectory"],
    ["按爬山轨迹", "By hill-climbing trajectory"],
    ["按来源", "By source"],
    ["按分数", "By score"],
    ["分数范围", "Score range"],
    ["分数高度", "Score height"],
    ["分数秩", "Score rank"],
    ["分数", "Score"],
    ["来源", "Source"],
    ["算子", "Operator"],
    ["算法摘要", "Algorithm summary"],
    ["无代码", "No code"],
    ["有效解", "valid solutions"],
    ["可见", "visible"],
    ["唯一", "unique"],
    ["个有效解", " valid solutions"],
    ["个可见", " visible"],
    ["个节点", " nodes"],
    ["个解", " solutions"],
    ["条 NBN 边", " NBN edges"],
    ["显示全部", "Show all"],
    ["重置视角", "Reset view"],
    ["显示 NBN 边", "Show NBN edges"],
    ["显示入口", "Show entries"],
    ["显示山根", "Show basin roots"],
    ["球（按规模排序）", "Balls (sorted by size)"],
    ["山（按规模排序）", "Basins (sorted by size)"],
    ["根分", "Root score"],
    ["根:", "Root:"],
    ["入口:", "Entry:"],
    ["评测:", "Evaluated:"],
    ["判定:", "Verdict:"],
    ["未判死", "not terminated"],
    ["非轨迹", "not in a trajectory"],
    ["非轨迹节点", "node not in a trajectory"],
    ["轨迹 #", "Trajectory #"],
    ["父链", "Parent chain"],
    ["链 ", "chain "],
    ["步", "steps"],
    ["适应画面", "Fit view"],
    ["关闭", "Close"],
    ["低", "Low"],
    ["高", "High"],
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
