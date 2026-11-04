/**
 * TheCore — postinstall.
 *
 * `better-sqlite3` ships a prebuilt binary for Node, not for Electron, and
 * the prebuilt binary crashes the Electron main process.  The module has to
 * be compiled against Electron's headers instead.
 *
 * Two things are needed for that:
 *   1. the Node prebuilds must be out of the way — better-sqlite3's
 *      binding.gyp skips compiling when it finds a prebuild, and its loader
 *      prefers the prebuild over the compiled binary anyway;
 *   2. `electron-rebuild` must run against the installed Electron version.
 *
 * The build is skipped when the binary is already present and was built for
 * the current Electron version.
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const root = path.join(__dirname, "..");
const moduleDir = path.join(root, "node_modules", "better-sqlite3");

function electronVersion() {
  try {
    return require(path.join(root, "node_modules", "electron", "package.json"))
      .version;
  } catch {
    return null;
  }
}

function alreadyBuiltFor(version) {
  const binary = path.join(
    moduleDir,
    "build",
    "Release",
    "better_sqlite3.node"
  );
  if (!fs.existsSync(binary)) return false;
  try {
    const config = fs.readFileSync(
      path.join(moduleDir, "build", "config.gypi"),
      "utf8"
    );
    return config.includes(`"target": "${version}"`);
  } catch {
    return false;
  }
}

function main() {
  if (!fs.existsSync(moduleDir)) return;

  const version = electronVersion();
  if (version && alreadyBuiltFor(version)) {
    console.log(
      `[postinstall] better-sqlite3 is already built for Electron ${version}.`
    );
    return;
  }

  // Hide the Node prebuilds so the module compiles from source.
  const prebuilds = path.join(moduleDir, "prebuilds");
  if (fs.existsSync(prebuilds)) {
    const hidden = path.join(moduleDir, "prebuilds.node-backup");
    try {
      if (fs.existsSync(hidden)) fs.rmSync(hidden, { recursive: true });
      fs.renameSync(prebuilds, hidden);
      console.log("[postinstall] moved the Node prebuilds out of the way.");
    } catch (err) {
      console.warn("[postinstall] could not move the prebuilds:", err.message);
    }
  }

  console.log("[postinstall] building better-sqlite3 for Electron…");
  const rebuild = path.join(
    root,
    "node_modules",
    ".bin",
    "electron-rebuild.cmd"
  );
  const cmd = fs.existsSync(rebuild) ? rebuild : "electron-rebuild";
  execFileSync(cmd, ["-f", "-o", "better-sqlite3"], {
    cwd: root,
    stdio: "inherit",
    shell: true,
  });
  console.log("[postinstall] better-sqlite3 is ready.");
}

try {
  main();
} catch (err) {
  // A failed native build must not break `npm install` for the rest of the
  // project — the app reports the problem when it starts.
  console.warn("[postinstall] better-sqlite3 build failed:", err.message);
}
