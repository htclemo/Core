/**
 * TheCore — debug logging (Electron main process).
 *
 * Writes a rotating log file when debugging is switched on with the
 * `THECORE_DEBUG=1` environment variable or the `--debug` command line flag.
 *
 * The file lives next to the other app data:
 *
 *     %APPDATA%\\TheCore\\thecore.log   (Windows)
 *     ~/.thecore/thecore.log             (other platforms)
 */

import * as fs from "fs";
import * as path from "path";
import { app } from "electron";

const MAX_BYTES = 2 * 1024 * 1024;
const BACKUPS = 3;

let logPath: string | null = null;
let stream: fs.WriteStream | null = null;

/** True when the user asked for debugging. */
export function debugRequested(argv: string[] = process.argv): boolean {
  if (
    (process.env.THECORE_DEBUG || "").trim().toLowerCase() === "1" ||
    process.env.THECORE_DEBUG === "true"
  ) {
    return true;
  }
  return argv.some((a) => a === "--debug" || a === "-d");
}

/** Switch the log file on.  Returns the path, or null when off. */
export function enableDebugging(argv: string[] = process.argv): string | null {
  if (!debugRequested(argv)) return null;
  if (logPath) return logPath;

  const base = process.env.APPDATA || path.join(app.getPath("home"), ".thecore");
  let dir = path.join(base, "TheCore");
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch {
    dir = app.getPath("userData");
  }
  logPath = path.join(dir, "thecore.log");
  try {
    // Rotate the old file out of the way.
    if (fs.existsSync(logPath) && fs.statSync(logPath).size > MAX_BYTES) {
      for (let i = BACKUPS - 1; i >= 0; i--) {
        const from = i === 0 ? logPath : `${logPath}.${i}`;
        const to = `${logPath}.${i + 1}`;
        if (fs.existsSync(from)) fs.renameSync(from, to);
      }
    }
    stream = fs.createWriteStream(logPath, { flags: "a" });
    log(
      "=".repeat(68) +
        "\nTheCore debug log started (pid " +
        process.pid +
        ")" +
        "\n" +
        "=".repeat(68)
    );
  } catch {
    logPath = null;
    stream = null;
  }
  return logPath;
}

/** Write a line to the log file (a no-op when debugging is off). */
export function log(message: string): void {
  if (!stream) return;
  const stamp = new Date().toISOString().slice(11, 23);
  try {
    stream.write(`${stamp}  ${message}\n`);
  } catch {
    // The log must never break the app.
  }
}

/** Log an error with its stack. */
export function logError(where: string, err: unknown): void {
  const message = err instanceof Error ? err.stack || err.message : String(err);
  log(`ERROR in ${where}:\n${message}`);
}

/** Log how long something took. */
export function logTiming(label: string, started: number): void {
  log(`${label.padEnd(34)} ${((Date.now() - started) / 1000).toFixed(1)} ms`);
}

export function logFilePath(): string | null {
  return logPath;
}
