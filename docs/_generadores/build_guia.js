// Guía Técnica STYLUS (estilo consultoría). Datos: docs/guia/guia_data.json + docs/guia/img/*.png
// Uso: python docs/_generadores/build_guia_data.py && node docs/_generadores/build_guia.js [paginas.json]
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, HeadingLevel, AlignmentType,
  WidthType, ShadingType, BorderStyle, LevelFormat, PageBreak, Header, Footer, PageNumber, TabStopType,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader, VerticalAlign, TableLayoutType,
} = require("docx");

const ROOT = path.resolve(__dirname, "../..");
const DATA = JSON.parse(fs.readFileSync(`${ROOT}/docs/guia/guia_data.json`, "utf8"));
const IMG = `${ROOT}/docs/guia/img`;
const OUT = `${ROOT}/docs/entrega1/Guia_Tecnica_STYLUS.docx`;
const PAGES = process.argv[2] ? JSON.parse(fs.readFileSync(process.argv[2], "utf8")) : {};

const NAVY = "1F3864", ACCENT = "2E75B6", GREY = "595959", LIGHT = "EAF1FB", ZEBRA = "F5F8FC";
const BRONZE = "B87333", SILVER = "8C99A6", GOLD = "C9A227", TEAL = "1B998B", ORANGE = "E07A1F", PURPLE = "6A4C93";
const OKF = "E3F1E4", OKC = "2E7D32", LIF = "FFF4D6", LIC = "8A6100", PEF = "FBE3E3", PEC = "C62828";
const FONT = "Arial";
const W = 9638; // A4 con márgenes de 2 cm
const P_ = DATA.params, D = DATA.derived;
const DS = { bronze: D.datasets.bronze, silver: D.datasets.silver, gold: D.datasets.gold, ops: D.datasets.ops, retail: "Cloud SQL · retail" };

// ---------------- utilidades de texto ----------------
const run = (t, o = {}) => new TextRun({ text: String(t), font: o.mono ? "Consolas" : FONT, size: o.size || 20, bold: o.bold,
  italics: o.italics, color: o.color, underline: o.underline ? {} : undefined,
  shading: o.mono ? { type: ShadingType.CLEAR, fill: "EEF1F5", color: "auto" } : undefined });

// **negrita**, __subrayado__, `código`
function rich(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`)/g;
  let last = 0, m;
  const s = String(text);
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(run(s.slice(last, m.index), base));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(run(tok.slice(2, -2), { ...base, bold: true, color: base.color || NAVY }));
    else if (tok.startsWith("__")) out.push(run(tok.slice(2, -2), { ...base, underline: true, bold: true }));
    else out.push(run(tok.slice(1, -1), { ...base, mono: true, size: (base.size || 20) - 2 }));
    last = m.index + tok.length;
  }
  if (last < s.length) out.push(run(s.slice(last), base));
  return out;
}

const P = (t, o = {}) => new Paragraph({ spacing: { after: o.after ?? 120, line: 276 }, alignment: o.align || AlignmentType.JUSTIFIED,
  keepNext: o.keepNext, children: rich(t, o) });
const B = (t, lvl = 0) => new Paragraph({ numbering: { reference: "bul", level: lvl }, spacing: { after: 60, line: 264 }, children: rich(t) });
const N = (t) => new Paragraph({ numbering: { reference: "num", level: 0 }, spacing: { after: 60, line: 264 }, children: rich(t) });
const SP = (after = 120) => new Paragraph({ spacing: { after }, children: [] });
const BR = () => new Paragraph({ children: [new PageBreak()] });

const TOC = [];
const H1 = (t, o = {}) => { TOC.push([1, t]); return new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: o.pb !== false, children: [run(t, { size: 32, bold: true, color: NAVY })] }); };
const H2 = (t) => { TOC.push([2, t]); return new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: [run(t, { size: 25, bold: true, color: ACCENT })] }); };
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, children: [run(t, { size: 21, bold: true, color: NAVY })] });

let nFig = 0, nTab = 0;
const capFig = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
  children: [run(`Figura ${++nFig}. `, { bold: true, size: 17, color: NAVY }), run(t, { italics: true, size: 17, color: GREY })] });
const capTab = (t) => new Paragraph({ keepNext: true, spacing: { before: 120, after: 60 },
  children: [run(`Tabla ${++nTab}. `, { bold: true, size: 17, color: NAVY }), run(t, { italics: true, size: 17, color: GREY })] });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}
function img(name, widthPx, caption) {
  const { w, h, data } = pngSize(`${IMG}/${name}`);
  const wpx = Math.min(widthPx, 640);
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 0 }, children: [new ImageRun({
    type: "png", data, transformation: { width: wpx, height: Math.round(wpx * h / w) },
    altText: { title: caption, description: caption, name } })] }), capFig(caption)];
}

// ---------------- tablas ----------------
const thin = { style: BorderStyle.SINGLE, size: 4, color: "C9D1DC" };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const ESTADO = {
  "Hecho": [OKF, OKC, "✔ Hecho"], "Listo para desplegar": [LIF, LIC, "● Listo p/desplegar"], "Pendiente": [PEF, PEC, "✖ Pendiente"],
  "R": ["D6E4F5", NAVY, "R"], "A": ["EEF1F5", GREY, "A"], "R/A": ["D6E4F5", NAVY, "R/A"],
  "Alta": [PEF, PEC, "Alta"], "Media": [LIF, LIC, "Media"], "Baja": [OKF, OKC, "Baja"],
};
function cell(text, width, o = {}) {
  const keep = o.keep;
  const st = o.status ? ESTADO[String(text)] : null;
  const fill = st ? st[0] : o.fill;
  return new TableCell({
    width: { size: width, type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
    shading: fill ? { type: ShadingType.CLEAR, fill, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: o.align || AlignmentType.LEFT, spacing: { after: 0 }, keepNext: keep,
      children: st ? [run(st[2], { bold: true, size: o.size || 17, color: st[1] })]
        : rich(text ?? "", { size: o.size || 17, bold: o.bold, color: o.color }) })],
  });
}
function table(headers, rows, widths, o = {}) {
  const tot = widths.reduce((a, b) => a + b, 0);
  const ws = widths.map(x => Math.round(x * W / tot));
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0);
  const size = o.size || 17;
  const keep = o.keep ?? rows.length <= 14;
  const head = new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, ws[i],
    { fill: o.headFill || NAVY, color: "FFFFFF", bold: true, size, keep: true })) });
  const body = rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((v, i) => cell(v, ws[i], {
    size, keep: keep && ri < rows.length - 1, status: (o.statusCols || []).includes(i), bold: o.boldFirst && i === 0, color: o.boldFirst && i === 0 ? NAVY : undefined,
    fill: o.rowFill ? o.rowFill(r, ri) : (ri % 2 ? ZEBRA : undefined), align: (o.right || []).includes(i) ? AlignmentType.RIGHT : undefined })) }));
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: ws, layout: TableLayoutType.FIXED, rows: [head, ...body] }), SP(160)];
}
function callout(title, lines, color = ACCENT, fill = LIGHT) {
  const side = { style: BorderStyle.SINGLE, size: 24, color };
  const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [new TableCell({
    width: { size: W, type: WidthType.DXA }, borders: { left: side, top: none, bottom: none, right: none },
    shading: { type: ShadingType.CLEAR, fill, color: "auto" }, margins: { top: 110, bottom: 110, left: 200, right: 160 },
    children: [new Paragraph({ spacing: { after: 60 }, children: [run(title, { bold: true, size: 20, color })] }),
      ...lines.map(l => new Paragraph({ spacing: { after: 40 }, children: rich(l, { size: 19 }) }))] })] })] }), SP(160)];
}
function kpis(items) {
  const w = Math.floor(W / items.length);
  const ws = items.map(() => w); ws[ws.length - 1] += W - w * items.length;
  const white = { style: BorderStyle.SINGLE, size: 18, color: "FFFFFF" };
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: ws, rows: [new TableRow({ children: items.map(([v, l, c], i) =>
    new TableCell({ width: { size: ws[i], type: WidthType.DXA }, borders: { top: white, bottom: white, left: white, right: white },
      shading: { type: ShadingType.CLEAR, fill: c, color: "auto" }, margins: { top: 140, bottom: 140, left: 100, right: 100 },
      children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [run(v, { bold: true, size: 34, color: "FFFFFF" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 }, children: [run(l, { size: 16, color: "FFFFFF" })] })] })) })] }), SP(200)];
}

// ---------------- datos derivados ----------------
const T = DATA.tareas;
const personas = ["Estuardo Oliver", "Winston Quispe", "Nicole Arenas", "Gianmarco Mejia"];
const ini = { "Estuardo Oliver": "EO", "Winston Quispe": "WQ", "Nicole Arenas": "NA", "Gianmarco Mejia": "GM" };
const cnt = (f) => T.filter(f).length;
const pct = (p) => Math.round(100 * cnt(t => t.paso === p && t.estado === "Hecho") / cnt(t => t.paso === p));
const fases = [...new Set(T.map(t => t.fase))];
const raci = fases.map(f => [f, ...personas.map(p => {
  const r = T.some(t => t.fase === f && t.responsable === p), a = T.some(t => t.fase === f && String(t.apoyo || "").includes(p));
  return r && a ? "R/A" : r ? "R" : a ? "A" : "";
})]);
const costo = DATA.costos.totales;
const usd = (x, d = 2) => "USD " + Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const dsName = (k) => DS[k] || k;

// ======================================================================
// PORTADA
// ======================================================================
const cover = [
  SP(1400),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [new TableCell({
    width: { size: W, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: NAVY, color: "auto" },
    borders: { top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, bottom: { style: BorderStyle.SINGLE, size: 48, color: GOLD },
      left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" } },
    margins: { top: 500, bottom: 500, left: 500, right: 500 },
    children: [
      new Paragraph({ spacing: { after: 80 }, children: [run("GUÍA TÉCNICA DE LA PLATAFORMA", { size: 22, bold: true, color: "C9D6EA" })] }),
      new Paragraph({ spacing: { after: 120 }, children: [run("STYLUS", { size: 80, bold: true, color: "FFFFFF" })] }),
      new Paragraph({ spacing: { after: 60 }, children: [run("Retail de moda con compras inteligentes asistidas por IA en tiempo real", { size: 28, color: "FFFFFF" })] }),
      new Paragraph({ spacing: { after: 0 }, children: [run("Arquitectura, pipelines, modelo de datos, operación, seguridad y costos en Google Cloud", { size: 20, italics: true, color: "C9D6EA" })] }),
    ] })] })] }),
  SP(500),
  ...table(["Campo", "Detalle"], [
    ["Curso", "UTEC · Taller de Arquitectura Big Data · Proyecto final"],
    ["Documento", "Guía técnica de la plataforma (versión consultoría)"],
    ["Versión / fecha", "v1.0 · 24 de octubre de 2026"],
    ["Fuente de datos", "Dataset público **H&M Personalized Fashion Recommendations** (Kaggle)"],
    ["Proyecto GCP", `\`${P_.project_id}\` · región \`${P_.region}\` · ambiente \`${P_.env}\``],
    ["Repositorio", "`github.com/estuardoo/STYLUS` (privado)"],
    ["Clasificación", "Uso académico · no contiene credenciales ni datos de clientes"],
  ], [2200, 7400], { boldFirst: true, size: 18 }),
  ...table(["Integrante", "Rol en el proyecto"], DATA.perfiles.map(p => [p[0], `**${p[1]}** · ${p[2]}`]), [2200, 7400], { boldFirst: true, size: 18, headFill: ACCENT }),
];

