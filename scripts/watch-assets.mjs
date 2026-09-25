import { spawn } from "node:child_process";
import { watch } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { context } from "esbuild";

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL("../", import.meta.url));
const javascript = await context({
  absWorkingDir: root,
  entryPoints: ["static/src/app.js"],
  bundle: true,
  outfile: "static/js/app.js",
  logLevel: "info",
});
const watchers = [];
let css;
let cssRunning = false;
let cssPending = false;
let debounce;
let stopping = false;

async function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  clearTimeout(debounce);
  watchers.forEach(watcher => watcher.close());
  css?.kill("SIGTERM");
  await javascript.dispose();
  process.exit(code);
}

function buildCss() {
  if (stopping || cssRunning || !cssPending) return;
  cssPending = false;
  cssRunning = true;
  css = spawn(process.execPath, [
    require.resolve("tailwindcss/lib/cli.js"),
    "-i", "static/src/app.css", "-o", "static/css/app.css", "--minify",
  ], { cwd: root, stdio: "inherit" });
  css.on("error", error => {
    console.error("CSS build failed:", error.message);
    stop(1);
  });
  css.on("exit", code => {
    cssRunning = false;
    css = undefined;
    if (stopping) return;
    if (code !== 0) return stop(code || 1);
    buildCss();
  });
}

function queueCssBuild() {
  cssPending = true;
  clearTimeout(debounce);
  debounce = setTimeout(buildCss, 100);
}

process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());

try {
  await javascript.watch();
  for (const directory of ["templates", "apps", "static/src"]) {
    const watcher = watch(new URL(`../${directory}/`, import.meta.url), { recursive: true }, (_, filename) => {
      if (filename && /\.(css|html|js)$/i.test(String(filename))) queueCssBuild();
    });
    watcher.on("error", error => {
      console.error(`Asset watcher failed in ${directory}:`, error.message);
      stop(1);
    });
    watchers.push(watcher);
  }
  const configWatcher = watch(new URL("../tailwind.config.js", import.meta.url), queueCssBuild);
  configWatcher.on("error", error => {
    console.error("Tailwind config watcher failed:", error.message);
    stop(1);
  });
  watchers.push(configWatcher);
  queueCssBuild();
  console.log("Watching CSS, HTML, and JavaScript changes; every change rebuilds CSS, and esbuild watches JavaScript.");
} catch (error) {
  console.error(error.message);
  await stop(1);
}
