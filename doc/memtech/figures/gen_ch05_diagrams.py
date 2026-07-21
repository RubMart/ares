# -*- coding: utf-8 -*-
"""Generate SW-architecture diagrams for chapter 05 (PNG via resvg)."""
from __future__ import annotations

import subprocess
from pathlib import Path

FIG = Path(__file__).resolve().parent

SVGS: dict[str, str] = {
    "di-composition-root.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 420" role="img">
  <defs>
    <style>
      .b { fill:#f8fafc; stroke:#0f766e; stroke-width:1.5; rx:8; }
      .s { fill:#ecfdf5; stroke:#047857; stroke-width:1.5; rx:8; }
      .r { fill:#eff6ff; stroke:#1d4ed8; stroke-width:1.5; rx:8; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:12.5px; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:14px; font-weight:700; }
      .m { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
      .e { stroke:#334155; stroke-width:1.4; fill:none; marker-end:url(#a); }
    </style>
    <marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#334155"/>
    </marker>
  </defs>
  <text class="h" x="24" y="28">Composition root (api/dependencies.py + lifespan)</text>

  <rect class="s" x="40" y="52" width="220" height="100"/>
  <text class="t" x="60" y="82">lifespan / init_services()</text>
  <text class="m" x="55" y="104">ClipOnnxTextEmbedder (singleton)</text>
  <text class="m" x="55" y="122">CachingQueryAnalyzer</text>
  <text class="m" x="55" y="140">  -&gt; OllamaQueryAnalyzer</text>

  <rect class="r" x="300" y="52" width="200" height="100"/>
  <text class="t" x="330" y="90">Request scope</text>
  <text class="m" x="320" y="112">AsyncSession (asyncpg)</text>
  <text class="m" x="320" y="132">yield por peticion</text>

  <rect class="b" x="540" y="52" width="240" height="100"/>
  <text class="t" x="560" y="82">build_search_use_case()</text>
  <text class="m" x="555" y="104">+ PostgresCatalogRepository</text>
  <text class="m" x="555" y="122">+ PostgresDetectionRepository</text>
  <text class="m" x="555" y="140">-&gt; SearchDetectionsUseCase</text>

  <path class="e" d="M260,102 H300"/>
  <path class="e" d="M500,102 H540"/>

  <rect class="b" x="40" y="200" width="740" height="180"/>
  <text class="t" x="60" y="232">Puertos inyectados (domain) vs adaptadores (infrastructure)</text>
  <text class="m" x="60" y="260">QueryAnalyzer  &lt;-- CachingQueryAnalyzer(OllamaQueryAnalyzer)</text>
  <text class="m" x="60" y="282">TextEmbedder   &lt;-- ClipOnnxTextEmbedder</text>
  <text class="m" x="60" y="304">CatalogRepository / DetectionRepository &lt;-- Postgres*Repository(session)</text>
  <text class="m" x="60" y="336">El use case no importa FastAPI, SQLAlchemy ni Ollama: solo ABCs + DTOs.</text>
  <text class="m" x="60" y="358">Tests unitarios sustituyen puertos por fakes sin levantar HTTP ni BD.</text>
</svg>
""",
    "frontend-architecture.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 380" role="img">
  <defs>
    <style>
      .b { fill:#f8fafc; stroke:#0f766e; stroke-width:1.5; rx:8; }
      .p { fill:#eff6ff; stroke:#1d4ed8; stroke-width:1.5; rx:8; }
      .l { fill:#fff7ed; stroke:#c2410c; stroke-width:1.5; rx:8; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:12.5px; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:14px; font-weight:700; }
      .m { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
    </style>
  </defs>
  <text class="h" x="24" y="28">frontend/ - composicion sin store global</text>

  <rect class="p" x="40" y="52" width="740" height="70"/>
  <text class="t" x="60" y="82">app/page.tsx  (composition root + useState / useCallback)</text>
  <text class="m" x="60" y="102">results GeoJSON, query, filters, selection, interpretation open/close</text>

  <rect class="b" x="40" y="150" width="170" height="90"/>
  <text class="t" x="60" y="185">SearchPanel</text>
  <text class="m" x="55" y="208">query, chips, top-k</text>

  <rect class="b" x="230" y="150" width="170" height="90"/>
  <text class="t" x="260" y="185">MapView (OL)</text>
  <text class="m" x="245" y="208">dynamic SSR=false</text>

  <rect class="b" x="420" y="150" width="170" height="90"/>
  <text class="t" x="445" y="185">ResultsTable</text>
  <text class="m" x="440" y="208">seleccion &lt;-&gt; mapa</text>

  <rect class="b" x="610" y="150" width="170" height="90"/>
  <text class="t" x="630" y="185">Filtros / Catalog</text>
  <text class="m" x="625" y="208">cliente + capas COG</text>

  <rect class="l" x="40" y="270" width="740" height="80"/>
  <text class="t" x="60" y="300">lib/api/*  -  fetch tipado (search, catalog, health)</text>
  <text class="m" x="60" y="322">NEXT_PUBLIC_API_URL  |  timeout 60s en POST /search  |  sin Redux/Zustand</text>
</svg>
""",
    "paquete-dependencias-api.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 460" role="img">
  <defs>
    <style>
      .L1 { fill:#eff6ff; stroke:#1d4ed8; stroke-width:1.5; rx:10; }
      .L2 { fill:#ecfdf5; stroke:#047857; stroke-width:1.5; rx:10; }
      .L3 { fill:#fff7ed; stroke:#c2410c; stroke-width:1.5; rx:10; }
      .L4 { fill:#f5f3ff; stroke:#6d28d9; stroke-width:1.5; rx:10; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:13px; }
      .s { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:14px; font-weight:700; }
      .note { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#334155; font-size:11px; }
    </style>
  </defs>
  <text class="h" x="24" y="28">Regla de dependencia: hacia el dominio</text>
  <rect class="L1" x="60" y="50" width="600" height="70"/>
  <text class="t" x="80" y="80">api (HTTP)  routes / schemas / rate_limit / dependencies</text>
  <text class="s" x="80" y="100">conoce application + schemas; no conoce SQL ni Ollama</text>
  <rect class="L2" x="60" y="140" width="600" height="70"/>
  <text class="t" x="80" y="170">application  SearchDetectionsUseCase + DTOs</text>
  <text class="s" x="80" y="190">conoce domain (puertos); orquesta el pipeline de busqueda</text>
  <rect class="L3" x="60" y="230" width="600" height="80"/>
  <text class="t" x="80" y="260">domain  entities / value objects / repository+service ABCs</text>
  <text class="s" x="80" y="280">Detection, CatalogLayer, StructuredQuery, SearchFilters</text>
  <text class="s" x="80" y="298">cero imports de FastAPI, SQLAlchemy, transformers, httpx</text>
  <rect class="L4" x="60" y="330" width="600" height="90"/>
  <text class="t" x="80" y="360">infrastructure  implementa puertos</text>
  <text class="s" x="80" y="380">postgres_* / clip_text_embedder / ollama_* / parsers / geojson</text>
  <text class="s" x="80" y="398">depende del domain; es sustituible en tests</text>
  <text class="note" x="60" y="445">Flecha conceptual: api -&gt; application -&gt; domain &lt;- infrastructure</text>
</svg>
""",
}

for name, content in SVGS.items():
    (FIG / name).write_text(content, encoding="utf-8", newline="\n")
    print("wrote", name)

subprocess.check_call(["node", str(FIG / "render-svg-to-png.js")], cwd=FIG)
for png in sorted(FIG.glob("*.png")):
    if png.name.startswith(("di-", "frontend-", "paquete-")):
        print("png", png.name, png.stat().st_size)
