const fs = require("fs");
const d = require("docx");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, HeadingLevel, AlignmentType,
  WidthType, ShadingType, BorderStyle, LevelFormat, PageBreak, Header, Footer, PageNumber, TableOfContents,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader, VerticalAlign } = d;

const REPO = process.argv[2];
const OUT = process.argv[3];
const cost = JSON.parse(fs.readFileSync(`${REPO}/cost/output/resumen.json`, "utf8"));
const usd = (x, dec = 2) => "USD " + x.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });

const NAVY = "1F3864", ACCENT = "2E75B6", GREY = "595959", LIGHT = "EAF1FB";
const W = 9026; // A4 con márgenes de 1"

// ---------- helpers ----------
const run = (t, o = {}) => new TextRun({ text: t, font: "Arial", ...o });
const P = (content, o = {}) => new Paragraph({
  spacing: { after: 120, line: 276 }, alignment: AlignmentType.JUSTIFIED, ...o,
  children: (Array.isArray(content) ? content : [content]).map(c => typeof c === "string" ? run(c) : c),
});
const TOC = [];
const H1 = (t, o = {}) => { TOC.push([1, t]); return new Paragraph({ heading: HeadingLevel.HEADING_1, ...o, children: [run(t)] }); };
const H2 = t => { TOC.push([2, t]); return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [run(t)] }); };
const H3 = t => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [run(t)] });
const B = (content, lvl = 0) => new Paragraph({
  numbering: { reference: "bul", level: lvl }, spacing: { after: 60, line: 264 },
  children: (Array.isArray(content) ? content : [content]).map(c => typeof c === "string" ? run(c) : c),
});
const bold = t => run(t, { bold: true });
const caption = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
  children: [run(t, { italics: true, size: 18, color: GREY })] });
const brk = () => new Paragraph({ children: [new PageBreak()] });

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(rows, widths, opt = {}) {
  const sum = widths.reduce((a, b) => a + b, 0);
  const ws = widths.map(w => Math.round(w * W / sum));
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: ws,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0, cantSplit: true,
      children: r.map((c, j) => {
        const head = i === 0;
        const total = opt.totalRow && i === rows.length - 1;
        return new TableCell({
          borders, width: { size: ws[j], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
          shading: head ? { fill: NAVY, type: ShadingType.CLEAR, color: "auto" }
            : total ? { fill: "D9E2F3", type: ShadingType.CLEAR, color: "auto" }
            : (i % 2 === 0 ? { fill: "F7F9FC", type: ShadingType.CLEAR, color: "auto" } : undefined),
          children: String(c).split("\n").map(line => new Paragraph({
            spacing: { after: 0, line: 252 },
            alignment: (opt.right || []).includes(j) && !head ? AlignmentType.RIGHT : AlignmentType.LEFT,
            children: [run(line, { size: 18, bold: head || total || (opt.boldFirst && j === 0), color: head ? "FFFFFF" : undefined })],
          })),
        });
      }),
    })),
  });
}
function callout(title, text) {
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: [W],
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({
      width: { size: W, type: WidthType.DXA },
      borders: { top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, left: { style: BorderStyle.SINGLE, size: 24, color: ACCENT } },
      shading: { fill: LIGHT, type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 120, bottom: 120, left: 200, right: 160 },
      children: [new Paragraph({ spacing: { after: 60 }, children: [run(title, { bold: true, color: NAVY, size: 20 })] }),
        new Paragraph({ spacing: { after: 0, line: 264 }, children: [run(text, { size: 20 })] })],
    })] })],
  });
}
const sp = () => new Paragraph({ spacing: { after: 80 }, children: [] });

// ---------- datos ----------
const c = cost;
const esc = ["dev", "demo", "produccion", "pico_black_friday"];
const escNom = { dev: "Desarrollo (curso)", demo: "Demo / sustentación", produccion: "Producción (escala H&M)", pico_black_friday: "Pico Black Friday (5×)" };
const servicios = {
  "Cloud Storage": ["gcs_standard_gb_mes", "gcs_nearline_gb_mes"],
  "BigQuery": ["bq_storage_gib_mes", "bq_query_tib"],
  "Pub/Sub": ["pubsub_tib", "pubsub_bq_sub_tib"],
  "Dataflow": ["dataflow_vcpu_h", "dataflow_mem_gb_h"],
  "Serverless Spark": ["dataproc_dcu_h"],
  "Cloud Run": ["cloudrun_vcpu_s", "cloudrun_gib_s", "cloudrun_req_millon"],
  "Cloud SQL": ["cloudsql_micro_h", "cloudsql_small_h", "cloudsql_ssd_gb_mes"],
  "Vertex AI Gemini": ["gemini_in_mtok", "gemini_out_mtok"],
  "Artifact Registry": ["artifact_gb_mes"],
};
const svcCost = (e, s) => servicios[s].reduce((a, k) => a + (c[e].detalle[k] || 0), 0);
const costRows = [["Servicio", ...esc.map(e => escNom[e])]];
for (const s of Object.keys(servicios)) costRows.push([s, ...esc.map(e => usd(svcCost(e, s)))]);
costRows.push(["Total mensual", ...esc.map(e => usd(c[e].total))]);
costRows.push(["Pedidos / mes", ...esc.map(e => c[e].pedidos.toLocaleString("en-US"))]);
costRows.push(["Costo por pedido", ...esc.map(e => "USD " + c[e].por_pedido.toFixed(5))]);

