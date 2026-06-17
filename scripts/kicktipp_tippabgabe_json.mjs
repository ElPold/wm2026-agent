#!/usr/bin/env node
/** Editable Kicktipp matches for one Spieltag (tippabgabe page) as JSON. */

import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentRoot =
  process.env.KICKTIPP_AGENT_ROOT ||
  path.resolve(__dirname, "..", ".kicktipp-agent");
const URL_BASE = process.env.KICKTIPP_BASE_URL || "https://www.kicktipp.de";

function writeCommunity(name) {
  const dir = path.join(os.homedir(), ".config", "kicktipp-agent");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, "config.ini");
  fs.writeFileSync(file, `[community]\nname = ${name}\n`, "utf-8");
  fs.chmodSync(file, 0o600);
}

function parseEditableMatches(html) {
  const rows = [];
  const rowRe = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  let rowMatch;
  while ((rowMatch = rowRe.exec(html)) !== null) {
    const rowHtml = rowMatch[1];
    if (!/_heimTipp/.test(rowHtml) || /nichttippbar/.test(rowHtml)) {
      continue;
    }
    const cells = [];
    const cellRe = /<td[^>]*>([\s\S]*?)<\/td>/gi;
    let cellMatch;
    while ((cellMatch = cellRe.exec(rowHtml)) !== null) {
      const text = cellMatch[1]
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      cells.push(text);
    }
    if (cells.length < 3) {
      continue;
    }
    rows.push({
      date: cells[0],
      home: cells[1],
      away: cells[2],
    });
  }
  return rows;
}

const community = process.env.KICKTIPP_COMMUNITY;
const spieltag = Number(process.argv[2] || "1");
if (!community) {
  console.error("KICKTIPP_COMMUNITY fehlt.");
  process.exit(1);
}
writeCommunity(community);

const { launchBrowser } = await import(path.join(agentRoot, "dist", "browser.js"));
const { browser, page } = await launchBrowser();

try {
  const url = `${URL_BASE}/${encodeURIComponent(community)}/tippabgabe?spieltagIndex=${spieltag}`;
  await page.goto(url);
  await page.waitForLoadState("domcontentloaded");
  const html = await page.content();
  const matches = parseEditableMatches(html);
  process.stdout.write(`${JSON.stringify(matches)}\n`);
} finally {
  await browser.close();
}
