export function clearElement(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

export function appendChildren(node, children = []) {
  children
    .flat()
    .filter((child) => child !== null && child !== undefined && child !== false)
    .forEach((child) => {
      if (typeof child === "string") {
        node.appendChild(document.createTextNode(child));
        return;
      }
      node.appendChild(child);
    });
  return node;
}

export function el(tagName, options = {}, children = []) {
  const node = document.createElement(tagName);
  const {
    className,
    text,
    html,
    attrs,
    dataset,
    on,
    value,
    type,
  } = options;

  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  if (html !== undefined) {
    node.innerHTML = html;
  }
  if (value !== undefined) {
    node.value = value;
  }
  if (type !== undefined) {
    node.type = type;
  }
  if (attrs) {
    Object.entries(attrs).forEach(([key, fieldValue]) => {
      if (fieldValue === null || fieldValue === undefined || fieldValue === false) {
        return;
      }
      if (fieldValue === true) {
        node.setAttribute(key, "");
        return;
      }
      node.setAttribute(key, String(fieldValue));
    });
  }
  if (dataset) {
    Object.entries(dataset).forEach(([key, fieldValue]) => {
      node.dataset[key] = String(fieldValue);
    });
  }
  if (on) {
    Object.entries(on).forEach(([eventName, handler]) => {
      node.addEventListener(eventName, handler);
    });
  }
  return appendChildren(node, children);
}