// ---------- contenido ----------
const portada = [
  new Paragraph({ spacing: { before: 600, after: 0 }, children: [run("UTEC · TALLER DE ARQUITECTURA BIG DATA · SECCIÓN 1", { size: 20, color: GREY, bold: true })] }),
  new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 4 } }, spacing: { after: 600 }, children: [] }),
  new Paragraph({ spacing: { after: 120 }, children: [run("STYLUS", { size: 72, bold: true, color: NAVY })] }),
  new Paragraph({ spacing: { after: 200 }, children: [run("Retail de moda con compras inteligentes asistidas por IA en tiempo real", { size: 34, bold: true, color: ACCENT })] }),
  new Paragraph({ spacing: { after: 600 }, children: [run("Plataforma Big Data en Google Cloud sobre el dataset público H&M (Kaggle): ingesta batch y streaming, lakehouse medallion, analítica, recomendaciones y asistente con Vertex AI Gemini", { size: 24, color: GREY })] }),
  new Paragraph({ spacing: { after: 120 }, children: [run("ENTREGA 1", { size: 24, bold: true, color: ACCENT })] }),
  new Paragraph({ spacing: { after: 60 }, children: [run("Examen (E): Caso de estudio y sustentación técnica, económica y de resiliencia", { size: 22 })] }),
  new Paragraph({ spacing: { after: 600 }, children: [run("Proyecto Parte 1 (P1): Blueprint, diseño de ingesta y almacenamiento", { size: 22 })] }),
  table([
    ["Integrante", "Perfil en el proyecto"],
    ["Estuardo Oliver", "ML / Analytics: asistente conversacional, analítica y recomendaciones"],
    ["Winston Quispe", "Cloud Computing: infraestructura GCP, ingesta y streaming"],
    ["Nicole Arenas", "Datos + API + Modelado: capas medallion, modelo dimensional y API"],
    ["Gianmarco Mejia", "Dashboard / BI: KPIs, tableros y visualización"],
  ], [3, 7], { boldFirst: true }),
  new Paragraph({ spacing: { before: 400 }, children: [run("Fecha de entrega: 24 de octubre de 2026 · Versión 1.1", { size: 20, color: GREY })] }),
  new Paragraph({ spacing: { before: 60 }, children: [run("Repositorio: github.com/estuardoo/STYLUS · Proyecto GCP: tranquil-leaf-512618-b9", { size: 20, color: GREY })] }),
  brk(),
];

const control = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run("Control del documento")] }),
  table([
    ["Campo", "Detalle"],
    ["Documento", "Entrega 1: Examen (E) + Proyecto Parte 1 (P1)"],
    ["Versión", "1.1 (24-oct-2026): nombre STYLUS, configuración en JSON + panel web, repositorio y proyecto GCP reales"],
    ["Fuente de requisitos", "UTEC, “Entregables del Proyecto Final: Taller de Arquitectura Big Data” (PDF, 3 páginas)"],
    ["Repositorio", "Estructura y código de soporte en el repositorio del proyecto (ver Anexo A)"],
    ["Datos", "H&M Personalized Fashion Recommendations (Kaggle). Única fuente de datos del proyecto"],
    ["Precios", "Lista pública de Google Cloud, región us-central1, consultados el 22-oct-2026"],
  ], [3, 7], { boldFirst: true }),
  sp(),
  P([bold("Convención de estado. "), run("En este documento distinguimos tres niveles de madurez para no sobredeclarar avances: "),
    bold("diseñado"), run(" (decisión documentada), "), bold("implementado"), run(" (código o configuración en el repositorio, probado localmente) y "),
    bold("desplegado"), run(" (funcionando en GCP con evidencia). Para la Entrega 1 el curso exige diseño; lo implementado se indica explícitamente.")]),
  brk(),
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run("Índice")] }),
  "TOC_MARK",
  brk(),
];

const s1 = [
  H1("1. Resumen ejecutivo"),
  P("Proponemos una plataforma analítica integral para un retailer de moda, construida sobre Google Cloud Platform (GCP) y alimentada con el dataset público de H&M: 31.8 millones de líneas de venta de dos años, 1.37 millones de clientes y 105,542 artículos con sus imágenes. La plataforma convierte ese histórico en tres productos de valor: analítica de ventas para gerencia, recomendaciones personalizadas y un asistente de compras conversacional que propone productos reales del catálogo."),
  P("La arquitectura sigue el patrón lakehouse medallion. Cloud Storage guarda los datos originales intactos (Bronze) y sus versiones limpias en Parquet (Silver/Gold); BigQuery actúa como data warehouse; Pub/Sub y Dataflow procesan eventos en tiempo real; Cloud Run expone la API y la web; Cloud SQL mantiene el estado transaccional del carrito y los pedidos; y Vertex AI Gemini 3.1 Flash-Lite impulsa el asistente. Todo se declara con Terraform y se despliega desde GitHub."),
  callout("Resultados clave del diseño",
    `Costo estimado de producción a escala H&M: ${usd(c.produccion.total)} al mes, equivalente a USD ${c.produccion.por_pedido.toFixed(5)} por pedido procesado. ` +
    `Año 1 (11 meses normales + 1 mes pico Black Friday): ${usd(c.anio1, 0)}. Costo de desarrollo y demo del curso: ${usd(c.curso)}. ` +
    "Todos los componentes de cómputo son serverless o autoescalables, por lo que el costo crece con la demanda y no con la capacidad reservada."),
  sp(),
  P("Los tres pilares que pide el examen se resuelven así:"),
  B([bold("Escalabilidad: "), run("desacople por Pub/Sub, autoescalado de Dataflow y Cloud Run, y tablas particionadas en BigQuery; modelamos un pico de 5 veces el tráfico normal.")]),
  B([bold("Economía: "), run("calculadora de costos automatizada (supuestos en YAML, Excel con fórmulas, refresco de precios desde la API oficial de facturación), presupuestos con alertas y medición del costo real por pedido.")]),
  B([bold("Resiliencia: "), run("Bronze inmutable y versionado como punto de reconstrucción, retención de mensajes en Pub/Sub, backups y PITR en Cloud SQL, con RPO/RTO definidos por componente.")]),
];