// ======================================================================
// CONTROL E ÍNDICE
// ======================================================================
const control = [
  new Paragraph({ spacing: { after: 160 }, children: [run("Control del documento", { size: 30, bold: true, color: NAVY })] }),
  ...table(["Versión", "Fecha", "Autor", "Cambios"], [
    ["v0.1", "23-oct-2026", "Estuardo Oliver", "Guía resumida (7 páginas) generada desde Markdown"],
    ["v1.0", "24-oct-2026", "Estuardo Oliver", "Reescritura en formato consultoría: diagramas por pipeline, RACI, riesgos, costos, rutas reales y anexos de esquemas"],
  ], [1000, 1400, 2000, 5200], { size: 17 }),
  ...callout("Cómo leer esta guía", [
    "Los capítulos **1 a 10** explican cada tema (qué se construyó, por qué y quién lo hizo). Los **anexos A a H** contienen el detalle completo: rutas, tablas, columnas, esquemas estrella, permisos y parámetros.",
    "Todo nombre de recurso, ruta y cifra proviene del repositorio real (`config/control_plataforma.json`, `docs/gestion/Matriz_Auditoria_Proyecto.xlsx`, calculadora de costos). La guía se regenera con `python docs/_generadores/build_guia_data.py` y `node docs/_generadores/build_guia.js`.",
    "Convención de estado: ✔ **Hecho** · ● **Listo para desplegar** (código probado en local, falta ejecutarlo en GCP) · ✖ **Pendiente**.",
  ]),
  new Paragraph({ pageBreakBefore: true, spacing: { after: 160 }, children: [run("Índice", { size: 30, bold: true, color: NAVY })] }),
  "TOC_MARK",
];

// ======================================================================
// 1. RESUMEN EJECUTIVO
// ======================================================================
const s1 = [
  H1("1. Resumen ejecutivo", { pb: true }),
  P("**STYLUS** es una plataforma de datos sobre **Google Cloud** que convierte el histórico público de compras de H&M en tres capacidades de negocio: **analítica** (lakehouse medallion y tableros), **personalización** (recomendador con +200% de precisión sobre la línea base) y **comercio asistido** (tienda web con asistente Vertex AI Gemini y billetera transaccional). Toda la infraestructura se declara como código y se controla desde un único archivo de configuración."),
  ...kpis([["31.8 M", "transacciones reales procesadas", NAVY], ["+200%", "MAP@12 vs. popularidad", PURPLE],
    [usd(costo["Costo por pedido"][2], 5), "costo por pedido en producción", TEAL], [`${pct(1)}%`, "Entrega 1 completada", ORANGE]]),
  H2("1.1 Mensajes clave"),
  B("**La arquitectura está completa y probada en local**: 51 tareas planificadas, " + cnt(t => t.estado === "Hecho") + " hechas y " + cnt(t => t.estado === "Listo para desplegar") + " listas para desplegar (código y pruebas terminados, falta ejecutarlas contra GCP)."),
  B("**Una sola fuente de verdad**: `config/control_plataforma.json` define 64 parámetros, 30 tablas, 240 columnas, 30 permisos IAM y 12 usuarios; `ops.py` valida y genera todo lo demás, y un **panel web** permite editarlo sin tocar código."),
  B("**Costo controlado**: " + usd(costo["TOTAL MENSUAL"][1]) + "/mes en demo y " + usd(costo["TOTAL MENSUAL"][2]) + "/mes en producción; presupuesto con alertas al 50/90/100% y costo real por pedido desde el billing export."),
  B("**Seguridad por diseño**: sin datos ni credenciales en Git (lo bloquea la CI), secretos en Secret Manager generados por Terraform, despliegue desde GitHub con **Workload Identity Federation** (sin llaves)."),
  H2("1.2 Recomendación"),
  ...callout("Siguiente paso crítico", [
    "Ejecutar `python ops.py todo` (o los botones del panel) contra el proyecto `" + P_.project_id + "` desde Cloud Shell o una PC con gcloud. Ese único paso convierte **" + cnt(t => t.estado === "Listo para desplegar") + " tareas listas** en tareas hechas y desbloquea la Entrega 2 (07-nov) y los tableros de la Entrega 3.",
    "Responsable sugerido: **Winston Quispe** (infraestructura) con apoyo de **Nicole Arenas** (cargas Bronze/Silver/Gold).",
  ], ORANGE, "FDF1E7"),
  ...img("avance_pasos.png", 560, "Avance por entrega (fuente: matriz de auditoría)."),
];

