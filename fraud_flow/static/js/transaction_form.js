(function () {
  const form = document.getElementById("transaction-form");
  const payloadPreview = document.getElementById("payload-preview");
  const resultEmpty = document.getElementById("result-empty");
  const resultShell = document.getElementById("result-shell");
  const resetButton = document.getElementById("reset-sample");
  const decisionCard = document.getElementById("decision-card");
  const routePill = document.getElementById("summary-route-pill");
  const rawPill = document.getElementById("summary-raw-pill");
  const openDashboardCase = document.getElementById("open-dashboard-case");
  const sample = window.__PAYSIM_EXAMPLE__ || {};

  const ACTION_LABELS = {
    approve: "Thông qua",
    review: "Xem xét",
    block: "Chặn",
    step_up: "Xác minh tăng cường",
  };

  const ROUTE_LABELS = {
    low: "Thấp",
    medium: "Trung bình",
    high: "Cao",
  };

  const TONE_CLASSES = ["tone-neutral", "tone-success", "tone-warning", "tone-danger", "tone-info"];

  if (!form) {
    return;
  }

  function parseNumber(value) {
    if (value === "" || value === null || value === undefined) {
      return 0;
    }
    return Number(value);
  }

  function formatScore(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(3) : "-";
  }

  function formatProbability(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${(number * 100).toFixed(4)}%` : "-";
  }

  function formatLatency(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(2)} ms` : "-";
  }

  function mapActionLabel(action) {
    return ACTION_LABELS[action] || String(action || "-");
  }

  function mapRouteLabel(route) {
    return ROUTE_LABELS[route] || String(route || "-");
  }

  function toneForAction(action) {
    if (action === "approve") {
      return "tone-success";
    }
    if (action === "review") {
      return "tone-warning";
    }
    if (action === "block") {
      return "tone-danger";
    }
    if (action === "step_up") {
      return "tone-info";
    }
    return "tone-neutral";
  }

  function toneForRoute(route) {
    if (route === "low") {
      return "tone-success";
    }
    if (route === "medium") {
      return "tone-warning";
    }
    if (route === "high") {
      return "tone-danger";
    }
    return "tone-neutral";
  }

  function applyTone(node, toneClass) {
    if (!node) {
      return;
    }
    TONE_CLASSES.forEach((item) => node.classList.remove(item));
    node.classList.add(toneClass);
  }

  function buildPayload() {
    const data = new FormData(form);
    const label = data.get("is_fraud");
    const payload = {
      source: "paysim",
      tx_type: String(data.get("tx_type") || "TRANSFER"),
      amount: parseNumber(data.get("amount")),
      timestamp: String(data.get("timestamp") || ""),
      extras: {
        card_id: String(data.get("card_id") || ""),
        merchant_id: String(data.get("merchant_id") || ""),
        device_id: String(data.get("device_id") || ""),
        ip_address: String(data.get("ip_address") || ""),
        location_id: String(data.get("location_id") || ""),
      },
      oldbalanceOrg: parseNumber(data.get("oldbalanceOrg")),
      newbalanceOrig: parseNumber(data.get("newbalanceOrig")),
      oldbalanceDest: parseNumber(data.get("oldbalanceDest")),
      newbalanceDest: parseNumber(data.get("newbalanceDest")),
    };

    if (label !== "") {
      payload.is_fraud = Number(label);
    }

    return payload;
  }

  function updatePreview() {
    payloadPreview.textContent = JSON.stringify(buildPayload(), null, 2);
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) {
      node.textContent = value;
    }
  }

  function fillFormWithSample() {
    form.querySelector('[name="tx_type"]').value = sample.tx_type || "TRANSFER";
    form.querySelector('[name="amount"]').value = sample.amount || 0;
    form.querySelector('[name="timestamp"]').value = sample.timestamp || "";
    form.querySelector('[name="card_id"]').value = sample.extras?.card_id || "";
    form.querySelector('[name="merchant_id"]').value = sample.extras?.merchant_id || "";
    form.querySelector('[name="device_id"]').value = sample.extras?.device_id || "";
    form.querySelector('[name="location_id"]').value = sample.extras?.location_id || "";
    form.querySelector('[name="ip_address"]').value = sample.extras?.ip_address || "";
    form.querySelector('[name="oldbalanceOrg"]').value = sample.oldbalanceOrg || 0;
    form.querySelector('[name="newbalanceOrig"]').value = sample.newbalanceOrig || 0;
    form.querySelector('[name="oldbalanceDest"]').value = sample.oldbalanceDest || 0;
    form.querySelector('[name="newbalanceDest"]').value = sample.newbalanceDest || 0;
    form.querySelector('[name="is_fraud"]').value = String(sample.is_fraud ?? 0);
    updatePreview();
  }

  function fillResult(data) {
    const action = data.final_action || "-";
    const route = data.prediction?.route || "-";
    const rawProbability = data.prediction?.raw_probability;

    resultEmpty.classList.add("hidden");
    resultShell.classList.remove("hidden");

    setText("summary-score", formatScore(data.prediction?.score));
    setText("summary-raw", formatProbability(rawProbability));
    setText("summary-route", mapRouteLabel(route));
    setText("summary-action", mapActionLabel(action));
    setText("summary-latency", formatLatency(data.end_to_end_latency_ms));
    setText("final-note", data.final_note || data.narrative?.dashboard_summary || "-");
    setText("human-explanation", data.narrative?.human_readable_explanation || data.final_note || "-");
    setText("analyst-report", data.narrative?.analyst_report || "-");
    setText("dashboard-summary", data.narrative?.dashboard_summary || "-");

    if (openDashboardCase) {
      const txId = data.event?.tx_id;
      openDashboardCase.href = txId ? `/dashboard/html?tx_id=${encodeURIComponent(txId)}` : "/dashboard/html";
      openDashboardCase.textContent = txId ? `Mở ${txId} trên dashboard` : "Mở case này trên dashboard";
    }

    if (routePill) {
      routePill.textContent = `Route ${mapRouteLabel(route)}`;
      applyTone(routePill, toneForRoute(route));
    }

    if (rawPill) {
      rawPill.textContent = `Raw ${formatProbability(rawProbability)}`;
      applyTone(rawPill, "tone-neutral");
    }

    applyTone(decisionCard, toneForAction(action));
  }

  function fillError(message) {
    resultEmpty.classList.add("hidden");
    resultShell.classList.remove("hidden");

    setText("summary-score", "Lỗi");
    setText("summary-raw", "-");
    setText("summary-route", "-");
    setText("summary-action", "Thất bại");
    setText("summary-latency", "-");
    setText("final-note", "Request thất bại.");
    setText("human-explanation", message || "Không gửi được giao dịch.");
    setText("analyst-report", "Kiểm tra lại dữ liệu đầu vào hoặc trạng thái server.");
    setText("dashboard-summary", "Request thất bại.");

    if (openDashboardCase) {
      openDashboardCase.href = "/dashboard/html";
      openDashboardCase.textContent = "Mở dashboard";
    }

    if (routePill) {
      routePill.textContent = "Route -";
      applyTone(routePill, "tone-neutral");
    }

    if (rawPill) {
      rawPill.textContent = "Raw -";
      applyTone(rawPill, "tone-neutral");
    }

    applyTone(decisionCard, "tone-danger");
  }

  async function submitPayload(event) {
    event.preventDefault();
    const payload = buildPayload();
    updatePreview();

    try {
      const response = await fetch("/gateway/transaction", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Không gửi được giao dịch.");
      }

      fillResult(data);
    } catch (error) {
      fillError(error.message);
    }
  }

  form.addEventListener("input", updatePreview);
  form.addEventListener("submit", submitPayload);
  resetButton.addEventListener("click", fillFormWithSample);
  fillFormWithSample();
})();