const s2 = [
  H1("2. Contexto de negocio y alcance"),
  H2("2.1 Problema"),
  P("Un retailer de moda con canal físico y online acumula millones de transacciones, pero las usa casi solo para reportes contables. Las preguntas de negocio que importan quedan sin respuesta oportuna: qué recomendar a cada cliente, qué productos empujar en temporada alta, cuánto cuesta realmente procesar un pedido y cómo reaccionar en minutos, no en días, ante un pico como Black Friday."),
  H2("2.2 Objetivos"),
  B("Integrar el histórico de ventas (batch) con eventos de navegación y compra en tiempo real (streaming) en una única plataforma gobernada."),
  B("Entregar analítica confiable mediante un modelo dimensional en BigQuery y tableros en Looker Studio."),
  B("Ofrecer recomendaciones personalizadas y un asistente conversacional que solo propone artículos reales del catálogo."),
  B("Mantener el costo por pedido medible, bajo y predecible, con alertas automáticas de presupuesto."),
  H2("2.3 Alcance y fuera de alcance"),
  table([
    ["En alcance", "Fuera de alcance"],
    ["Dataset H&M completo: artículos, clientes, transacciones e imágenes", "Otros datasets (Amazon Reviews se descartó; ver §4.3)"],
    ["Ingesta batch a GCS y BigQuery; streaming vía Pub/Sub y Dataflow", "Integración con sistemas reales de una tienda (POS, ERP)"],
    ["Capas Bronze, Silver y Gold; modelo estrella", "Pagos reales: el saldo es simulado y no usa tarjetas ni bancos"],
    ["API, recomendador, asistente Gemini y web demo", "Alta disponibilidad multirregional desplegada (se diseña; el prototipo es de una región)"],
    ["Tableros gerenciales y operativos; calculadora de costos", "Recomendador visual con imágenes (queda como extensión)"],
  ], [1, 1]),
  H2("2.4 Supuestos"),
  B("La compra es una simulación: cada recarga de saldo es explícita y auditable; no hay dinero real."),
  B("Los eventos de 2026 se generan re-emitiendo transacciones reales de H&M con un nuevo event_time; la fecha original se conserva en source_t_dat y todo evento lleva is_synthetic = true."),
  B("El precio de H&M viene normalizado (máximo 0.59); la web aplica un factor de precio demo configurable, señalado como sintético."),
  B("Región principal us-central1 (precios de nivel 1 y disponibilidad de Gemini); los datos son públicos y anonimizados, por lo que no hay restricción de residencia."),
];

const s3 = [
  H1("3. Equipo y roles"),
  P("Los roles se asignaron por perfil profesional. Cada tarea tiene un responsable único y un apoyo; el seguimiento detallado está en la matriz de auditoría (docs/gestion/Matriz_Auditoria_Proyecto.xlsx)."),
  table([
    ["Integrante", "Perfil", "Responsabilidades principales"],
    ["Estuardo Oliver", "ML / Analytics", "Asistente con Vertex AI Gemini (function calling sobre catálogo), recomendador (baseline y contenido), features analíticas, evaluación de modelos, guion de demo y documento técnico"],
    ["Winston Quispe", "Cloud Computing", "Terraform, proyecto GCP e IAM, buckets y Pub/Sub, pipeline Dataflow, CI/CD con GitHub Actions, monitoreo, DRP/HA y automatización de costos"],
    ["Nicole Arenas", "Datos + API + Modelado", "Ingesta batch y Bronze, limpieza Silver y calidad, modelo estrella Gold, diccionario de datos, API FastAPI y base transaccional Cloud SQL"],
    ["Gianmarco Mejia", "Dashboard / BI", "Catálogo de KPIs, calculadora y tablero de costos, diagramas, tableros Looker Studio (gerencial y operativo) y presentación final"],
  ], [2.2, 2, 6], { boldFirst: true }),
];

const s4 = [
  H1("4. Inventario y perfil de datos"),
  P("Antes de diseñar, perfilamos los archivos reales en data/raw. Las cifras de esta sección provienen de una lectura completa de cada archivo, no de la documentación del dataset."),
  table([
    ["Archivo", "Tamaño", "Filas", "Contenido y clave"],
    ["transactions_train.csv", "3.49 GB", "31,788,324", "Venta por línea: t_dat, customer_id, article_id, price, sales_channel_id. 20-sep-2018 a 22-sep-2020 (734 días)"],
    ["customers.csv", "207 MB", "1,371,980", "customer_id (hash SHA-256), edad, estado de membresía, código postal hasheado"],
    ["articles.csv", "36 MB", "105,542", "article_id, 47,224 product_code, 131 tipos de producto, 5 grupos de índice, descripción"],
    ["images/", "29 GB", "105,100 jpg", "Una imagen por artículo en carpetas por prefijo (442 artículos sin imagen)"],
    ["sample_submission.csv", "270 MB", "1,371,980", "Formato de predicción de la competencia; no se usa como dato de negocio"],
  ], [2.4, 1.1, 1.4, 5.5], { right: [1, 2] }),
  caption("Tabla 1. Inventario de la fuente H&M (medido el 22-oct-2026)."),
  H2("4.1 Hallazgos de calidad"),
  table([
    ["Hallazgo", "Medición", "Tratamiento en Silver"],
    ["Edad faltante", "15,861 clientes (1.2%)", "Imputar como desconocida; segmento 'sin edad'"],
    ["FN y Active vacíos", "895,050 y 907,576 nulos", "Interpretar vacío como 0 (bandera no activada)"],
    ["Estado de membresía y newsletter", "6,062 y 16,009 nulos", "Categoría 'NONE'"],
    ["Descripción de artículo", "416 nulos", "Usar nombre y tipo de producto como respaldo"],
    ["Precio normalizado", "Máximo 0.59; sin moneda", "Se conserva; factor de precio demo solo en la web"],
    ["Pedido no explícito", "Sin order_id", "Pedido = cliente + día: 9,080,179 pedidos, 3.5 líneas de media"],
  ], [2.4, 2.4, 4]),
  caption("Tabla 2. Calidad de datos y regla de tratamiento."),
  H2("4.2 Patrones de negocio útiles para el diseño"),
  B([bold("Volumen: "), run("~1.32 millones de líneas y ~377 mil pedidos por mes; el mes más alto (junio de 2019, 1.91 millones de líneas) es 1.44 veces el promedio.")]),
  B([bold("Canal: "), run("70.4% de las líneas son del canal online (22.4 millones) y 29.6% de tienda física.")]),
  B([bold("Caso bebé: "), run("34,711 artículos pertenecen al grupo Baby/Children (8,875 de ellos con tallas de bebé), por lo que el caso de demo “necesito algo para mi bebé” se resuelve con catálogo real.")]),
  B([bold("Privacidad: "), run("customer_id y postal_code ya vienen seudonimizados con hash; no hay nombres, correos ni teléfonos.")]),
  H2("4.3 Decisión sobre la fuente Amazon Reviews 2023"),
  P("Evaluamos Amazon Reviews 2023 como segunda fuente. La descartamos porque sus identificadores (ASIN, user_id) no comparten espacio con los de H&M y tres de las seis categorías descargadas no tienen relación con moda. Unir ambas fuentes sin una clave común habría requerido inventar correspondencias. Los archivos quedan archivados fuera del repositorio."),
];