// ======================================================================
// 2. CONTEXTO, ALCANCE Y DATOS
// ======================================================================
const s2 = [
  H1("2. Contexto, alcance y fuente de datos"),
  H2("2.1 Objetivo del proyecto"),
  P("Diseñar y desplegar una arquitectura Big Data de retail que soporte **ingesta batch y streaming**, **almacenamiento por capas**, **modelado analítico**, **exposición vía API** con un asistente de IA, y **control de costos automatizado**, cumpliendo las tres entregas del curso."),
  ...table(["Dentro del alcance", "Fuera del alcance"], [
    ["Lakehouse Bronze/Silver/Gold en GCS + BigQuery", "Pagos reales (el saldo de la tienda es simulado)"],
    ["Replay de transacciones como eventos 2026 (Pub/Sub + Dataflow)", "Datos de clientes reales distintos del dataset público"],
    ["Recomendador baseline evaluado con MAP@12", "Modelos de deep learning entrenados a medida"],
    ["API FastAPI + web + asistente Gemini + wallet ACID", "Aplicación móvil"],
    ["Infraestructura como código, CI/CD sin llaves, costos", "Multirregión activa-activa (se documenta DRP)"],
  ], [4800, 4800], { size: 17 }),
  H2("2.2 Fuente de datos: dataset público H&M"),
  P("Todo el proyecto usa **exclusivamente** el dataset público de Kaggle __H&M Personalized Fashion Recommendations__ (H&M Group, 2022). Los eventos de streaming de 2026 no son datos inventados: son **re-emisiones** de esas mismas transacciones con fecha 2026, marcadas con `is_synthetic = true` y conservando la fecha original en `source_t_dat`."),
  ...table(["Archivo original", "Filas", "Contenido", "Ruta local → destino en GCS"], [
    ["`articles.csv`", "105,542", "Catálogo: tipo, color, sección, descripción", `\`data/raw/articles.csv\` → \`gs://${D.bucket_raw}/hm/\``],
    ["`customers.csv`", "1,371,980", "Clientes: edad, membresía, frecuencia de noticias", `\`data/raw/customers.csv\` → \`gs://${D.bucket_raw}/hm/\``],
    ["`transactions_train.csv`", "31,788,324", "Compras 2018-2020: cliente, artículo, fecha, precio, canal", `\`data/raw/transactions_train.csv\` → \`gs://${D.bucket_raw}/hm/\``],
    ["`images/`", "105,100", "Fotos de producto (opcionales, `--con-imagenes`)", `\`data/raw/images/\` → \`gs://${D.bucket_raw}/hm/images/\` (Nearline a los 30 días)`],
  ], [2000, 1200, 3000, 3400], { size: 16, right: [1] }),
  ...img("volumen_datos.png", 560, "Volumen del dataset (escala logarítmica)."),
  ...callout("Hallazgos de la auditoría de datos (P1-01)", [
    "H&M **no trae identificador de pedido**: se define pedido = cliente + día + fuente (9,080,179 pedidos derivados).",
    "H&M no documenta los canales 1 y 2: se asumen **Tienda física** y **Online** (dimensión `dim_channel`, supuesto explícito).",
    "`article_id` tiene ceros a la izquierda: Bronze usa **esquema explícito STRING** para no perderlos.",
    "Los datos se usan según las reglas de la competencia; los CSV **nunca** se suben a GitHub (`data/` en `.gitignore` + regla de CI).",
  ], GOLD, "FBF6EC"),
  H2("2.3 Cronograma"),
  ...img("cronograma.png", 600, "Hitos del curso. La línea roja marca la fecha de esta versión."),
  ...table(["Paso", "Entrega", "Fecha límite", "Tareas", "Hechas", "Avance"], [1, 2, 3].map(p => [
    `Paso ${p}`, { 1: "Examen + P1: diseño, costos, ingesta/storage", 2: "P2: pipelines batch + streaming, modelado", 3: "P3: API, asistente, tableros, demo, sustentación" }[p],
    { 1: "24-oct-2026", 2: "07-nov-2026", 3: "20-nov-2026" }[p], String(cnt(t => t.paso === p)), String(cnt(t => t.paso === p && t.estado === "Hecho")), `**${pct(p)}%**`]),
    [900, 4200, 1500, 900, 900, 1000], { size: 17, right: [3, 4, 5] }),
];

// ======================================================================
// 3. EQUIPO, ROLES Y GOBIERNO
// ======================================================================
const porPersona = (p, paso) => T.filter(t => t.responsable === p && (!paso || t.paso === paso));
const s3 = [
  H1("3. Equipo, roles y gobierno"),
  P("Cada integrante es **responsable (R)** de un dominio técnico y **apoya (A)** en los dominios vecinos. La asignación vive en la matriz de auditoría (`docs/gestion/Matriz_Auditoria_Proyecto.xlsx`), que se genera desde `docs/_generadores/build_matriz.py`."),
  H2("3.1 Perfiles y responsabilidades"),
  ...table(["Integrante", "Perfil", "Responsabilidad principal", "Tareas (R)", "Entregables clave"], [
    ["Estuardo Oliver", "ML / Analytics", "Asistente Vertex AI Gemini, recomendador y su evaluación, documentos de entrega, matriz de auditoría, guion de demo, publicación del repositorio y costos reales (D06, D19)", String(porPersona("Estuardo Oliver").length), "`api/assistant.py`, `pipelines/reco/baseline_eval.py`, `docs/entrega1/`"],
    ["Winston Quispe", "Cloud Computing", "Terraform, IAM, Pub/Sub, Dataflow (streaming), CI/CD sin llaves, presupuesto y DRP, orquestador `ops.py`", String(porPersona("Winston Quispe").length), "`infra/terraform/`, `ops.py`, `pipelines/streaming/`, `.github/workflows/`"],
    ["Nicole Arenas", "Datos + API + Modelado", "Auditoría de datos, Bronze/Silver/Gold, calidad, modelo estrella, FastAPI y Cloud SQL", String(porPersona("Nicole Arenas").length), "`sql/`, `pipelines/batch/silver_hm.py`, `api/main.py`, `api/schema.sql`"],
    ["Gianmarco Mejia", "Dashboard / BI", "Diagrama end-to-end, calculadora de costos, catálogo de KPIs, vistas BI, Looker Studio y slides", String(porPersona("Gianmarco Mejia").length), "`docs/architecture/`, `cost/`, `sql/gold/02_kpi_views.sql`"],
  ], [1500, 1300, 3600, 800, 2400], { boldFirst: true, size: 16, right: [3] }),
  H2("3.2 Matriz RACI por dominio"),
  P("R = responsable de al menos una tarea del dominio; A = apoyo; R/A = ambas. Calculada automáticamente desde las 51 tareas."),
  ...table(["Dominio", ...personas.map(p => ini[p] + " · " + p.split(" ")[0])], raci, [2200, 1850, 1850, 1850, 1850], { boldFirst: true, statusCols: [1, 2, 3, 4], size: 17 }),
  ...img("tareas_persona.png", 580, "Carga de trabajo por persona y estado."),
  H2("3.3 Qué hace cada persona en la Entrega 1"),
  ...personas.flatMap(p => [
    H3(`${p} — ${porPersona(p, 1).filter(t => t.estado === "Hecho").length}/${porPersona(p, 1).length} tareas hechas`),
    ...table(["ID", "Tarea", "Qué hace", "Entregable", "Estado"], porPersona(p, 1).map(t => [t.id, `**${t.nombre}**`, t.accion, `\`${t.entregable}\``, t.estado]),
      [700, 1900, 3300, 2200, 1500], { statusCols: [4], size: 16 }),
  ]),
  H2("3.4 Modelo de gobierno"),
  B("**Configuración**: un solo dueño por cambio del JSON de control; el diff del JSON generado se revisa en el pull request."),
  B("**Infraestructura**: `plan` antes de `apply`; la CI nunca ejecuta `apply` ni `destroy`."),
  B("**Datos**: ninguna fila se pierde en silencio — lo rechazado va a `quarantine/` y se concilia (entrada = salida + rechazadas)."),
  B("**Seguimiento**: la matriz de auditoría es la fuente del avance; esta guía y los gráficos se regeneran desde ella."),
];

