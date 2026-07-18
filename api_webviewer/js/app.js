(function () {
  const apiUrlInput = document.getElementById("api-url");
  const healthBadge = document.getElementById("health-badge");
  const healthDetail = document.getElementById("health-detail");
  const btnHealth = document.getElementById("btn-health");
  const searchForm = document.getElementById("search-form");
  const btnSearch = document.getElementById("btn-search");
  const queryInput = document.getElementById("query");
  const errorBanner = document.getElementById("error-banner");
  const infoBanner = document.getElementById("info-banner");
  const resultsSection = document.getElementById("results-section");
  const emptyState = document.getElementById("empty-state");
  const metadataPanel = document.getElementById("metadata-panel");
  const resultsTable = document.getElementById("results-table");
  const tableBody = resultsTable.querySelector("tbody");
  const jsonOutput = document.getElementById("json-output");
  const btnCopyJson = document.getElementById("btn-copy-json");
  const catalogList = document.getElementById("catalog-list");
  const btnRefreshCatalog = document.getElementById("btn-refresh-catalog");
  const splitView = document.getElementById("split-view");
  const splitResizer = document.getElementById("split-resizer");
  const paneMap = document.getElementById("pane-map");
  const paneTable = document.getElementById("pane-table");
  const filtersPanel = document.getElementById("filters-panel");
  const filterCount = document.getElementById("filter-count");
  const btnResetFilters = document.getElementById("btn-reset-filters");
  const classToggles = document.getElementById("class-toggles");
  const btnClassesAll = document.getElementById("btn-classes-all");
  const btnClassesNone = document.getElementById("btn-classes-none");
  const confidenceRangeEl = document.getElementById("confidence-range");
  const similarityRangeEl = document.getElementById("similarity-range");
  const confidenceValuesEl = document.getElementById("confidence-values");
  const similarityValuesEl = document.getElementById("similarity-values");

  const detectionMap = new DetectionMap("map", "map-popup");

  let currentResponse = null;
  let tableRows = [];
  let sortKey = "confianza";
  let sortDir = "desc";
  let selectedFeatureIndex = null;
  let catalogLayers = [];
  let activeCatalogLayerName = null;
  let dataBounds = {
    confidence: { min: 0, max: 1 },
    similarity: { min: 0, max: 1 },
  };
  let filters = {
    enabledClasses: new Set(),
    confidence: { min: 0, max: 1 },
    similarity: { min: 0, max: 1 },
  };
  let rangeControls = {
    confidence: null,
    similarity: null,
  };

  function getBaseUrl() {
    return ApiClient.normalizeBaseUrl(apiUrlInput.value.trim());
  }

  function setLoading(isLoading) {
    btnSearch.disabled = isLoading;
    btnSearch.querySelector(".btn-label").classList.toggle("hidden", isLoading);
    btnSearch.querySelector(".spinner").classList.toggle("hidden", !isLoading);
  }

  function hideBanner(el) {
    el.classList.add("hidden");
    el.textContent = "";
  }

  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.classList.remove("hidden");
    hideBanner(infoBanner);
  }

  function showInfo(message) {
    infoBanner.textContent = message;
    infoBanner.classList.remove("hidden");
    hideBanner(errorBanner);
  }

  function updateHealthBadge(data, isError) {
    if (isError) {
      healthBadge.textContent = "Error";
      healthBadge.className = "health-badge health-badge--error";
      healthDetail.textContent = data || "Sin conexión";
      return;
    }

    const status = data.status || "unknown";
    healthBadge.textContent = status;
    healthBadge.className = `health-badge health-badge--${status === "ok" ? "ok" : "degraded"}`;
    healthDetail.textContent = `DB: ${data.database} · ${data.clip_model} (${data.embedding_dim}d)`;
  }

  async function checkHealth() {
    try {
      const data = await ApiClient.health(getBaseUrl());
      updateHealthBadge(data, false);
    } catch (error) {
      updateHealthBadge(error.message, true);
    }
  }

  function renderCatalogList() {
    if (!catalogLayers.length) {
      catalogList.innerHTML = '<p class="muted">No hay capas en el catálogo.</p>';
      return;
    }

    catalogList.innerHTML = catalogLayers
      .map(
        (layer, index) => `
          <button
            type="button"
            class="catalog-item${layer.nombre_capa === activeCatalogLayerName ? " catalog-item--active" : ""}"
            data-layer-index="${index}"
          >
            <strong>${escapeHtml(layer.nombre_capa)}</strong>
            <span>${escapeHtml(layer.cog_url || "—")}</span>
          </button>`
      )
      .join("");
  }

  async function activateCatalogLayer(layer, options = {}) {
    const { fitBbox = true, showMessage = true } = options;
    if (!layer) return false;

    activeCatalogLayerName = layer.nombre_capa;
    renderCatalogList();

    if (!DetectionMap.isHttpCogUrl(layer.cog_url)) {
      detectionMap.removeCogLayer();
      if (showMessage) {
        showInfo(`La capa "${layer.nombre_capa}" no tiene una URL COG accesible por HTTP.`);
      }
      return false;
    }

    const loaded = await detectionMap.loadCogLayer(layer.cog_url, {
      fitBbox: fitBbox ? layer.bbox : null,
    });

    if (!loaded) {
      if (showMessage) {
        showInfo(`No se pudo cargar el COG de "${layer.nombre_capa}".`);
      }
      return false;
    }

    hideBanner(errorBanner);
    if (showMessage) {
      showInfo(`Ortofoto COG cargada: ${layer.nombre_capa}`);
      setTimeout(() => hideBanner(infoBanner), 2500);
    }

    return true;
  }

  function findCatalogLayerByName(name) {
    return catalogLayers.find((layer) => layer.nombre_capa === name);
  }

  function activateCatalogLayersByName(layerNames, options = {}) {
    const names = (layerNames || []).filter(Boolean);
    if (!names.length) return Promise.resolve(false);

    const layer = findCatalogLayerByName(names[0]);
    if (!layer) return Promise.resolve(false);

    return activateCatalogLayer(layer, {
      ...options,
      fitBbox: options.fitBbox ?? false,
      showMessage: options.showMessage ?? false,
    });
  }

  async function loadCatalog() {
    catalogList.innerHTML = '<p class="muted">Cargando catálogo…</p>';
    try {
      catalogLayers = await ApiClient.catalog(getBaseUrl());
      if (!catalogLayers.length) {
        catalogList.innerHTML = '<p class="muted">No hay capas en el catálogo.</p>';
        return;
      }

      const keepActive = catalogLayers.some((layer) => layer.nombre_capa === activeCatalogLayerName);
      if (!keepActive) {
        activeCatalogLayerName = catalogLayers[0].nombre_capa;
      }

      renderCatalogList();
      activateCatalogLayer(findCatalogLayerByName(activeCatalogLayerName), {
        fitBbox: true,
        showMessage: false,
      });
    } catch (error) {
      catalogLayers = [];
      activeCatalogLayerName = null;
      catalogList.innerHTML = `<p class="muted">Error: ${escapeHtml(error.message)}</p>`;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
  }

  function renderMetadata(response) {
    const meta = response.metadata || {};
    const sq = meta.structured_query || {};
    const candidates = (sq.clase_yolo_candidates || []).join(", ") || "—";
    const layers = (meta.layers_searched || []).join(", ") || "—";

    metadataPanel.innerHTML = `
      <div class="metadata-item">
        <label>Consulta</label>
        <span>${escapeHtml(meta.query || "—")}</span>
      </div>
      <div class="metadata-item">
        <label>Idioma</label>
        <span>${escapeHtml(meta.detected_language || "—")}</span>
      </div>
      <div class="metadata-item">
        <label>Total features</label>
        <span>${meta.total_features ?? 0}</span>
      </div>
      <div class="metadata-item">
        <label>Clases YOLO</label>
        <span>${escapeHtml(candidates)}</span>
      </div>
      <div class="metadata-item">
        <label>Capas</label>
        <span>${escapeHtml(layers)}</span>
      </div>
      ${
        sq.reasoning
          ? `<div class="metadata-reasoning">
               <details>
                 <summary>Razonamiento del analizador</summary>
                 <p>${escapeHtml(sq.reasoning)}</p>
               </details>
             </div>`
          : ""
      }
    `;
  }

  function formatMetric(value) {
    return Number(value).toFixed(4);
  }

  function computeDataBounds(rows) {
    const bounds = {
      confidence: { min: Infinity, max: -Infinity },
      similarity: { min: Infinity, max: -Infinity },
    };

    rows.forEach((row) => {
      if (typeof row.confianza === "number") {
        bounds.confidence.min = Math.min(bounds.confidence.min, row.confianza);
        bounds.confidence.max = Math.max(bounds.confidence.max, row.confianza);
      }
      if (typeof row.similarity === "number") {
        bounds.similarity.min = Math.min(bounds.similarity.min, row.similarity);
        bounds.similarity.max = Math.max(bounds.similarity.max, row.similarity);
      }
    });

    if (!Number.isFinite(bounds.confidence.min)) {
      bounds.confidence = { min: 0, max: 1 };
    }
    if (!Number.isFinite(bounds.similarity.min)) {
      bounds.similarity = { min: 0, max: 1 };
    }

    if (bounds.confidence.min === bounds.confidence.max) {
      bounds.confidence.max = Math.min(1, bounds.confidence.min + 0.01);
    }
    if (bounds.similarity.min === bounds.similarity.max) {
      bounds.similarity.max = Math.min(1, bounds.similarity.min + 0.01);
    }

    return bounds;
  }

  function getClassCounts(rows) {
    const counts = new Map();
    rows.forEach((row) => {
      counts.set(row.clase_yolo, (counts.get(row.clase_yolo) || 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }

  function rowPassesFilter(row) {
    if (!filters.enabledClasses.has(row.clase_yolo)) return false;
    if (row.confianza < filters.confidence.min || row.confianza > filters.confidence.max) return false;
    if (row.similarity < filters.similarity.min || row.similarity > filters.similarity.max) return false;
    return true;
  }

  function getSortedRows() {
    return [...tableRows].sort((a, b) => {
      const cmp = compareRows(a, b, sortKey);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }

  function getFilteredRows() {
    return getSortedRows().filter(rowPassesFilter);
  }

  function getVisibleIndices() {
    const visible = new Set();
    tableRows.forEach((row) => {
      if (rowPassesFilter(row)) {
        visible.add(row.featureIndex);
      }
    });
    return visible;
  }

  function updateRangeLabels() {
    confidenceValuesEl.textContent = `${formatMetric(filters.confidence.min)} – ${formatMetric(filters.confidence.max)}`;
    similarityValuesEl.textContent = `${formatMetric(filters.similarity.min)} – ${formatMetric(filters.similarity.max)}`;
  }

  function updateFilterCount() {
    const visible = getFilteredRows().length;
    const total = tableRows.length;
    filterCount.textContent = `${visible} de ${total} visibles`;
  }

  function escapeAttr(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;");
  }

  function renderClassToggles() {
    const classes = getClassCounts(tableRows);
    if (!classes.length) {
      classToggles.innerHTML = '<p class="muted filters-empty">Sin clases en los resultados.</p>';
      return;
    }

    classToggles.innerHTML = classes
      .map(
        ([className, count]) => `
          <button
            type="button"
            class="class-toggle ${filters.enabledClasses.has(className) ? "class-toggle--active" : ""}"
            data-class="${escapeAttr(className)}"
          >
            ${escapeHtml(className)}
            <span class="class-toggle__count">${count}</span>
          </button>`
      )
      .join("");
  }

  function createDualRange(container, options) {
    const { bounds, values, onChange } = options;
    const min = bounds.min;
    const max = bounds.max;
    const step = 0.0001;
    const totalSteps = Math.max(1, Math.round((max - min) / step));

    container.innerHTML = `
      <div class="dual-range__track"></div>
      <div class="dual-range__fill"></div>
      <input type="range" class="dual-range__input dual-range__input--min" min="0" max="${totalSteps}" value="0" aria-label="Mínimo">
      <input type="range" class="dual-range__input dual-range__input--max" min="0" max="${totalSteps}" value="${totalSteps}" aria-label="Máximo">
    `;

    const fill = container.querySelector(".dual-range__fill");
    const inputMin = container.querySelector(".dual-range__input--min");
    const inputMax = container.querySelector(".dual-range__input--max");

    function stepToValue(stepValue) {
      return min + stepValue * step;
    }

    function valueToStep(value) {
      const clamped = Math.max(min, Math.min(max, value));
      return Math.round((clamped - min) / step);
    }

    function updateFill() {
      const lo = Number(inputMin.value);
      const hi = Number(inputMax.value);
      const percentLo = (lo / totalSteps) * 100;
      const percentHi = (hi / totalSteps) * 100;
      fill.style.left = `${percentLo}%`;
      fill.style.width = `${Math.max(0, percentHi - percentLo)}%`;
    }

    function emit() {
      let lo = stepToValue(Number(inputMin.value));
      let hi = stepToValue(Number(inputMax.value));
      if (lo > hi) {
        [lo, hi] = [hi, lo];
      }
      updateFill();
      onChange(lo, hi);
    }

    inputMin.addEventListener("input", () => {
      if (Number(inputMin.value) > Number(inputMax.value)) {
        inputMin.value = inputMax.value;
      }
      emit();
    });

    inputMax.addEventListener("input", () => {
      if (Number(inputMax.value) < Number(inputMin.value)) {
        inputMax.value = inputMin.value;
      }
      emit();
    });

    return {
      setValues(nextMin, nextMax) {
        inputMin.value = valueToStep(nextMin);
        inputMax.value = valueToStep(nextMax);
        updateFill();
      },
    };
  }

  function initFiltersPanel() {
    dataBounds = computeDataBounds(tableRows);
    filters.enabledClasses = new Set(getClassCounts(tableRows).map(([className]) => className));
    filters.confidence = { ...dataBounds.confidence };
    filters.similarity = { ...dataBounds.similarity };

    renderClassToggles();
    updateRangeLabels();

    rangeControls.confidence = createDualRange(confidenceRangeEl, {
      bounds: dataBounds.confidence,
      values: filters.confidence,
      onChange: (min, max) => {
        filters.confidence = { min, max };
        updateRangeLabels();
        applyFilters();
      },
    });

    rangeControls.similarity = createDualRange(similarityRangeEl, {
      bounds: dataBounds.similarity,
      values: filters.similarity,
      onChange: (min, max) => {
        filters.similarity = { min, max };
        updateRangeLabels();
        applyFilters();
      },
    });

    rangeControls.confidence.setValues(filters.confidence.min, filters.confidence.max);
    rangeControls.similarity.setValues(filters.similarity.min, filters.similarity.max);
  }

  function resetFilters() {
    filters.enabledClasses = new Set(getClassCounts(tableRows).map(([className]) => className));
    filters.confidence = { ...dataBounds.confidence };
    filters.similarity = { ...dataBounds.similarity };

    renderClassToggles();
    rangeControls.confidence?.setValues(filters.confidence.min, filters.confidence.max);
    rangeControls.similarity?.setValues(filters.similarity.min, filters.similarity.max);
    updateRangeLabels();
    applyFilters();
  }

  function applyFilters() {
    const visibleIndices = getVisibleIndices();
    detectionMap.setFilteredIndices(visibleIndices);
    updateFilterCount();
    renderTable();

    if (selectedFeatureIndex !== null && !visibleIndices.has(selectedFeatureIndex)) {
      const firstVisible = getFilteredRows()[0];
      if (firstVisible) {
        detectionMap.selectFeature(firstVisible.featureIndex, { zoom: false, showPopup: false });
      } else {
        selectedFeatureIndex = null;
        detectionMap.selectedFeatureIndex = null;
        detectionMap.hidePopup();
        detectionMap.vectorLayer.changed();
        renderTable();
      }
    }

    if (tableRows.length > 0 && visibleIndices.size === 0) {
      showInfo("Ninguna detección coincide con los filtros actuales.");
    } else if (tableRows.length > 0) {
      hideBanner(infoBanner);
    }
  }

  function buildTableRows(features) {
    return features.map((feature, index) => {
      const p = feature.properties || {};
      return {
        featureIndex: index,
        index: index + 1,
        clase_yolo: p.clase_yolo ?? "—",
        similarity: p.similarity ?? 0,
        confianza: p.confianza ?? 0,
        layer: p.layer ?? "—",
        tile_id: p.tile_id ?? "—",
      };
    });
  }

  function scrollTableRowIntoView(featureIndex) {
    const row = tableBody.querySelector(`tr[data-feature-index="${featureIndex}"]`);
    if (row) {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function updateTableSelection(featureIndex) {
    selectedFeatureIndex = featureIndex;
    renderTable();
    scrollTableRowIntoView(featureIndex);
  }

  function focusFirstTableRow() {
    const firstRow = getFilteredRows()[0];
    if (!firstRow) return;
    detectionMap.selectFeature(firstRow.featureIndex, { zoom: true, showPopup: false });
  }

  function compareRows(a, b, key) {
    const va = a[key];
    const vb = b[key];

    if (typeof va === "number" && typeof vb === "number") {
      return va - vb;
    }
    return String(va).localeCompare(String(vb), undefined, { numeric: true });
  }

  function renderTable() {
    const sorted = getFilteredRows();

    tableBody.innerHTML = sorted
      .map(
        (row) => `
          <tr data-feature-index="${row.featureIndex}" class="${row.featureIndex === selectedFeatureIndex ? "row--selected" : ""}">
            <td>${row.index}</td>
            <td>${escapeHtml(row.clase_yolo)}</td>
            <td>${row.similarity.toFixed(4)}</td>
            <td>${typeof row.confianza === "number" ? row.confianza.toFixed(4) : row.confianza}</td>
            <td>${escapeHtml(row.layer)}</td>
            <td>${escapeHtml(row.tile_id)}</td>
          </tr>`
      )
      .join("");

    resultsTable.querySelectorAll("th").forEach((th) => {
      th.classList.remove("sorted-asc", "sorted-desc");
      if (th.dataset.sort === sortKey) {
        th.classList.add(sortDir === "asc" ? "sorted-asc" : "sorted-desc");
      }
    });
  }

  function initSplitResizer() {
    const MIN_MAP = 200;
    const MIN_TABLE = 200;
    let isDragging = false;

    function setSplitRatio(ratio) {
      const clamped = Math.max(0.25, Math.min(0.75, ratio));
      paneMap.style.flex = `0 0 ${clamped * 100}%`;
      detectionMap.updateSize();
    }

    function resizeFromPointer(clientX) {
      const rect = splitView.getBoundingClientRect();
      const resizerWidth = splitResizer.offsetWidth;
      const available = rect.width - resizerWidth;
      const offset = clientX - rect.left;
      const mapWidth = Math.max(MIN_MAP, Math.min(available - MIN_TABLE, offset));
      setSplitRatio(mapWidth / available);
    }

    function stopDragging() {
      if (!isDragging) return;
      isDragging = false;
      splitResizer.classList.remove("split-resizer--dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      detectionMap.updateSize();
    }

    splitResizer.addEventListener("mousedown", (event) => {
      isDragging = true;
      splitResizer.classList.add("split-resizer--dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      event.preventDefault();
    });

    splitResizer.addEventListener("touchstart", (event) => {
      isDragging = true;
      splitResizer.classList.add("split-resizer--dragging");
      event.preventDefault();
    }, { passive: false });

    document.addEventListener("mousemove", (event) => {
      if (!isDragging) return;
      resizeFromPointer(event.clientX);
    });

    document.addEventListener("touchmove", (event) => {
      if (!isDragging || !event.touches.length) return;
      resizeFromPointer(event.touches[0].clientX);
    }, { passive: true });

    document.addEventListener("mouseup", stopDragging);
    document.addEventListener("touchend", stopDragging);
    document.addEventListener("touchcancel", stopDragging);

    splitResizer.addEventListener("keydown", (event) => {
      const rect = splitView.getBoundingClientRect();
      const resizerWidth = splitResizer.offsetWidth;
      const available = rect.width - resizerWidth;
      const current = paneMap.getBoundingClientRect().width / available;
      const step = event.shiftKey ? 0.1 : 0.05;

      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const delta = event.key === "ArrowLeft" ? -step : step;
        setSplitRatio(current + delta);
      }
    });

    window.addEventListener("resize", () => detectionMap.updateSize());
  }

  function renderResults(response) {
    currentResponse = response;
    emptyState.classList.add("hidden");
    resultsSection.classList.remove("hidden");

    renderMetadata(response);
    selectedFeatureIndex = null;

    const searchedLayers = response.metadata?.layers_searched || [];
    void activateCatalogLayersByName(searchedLayers, { fitBbox: false, showMessage: false });

    detectionMap.loadGeoJson(response);
    detectionMap.refreshMapSize();
    tableRows = buildTableRows(response.features || []);
    initFiltersPanel();
    applyFilters();
    focusFirstTableRow();
    jsonOutput.textContent = JSON.stringify(response, null, 2);
    requestAnimationFrame(() => detectionMap.updateSize());

    const total = response.metadata?.total_features ?? response.features?.length ?? 0;
    if (total === 0) {
      showInfo("0 detecciones encontradas para esta consulta.");
    } else {
      hideBanner(infoBanner);
    }
  }

  apiUrlInput.value = ApiClient.loadBaseUrl();

  apiUrlInput.addEventListener("change", () => {
    ApiClient.saveBaseUrl(apiUrlInput.value);
    checkHealth();
    loadCatalog();
  });

  btnHealth.addEventListener("click", checkHealth);
  btnRefreshCatalog.addEventListener("click", loadCatalog);

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      queryInput.value = chip.dataset.query;
      queryInput.focus();
    });
  });

  detectionMap.onFeatureSelect = updateTableSelection;

  detectionMap.onCogError = (error, cogUrl) => {
    showError(
      `No se pudo leer el COG (${cogUrl}). Comprueba que el servidor admite Range requests y CORS. ${error?.message || ""}`.trim()
    );
  };

  catalogList.addEventListener("click", (event) => {
    const item = event.target.closest("[data-layer-index]");
    if (!item) return;

    const layer = catalogLayers[Number(item.dataset.layerIndex)];
    if (layer) {
      activateCatalogLayer(layer, { fitBbox: true, showMessage: true });
    }
  });

  classToggles.addEventListener("click", (event) => {
    const toggle = event.target.closest(".class-toggle");
    if (!toggle) return;

    const className = toggle.dataset.class;
    if (filters.enabledClasses.has(className)) {
      filters.enabledClasses.delete(className);
    } else {
      filters.enabledClasses.add(className);
    }

    toggle.classList.toggle("class-toggle--active");
    applyFilters();
  });

  btnClassesAll.addEventListener("click", () => {
    filters.enabledClasses = new Set(getClassCounts(tableRows).map(([className]) => className));
    renderClassToggles();
    applyFilters();
  });

  btnClassesNone.addEventListener("click", () => {
    filters.enabledClasses.clear();
    renderClassToggles();
    applyFilters();
  });

  btnResetFilters.addEventListener("click", resetFilters);

  tableBody.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-feature-index]");
    if (!row) return;
    detectionMap.selectFeature(Number(row.dataset.featureIndex), { zoom: true });
  });

  resultsTable.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDir = key === "similarity" || key === "confianza" ? "desc" : "asc";
      }
      renderTable();
    });
  });

  btnCopyJson.addEventListener("click", async () => {
    if (!currentResponse) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(currentResponse, null, 2));
      showInfo("JSON copiado al portapapeles.");
      setTimeout(() => hideBanner(infoBanner), 2000);
    } catch {
      showError("No se pudo copiar al portapapeles.");
    }
  });

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideBanner(errorBanner);
    hideBanner(infoBanner);
    setLoading(true);

    try {
      ApiClient.saveBaseUrl(apiUrlInput.value);
      const response = await ApiClient.search(getBaseUrl(), {
        query: queryInput.value,
        top_k: document.getElementById("top-k").value,
        per_layer_limit: document.getElementById("per-layer-limit").value,
        min_confidence: document.getElementById("min-confidence").value,
      });
      renderResults(response);
    } catch (error) {
      showError(error.message);
    } finally {
      setLoading(false);
    }
  });

  checkHealth();
  loadCatalog();
  initSplitResizer();
})();