const s5 = [
  H1("5. Stack tecnológico y justificación"),
  P("Priorizamos componentes de GCP vistos en clase, serverless y con pago por uso. Cada decisión se tomó frente a una alternativa concreta."),
  table([
    ["Capa", "Servicio elegido", "Por qué", "Alternativa descartada"],
    ["Data Lake", "Cloud Storage (2 buckets privados)", "Barato (USD 0.020/GB-mes), durable, versionado; desacopla almacenamiento de cómputo", "HDFS en Dataproc: paga nodos encendidos"],
    ["Data Warehouse", "BigQuery", "Serverless, SQL estándar, particionado y clustering; 1 TiB de consulta gratis al mes", "Cloud SQL para analítica: no escala a 31.8M filas con consultas ad hoc"],
    ["Ingesta streaming", "Pub/Sub + suscripción BigQuery", "Absorbe picos, retiene mensajes, DLQ nativa; la suscripción BQ evita un job permanente", "Kafka autogestionado: operación y costo fijo"],
    ["Procesamiento streaming", "Dataflow (Apache Beam)", "Ventanas, deduplicación, datos tardíos y autoescalado; mismo código batch/stream", "Cloud Functions: sin estado ni ventanas"],
    ["Procesamiento batch", "Serverless for Apache Spark (Dataproc) + BigQuery SQL", "Spark sin clúster para limpieza a Parquet; SQL para Gold", "Clúster Dataproc permanente"],
    ["OLTP", "Cloud SQL PostgreSQL", "ACID para carrito, pedidos y ledger del saldo", "BigQuery: no es transaccional"],
    ["API y web", "Cloud Run", "Contenedores que escalan a cero; 2M requests gratis/mes", "GKE: sobredimensionado para el caso"],
    ["IA generativa", "Vertex AI Gemini 3.1 Flash-Lite", "Gemini más económico vigente en Vertex AI (USD 0.25/1.50 por millón de tokens); salida estructurada", "LLM propio en GPU: costo fijo alto"],
    ["BI", "Looker Studio", "Sin licencia, conector nativo a BigQuery", "Tableau/Power BI: licencias"],
    ["IaC y CI/CD", "Terraform + GitHub Actions (WIF)", "Infraestructura reproducible; sin llaves permanentes", "Configuración manual en consola"],
  ], [1.6, 2.2, 3.6, 2.6], { boldFirst: true }),
  caption("Tabla 3. Decisiones tecnológicas (ADR resumidos)."),
  callout("Sobre el costo de Vertex AI Gemini",
    "Gemini en Vertex AI no es gratuito, pero su costo es marginal: una conversación típica (≈3,000 tokens de entrada y 400 de salida) cuesta alrededor de USD 0.0014. " +
    "Mil conversaciones de prueba cuestan unos USD 1.40, y los créditos de bienvenida de GCP (USD 300 para cuentas nuevas) cubren holgadamente el proyecto. " +
    "Se limita además con cuotas por minuto y con el presupuesto con alertas descrito en §9.3."),
];

