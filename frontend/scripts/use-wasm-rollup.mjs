// Reproducible workaround for Windows "Application Control" policies that block
// rollup's native .node binary (ERR_DLOPEN_FAILED). If the native build cannot
// load, replace node_modules/rollup with the pure-JS @rollup/wasm-node package.
// Safe no-op on normal machines where the native binary loads fine.
import { createRequire } from "node:module";
import { cpSync, rmSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const nm = join(here, "..", "node_modules");

function nativeLoads() {
  try {
    require("@rollup/rollup-win32-x64-msvc/rollup.win32-x64-msvc.node");
    return true;
  } catch {
    return false;
  }
}

if (!nativeLoads()) {
  const wasmDir = join(nm, "@rollup", "wasm-node");
  const rollupDir = join(nm, "rollup");
  if (existsSync(wasmDir)) {
    rmSync(rollupDir, { recursive: true, force: true });
    cpSync(wasmDir, rollupDir, { recursive: true });
    const pkgPath = join(rollupDir, "package.json");
    const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
    pkg.name = "rollup";
    writeFileSync(pkgPath, JSON.stringify(pkg, null, 2));
    console.log("[spamsms] Applied WASM rollup fallback (native binary blocked by OS policy).");
  } else {
    console.warn("[spamsms] Native rollup blocked but @rollup/wasm-node not installed.");
  }
}