// ======================================================================
// 4. ARQUITECTURA
// ======================================================================
const s4 = [
  H1("4. Arquitectura de la solución"),
  P("La plataforma sigue una arquitectura **lakehouse medallion** con dos rutas de ingesta (batch y streaming) que convergen en un modelo estrella, y una capa de exposición que sirve tanto a analistas (Looker Studio) como a clientes (tienda web con asistente)."),
  ...img("arquitectura.png", 600, "Arquitectura end-to-end por capas: bronze, silver y gold; verde = ingesta; flechas azules = cómputo (Spark, SQL, Dataflow); naranja = exposición."),
  H2("4.1 Decisiones por capa"),
  ...table(["Capa", "Servicio elegido", "Por qué", "Alternativa descartada"], [
    ["Almacenamiento", "**Cloud Storage** (raw, lake)", "Barato, versionado, ciclo de vida a Nearline para imágenes", "Disco en VM (sin durabilidad gestionada)"],
    ["Data warehouse", "**BigQuery**", "Serverless, tablas externas sobre GCS, particiones y clustering, SQL estándar", "Cluster Hadoop/Hive permanente"],
    ["Batch", "**Serverless for Apache Spark**", "Spark sin administrar clúster; se paga por DCU-hora", "Dataproc con clúster 24/7"],
    ["Mensajería", "**Pub/Sub** + suscripción BigQuery + DLQ", "Desacople, reintentos, ruta económica directa a BigQuery", "Kafka autogestionado"],
    ["Streaming", "**Dataflow** (Apache Beam)", "Ventanas, datos tardíos, deduplicación y métricas de lag gestionadas", "Spark Streaming en clúster"],
    ["API / web", "**Cloud Run**", "Escala a cero, contenedor estándar, HTTPS incluido", "GKE (sobredimensionado para el alcance)"],
    ["Transaccional", "**Cloud SQL Postgres 15**", "ACID para checkout y billetera append-only, PITR", "Firestore (sin transacciones SQL multi-tabla)"],
    ["IA generativa", "**Vertex AI Gemini 3.1 Flash-Lite**", "Misma IAM y facturación de GCP; costo bajo por conversación", "API externa (otra llave y otra factura)"],
    ["BI", "**Looker Studio**", "Gratis, conector nativo a BigQuery", "Power BI / Tableau (licencias)"],
    ["IaC / CI", "**Terraform** + **GitHub Actions** + WIF", "Reproducible, revisable, sin llaves en GitHub", "Configuración manual en consola"],
  ], [1500, 2300, 3300, 2500], { boldFirst: true, size: 16 }),
  H2("4.2 Principios de diseño"),
  B("**Idempotencia**: subir datos, re-ejecutar capas o re-publicar eventos no duplica resultados (`rsync`, `LOAD DATA OVERWRITE`, `event_id` determinista, `idempotency key` en checkout)."),
  B("**Trazabilidad del origen**: cada fila conserva `source`/`_source_system`, `is_synthetic` y la fecha original."),
  B("**Configuración declarativa**: nombres, permisos y esquemas salen del JSON de control, nunca están escritos a mano en varios lugares."),
  B("**Costo por defecto mínimo**: Cloud Run con 0 instancias mínimas, Dataflow solo durante la demo, Cloud SQL `" + P_.cloudsql_tier + "`."),
  H2("4.3 Nombres reales de los recursos"),
  ...table(["Recurso", "Nombre en GCP"], [
    ["Proyecto / región / ambiente", `\`${P_.project_id}\` · \`${P_.region}\` · \`${P_.env}\``],
    ["Bucket Bronze (raw)", `\`gs://${D.bucket_raw}\``],
    ["Bucket Silver/Gold (lake)", `\`gs://${D.bucket_lake}\``],
    ["Estado de Terraform", `\`gs://${D.bucket_tfstate}/${D.tfstate_prefix}\``],
    ["Datasets BigQuery", Object.values(D.datasets).map(x => `\`${x}\``).join(" · ")],
    ["Tópico Pub/Sub", `\`${P_.pubsub_topic}\` (+ DLQ)`],
    ["Imagen de la API", `\`${D.image_repo}\``],
    ["Servicio Cloud Run", `\`${P_.cloudrun_service}\``],
    ["Modelo de IA", `\`${P_.gemini_model}\` en \`${P_.gemini_location}\``],
    ...Object.entries(D.sa_emails).map(([k, v]) => [`Cuenta de servicio · ${k}`, `\`${v}\``]),
  ], [2800, 6800], { boldFirst: true, size: 16 }),
];

