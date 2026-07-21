const { Resvg } = require("@resvg/resvg-js");
const fs = require("fs");
const path = require("path");

const dir = __dirname;
const files = fs.readdirSync(dir).filter((f) => f.endsWith(".svg"));
if (!files.length) {
  console.error("No SVG files found in", dir);
  process.exit(1);
}
for (const f of files) {
  const svgPath = path.join(dir, f);
  let svg = fs.readFileSync(svgPath, "utf8");
  // Drop non-XML control characters (can appear after encoding mishaps)
  svg = [...svg].filter((ch) => {
    const c = ch.codePointAt(0);
    return ch === "\n" || ch === "\r" || ch === "\t" || c >= 32;
  }).join("");
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: 1400 },
    background: "white",
  });
  const png = resvg.render().asPng();
  const out = path.join(dir, f.replace(/\.svg$/, ".png"));
  fs.writeFileSync(out, png);
  console.log("wrote", path.basename(out), png.length, "bytes");
}
