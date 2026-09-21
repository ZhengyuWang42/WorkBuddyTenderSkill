import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const stdinChunks = [];
for await (const chunk of process.stdin) {
  stdinChunks.push(chunk);
}
const payload = JSON.parse(Buffer.concat(stdinChunks).toString("utf8"));
const artifactToolPath = path.join(
  payload.node_modules_dir,
  "@oai",
  "artifact-tool",
  "dist",
  "artifact_tool.mjs",
);
const { FileBlob, SpreadsheetFile } = await import(pathToFileURL(artifactToolPath).href);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(payload.template_path));
const worksheet = workbook.worksheets.getItem(payload.sheet_name);
if (!worksheet) {
  throw new Error(`Template sheet not found: ${payload.sheet_name}`);
}

for (const [address, value] of Object.entries(payload.writes || {})) {
  const values = Array.isArray(value) && Array.isArray(value[0]) ? value : [[value]];
  worksheet.getRange(address).values = values;
}

workbook.recalculate();
await fs.mkdir(path.dirname(payload.output_path), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(payload.output_path);
// artifact-tool may emit an inspection sidecar next to the XLSX.  It is an
// authoring diagnostic, not a delivery artifact, so keep the output directory
// aligned with the pipeline contract.
try {
  await fs.rm(`${payload.output_path}.inspect.ndjson`, { force: true });
} catch (_error) {
  // The XLSX itself has already been written; a missing sidecar is harmless.
}
console.log(JSON.stringify({ sheet: payload.sheet_name, writes: Object.keys(payload.writes || {}) }));