const s6 = [
  H1("6. Arquitectura end-to-end", { pageBreakBefore: true }),
  P("La Figura 1 muestra las cinco capas que exige P1 (ingesta, almacenamiento, cómputo y exposición, más las fuentes) y los componentes transversales de seguridad, operación y costos."),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 }, children: [new ImageRun({
    type: "png", data: fs.readFileSync(`${REPO}/docs/architecture/arquitectura.png`),
    transformation: { width: 580, height: Math.round(580 * 2288 / 1797) },
    altText: { title: "Arquitectura", description: "Arquitectura end-to-end de la plataforma", name: "arquitectura" } })] }),
  caption("Figura 1. Arquitectura end-to-end (fuente regenerable: docs/architecture/arquitectura_vertical.dot)."),
  H2("6.1 Flujo batch"),
  B("upload_raw.py calcula un manifiesto (SHA-256, bytes, filas, columnas) y sincroniza data/raw con el bucket raw mediante gcloud storage rsync. Reejecutar no duplica datos."),
  B("BigQuery lee los CSV de Bronze como tablas externas y materializa transactions particionada por día y agrupada por cliente y artículo (sql/bronze/01_bronze_hm.sql)."),
  B("Serverless Spark limpia y tipa hacia Silver en Parquet; BigQuery SQL construye el modelo estrella Gold."),
  H2("6.2 Flujo streaming"),
  B("El publicador replay_publisher.py re-emite transacciones reales como eventos de 2026 hacia el tópico retail-events. Cada evento lleva event_id determinista (idempotencia), event_time 2026, source_t_dat original y la marca is_synthetic."),
  B("Ruta económica: una suscripción Pub/Sub → BigQuery escribe los mensajes crudos en retail_bronze.events_raw sin ningún job intermedio."),
  B("Ruta enriquecida (ventana de demo): Dataflow lee la suscripción dedicada, deduplica por event_id, agrega en ventanas de 1 minuto, maneja datos tardíos y envía errores a la DLQ."),
  H2("6.3 Integración multifuente"),
  P("El histórico batch y el flujo streaming se cruzan por las claves naturales de H&M (article_id y customer_id), que son las mismas en ambos caminos porque el streaming re-emite registros del propio dataset. Para no mezclar historia con simulación separamos dos relojes: source_t_dat (fecha real, nunca se reescribe) y event_time (fecha simulada 2026). Toda tabla lleva _source_system y _ingested_at para trazabilidad."),
];

const s7 = [
  H1("7. Definición de ingesta y almacenamiento"),
  H2("7.1 Mecanismos de captura"),
  table([
    ["Flujo", "Mecanismo", "Frecuencia", "Garantías"],
    ["Histórico H&M (CSV + imágenes)", "gcloud storage rsync + manifiesto SHA-256", "Carga inicial y reprocesos", "Idempotente; checksum y conteo por archivo"],
    ["Eventos de compra/navegación", "Pub/Sub (tópico retail-events)", "Continuo, segundos", "Entrega al menos una vez; dedup por event_id; DLQ tras 5 intentos"],
    ["Pedidos y saldo de la web", "Cloud SQL (escritura transaccional)", "En línea", "ACID; clave de idempotencia por checkout"],
    ["Costos de la plataforma", "Billing export a BigQuery", "Diario", "Fuente oficial de facturación"],
  ], [2.4, 2.6, 1.6, 3]),
  caption("Tabla 4. Mecanismos de captura."),
  H2("7.2 Motores de almacenamiento y modelo medallion"),
  table([
    ["Capa", "Motor y ubicación", "Formato", "Contenido", "Política"],
    ["Bronze", "GCS raw (gs://…-retail-raw/hm/) + BigQuery retail_bronze", "CSV/JPG originales; tablas externas y events_raw", "Copia exacta de H&M y eventos crudos", "Inmutable, versionado, imágenes a Nearline a los 30 días"],
    ["Silver", "GCS lake + BigQuery retail_silver", "Parquet particionado por fecha", "Datos tipados, sin duplicados, nulos tratados", "Reproducible desde Bronze"],
    ["Gold", "BigQuery retail_gold", "Tablas nativas particionadas", "Modelo estrella: fact_sales, fact_orders, dim_article, dim_customer, dim_date, dim_channel; features", "Optimizado para consumo"],
    ["Operación", "BigQuery retail_ops", "Tablas y vistas", "Calidad, lag de streaming, costos reales", "Retención 13 meses"],
    ["Transaccional", "Cloud SQL PostgreSQL", "Relacional", "Usuarios demo, carrito, pedidos, wallet y ledger", "Backups diarios + PITR"],
  ], [1.5, 2.2, 1.8, 2.7, 2.0], { boldFirst: true }),
  caption("Tabla 5. Motores de almacenamiento por capa."),
  P("No usamos una base NoSQL (Bigtable o Firestore): el acceso por clave de baja latencia que justificaría una se cubre con Cloud SQL para el estado del usuario y con BigQuery más una caché en memoria de la API para las recomendaciones precalculadas. Una NoSQL agregaría costo fijo sin un caso de uso que la requiera."),
  H2("7.3 Implementado para esta entrega"),
  table([
    ["Artefacto", "Ruta en el repositorio", "Estado"],
    ["Infraestructura: buckets privados, datasets por capa, Pub/Sub + DLQ + suscripción BQ, cuentas de servicio, presupuesto", "infra/terraform/", "Implementado; pendiente de plan/apply en GCP"],
    ["Ingesta batch con manifiesto", "ingestion/batch/upload_raw.py", "Implementado y probado localmente"],
    ["Bronze en BigQuery", "sql/bronze/01_bronze_hm.sql", "Implementado; pendiente de ejecución en GCP"],
    ["Publicador streaming 2026", "ingestion/streaming/replay_publisher.py", "Implementado; pruebas unitarias OK"],
    ["Calculadora de costos automatizada", "cost/", "Implementado y ejecutado"],
  ], [4.5, 3, 2.5]),
];

