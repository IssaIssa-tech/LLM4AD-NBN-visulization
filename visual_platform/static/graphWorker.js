self.addEventListener("message", async (event) => {
  const { type, payload, id } = event.data;
  if (type === "FETCH_GRAPH") {
    try {
      const { url } = payload;
      const response = await fetch(url);
      const graphData = await response.json();
      if (!response.ok) {
        throw new Error(graphData.error || `请求失败: ${response.status}`);
      }
      self.postMessage({ id, type: "FETCH_GRAPH_SUCCESS", payload: graphData });
    } catch (error) {
      self.postMessage({ id, type: "FETCH_GRAPH_ERROR", payload: error.message });
    }
  }
});
