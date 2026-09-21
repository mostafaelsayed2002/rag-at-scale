// Copies PDF.js's worker into public/ before dev and build.
//
// It cannot be bundled: Next's minifier rejects the worker's module syntax
// ("'import' and 'export' cannot be used outside of module code"). Served as
// a static file instead, and copied rather than committed so it can never
// drift from the installed pdfjs-dist version.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const pdfjsRoot = dirname(require.resolve("pdfjs-dist/package.json"));
const source = join(pdfjsRoot, "build", "pdf.worker.min.mjs");

mkdirSync("public", { recursive: true });
copyFileSync(source, join("public", "pdf.worker.min.mjs"));
console.log("copied pdf.worker.min.mjs into public/");