const s8 = [
  H1("8. Escalabilidad y performance"),
  P("Dimensionamos con los datos reales. En operación normal H&M procesa ~12,400 pedidos diarios (~43,000 líneas). Suponiendo 20 eventos de navegación por línea comprada, el tráfico medio es de ~10 eventos por segundo. Para Black Friday modelamos 5 veces el volumen mensual y una hora punta 50 veces superior a la media: ~500 eventos por segundo."),
  table([
    ["Componente", "Cómo escala", "Comportamiento en el pico", "Límite / control"],
    ["Pub/Sub", "Automático, sin aprovisionar", "Absorbe ráfagas y retiene 7 días si el consumidor se atrasa", "Cuota de publicación por región; alerta por backlog"],
    ["Dataflow", "Autoescalado horizontal de workers", "Pasa de 1 a N workers según backlog; Streaming Engine separa estado y cómputo", "max_num_workers acotado para el presupuesto"],
    ["BigQuery", "Slots bajo demanda", "Consultas sobre particiones del día; clustering por cliente y artículo reduce bytes escaneados", "Costo por TiB; require_partition_filter evita escaneos completos"],
    ["Cloud Run (API/web)", "Instancias por concurrencia", "De 0 a decenas de instancias en segundos; 80 requests concurrentes por instancia", "max-instances y min-instances=1 en temporada alta"],
    ["Cloud SQL", "Vertical + réplicas de lectura", "Solo escrituras de carrito y pedidos; las lecturas analíticas van a BigQuery", "Pool de conexiones; réplica para lecturas"],
    ["Vertex AI Gemini", "Servicio gestionado", "Respuestas en ~1 s; caché de recomendaciones por segmento", "Cuota por minuto; respaldo a recomendador por reglas"],
  ], [1.7, 2, 3.5, 2.8], { boldFirst: true }),
  caption("Tabla 6. Estrategia de escalado por componente."),
  H2("8.1 Degradación controlada"),
  B("Si Gemini supera su cuota, el asistente responde con recomendaciones por popularidad del segmento, sin bloquear la compra."),
  B("Si Dataflow se atrasa, la suscripción directa a BigQuery sigue registrando los eventos crudos; los agregados se recalculan después."),
  B("Si Cloud SQL se satura, el checkout responde con reintento y clave de idempotencia; nunca cobra dos veces."),
  H2("8.2 Metas de performance"),
  P("Latencia p95 de la API menor a 500 ms (sin asistente) y menor a 3 s con Gemini; lag de streaming p95 menor a 60 s entre publicación y disponibilidad en BigQuery; consultas Gold de tablero menores a 5 s."),
];

const s9 = [
  H1("9. Justificación económica y optimización de costos"),
  H2("9.1 Escenarios"),
  P("La calculadora (cost/assumptions.yaml → cost/output/cost_estimate.xlsx) estima el costo mensual por servicio en cuatro escenarios. Los volúmenes de producción salen del perfil real de H&M: 377,000 pedidos al mes. Precios de lista en us-central1, consultados el 22-oct-2026, aplicando los niveles gratuitos mensuales."),
  table(costRows, [2.2, 1.9, 1.9, 2.1, 2.1], { right: [1, 2, 3, 4], boldFirst: true }),
  caption("Tabla 7. Costo mensual estimado por servicio y escenario (USD)."),
  callout("Costo por pedido",
    `En producción la plataforma cuesta USD ${c.produccion.por_pedido.toFixed(5)} por pedido (menos de una décima de centavo). En el pico de Black Friday baja a USD ${c.pico_black_friday.por_pedido.toFixed(5)}, porque los costos fijos (Cloud SQL, almacenamiento) se reparten entre más pedidos y el resto escala con el uso. ` +
    `El año 1 completo se estima en ${usd(c.anio1, 0)}.`),
  sp(),
  H2("9.2 Palancas de optimización aplicadas"),
  B([bold("Serverless y escala a cero: "), run("Cloud Run, Serverless Spark y BigQuery no cobran sin uso.")]),
  B([bold("Ruta streaming sin job permanente: "), run("la suscripción Pub/Sub → BigQuery cuesta USD 50/TiB sin cargos de ingesta; Dataflow se enciende solo cuando se necesita enriquecimiento con ventanas.")]),
  B([bold("Menos bytes escaneados: "), run("particionado por fecha, clustering y filtro de partición obligatorio; Parquet columnar en Silver.")]),
  B([bold("Ciclo de vida del almacenamiento: "), run("las 105,100 imágenes (29 GB) pasan a Nearline a los 30 días, a la mitad del precio.")]),
  B([bold("Modelo de IA más barato: "), run("Gemini 3.1 Flash-Lite (el modelo se cambia desde config/control_plataforma.json) y caché de respuestas frecuentes.")]),
  B([bold("Región de nivel 1: "), run("us-central1 tiene las tarifas más bajas para Cloud Run y Dataflow.")]),
  H2("9.3 Automatización de costos"),
  P("El control de costos no depende de revisiones manuales. Implementamos tres mecanismos que se refuerzan entre sí:"),
  table([
    ["Mecanismo", "Qué hace", "Dónde"],
    ["1. Estimador automatizado", "Supuestos en un único YAML; un script genera el Excel con fórmulas y el resumen. Con --refresh-prices consulta la API Cloud Billing Catalog y actualiza las tarifas con fecha. Corre en cada push (CI).", "cost/estimate_costs.py (--refresh-prices)"],
    ["2. Presupuesto con alertas", "Budget por proyecto con umbrales del 50%, 90% y 100% (real) y 100% (pronosticado); publica en un tópico Pub/Sub para notificar o apagar recursos de demo.", "infra/terraform/main.tf (google_billing_budget)"],
    ["3. Costo real por pedido", "Billing export a BigQuery + vista que cruza costo diario por servicio con pedidos procesados en Gold; alimenta el tablero de costos.", "cost/real_cost_per_order.sql"],
  ], [2, 5, 3], { boldFirst: true }),
  caption("Tabla 8. Mecanismos de automatización de costos."),
  P("El ciclo se cierra comparando lo estimado (mecanismo 1) con lo facturado (mecanismo 3) y recalibrando los supuestos; esa comparación forma parte de la Entrega 3."),
  P([run("Nota: ", { bold: true }), run("son estimaciones con precios de lista, no una cotización. Deben validarse en la calculadora oficial https://cloud.google.com/products/calculator; el costo final depende del uso real.", { italics: true })]),
];

