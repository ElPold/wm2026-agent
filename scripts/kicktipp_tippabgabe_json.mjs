#!/usr/bin/env node
/** Editable Kicktipp matches for one Spieltag (tippabgabe page) as JSON. */

import { createRequire } from "module";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentRoot =
  process.env.KICKTIPP_AGENT_ROOT ||
  path.resolve(__dirname, "..", ".kicktipp-agent");
const URL_BASE = process.env.KICKTIPP_BASE_URL || "https://www.kicktipp.de";
const require = createRequire(import.meta.url);
const cheerio = require(path.join(agentRoot, "node_modules", "cheerio"));

function writeCommunity(name) {
  const dir = path.join(os.homedir(), ".config", "kicktipp-agent");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, "config.ini");
  fs.writeFileSync(file, `[community]\nname = ${name}\n`, "utf-8");
  fs.chmodSync(file, 0o600);
}

function parseEditableMatches(html) {
  const $ = cheerio.load(html);
  const rows = [];
  $("#kicktipp-content tbody tr").each((_, tr) => {
    const cols = $(tr).find("td");
    if (cols.length < 4) {
      return;
    }
    const betTd = $(cols[3]);
    if (betTd.hasClass("nichttippbar")) {
      return;
    }
    const heimInput = betTd.find('input[id$="_heimTipp"]');
    const gastInput = betTd.find('input[id$="_gastTipp"]');
    if (!heimInput.length || !gastInput.length) {
      return;
    }
    rows.push({
      date: $(cols[0]).text().trim(),
      home: $(cols[1]).text().trim(),
      away: $(cols[2]).text().trim(),
    });
  });
  return rows;
}

const community = process.env.KICKTIPP_COMMUNITY;
const spieltag = Number(process.argv[2] || "1");
if (!community) {
  console.error("KICKTIPP_COMMUNITY fehlt.");
  process.exit(1);
}
writeCommunity(community);

const browserModule = path.join(agentRoot, "dist", "browser.js");
const { launchBrowser, dismissConsent } = await import(pathToFileURL(browserModule).href);
const { browser, page } = await launchBrowser();

try {
  const url = `${URL_BASE}/${encodeURIComponent(community)}/tippabgabe?spieltagIndex=${spieltag}`;
  await page.goto(url);
  await page.waitForLoadState("domcontentloaded");
  await dismissConsent(page);
  const html = await page.content();
  const matches = parseEditableMatches(html);
  process.stdout.write(`${JSON.stringify(matches)}\n`);
} finally {
  await browser.close();
}
