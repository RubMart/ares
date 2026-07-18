class ApiError extends Error {
  constructor(status, payload) {
    const detail = ApiClient.formatDetail(payload);
    super(detail || `Error HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

class ApiClient {
  static STORAGE_KEY = "api_webviewer_base_url";
  static HISTORY_KEY = "api_webviewer_search_history";
  static HISTORY_MAX = 5;

  static normalizeBaseUrl(url) {
    return url.replace(/\/+$/, "");
  }

  static loadHistory() {
    try {
      const raw = localStorage.getItem(ApiClient.HISTORY_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter((item) => typeof item === "string" && item.trim())
        .map((item) => item.trim())
        .slice(0, ApiClient.HISTORY_MAX);
    } catch {
      return [];
    }
  }

  static saveHistory(list) {
    localStorage.setItem(
      ApiClient.HISTORY_KEY,
      JSON.stringify(list.slice(0, ApiClient.HISTORY_MAX))
    );
  }

  static addToHistory(query) {
    const text = String(query || "").trim();
    if (!text) return ApiClient.loadHistory();
    const next = [text, ...ApiClient.loadHistory().filter((item) => item !== text)];
    ApiClient.saveHistory(next);
    return next;
  }

  static clearHistory() {
    localStorage.removeItem(ApiClient.HISTORY_KEY);
    return [];
  }

  static formatDetail(payload) {
    if (!payload) return null;
    if (typeof payload === "string") return payload;
    if (payload.detail) {
      if (typeof payload.detail === "string") return payload.detail;
      if (Array.isArray(payload.detail)) {
        return payload.detail
          .map((item) => item.msg || JSON.stringify(item))
          .join("; ");
      }
      return JSON.stringify(payload.detail);
    }
    return JSON.stringify(payload);
  }

  static async request(baseUrl, path, options = {}) {
    const url = `${ApiClient.normalizeBaseUrl(baseUrl)}${path}`;
    let response;

    try {
      response = await fetch(url, options);
    } catch (error) {
      throw new ApiError(0, {
        detail: `No se pudo conectar con la API (${error.message})`,
      });
    }

    let payload = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      payload = await response.json();
    } else if (!response.ok) {
      payload = { detail: await response.text() };
    }

    if (!response.ok) {
      throw new ApiError(response.status, payload);
    }

    return payload;
  }

  static async health(baseUrl) {
    return ApiClient.request(baseUrl, "/health");
  }

  static async catalog(baseUrl) {
    return ApiClient.request(baseUrl, "/catalog");
  }

  static async getLlmCache(baseUrl) {
    return ApiClient.request(baseUrl, "/cache/llm");
  }

  static async clearLlmCache(baseUrl) {
    return ApiClient.request(baseUrl, "/cache/llm", { method: "DELETE" });
  }

  static async search(baseUrl, params) {
    const body = { query: params.query.trim() };

    if (params.top_k != null && params.top_k !== "") {
      body.top_k = Number(params.top_k);
    }
    if (params.per_layer_limit != null && params.per_layer_limit !== "") {
      body.per_layer_limit = Number(params.per_layer_limit);
    }
    if (params.min_confidence != null && params.min_confidence !== "") {
      body.min_confidence = Number(params.min_confidence);
    }
    if (params.spatial_distance_m != null && params.spatial_distance_m !== "") {
      body.spatial_distance_m = Number(params.spatial_distance_m);
    }
    if (params.target) {
      body.target = String(params.target).trim();
    }
    if (params.reference) {
      body.reference = String(params.reference).trim();
    }
    if (params.spatial_relation) {
      body.spatial_relation = params.spatial_relation;
    }

    return ApiClient.request(baseUrl, "/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  static loadBaseUrl() {
    return localStorage.getItem(ApiClient.STORAGE_KEY) || "http://localhost:8000";
  }

  static saveBaseUrl(url) {
    localStorage.setItem(ApiClient.STORAGE_KEY, ApiClient.normalizeBaseUrl(url));
  }
}