const s10 = [
  H1("10. Plan de recuperación y alta disponibilidad (DRP/HA)"),
  P("El principio central es que todo dato derivado puede reconstruirse desde Bronze, que es inmutable y versionado. Por eso la pérdida de cualquier capa de cómputo o de Silver/Gold se resuelve reprocesando, y la protección se concentra en Bronze y en el estado transaccional."),
  table([
    ["Componente", "Falla considerada", "Protección", "RPO", "RTO"],
    ["GCS raw (Bronze)", "Borrado o sobrescritura accidental", "Versionado de objetos, acceso uniforme, sin acceso público; durabilidad 11 nueves", "0", "< 15 min"],
    ["BigQuery Silver/Gold", "Tabla dañada o borrada", "Time travel 7 días + reproceso desde Bronze", "0", "< 1 h"],
    ["Pub/Sub", "Consumidor caído", "Retención de mensajes no confirmados (7 días), DLQ, seek para reprocesar", "0", "< 15 min"],
    ["Dataflow", "Falla del job o de workers", "Reemplazo automático de workers; relanzamiento desde plantilla; la suscripción BQ sigue capturando", "0", "< 30 min"],
    ["Cloud SQL", "Corrupción o falla de zona", "Backup diario + recuperación a un punto en el tiempo (PITR); en producción, instancia HA regional", "≤ 5 min", "< 1 h (prototipo) / ~1 min (HA)"],
    ["Cloud Run", "Falla de zona", "Servicio regional multizona por defecto", "N/A", "Segundos"],
    ["Región completa", "Caída de us-central1", "Terraform reproduce todo en una segunda región; Bronze en dual-region en producción", "≤ 24 h (prototipo)", "< 4 h"],
    ["Estado de Terraform", "Pérdida o conflicto", "Bucket GCS versionado con bloqueo de estado", "0", "< 15 min"],
  ], [1.8, 1.9, 3.6, 1, 1.5], { boldFirst: true }),
  caption("Tabla 9. Matriz de fallas, RPO y RTO."),
  H2("10.1 Prototipo frente a producción"),
  P("El prototipo del curso es de una sola región para mantener el costo bajo; no lo presentamos como alta disponibilidad probada. Para producción, el diseño agrega Cloud SQL en modo HA regional, Bronze en un bucket dual-region, BigQuery en la multirregión US y Cloud Run en dos regiones detrás de un balanceador global. La Entrega 3 incluirá una prueba real de restauración de Cloud SQL y de una versión de objeto en GCS, con el RTO medido."),
];

const s11 = [
  H1("11. KPIs de éxito y performance"),
  table([
    ["Dimensión", "KPI", "Meta", "Fuente"],
    ["Datos", "Filas cargadas vs manifiesto", "100% conciliado", "retail_ops + manifiesto"],
    ["Datos", "Filas rechazadas en Silver", "< 0.5% y todas contabilizadas", "Reporte de calidad"],
    ["Streaming", "Lag p95 publicación → BigQuery", "< 60 s", "events_raw.publish_time vs ingesta"],
    ["Streaming", "Mensajes en DLQ", "< 0.1%", "Monitoreo Pub/Sub"],
    ["Modelo", "MAP@12 del recomendador vs baseline de popularidad", "Mejora > 10%", "Evaluación con split temporal"],
    ["API", "Latencia p95 / disponibilidad", "< 500 ms / ≥ 99.5% en ventana de prueba", "Cloud Monitoring"],
    ["Negocio (simulado)", "Conversión, ticket medio, pedidos", "Visibles por día y canal", "Gold + Looker Studio"],
    ["Costos", "USD por pedido", `≤ USD ${(c.produccion.por_pedido * 1.2).toFixed(4)} (estimado + 20%)`, "Billing export"],
  ], [1.6, 3.3, 2.6, 2.5], { boldFirst: true }),
  caption("Tabla 10. Catálogo de KPIs."),
];

const s12 = [
  H1("12. Seguridad y gobierno"),
  B("Buckets privados con acceso uniforme y prevención de acceso público forzada; cifrado en reposo y TLS en tránsito por defecto."),
  B("Cuatro cuentas de servicio con mínimo privilegio (ingesta, pipelines, API y despliegue); GitHub Actions usa Workload Identity Federation, sin llaves JSON."),
  B("Secretos en Secret Manager; .gitignore y una regla de CI impiden versionar datos, credenciales o estado de Terraform."),
  B("Datos de clientes ya seudonimizados; los eventos sintéticos se identifican con is_synthetic y simulation_run_id."),
  B("El asistente solo puede proponer artículos existentes y requiere confirmación explícita del usuario antes del checkout."),
];

const s13 = [
  H1("13. Plan de trabajo por entregas"),
  table([
    ["Paso", "Fecha", "Entregable", "Contenido principal"],
    ["1", "24-oct-2026", "Examen + P1", "Este documento: stack, escalabilidad, costos, DRP/HA, arquitectura, ingesta y almacenamiento; repositorio base"],
    ["2", "07-nov-2026", "P2", "Infraestructura desplegada, Bronze/Silver/Gold, replay streaming con Dataflow, modelo estrella, recomendador baseline"],
    ["3", "20/21-nov-2026", "P3 + sustentación", "API en Cloud Run, asistente Gemini, wallet en Cloud SQL, tableros, demo end-to-end, slides y costo real"],
  ], [0.8, 1.6, 1.8, 6]),
  caption("Tabla 11. Hitos. El detalle por tarea y responsable está en la matriz de auditoría."),
  H1("14. Riesgos y mitigaciones"),
  table([
    ["Riesgo", "Impacto", "Mitigación"],
    ["Gasto inesperado en nube", "Alto", "Presupuesto con alertas, Dataflow solo en demo, checklist de apagado"],
    ["Subida lenta de 33 GB desde la red local", "Medio", "rsync reanudable; imágenes en segundo plano; CSV primero"],
    ["Cuotas de Gemini o Dataflow en cuenta nueva", "Medio", "Solicitar cuota temprano; respaldo por reglas"],
    ["Plazo corto entre entregas", "Alto", "MVP por hito; responsables únicos por tarea; matriz de seguimiento"],
    ["Confundir datos simulados con reales", "Medio", "Doble reloj (source_t_dat / event_time) e is_synthetic en todo evento"],
  ], [3.5, 1.2, 5.3]),
];

