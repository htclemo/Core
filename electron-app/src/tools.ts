/**
 * TheCore — tools for local models (Electron main process).
 *
 * Mirrors `thecore/ai/tools.py`: the model asks for a tool, the main process
 * runs it, and the result goes back into the conversation.
 *
 * Every path is resolved inside the project folder and may not escape it, so
 * a confused model cannot touch the rest of the machine.
 */

import * as fs from "fs";
import * as path from "path";
import { execFile } from "child_process";

const MAX_READ_BYTES = 60_000;
const MAX_LIST_ENTRIES = 200;
const COMMAND_TIMEOUT = 60_000;

export interface ToolResult {
  ok: boolean;
  content: string;
  display: string;
}

export interface ToolDefinition {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export class ToolRegistry {
  private root: string;

  constructor(root: string) {
    this.root = path.resolve(root);
  }

  /** The tool definitions in Ollama's format. */
  definitions(): ToolDefinition[] {
    return [
      {
        type: "function",
        function: {
          name: "read_file",
          description:
            "Read a text file from the project folder. " +
            "Returns the content with line numbers.",
          parameters: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path of the file, relative to the project folder.",
              },
            },
            required: ["path"],
          },
        },
      },
      {
        type: "function",
        function: {
          name: "write_file",
          description:
            "Create a file or replace its entire content. " +
            "Use this for new files and for complete rewrites.",
          parameters: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path of the file, relative to the project folder.",
              },
              content: {
                type: "string",
                description: "The full new content of the file.",
              },
            },
            required: ["path", "content"],
          },
        },
      },
      {
        type: "function",
        function: {
          name: "edit_file",
          description:
            "Replace an exact piece of text in a file. " +
            "The old text must appear exactly once.",
          parameters: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path of the file, relative to the project folder.",
              },
              old_text: {
                type: "string",
                description: "The exact text to replace.",
              },
              new_text: {
                type: "string",
                description: "The text to put in its place.",
              },
            },
            required: ["path", "old_text", "new_text"],
          },
        },
      },
      {
        type: "function",
        function: {
          name: "list_directory",
          description:
            "List the files and folders of a directory in the project folder.",
          parameters: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description:
                  "Folder to list, relative to the project folder. Empty for the root.",
              },
            },
            required: ["path"],
          },
        },
      },
      {
        type: "function",
        function: {
          name: "run_command",
          description:
            "Run a PowerShell command in the project folder and return its output.",
          parameters: {
            type: "object",
            properties: {
              command: {
                type: "string",
                description: "The PowerShell command to run.",
              },
            },
            required: ["command"],
          },
        },
      },
    ];
  }

  // ------------------------------------------------------------------ paths

  private resolve(relative: string): string {
    const cleaned = String(relative || "").trim().replace(/^"|"$/g, "");
    const target = path.resolve(
      path.isAbsolute(cleaned) ? cleaned : path.join(this.root, cleaned)
    );
    const relation = path.relative(this.root, target);
    if (relation.startsWith("..") || path.isAbsolute(relation)) {
      throw new Error(
        `'${relative}' is outside the project folder (${this.root}); that is not allowed.`
      );
    }
    return target;
  }

  private relative(target: string): string {
    const relation = path.relative(this.root, target);
    return relation ? relation.split(path.sep).join("/") : target;
  }

  // ------------------------------------------------------------------ execute

  async execute(name: string, args: Record<string, any>): Promise<ToolResult> {
    try {
      switch (name) {
        case "read_file":
          return this.readFile(args);
        case "write_file":
          return this.writeFile(args);
        case "edit_file":
          return this.editFile(args);
        case "list_directory":
          return this.listDirectory(args);
        case "run_command":
          return this.runCommand(args);
        default:
          return {
            ok: false,
            content: `Unknown tool '${name}'.`,
            display: "",
          };
      }
    } catch (err) {
      return {
        ok: false,
        content: `Tool '${name}' failed: ${
          err instanceof Error ? err.message : String(err)
        }`,
        display: "",
      };
    }
  }

  private readFile(args: Record<string, any>): ToolResult {
    const target = this.resolve(String(args.path || ""));
    if (!fs.existsSync(target)) {
      return { ok: false, content: `File not found: ${this.relative(target)}`, display: "" };
    }
    if (!fs.statSync(target).isFile()) {
      return { ok: false, content: `Not a file: ${this.relative(target)}`, display: "" };
    }
    const buffer = fs.readFileSync(target);
    const data = buffer.subarray(0, MAX_READ_BYTES);
    const text = data.toString("utf8");
    const numbered = text
      .split(/\r?\n/)
      .map((line, index) => `${String(index + 1).padStart(5)}  ${line}`)
      .join("\n");
    return {
      ok: true,
      content: numbered,
      display: `read ${this.relative(target)} (${text.length} chars)`,
    };
  }

  private writeFile(args: Record<string, any>): ToolResult {
    const target = this.resolve(String(args.path || ""));
    const content = String(args.content || "");
    const existed = fs.existsSync(target);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content, "utf8");
    const action = existed ? "updated" : "created";
    return {
      ok: true,
      content: `${action} ${this.relative(target)} (${content.length} chars)`,
      display: `wrote ${this.relative(target)}`,
    };
  }

  private editFile(args: Record<string, any>): ToolResult {
    const target = this.resolve(String(args.path || ""));
    if (!fs.existsSync(target)) {
      return { ok: false, content: `File not found: ${this.relative(target)}`, display: "" };
    }
    const text = fs.readFileSync(target, "utf8");
    const oldText = String(args.old_text || "");
    const newText = String(args.new_text || "");
    const count = text.split(oldText).length - 1;
    if (count === 0) {
      return {
        ok: false,
        content:
          `The text to replace was not found in ${this.relative(target)}. ` +
          "Read the file first and copy the text exactly.",
        display: "",
      };
    }
    if (count > 1) {
      return {
        ok: false,
        content:
          `The text to replace appears ${count} times in ${this.relative(target)}; ` +
          "include more context so it is unique.",
        display: "",
      };
    }
    fs.writeFileSync(target, text.replace(oldText, newText), "utf8");
    return {
      ok: true,
      content: `edited ${this.relative(target)}`,
      display: `edited ${this.relative(target)}`,
    };
  }

  private listDirectory(args: Record<string, any>): ToolResult {
    const target = this.resolve(String(args.path || ""));
    if (!fs.existsSync(target)) {
      return { ok: false, content: `Folder not found: ${this.relative(target)}`, display: "" };
    }
    if (!fs.statSync(target).isDirectory()) {
      return { ok: false, content: `Not a folder: ${this.relative(target)}`, display: "" };
    }
    const entries = fs
      .readdirSync(target, { withFileTypes: true })
      .sort((a, b) => {
        const aDir = a.isDirectory() ? 0 : 1;
        const bDir = b.isDirectory() ? 0 : 1;
        return aDir - bDir || a.name.toLowerCase().localeCompare(b.name.toLowerCase());
      });
    const lines = entries
      .slice(0, MAX_LIST_ENTRIES)
      .map((entry) => `${entry.name}${entry.isDirectory() ? "/" : ""}`);
    if (!lines.length) lines.push("(empty)");
    return {
      ok: true,
      content: lines.join("\n"),
      display: `listed ${this.relative(target) || "."} (${lines.length} entries)`,
    };
  }

  private runCommand(args: Record<string, any>): Promise<ToolResult> {
    const command = String(args.command || "").trim();
    if (!command) {
      return Promise.resolve({ ok: false, content: "No command given.", display: "" });
    }
    return new Promise((resolve) => {
      execFile(
        "powershell.exe",
        ["-NoProfile", "-Command", command],
        { cwd: this.root, encoding: "utf8", timeout: COMMAND_TIMEOUT, windowsHide: true },
        (err, stdout, stderr) => {
          const out = String(stdout || "").trim();
          const errText = String(stderr || "").trim();
          const parts: string[] = [];
          if (out) parts.push(out);
          if (errText) parts.push(`[stderr]\n${errText}`);
          if (!parts.length) {
            parts.push(`(no output, exit code ${err ? 1 : 0})`);
          }
          resolve({
            ok: !err,
            content: parts.join("\n"),
            display: `ran: ${command.slice(0, 60)}`,
          });
        }
      );
    });
  }
}