// ======================================================================
// 5. PIPELINES
// ======================================================================
const s5 = [
  H1("5. Pipelines de datos"),
  P("La plataforma tiene **cuatro pipelines**. Cada uno se ejecuta con un comando de `ops.py` (o un botón del panel) y deja evidencia verificable."),
  ...table(["Pipeline", "Disparador", "Entrada", "Salida", "Dueño"], [
    ["**A. Batch** (lakehouse)", "`ops.py subir-datos · bronze · silver · gold`", "CSV H&M", `\`${DS.gold}.*\``, "Nicole Arenas"],
    ["**B. Streaming**", "`ops.py replay · dataflow-iniciar`", "Transacciones re-emitidas", `\`${DS.silver}.v_events\`, \`${DS.ops}.*\``, "Winston Quispe"],
    ["**C. Servicio** (API)", "`ops.py api · catalogo`", `\`${DS.gold}.v_catalog_serving\``, "Cloud Run + Cloud SQL", "Nicole Arenas / Estuardo Oliver"],
    ["**D. Control y CI/CD**", "Edición del JSON · push a GitHub", "`config/control_plataforma.json`", "Terraform + despliegue", "Winston Quispe"],
  ], [1800, 2600, 1800, 2000, 1400], { size: 16 }),
  H2("5.1 Pipeline A — Batch (Bronze → Silver → Gold)"),
  ...img("pipeline_batch.png", 470, "Pipeline batch con comandos, rutas y tablas reales."),
  ...table(["#", "Etapa", "Comando", "Código", "Qué hace", "Resultado verificable"], [
    ["A1", "Carga a Bronze", "`ops.py subir-datos`", "`ingestion/batch/upload_raw.py`", "SHA-256 y filas por archivo; `gcloud storage rsync` idempotente", "`_manifests/hm_raw_manifest.json`"],
    ["A2", "Bronze", "`ops.py bronze`", "`sql/bronze/01_bronze_hm.sql`", "Tablas externas con esquema STRING explícito; copia nativa particionada por día", `31,788,324 filas en \`${DS.bronze}.transactions\``],
    ["A3", "Silver (Spark)", "`ops.py silver`", "`pipelines/batch/silver_hm.py`", "Tipado, imputación, bandas de edad, validación con motivo de rechazo", "`_quality_report` con `conciliado = true`"],
    ["A4", "Silver (BQ)", "(incluido en A3)", "`sql/silver/01_load_silver.sql`", "`LOAD DATA OVERWRITE` desde Parquet; vista de eventos deduplicada", `\`${DS.silver}.articles/customers/transactions\``],
    ["A5", "Gold", "`ops.py gold`", "`sql/gold/01_gold_model.sql`, `02_kpi_views.sql`", "Modelo estrella, pedidos, popularidad, catálogo de servicio y vistas BI", `\`${DS.gold}.fact_sales\` y \`v_*\``],
    ["A6", "Catálogo", "`ops.py catalogo`", "`api/load_catalog.py`", "Cloud Run Job copia `v_catalog_serving` a Cloud SQL", "`/ready` con 105,542 artículos"],
  ], [500, 1200, 1500, 2100, 2600, 1800], { size: 15 }),
  H3("Reglas de calidad en Silver (motivo de rechazo)"),
  ...table(["Motivo", "Regla", "Destino"], [
    ["`fecha_invalida`", "`t_dat` no se puede convertir a fecha", "`quarantine/transactions`"],
    ["`sin_cliente`", "`customer_id` nulo", "`quarantine/transactions`"],
    ["`articulo_inexistente`", "`article_id` no existe en artículos", "`quarantine/transactions`"],
    ["`precio_invalido`", "Precio nulo o ≤ 0", "`quarantine/transactions`"],
    ["`canal_invalido`", "`sales_channel_id` distinto de 1 o 2", "`quarantine/transactions`"],
  ], [2200, 4600, 2800], { size: 16 }),
  ...callout("Control de conciliación", ["El job falla si **entrada ≠ salida + rechazadas**. En la prueba local: 546,741 filas, 3 rechazos inyectados detectados, `conciliado = true`."], OKC, OKF),
  H2("5.2 Pipeline B — Streaming (replay 2026)"),
  ...img("pipeline_streaming.png", 640, "Dos rutas desde el mismo tópico: económica (suscripción BigQuery) y analítica (Dataflow)."),
  ...table(["Aspecto", "Diseño"], [
    ["Contrato del evento", "Campos obligatorios: `event_id`, `event_type`, `event_time`, `article_id`, `customer_id`, `price`"],
    ["Idempotencia", "`event_id` determinista; `silver.v_events` deduplica por `event_id`"],
    ["Ventanas", "Fijas de **60 s** con datos tardíos aceptados hasta **300 s**"],
    ["Métricas", `\`${DS.ops}.stream_metrics_1m\`: eventos, compras, importe, lag p50/p95`],
    ["Errores", `Inválidos a \`${DS.ops}.stream_dlq\`; Pub/Sub reenvía al tópico DLQ tras ${P_.pubsub_max_delivery_attempts} intentos`],
    ["Origen trazable", "`is_synthetic = true` y `source_t_dat` con la fecha original de H&M"],
    ["Costo", "Dataflow cobra mientras corre: `ops.py dataflow-detener` al terminar la demo"],
  ], [2200, 7400], { boldFirst: true, size: 16 }),
  H2("5.3 Pipeline C — Servicio (API, asistente y tienda)"),
  ...img("pipeline_serving.png", 560, "Ruta de una compra: navegador → Cloud Run → Cloud SQL / Vertex AI → evento de vuelta a Pub/Sub."),
  ...table(["Método", "Ruta", "Función"], [
    ["GET", "`/health`, `/ready`", "Salud del servicio y catálogo cargado"],
    ["GET", "`/api/v1/catalog/products`", "Búsqueda en el catálogo (prefijo por tipo de producto)"],
    ["GET", "`/api/v1/catalog/products/{article_id}/image`", "Imagen desde GCS o carpeta local"],
    ["POST", "`/api/v1/recommendations`", "Recomendaciones por perfil; popularidad global para cold-start"],
    ["POST", "`/api/v1/assistant/message`", "Asistente: Gemini interpreta, el backend busca en el catálogo real; respaldo por reglas"],
    ["GET/POST/DELETE", "`/api/v1/cart`, `/api/v1/cart/items`", "Carrito"],
    ["POST", "`/api/v1/checkout`", "Compra ACID con `idempotency key`; **409** si no hay saldo"],
    ["GET / POST", "`/api/v1/wallet`, `/api/v1/wallet/demo-topups`", "Saldo (libro append-only) y recarga con token de administrador"],
    ["GET", "`/api/v1/orders`, `/api/v1/metrics/summary`", "Pedidos y métricas"],
  ], [1500, 3900, 4200], { size: 16 }),
  H2("5.4 Pipeline D — Control de configuración y CI/CD"),
  ...img("control_cicd.png", 640, "Del JSON de control a GCP: validación, archivos generados, Terraform y GitHub Actions."),
  ...table(["Workflow", "Cuándo corre", "Pasos"], [
    ["`ci.yml`", "Cada push y pull request", "Bloquea archivos prohibidos (CSV, Parquet, ZIP, `.db`, `.tfstate`, credenciales) · `ops.py config --check` · pruebas · calculadora de costos · `terraform fmt/validate`"],
    ["`deploy.yml`", "Push a `api/**` o `config/**`, o manual", "Lee `config/generated/plataforma.json` · construye y publica la imagen · `gcloud run deploy` · prueba de humo. Se omite si no existe la variable `GCP_WIF_PROVIDER`"],
  ], [1400, 2400, 5800], { size: 16 }),
];

// ======================================================================
// 6. DATOS Y MODELO
// ======================================================================
const capas = { bronze: [BRONZE, "Datos tal como llegan"], silver: [SILVER, "Datos limpios y tipados"], gold: [GOLD, "Modelo para negocio y BI"], ops: [NAVY, "Operación y costos"], retail: [ORANGE, "Transaccional de la tienda"] };
const s6 = [
  H1("6. Modelo de datos"),
  P(`Hay **${DATA.tablas.length} tablas y vistas** en ${Object.keys(capas).length} zonas. El detalle de cada columna está en el **Anexo C** y el diagrama del modelo estrella en el **Anexo D**.`),
  ...table(["Zona", "Dataset / base", "Propósito", "Tablas y vistas"], Object.keys(capas).map(k => [
    `**${k.toUpperCase()}**`, `\`${dsName(k)}\``, capas[k][1], DATA.tablas.filter(t => t.dataset === k).map(t => `\`${t.tabla}\``).join(", ")]),
    [1200, 2000, 2000, 4400], { size: 16, rowFill: (r, i) => ["F6EDE4", "EEF0F2", "FBF5E1", "E6EBF3", "FDF1E7"][i] }),
  H2("6.1 Modelo estrella (Gold)"),
  P("**Grano de `fact_sales`**: una línea de venta (H&M registra una línea por unidad). `fact_orders` agrega por cliente + día + fuente porque el dataset no trae `order_id`. Las dimensiones de cliente, artículo, fecha y canal permiten responder ventas por segmento, categoría, temporada y canal."),
  ...table(["Tabla", "Tipo", "Grano", "Partición / cluster", "Origen"], DATA.tablas.filter(t => t.dataset === "gold" && !t.tabla.startsWith("v_")).map(t => [
    `\`${t.tabla}\``, t.tipo, t.descripcion, [t.particion, t.cluster].filter(Boolean).join(" / ") || "—", `\`${t.creado_por}\``]),
    [1600, 900, 3000, 1900, 2200], { size: 15 }),
  ...callout("Ver Anexo D", ["El diagrama completo del modelo estrella, con todas las columnas y sus tipos, está en el **Anexo D**; el diccionario columna por columna en el **Anexo C**."], PURPLE, "F1ECF7"),
  H2("6.2 Vistas para tableros"),
  ...table(["Vista", "Tablero", "Pregunta de negocio"], [
    [`\`${DS.gold}.v_ventas_mensuales\``, "Gerencial", "¿Cómo evolucionan ventas, pedidos y ticket promedio por mes y canal?"],
    [`\`${DS.gold}.v_top_articulos\``, "Gerencial", "¿Qué artículos y categorías concentran las ventas?"],
    [`\`${DS.gold}.v_recurrencia_clientes\``, "Gerencial", "¿Cuántos clientes recompran y con qué frecuencia?"],
    [`\`${DS.ops}.v_stream_salud\``, "Operativo", "¿El streaming está al día (eventos/min, lag p95, DLQ)?"],
    [`\`${DS.ops}.v_costo_real_mensual\``, "Costos", "¿Cuánto costó realmente el mes y cuánto por pedido?"],
  ], [3200, 1300, 5100], { size: 16 }),
  H2("6.3 Recomendador"),
  P("Evaluación con **split temporal real**: entrenamiento hasta 2020-09-16, prueba 2020-09-16 a 2020-09-22 (68,984 clientes, 26,447 en cold-start). El modelo B (recompra de 8 semanas + popularidad) **triplica** la precisión de la línea base."),
  ...img("map12.png", 500, "MAP@12 de los modelos evaluados (pipelines/reco/baseline_eval.py)."),
];

