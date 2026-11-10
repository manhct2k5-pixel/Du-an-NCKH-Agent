(() => {
  const tooltip = document.createElement("div");
  tooltip.id = "metric-help";
  tooltip.className = "floating-tooltip";
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  document.body.append(tooltip);
  let active = null;
  function close() {
    tooltip.hidden = true;
    active?.removeAttribute("aria-describedby");
    active = null;
  }
  function show(button) {
    close(); active = button;
    tooltip.textContent = button.dataset.tooltip;
    tooltip.hidden = false;
    button.setAttribute("aria-describedby", tooltip.id);
    const box = button.getBoundingClientRect();
    const left = Math.max(16, Math.min(innerWidth - tooltip.offsetWidth - 16, box.left - tooltip.offsetWidth / 2));
    const top = box.top > tooltip.offsetHeight + 20 ? box.top - tooltip.offsetHeight - 10 : box.bottom + 10;
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${Math.max(12, Math.min(innerHeight - tooltip.offsetHeight - 12, top))}px`;
  }
  document.querySelectorAll(".metric-tooltip-icon").forEach(button => {
    button.addEventListener("mouseenter", () => show(button));
    button.addEventListener("mouseleave", close);
    button.addEventListener("focus", () => show(button));
    button.addEventListener("blur", close);
    button.addEventListener("click", () => show(button));
  });
  document.addEventListener("keydown", event => { if (event.key === "Escape") close(); });
  function reposition() {
    if (!active) return;
    const button=active, box=button.getBoundingClientRect();
    if (box.bottom < 0 || box.top > innerHeight) close();
    else show(button);
  }
  window.addEventListener("scroll", reposition, true);
  window.addEventListener("resize", reposition);
  function scrollRegions() {
    document.querySelectorAll(".table-wrap,.table-shell,.confusion-wrap,.sim-confusion-grid,.case-list,.queue-list,.trace-list").forEach(node => {
      if (node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1) {
        node.tabIndex = 0;
        node.setAttribute("role", "region");
        node.setAttribute("aria-label", node.closest("section,article")?.querySelector("h2,h3,.section-label")?.textContent.trim() || "Nội dung có thể cuộn");
      } else {
        node.removeAttribute("tabindex"); node.removeAttribute("role"); node.removeAttribute("aria-label");
      }
    });
  }
  scrollRegions();
  window.addEventListener("resize", scrollRegions);
  window.addEventListener("load", scrollRegions);
  document.addEventListener("toggle", scrollRegions, true);
  document.fonts?.ready.then(scrollRegions);
})();