const anexo = [
  H1("Anexo A. Repositorio y reproducibilidad"),
  P("El repositorio github.com/estuardoo/STYLUS (privado) se publica sin datos ni secretos. Estructura:"),
  ...[
    "config/                 JSON de control: parámetros, tablas, columnas, usuarios y permisos",
    "panel/                  Panel web local para editar la configuración y desplegar",
    "ops.py                  Orquestador de despliegue (Windows, Linux, Cloud Shell)",
    "infra/terraform/        Infraestructura GCP (estado remoto en GCS)",
    "ingestion/batch/        Carga de H&M a Bronze con manifiesto",
    "ingestion/streaming/    Publicador replay de eventos 2026",
    "pipelines/              Spark (Silver), Dataflow (streaming), recomendador",
    "sql/                    Bronze, Silver, Gold y vistas BI en BigQuery",
    "api/                    FastAPI, web, asistente Gemini y wallet",
    "cost/                   Calculadora y automatización de costos",
    "docs/architecture/      Diagramas regenerables (Graphviz)",
    "docs/entrega1/          Este documento",
    "docs/gestion/           Matriz de auditoría y roles",
    "tests/                  Pruebas unitarias",
    ".github/workflows/      CI: pruebas, costos, terraform validate",
    "data/                   Solo local; excluido de Git",
  ].map(l => new Paragraph({ spacing: { after: 0 }, children: [run(l, { font: "Consolas", size: 18 })] })),
  sp(),
  P("Todos los nombres, parámetros, tablas, columnas, usuarios iniciales y permisos se controlan desde config/control_plataforma.json (editable con python ops.py panel); python ops.py config los convierte en variables de Terraform y semillas de la API, y python ops.py verificar compara lo desplegado contra ese archivo."),
  P("Comandos principales: python ops.py config · bootstrap · plan · apply · subir-datos · bronze · silver · gold · api · verificar · todo. Guía de despliegue en docs/DEPLOY.md y guía técnica completa en docs/entrega1/Guia_Tecnica_STYLUS.pdf."),
  H1("Referencias"),
  ...[
    "UTEC. Entregables del Proyecto Final: Taller de Arquitectura Big Data. Sección 1, 2026.",
    "Kaggle. H&M Personalized Fashion Recommendations. https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations",
    "Google Cloud. Cloud Storage pricing. https://cloud.google.com/storage/pricing",
    "Google Cloud. BigQuery pricing. https://cloud.google.com/bigquery/pricing",
    "Google Cloud. Pub/Sub pricing. https://cloud.google.com/pubsub/pricing",
    "Google Cloud. Dataflow pricing. https://cloud.google.com/dataflow/pricing",
    "Google Cloud. Serverless for Apache Spark pricing. https://cloud.google.com/dataproc-serverless/pricing",
    "Google Cloud. Cloud Run pricing. https://cloud.google.com/run/pricing",
    "Google Cloud. Cloud SQL pricing. https://cloud.google.com/sql/pricing",
    "Google Cloud. Vertex AI generative AI pricing. https://cloud.google.com/vertex-ai/generative-ai/pricing",
    "Google Cloud. Pricing Calculator. https://cloud.google.com/products/calculator",
  ].map(t => new Paragraph({ numbering: { reference: "refs", level: 0 }, spacing: { after: 60 }, children: [run(t, { size: 19 })] })),
];

const PAGES = process.argv[4] ? JSON.parse(fs.readFileSync(process.argv[4], "utf8")) : {};
fs.writeFileSync(OUT + ".toc.json", JSON.stringify(TOC));
const tocParas = TOC.map(([lvl, t]) => new Paragraph({
  tabStops: [{ type: d.TabStopType.RIGHT, position: W, leader: "dot" }],
  spacing: { before: lvl === 1 ? 100 : 0, after: 40 }, indent: { left: lvl === 1 ? 0 : 360 },
  children: [run(t, { bold: lvl === 1, size: lvl === 1 ? 21 : 20 }), run("\t" + (PAGES[t] || "0"), { bold: lvl === 1, size: lvl === 1 ? 21 : 20 })],
}));
control.splice(control.indexOf("TOC_MARK"), 1, new TableOfContents("Índice", { hyperlink: true, headingStyleRange: "1-2" }), ...tocParas);
const doc = new Document({
  creator: "Equipo Retail Big Data", features: { updateFields: true }, title: "Entrega 1 - Arquitectura Big Data Retail",
  styles: {
    default: { document: { run: { font: "Arial", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: NAVY }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: ACCENT }, paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial" }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "refs", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "[%1]", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 540 } } } }] },
  ] },
  sections: [
    { properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      children: portada },
    { properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      headers: { default: new Header({ children: [new Paragraph({ tabStops: [{ type: d.TabStopType.RIGHT, position: W }], border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 } },
        children: [run("STYLUS · Retail con compras inteligentes asistidas por IA", { size: 16, color: GREY }),
          run("\tEntrega 1 · Examen + P1", { size: 16, color: GREY })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [run("Página ", { size: 16, color: GREY }), new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: GREY })] })] }) },
      children: [...control, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8, ...s9, ...s10, ...s11, ...s12, ...s13, ...anexo] },
  ],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("ok", OUT); });
