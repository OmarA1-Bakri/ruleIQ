#!/usr/bin/env node
/**
 * Iron-Fist static scanner:
 * - Allows only tokens/colors from _index_ops/quality_gate/style_rules.json
 * - Flags inline hex colors not present in tokens
 * - Flags box-shadow values not present in tokens
 *
 * Exit non-zero on any FAIL; prints JSON and MD summary alongside.
 */

import fs from "node:fs";
import path from "node:path";
// eslint-disable-next-line no-unused-vars
import { fileURLToPath as _fileURLToPath } from "node:url";
import { glob } from "glob";

const cwd = process.cwd();
const rulesPath = path.resolve(cwd, "_index_ops/quality_gate/style_rules.json");
const outDir = path.resolve(cwd, "_index_ops/quality_gate");
const reportJson = path.join(outDir, "report.json");
const reportMd = path.join(outDir, "report.md");

function loadRules() {
  const raw = fs.readFileSync(rulesPath, "utf8");
  return JSON.parse(raw);
}

async function collectFiles() {
  // Scan UI primitives + navigation, as initial surface
  const patterns = [
    "components/ui/**/*.tsx",
    "components/navigation/**/*.tsx",
    "app/(requirements)/**/*.tsx"
  ];
  const files = new Set();
  for (const pat of patterns) {
    const matches = await glob(pat, { cwd });
    for (const f of matches) {
      files.add(path.resolve(cwd, f));
    }
  }
  return Array.from(files);
}

function scan(files, rules) {
  const allowedHex = new Set(
    Object.values(rules.colors).map((v) => v.toLowerCase())
  );
  const allowedShadows = new Set(
    Object.values(rules.shadows).map((v) => v.replace(/\s+/g, " "))
  );

  const findings = [];
  for (const file of files) {
    const src = fs.readFileSync(file, "utf8");

    // 1) Inline hex colors (JSX, CSS-in-JS, or strings)
    const hexMatches = src.match(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})/g) || [];
    for (const hex of hexMatches) {
      const hexLower = hex.toLowerCase();
      if (!allowedHex.has(hexLower)) {
        findings.push({
          file,
          rule: "no-untokenized-hex",
          message: `Found inline color ${hex} not in style_rules.json`,
          severity: "FAIL"
        });
      }
    }

    // 1a) Tailwind arbitrary colors like bg-[#0f0f0f] or from-[#123456]
    const twArbitrary = src.match(/(?:bg|text|from|to|via)-\[#[0-9a-fA-F]{3,6}\]/g) || [];
    for (const cls of twArbitrary) {
      const hex = cls.match(/#[0-9a-fA-F]{3,6}/)?.[0]?.toLowerCase();
      if (hex && !allowedHex.has(hex)) {
        findings.push({
          file,
          rule: "no-untokenized-tailwind-arbitrary",
          message: `Tailwind arbitrary color ${cls} not in style_rules.json`,
          severity: "FAIL"
        });
      }
    }

    // 2) Box-shadow strings (very naive heuristic)
    const shadowMatches = src.match(/box-shadow:\s*[^;]+;/g) || [];
    for (const m of shadowMatches) {
      const val = m.replace(/^box-shadow:\s*/, "").replace(/;$/, "").replace(/\s+/g, " ");
      if (!allowedShadows.has(val)) {
        findings.push({
          file,
          rule: "no-untokenized-shadow",
          message: `Box-shadow not mapped to token: ${val}`,
          severity: "WARN"
        });
      }
    }
  }

  const status = findings.some(f => f.severity === "FAIL") ? "FAIL" : (findings.length ? "WARN" : "PASS");
  return { status, findings };
}

function writeReports(result) {
  fs.writeFileSync(reportJson, JSON.stringify(result, null, 2));
  const md = [
    `# Quality Gate Report`,
    `\n**Status:** ${result.status}\n`,
    `## Findings (${result.findings.length})`,
    ...result.findings.map(f => `- [${f.severity}] ${f.rule}: ${f.message} (in ${path.relative(cwd, f.file)})`)
  ].join("\n");
  fs.writeFileSync(reportMd, md);
}

(async function main() {
  const rules = loadRules();
  const files = await collectFiles();
  const result = scan(files, rules);
  writeReports(result);
  if (result.status === "FAIL") process.exit(1);
  if (result.status === "WARN") process.exit(0); // allow proceed but flagged
  process.exit(0);
})();