// ======================================================================
// 7. CONFIGURACIÓN Y OPERACIÓN
// ======================================================================
const secCfg = [["parametros", "Parámetros del proyecto"], ["apis", "APIs a activar"], ["cuentas_servicio", "Cuentas de servicio"], ["permisos", "Permisos IAM"],
  ["usuarios", "Equipo y usuarios de la tienda"], ["datasets", "Datasets BigQuery"], ["tablas", "Tablas y vistas"], ["columnas", "Columnas"], ["secretos", "Secretos (solo nombres)"]];
const cntSec = { parametros: DATA.parametros.length, apis: DATA.apis.length, cuentas_servicio: DATA.cuentas.length, permisos: DATA.permisos.length,
  usuarios: DATA.usuarios.length, datasets: DATA.datasets.length, tablas: DATA.tablas.length, columnas: DATA.columnas.length, secretos: DATA.secretos.length };
const editPanel = { parametros: "Sí (38 campos)", apis: "Sí", cuentas_servicio: "Sí", permisos: "Sí", usuarios: "Sí", datasets: "Solo lectura", tablas: "Solo lectura", columnas: "Solo lectura", secretos: "Solo lectura" };
const s7 = [
  H1("7. Configuración y operación"),
  H2("7.1 Fuente única: config/control_plataforma.json"),
  P("Todos los insumos de la plataforma están en **un solo archivo versionado**. `python ops.py config` lo valida (formatos, roles que empiezan con `roles/`, referencias entre secciones, `roles/owner` prohibido por API) y genera de forma determinística los archivos que consumen Terraform, `ops.py` y la API."),
  ...table(["Sección", "Contenido", "Filas", "Editable en el panel"], secCfg.map(([k, d]) => [`\`${k}\``, d, String(cntSec[k]), editPanel[k]]), [2200, 3800, 1000, 2600], { size: 16, right: [2] }),
  ...table(["Archivo generado", "Lo consume", "Contenido"], [
    ["`infra/terraform/plataforma.auto.tfvars.json`", "Terraform / OpenTofu", "Variables tipadas: buckets, datasets, tablas, IAM, Cloud SQL, Cloud Run, WIF"],
    ["`config/generated/plataforma.json`", "`ops.py`, GitHub Actions", "Parámetros, nombres derivados, columnas, usuarios"],
    ["`api/seed.json`", "API (al iniciar)", "Usuarios iniciales de la tienda y su saldo"],
  ], [3600, 2000, 4000], { size: 16 }),
  H2("7.2 Panel de control web"),
  P("`python ops.py panel` abre `http://127.0.0.1:8765` (solo en la máquina local). Tiene pestañas por sección del JSON, tablas editables con **agregar/quitar fila**, y un botón por cada comando de `ops.py` con el **registro en vivo** (Server-Sent Events). `apply` y `destroy` piden confirmación explícita."),
  H2("7.3 Orquestador ops.py"),
  ...table(["Comando", "Qué hace", "Requiere GCP"], [
    ["`config [--check]`", "Valida el JSON y regenera los derivados", "No"], ["`estado`", "Nombres y valores efectivos", "No"],
    ["`local`", "Tienda en `localhost:8080` con SQLite", "No"], ["`panel`", "Panel web local", "No"],
    ["`bootstrap`", "APIs, red, bucket de estado, `terraform init`", "Sí"], ["`plan` / `apply` / `destroy`", "Ciclo de vida de la infraestructura", "Sí"],
    ["`subir-datos`", "CSV a GCS con manifiesto", "Sí"], ["`bronze` / `silver` / `gold`", "Capas del lakehouse", "Sí"],
    ["`api` / `catalogo`", "Imagen, Cloud Run y catálogo en Cloud SQL", "Sí"], ["`replay` / `dataflow-iniciar` / `dataflow-detener`", "Streaming", "Sí"],
    ["`verificar`", "BigQuery real vs. JSON + `/health`", "Sí"], ["`github`", "Valor de `GCP_WIF_PROVIDER`", "Sí"],
    ["`costo-real`", "Vista de costo real por pedido", "Sí"], ["`todo`", "bootstrap → apply → bronze → silver → gold → api → verificar", "Sí"],
  ], [3200, 5200, 1200], { size: 16 }),
  H2("7.4 Procedimiento de despliegue"),
  ...table(["Paso", "#", "Acción", "Comando", "Responsable", "Verificación"], DATA.despliegue.map(d => [String(d[0]), d[1], `**${d[2]}**`, `\`${d[3]}\``, d[4], d[6]]),
    [550, 600, 1900, 3200, 1500, 1850], { size: 14 }),
];

// ======================================================================
// 8. SEGURIDAD
// ======================================================================
const porPrincipal = {};
DATA.permisos.forEach(p => { (porPrincipal[p.principal] = porPrincipal[p.principal] || []).push(p.rol.replace("roles/", "")); });
const s8 = [
  H1("8. Seguridad, identidad y gobierno de datos"),
  H2("8.1 Cuentas de servicio (mínimo privilegio)"),
  ...table(["Clave", "Cuenta", "Propósito", "Roles asignados"], DATA.cuentas.map(c => [`**${c.clave}**`, `\`${D.sa_emails[c.clave] || c.account_id}\``, c.descripcion,
    (porPrincipal["sa:" + c.clave] || []).join(", ") || "—"]), [1000, 3300, 2500, 2800], { size: 15 }),
  P(`El detalle de los **${DATA.permisos.length} permisos** (principal, rol, alcance y motivo) está en el **Anexo E**.`),
  H2("8.2 Secretos"),
  ...table(["Secreto", "Contenido", "Lo genera", "Lo consume"], DATA.secretos.map(s => [`\`${s.nombre}\``, s.contenido, s.generado_por, s.consumido_por]), [2200, 2600, 2400, 2400], { size: 16 }),
  H2("8.3 Controles"),
  ...table(["Control", "Cómo se implementa", "Evidencia"], [
    ["Nada sensible en Git", "`.gitignore` (`data/`, `.secrets/`, `*.tfstate`, tokens) + regla en `ci.yml`", "CI en verde; repositorio privado"],
    ["Secretos fuera del código", "Terraform genera contraseña y token en Secret Manager; Cloud Run los monta", "`cloudsql.tf`, `cloudrun.tf`"],
    ["Despliegue sin llaves", "Workload Identity Federation para GitHub Actions", "`cicd.tf`, `deploy.yml`"],
    ["Privilegio mínimo", "4 cuentas de servicio con roles por recurso; `roles/owner` bloqueado en el JSON", "Anexo E"],
    ["Datos seudonimizados", "`customer_id` es un hash en el dataset original", "`dim_customer`"],
    ["Compras seguras", "Checkout ACID, idempotente, libro de saldo append-only (sin UPDATE/DELETE)", "`api/schema_pg.sql`, pruebas"],
  ], [2200, 4600, 2800], { boldFirst: true, size: 16 }),
  ...callout("Atención", ["La llave de cuenta de servicio de automatización (`.secrets/gcp-admin-key.json`) tiene rol **owner**: está fuera de Git, pero debe **rotarse o eliminarse** después del despliegue y reemplazarse por Workload Identity."], PEC, PEF),
];

