# -*- coding: utf-8 -*-
"""Regenerate memtech SVG figures (ASCII-safe) and rasterize to PNG."""
from __future__ import annotations

import subprocess
from pathlib import Path

FIG = Path(__file__).resolve().parent

SVGS: dict[str, str] = {
    "arquitectura-e2e.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 420" role="img">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#334155"/>
    </marker>
    <style>
      .box { fill:#f8fafc; stroke:#0f766e; stroke-width:1.5; rx:8; }
      .box-db { fill:#ecfdf5; stroke:#047857; stroke-width:2; rx:8; }
      .box-ui { fill:#eff6ff; stroke:#1d4ed8; stroke-width:1.5; rx:8; }
      .lbl { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:13px; }
      .sub { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
      .title { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:15px; font-weight:700; }
      .band { fill:#f1f5f9; stroke:#cbd5e1; stroke-width:1; rx:10; }
      .line { stroke:#334155; stroke-width:1.6; fill:none; marker-end:url(#arrow); }
    </style>
  </defs>
  <rect class="band" x="16" y="16" width="888" height="170"/>
  <text class="title" x="32" y="42">Plano offline - indexacion (tools/)</text>
  <rect class="box" x="36" y="64" width="110" height="88"/>
  <text class="lbl" x="54" y="100">Ortofoto</text>
  <text class="sub" x="48" y="118">COG + tiles</text>
  <text class="sub" x="62" y="134">z=16 XYZ</text>
  <path class="line" d="M146,108 H168"/>
  <rect class="box" x="168" y="64" width="120" height="88"/>
  <text class="lbl" x="196" y="100">YOLO</text>
  <text class="sub" x="182" y="118">detect.py</text>
  <text class="sub" x="178" y="134">{stem}.json</text>
  <path class="line" d="M288,108 H310"/>
  <rect class="box" x="310" y="64" width="120" height="88"/>
  <text class="lbl" x="340" y="100">CLIP</text>
  <text class="sub" x="324" y="118">embed.py</text>
  <text class="sub" x="312" y="134">vector(512) L2</text>
  <path class="line" d="M430,108 H452"/>
  <rect class="box" x="452" y="64" width="130" height="88"/>
  <text class="lbl" x="474" y="100">SQL</text>
  <text class="sub" x="462" y="118">embed2psql.py</text>
  <text class="sub" x="458" y="134">schema + data</text>
  <path class="line" d="M582,108 H604"/>
  <rect class="box-db" x="604" y="64" width="270" height="88"/>
  <text class="lbl" x="648" y="96">PostgreSQL</text>
  <text class="sub" x="628" y="116">PostGIS - geometrias 3857</text>
  <text class="sub" x="628" y="134">pgvector - HNSW coseno</text>
  <rect class="band" x="16" y="210" width="888" height="190"/>
  <text class="title" x="32" y="236">Plano online - consulta (api/ + frontend/)</text>
  <rect class="box-ui" x="36" y="260" width="150" height="100"/>
  <text class="lbl" x="72" y="300">Usuario</text>
  <text class="sub" x="48" y="320">consulta NL</text>
  <text class="sub" x="52" y="338">ES / EN</text>
  <path class="line" d="M186,310 H208"/>
  <rect class="box-ui" x="208" y="260" width="150" height="100"/>
  <text class="lbl" x="242" y="296">Frontend</text>
  <text class="sub" x="222" y="316">Next.js + OL</text>
  <text class="sub" x="228" y="334">mapa / tabla</text>
  <path class="line" d="M358,310 H380"/>
  <rect class="box" x="380" y="260" width="170" height="100"/>
  <text class="lbl" x="426" y="292">API FastAPI</text>
  <text class="sub" x="392" y="312">override / parser</text>
  <text class="sub" x="400" y="328">Ollama / CLIP</text>
  <text class="sub" x="398" y="344">hibrida / espacial</text>
  <path class="line" d="M550,310 H572"/>
  <rect class="box-db" x="572" y="260" width="300" height="100"/>
  <text class="lbl" x="640" y="296">Indice materializado</text>
  <text class="sub" x="600" y="318">filtro clase + ranking CLIP</text>
  <text class="sub" x="600" y="336">ST_DWithin (near)</text>
  <text class="sub" x="600" y="354">GeoJSON + interpretacion</text>
  <path class="line" d="M722,64 V250" style="stroke-dasharray:4 3"/>
</svg>
""",
    "pipeline-offline-artefactos.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 300" role="img">
  <defs>
    <marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#334155"/>
    </marker>
    <style>
      .b { fill:#f8fafc; stroke:#0f766e; stroke-width:1.5; rx:8; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:12px; }
      .s { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:10.5px; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:14px; font-weight:700; }
      .e { stroke:#334155; stroke-width:1.5; fill:none; marker-end:url(#ar); }
    </style>
  </defs>
  <text class="h" x="20" y="28">Artefactos por etapa (companions junto al tile)</text>
  <rect class="b" x="20" y="60" width="120" height="90"/>
  <text class="t" x="48" y="98">tile.png</text>
  <text class="s" x="36" y="118">16/x/y.png</text>
  <path class="e" d="M140,105 H160"/>
  <rect class="b" x="160" y="60" width="120" height="90"/>
  <text class="t" x="182" y="92">detect.py</text>
  <text class="s" x="172" y="112">{stem}.json</text>
  <text class="s" x="168" y="128">bbox + 3857</text>
  <path class="e" d="M280,105 H300"/>
  <rect class="b" x="300" y="60" width="120" height="90"/>
  <text class="t" x="324" y="92">embed.py</text>
  <text class="s" x="306" y="112">*_emb.json</text>
  <text class="s" x="314" y="128">512-d L2</text>
  <path class="e" d="M420,105 H440"/>
  <rect class="b" x="440" y="60" width="130" height="90"/>
  <text class="t" x="454" y="92">thumbnail.py</text>
  <text class="s" x="454" y="112">*_thumb.jpg</text>
  <text class="s" x="458" y="128">opcional</text>
  <path class="e" d="M570,105 H590"/>
  <rect class="b" x="590" y="60" width="200" height="90"/>
  <text class="t" x="622" y="92">embed2psql.py</text>
  <text class="s" x="608" y="112">*_schema.sql / *_data.sql</text>
  <text class="s" x="618" y="128">+ detecciones_catalogo</text>
  <text class="s" x="20" y="190">Requisito: layout XYZ de gdal2tiles (z/x/y). Sin el no hay tile_id ni bbox3857 validos.</text>
  <text class="s" x="20" y="212">Modelos (--all-models): visdrone, photovoltaic, building, swimming-pool, yolo11m-obb.</text>
  <text class="s" x="20" y="234">Pesos en repo/models/ (fuera de git). Inferencia operable en CPU.</text>
  <text class="s" x="20" y="256">Catalogo: nombre_capa - tabla de detecciones; bbox de capa + cog_url para el visor.</text>
</svg>
""",
    "flujo-consulta-online.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 560" role="img">
  <defs>
    <marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#334155"/>
    </marker>
    <style>
      .n { fill:#f8fafc; stroke:#0f766e; stroke-width:1.5; }
      .d { fill:#fff7ed; stroke:#c2410c; stroke-width:1.5; }
      .ok { fill:#ecfdf5; stroke:#047857; stroke-width:1.5; }
      .llm { fill:#f5f3ff; stroke:#6d28d9; stroke-width:1.5; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:13px; }
      .s { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:15px; font-weight:700; }
      .e { stroke:#334155; stroke-width:1.5; fill:none; marker-end:url(#a); }
    </style>
  </defs>
  <text class="h" x="24" y="28">SearchDetectionsUseCase - orden de interpretacion</text>
  <rect class="n" x="280" y="48" width="220" height="48" rx="8"/>
  <text class="t" x="318" y="78">POST /search (query...)</text>
  <path class="e" d="M390,96 V118"/>
  <rect class="d" x="250" y="118" width="280" height="52" rx="8"/>
  <text class="t" x="290" y="140">Overrides suficientes?</text>
  <text class="s" x="278" y="158">target [, reference, relation]</text>
  <path class="e" d="M250,144 H140"/>
  <text class="s" x="148" y="136">si</text>
  <rect class="ok" x="40" y="122" width="100" height="44" rx="8"/>
  <text class="t" x="52" y="150">override</text>
  <path class="e" d="M390,170 V192"/>
  <text class="s" x="398" y="186">no</text>
  <rect class="d" x="250" y="192" width="280" height="52" rx="8"/>
  <text class="t" x="278" y="214">Parser determinista?</text>
  <text class="s" x="268" y="232">match exacto de catalogo</text>
  <path class="e" d="M250,218 H140"/>
  <text class="s" x="148" y="210">si</text>
  <rect class="ok" x="40" y="196" width="100" height="44" rx="8"/>
  <text class="t" x="62" y="224">parser</text>
  <path class="e" d="M390,244 V266"/>
  <text class="s" x="398" y="260">no</text>
  <rect class="llm" x="250" y="266" width="280" height="52" rx="8"/>
  <text class="t" x="300" y="288">Ollama (+ cache)</text>
  <text class="s" x="272" y="306">+ fallback de catalogo - llm</text>
  <path class="e" d="M90,166 V360"/>
  <path class="e" d="M90,240 V360"/>
  <path class="e" d="M390,318 V360"/>
  <rect class="n" x="200" y="360" width="380" height="56" rx="8"/>
  <text class="t" x="250" y="384">StructuredQuery consolidada</text>
  <text class="s" x="230" y="402">intent / clases / attrs / spatial fields</text>
  <path class="e" d="M390,416 V438"/>
  <rect class="n" x="200" y="438" width="380" height="48" rx="8"/>
  <text class="t" x="236" y="468">CLIP texto = target + atributos</text>
  <path class="e" d="M390,486 V508"/>
  <rect class="ok" x="120" y="508" width="540" height="40" rx="8"/>
  <text class="t" x="180" y="534">BD: search_hybrid | search_spatial_near - GeoJSON</text>
</svg>
""",
    "busqueda-hibrida-vs-espacial.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 380" role="img">
  <defs>
    <style>
      .card { fill:#f8fafc; stroke:#64748b; stroke-width:1.2; rx:10; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:15px; font-weight:700; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:12.5px; }
      .s { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
      .pill { fill:#ccfbf1; stroke:#0f766e; }
      .pill2 { fill:#dbeafe; stroke:#1d4ed8; }
    </style>
  </defs>
  <text class="h" x="24" y="28">Dos modos de recuperacion sobre el mismo indice</text>
  <rect class="card" x="24" y="52" width="390" height="300"/>
  <rect class="pill" x="44" y="72" width="160" height="28" rx="14"/>
  <text class="t" x="68" y="91">search_hybrid</text>
  <text class="t" x="44" y="124">Intent: search_class</text>
  <text class="s" x="44" y="148">Ej.: piscinas, coches rojos</text>
  <text class="t" x="44" y="180">1. WHERE clase_yolo = ANY(...)</text>
  <text class="t" x="44" y="202">2. ORDER BY embedding &lt;=&gt; q</text>
  <text class="t" x="44" y="224">3. similarity = 1 - distancia</text>
  <text class="s" x="44" y="256">CLIP embebe solo target + attrs</text>
  <text class="s" x="44" y="274">(p. ej. coches rojos - color)</text>
  <text class="s" x="44" y="304">Indice: HNSW vector_cosine_ops</text>
  <text class="s" x="44" y="322">+ filtro categorico duro</text>
  <rect class="card" x="446" y="52" width="390" height="300"/>
  <rect class="pill2" x="466" y="72" width="200" height="28" rx="14"/>
  <text class="t" x="486" y="91">search_spatial_near</text>
  <text class="t" x="466" y="124">Intent: search_spatial</text>
  <text class="s" x="466" y="148">Ej.: coches cerca de rotonda</text>
  <text class="t" x="466" y="180">1. Candidatos target + reference</text>
  <text class="t" x="466" y="202">2. ST_DWithin(t.geom, r.geom, d)</text>
  <text class="t" x="466" y="224">3. Nearest ref + rank CLIP target</text>
  <text class="s" x="466" y="256">d default 50 m (max. 500 m)</text>
  <text class="s" x="466" y="274">EPSG:3857 ~ metros</text>
  <text class="s" x="466" y="304">Respuesta: distance_to_reference_m</text>
  <text class="s" x="466" y="322">+ metadata.reference_features</text>
</svg>
""",
    "clean-architecture-api.svg": """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 420" role="img">
  <defs>
    <style>
      .L1 { fill:#eff6ff; stroke:#1d4ed8; stroke-width:1.5; rx:10; }
      .L2 { fill:#ecfdf5; stroke:#047857; stroke-width:1.5; rx:10; }
      .L3 { fill:#fff7ed; stroke:#c2410c; stroke-width:1.5; rx:10; }
      .L4 { fill:#f5f3ff; stroke:#6d28d9; stroke-width:1.5; rx:10; }
      .t { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:13px; }
      .s { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#475569; font-size:11px; }
      .h { font-family:Segoe UI,Helvetica,Arial,sans-serif; fill:#0f172a; font-size:15px; font-weight:700; }
    </style>
  </defs>
  <text class="h" x="24" y="28">api/ - capas y dependencias hacia dentro</text>
  <rect class="L1" x="40" y="52" width="680" height="70"/>
  <text class="t" x="60" y="82">api (HTTP)</text>
  <text class="s" x="60" y="102">routes / schemas Pydantic / dependencies / rate limit</text>
  <rect class="L2" x="40" y="140" width="680" height="70"/>
  <text class="t" x="60" y="170">application</text>
  <text class="s" x="60" y="190">SearchDetectionsUseCase / DTOs / orquestacion override-parser-LLM-CLIP-BD</text>
  <rect class="L3" x="40" y="228" width="680" height="70"/>
  <text class="t" x="60" y="258">domain</text>
  <text class="s" x="60" y="278">Detection / CatalogLayer / StructuredQuery / puertos ABC</text>
  <rect class="L4" x="40" y="316" width="680" height="80"/>
  <text class="t" x="60" y="346">infrastructure</text>
  <text class="s" x="60" y="366">PostgresDetectionRepository / ClipOnnxTextEmbedder / OllamaQueryAnalyzer</text>
  <text class="s" x="60" y="384">deterministic_query_parser / GeoJsonSerializer / catalogos YOLO</text>
</svg>
""",
}


def main() -> None:
    for name, content in SVGS.items():
        path = FIG / name
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"svg: {name}")

    subprocess.check_call(["node", str(FIG / "render-svg-to-png.js")], cwd=FIG)
    for png in sorted(FIG.glob("*.png")):
        print(f"png: {png.name} ({png.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