// ======================================================================
// 9. COSTOS
// ======================================================================
const serv = Object.entries(DATA.costos.por_servicio).sort((a, b) => b[1][2] - a[1][2]);
const s9 = [
  H1("9. Costos y FinOps"),
  P("`cost/assumptions.yaml` es la única fuente de supuestos; `python cost/estimate_costs.py` genera la calculadora con fórmulas (`docs/entrega1/Calculadora_Costos_GCP.xlsx`) y `--refresh-prices` actualiza las tarifas desde la API de Cloud Billing Catalog."),
  ...table(["Escenario", "USD / mes", "Pedidos / mes", "USD / pedido"], [["Desarrollo", 0], ["Demo", 1], ["Producción", 2], ["Pico Black Friday", 3]].map(([n, i]) => [
    `**${n}**`, usd(costo["TOTAL MENSUAL"][i]), Number(costo["Pedidos/mes"][i]).toLocaleString("en-US"), usd(costo["Costo por pedido"][i], 5)]), [3000, 2200, 2200, 2200], { size: 17, right: [1, 2, 3] }),
  ...img("costo_escenarios.png", 560, "Costo mensual por escenario (escala logarítmica)."),
  ...img("costo_servicios.png", 560, "Producción: distribución del costo por servicio."),
  ...table(["Servicio", "Desarrollo", "Demo", "Producción", "Pico"], serv.map(([k, v]) => [k, ...v.map(x => usd(x))]), [3200, 1600, 1600, 1600, 1600], { boldFirst: true, size: 16, right: [1, 2, 3, 4] }),
  H2("9.1 Palancas de ahorro"),
  B("**Gemini** y **Dataflow** explican el 69% del costo de producción: `assistant_mode = rules` y apagar Dataflow fuera de la demo son las dos palancas mayores."),
  B("Cloud Run con **0 instancias mínimas**; Cloud SQL `" + P_.cloudsql_tier + "` en desarrollo."),
  B("Imágenes a **Nearline** a los " + P_.images_nearline_days + " días; consultas BigQuery sobre tablas **particionadas y agrupadas**."),
  B("Presupuesto de **USD " + P_.monthly_budget_usd + "/mes** con alertas al 50/90/100% (Terraform) y costo real por pedido (`cost/real_cost_per_order.sql`)."),
];

// ======================================================================
// 10. CALIDAD, ESTADO Y RIESGOS
// ======================================================================
const s10 = [
  H1("10. Calidad, estado y hoja de ruta"),
  H2("10.1 Pruebas automatizadas"),
  ...table(["Archivo", "Prueba", "Qué garantiza"], [
    ["`tests/test_config.py`", "`test_generados_al_dia`", "Los archivos generados coinciden con el JSON de control"],
    ["`tests/test_config.py`", "`test_validacion_detecta_errores`", "Un permiso inválido o un principal inexistente se rechaza"],
    ["`tests/test_config.py`", "`test_contrato_cloudsql_igual_a_schema_sql`", "Las columnas de Cloud SQL del JSON son las de `api/schema.sql`"],
    ["`tests/test_api.py`", "`test_flujo_compra_segura`", "Checkout idempotente, sin saldo negativo, 409 sin fondos"],
    ["`tests/test_api.py`", "`test_reco_cold_start_y_health`", "Recomendaciones para clientes nuevos y salud del servicio"],
    ["`tests/test_core.py`", "`test_event_2026_preserva_origen_e_idempotente`", "El replay conserva la fecha original y no duplica"],
    ["`tests/test_core.py`", "`test_free_tier_y_total`", "La calculadora aplica el nivel gratuito y suma bien"],
  ], [2200, 3600, 3800], { size: 15 }),
  ...img("codigo_tipo.png", 560, "Código y configuración versionados por tipo de archivo."),
  H2("10.2 Estado por entrega"),
  ...[1, 2, 3].flatMap(p => [
    H3(`Paso ${p} — ${pct(p)}% hecho`),
    ...table(["ID", "Tarea", "Responsable", "Estado", "Evidencia"], T.filter(t => t.paso === p).map(t => [t.id, t.nombre, t.responsable, t.estado, t.evidencia || "—"]),
      [700, 2700, 1600, 1600, 3000], { statusCols: [3], size: 14 }),
  ]),
  H2("10.3 Riesgos y mitigación"),
  ...table(["Riesgo", "Prob.", "Impacto", "Mitigación", "Dueño"], [
    ["Infraestructura real aún no desplegada (bloquea 15 tareas listas)", "Alta", "Alta", "Ejecutar `ops.py todo` desde Cloud Shell esta semana", "Winston Quispe"],
    ["Dataflow encendido fuera de la demo", "Media", "Alta", "`dataflow-detener` en el checklist; alertas de presupuesto", "Winston Quispe"],
    ["Llave owner en disco local", "Media", "Alta", "Rotar/eliminar tras el despliegue; usar WIF", "Estuardo Oliver"],
    ["Retiro de modelos Gemini (ya ocurrió con 2.5)", "Media", "Media", "Modelo como parámetro + modo `rules` de respaldo", "Estuardo Oliver"],
    ["Emails del equipo vacíos (sin acceso IAM)", "Alta", "Media", "Completar la sección `usuarios` en el panel", "Todo el equipo"],
    ["Tableros sin construir", "Media", "Media", "Vistas `v_*` ya definidas; conectar Looker Studio tras Gold", "Gianmarco Mejia"],
    ["Pedido inferido (sin `order_id`)", "Alta", "Baja", "Definición documentada cliente + día + fuente", "Nicole Arenas"],
  ], [3200, 800, 900, 3200, 1500], { statusCols: [1, 2], size: 15 }),
  H2("10.4 Próximos pasos"),
  N("**Hoy (24-oct)**: revisión cruzada y envío de la Entrega 1 — Estuardo Oliver."),
  N("**Semana 1**: `bootstrap`, `apply`, `subir-datos`, `bronze` en `" + P_.project_id + "` — Winston Quispe y Nicole Arenas."),
  N("**Semana 2**: `silver`, `gold`, `replay` + Dataflow, primer tablero, informe de Entrega 2 (07-nov)."),
  N("**Semanas 3-4**: `api`, catálogo en Cloud SQL, tableros finales, prueba de DRP, costo real, slides y sustentación (20/21-nov)."),
];

// ======================================================================
// ANEXOS
// ======================================================================
const desc = (r) => {
  const m = [["ops.py", "Orquestador de la plataforma"], ["panel/", "Panel web local de configuración y despliegue"], ["config/control", "Fuente única de configuración"],
    ["config/generated", "Generado por ops.py config (no editar)"], ["infra/terraform/plataforma", "Variables de Terraform generadas"], ["infra/terraform", "Infraestructura como código"],
    ["sql/bronze", "SQL de la capa Bronze"], ["sql/silver", "SQL de la capa Silver"], ["sql/gold", "SQL del modelo estrella y vistas BI"], ["pipelines/batch", "Spark: Bronze → Silver"],
    ["pipelines/streaming", "Dataflow / Apache Beam"], ["pipelines/reco", "Evaluación del recomendador"], ["ingestion/batch", "Carga de CSV a GCS"], ["ingestion/streaming", "Replay de eventos 2026"],
    ["api/static", "Tienda web"], ["api/seed", "Usuarios iniciales (generado)"], ["api/", "API FastAPI, asistente y carga de catálogo"], ["cost/", "Calculadora y costo real"], ["tests/", "Pruebas unitarias"],
    [".github/", "CI/CD (GitHub Actions)"], ["docs/entrega1", "Entregables de la Entrega 1"], ["docs/gestion", "Matriz de auditoría"], ["docs/architecture", "Diagramas de arquitectura"],
    ["docs/guia", "Figuras y datos de esta guía"], ["docs/_generadores", "Generadores de documentos"], ["docs/runbooks", "Runbooks de operación / DRP"], ["docs/", "Documentación"],
    [".gitignore", "Exclusión de datos y secretos"], ["README", "Portada del repositorio"], ["requirements", "Dependencias Python"]];
  const hit = m.find(([k]) => r.startsWith(k));
  return hit ? hit[1] : "—";
};
const colsPor = {};
DATA.columnas.forEach(c => { const k = `${c.motor}|${c.dataset}|${c.tabla}`; (colsPor[k] = colsPor[k] || []).push(c); });
const anexos = [
  H1("Anexo A. Inventario de rutas del repositorio"),
  P(`Archivos versionados en \`github.com/estuardoo/STYLUS\` (rama \`main\`). Total: **${DATA.files.length} archivos**. Los datos (\`data/\`) y secretos (\`.secrets/\`) existen solo en la PC del equipo y están excluidos de Git.`),
  ...table(["Ruta", "Líneas", "Propósito"], DATA.files.filter(f => !f.ruta.startsWith("docs/guia/img")).map(f => [`\`${f.ruta}\``, f.lineas ? String(f.lineas) : "binario", desc(f.ruta)]),
    [5300, 900, 3400], { size: 14, right: [1] }),
  H1("Anexo B. Catálogo de tablas y vistas"),
  ...table(["Motor", "Dataset real", "Tabla", "Tipo", "Creado por", "Partición / cluster", "Descripción"], DATA.tablas.map(t => [t.motor, `\`${dsName(t.dataset)}\``, `**${t.tabla}**`, t.tipo,
    `\`${t.creado_por}\``, [t.particion, t.cluster].filter(Boolean).join(" / ") || "—", t.descripcion]), [900, 1400, 1500, 700, 1900, 1300, 1900], { size: 13 }),
  H1("Anexo C. Diccionario de columnas"),
  P(`**${DATA.columnas.length} columnas** en ${Object.keys(colsPor).length} tablas, agrupadas por tabla. Fuente: sección \`columnas\` del JSON de control; \`ops.py verificar\` las compara contra BigQuery real.`),
  ...Object.entries(colsPor).flatMap(([k, cols]) => {
    const [motor, ds, tb] = k.split("|");
    const conDesc = cols.some(c => c.descripcion);
    return [H3(`${dsName(ds)}.${tb}  (${motor}, ${cols.length} columnas)`),
      ...(conDesc ? table(["Columna", "Tipo", "Modo", "Descripción"], cols.map(c => [`**${c.columna}**`, c.tipo, c.modo || "", c.descripcion || "—"]), [2600, 1400, 1300, 4300], { size: 14 })
        : table(["Columna", "Tipo", "Modo"], cols.map(c => [`**${c.columna}**`, c.tipo, c.modo || ""]), [4600, 2500, 2500], { size: 14 }))];
  }),
  H1("Anexo D. Modelo estrella (Gold)"),
  P(`Dataset \`${DS.gold}\`. Hechos en dorado, dimensiones en azul y tabla de recomendación en morado. Las flechas indican la clave de unión.`),
  ...img("estrella.png", 600, "Modelo estrella con todas las columnas y tipos."),
  H1("Anexo E. Matriz de permisos IAM"),
  ...table(["Principal", "Rol", "Alcance", "Motivo", "Gestión"], DATA.permisos.map(p => [`\`${p.principal}\``, `\`${p.rol}\``, p.alcance, p.motivo, p.gestion]),
    [1800, 2800, 1500, 2600, 900], { size: 14 }),
  H2("Usuarios iniciales"),
  ...table(["Tipo", "ID", "Nombre", "Perfil", "Roles GCP / saldo inicial"], DATA.usuarios.map(u => [u.tipo, `\`${u.id}\``, u.nombre, u.perfil || "—",
    u.tipo === "gcp" ? (String(u.roles_gcp || "").split(";").filter(Boolean).map(x => x.replace("roles/", "")).join(", ") || "—") : (u.saldo_inicial_cents !== "" ? usd(Number(u.saldo_inicial_cents) / 100) : "—")]),
    [800, 1300, 1800, 1800, 3900], { size: 14 }),
  H1("Anexo F. Parámetros de configuración"),
  ...[...new Set(DATA.parametros.map(p => p.seccion))].flatMap(sec => [H3(sec),
    ...table(["Clave", "Valor", "Tipo", "Editable", "Descripción"], DATA.parametros.filter(p => p.seccion === sec).map(p => [`**${p.clave}**`,
      p.clave === "admin_token_local" ? "(local, no productivo)" : `\`${p.valor === "" || p.valor === null ? "—" : p.valor}\``, p.tipo, p.editable ? "Sí" : "No", p.descripcion]),
      [2200, 2300, 900, 800, 3400], { size: 13 })]),
  H1("Anexo G. APIs de Google Cloud habilitadas"),
  ...table(["API", "Motivo"], DATA.apis.map(a => [`\`${a.api}\``, a.motivo]), [4000, 5600], { size: 15 }),
  H1("Anexo H. Glosario"),
  ...table(["Término", "Significado"], [
    ["Medallion", "Organización del lago en Bronze (crudo), Silver (limpio) y Gold (modelo de negocio)"],
    ["Modelo estrella", "Tabla de hechos rodeada de dimensiones; optimizado para BI"],
    ["DLQ", "Dead Letter Queue: destino de mensajes que no se pudieron procesar"],
    ["Idempotencia", "Repetir una operación produce el mismo resultado sin duplicar"],
    ["WIF", "Workload Identity Federation: GitHub se autentica en GCP sin llaves"],
    ["MAP@12", "Mean Average Precision de las 12 primeras recomendaciones"],
    ["PITR", "Point-in-time recovery de Cloud SQL"],
    ["Cold-start", "Cliente sin historial; recibe recomendaciones por popularidad"],
  ], [2000, 7600], { boldFirst: true, size: 16 }),
];

// ---------------- índice manual (dos pasadas) ----------------
const body = [...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8, ...s9, ...s10, ...anexos];
fs.writeFileSync(OUT + ".toc.json", JSON.stringify(TOC));
const tocParas = TOC.map(([lvl, t]) => new Paragraph({
  spacing: { before: lvl === 1 ? 90 : 0, after: 30 }, indent: { left: lvl === 1 ? 0 : 400 },
  children: [run(t, { bold: lvl === 1, size: lvl === 1 ? 20 : 18, color: lvl === 1 ? NAVY : undefined }),
    new TextRun({ children: [new PositionalTab({ alignment: PositionalTabAlignment.RIGHT, relativeTo: PositionalTabRelativeTo.MARGIN, leader: PositionalTabLeader.DOT })], font: FONT }),
    run(String(PAGES[t] || ""), { bold: lvl === 1, size: lvl === 1 ? 20 : 18 })],
}));
control.splice(control.indexOf("TOC_MARK"), 1, ...tocParas);

const pageProps = { page: { size: { width: 11906, height: 16838 }, margin: { top: 1300, bottom: 1200, left: 1134, right: 1134, header: 560, footer: 560 } } };
const grey = (t, o = {}) => run(t, { size: 15, color: GREY, ...o });
const doc = new Document({
  creator: "Equipo STYLUS", title: "STYLUS — Guía Técnica de la Plataforma", description: "Guía técnica en formato consultoría",
  styles: {
    default: { document: { run: { font: FONT, size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, font: FONT, color: NAVY },
        paragraph: { spacing: { before: 120, after: 200 }, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: GOLD, space: 6 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 25, bold: true, font: FONT, color: ACCENT },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 21, bold: true, font: FONT, color: NAVY },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "■", alignment: AlignmentType.LEFT,
      style: { run: { color: ACCENT, size: 14 }, paragraph: { indent: { left: 500, hanging: 280 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { run: { bold: true, color: NAVY }, paragraph: { indent: { left: 500, hanging: 320 } } } }] },
  ] },
  sections: [
    { properties: pageProps, children: cover },
    { properties: pageProps,
      headers: { default: new Header({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: W }],
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 4 } },
        children: [run("STYLUS", { size: 16, bold: true, color: NAVY }), grey("  ·  Guía Técnica de la Plataforma"), grey("\tv1.0 · 24-oct-2026")] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: W }],
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: "C9D1DC", space: 4 } },
        children: [grey("UTEC · Taller de Arquitectura Big Data · Uso académico"), grey("\tPágina "),
          new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 15, bold: true, color: NAVY }), grey(" de "),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 15, color: GREY })] })] }) },
      children: [...control, ...body] },
  ],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("ok", OUT, "secciones índice:", TOC.length); });
