#!/usr/bin/env node
/** Dump Kicktipp schedule rows as JSON (uses kicktipp-agent browser + fetchSchedule). */

import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentRoot = process.env.KICKTIPP_AGENT_ROOT
  || path.resolve(__dirname, "..", ".kicktipp-agent");

function writeCommunity(name) {
  const dir = path.join(os.homedir(), ".config", "kicktipp-agent");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, "config.ini");
  fs.writeFileSync(file, `[community]\nname = ${name}\n`, "utf-8");
  fs.chmodSync(file, 0o600);
}

function parseMatchdayRange(value) {
  if (value.includes("-")) {
    const [start, end] = value.split("-", 2).map((part) => Number(part.trim()));
    const days = [];
    for (let day = start; day <= end; day += 1) {
      days.push(day);
    }
    return days;
  }
  return [Number(value)];
}

const community = process.env.KICKTIPP_COMMUNITY;
if (!community) {
  console.error("KICKTIPP_COMMUNITY fehlt.");
  process.exit(1);
}
writeCommunity(community);

const matchdays = parseMatchdayRange(process.argv[2] || "1-18");

const { launchBrowser } = await import(path.join(agentRoot, "dist", "browser.js"));
const { fetchSchedule } = await import(path.join(agentRoot, "dist", "core.js"));

const { browser, page } = await launchBrowser();
const rows = [];
const seen = new Set();

try {
  for (const matchday of matchdays) {
    const { title, matches } = await fetchSchedule(page, community, matchday);
    for (const match of matches) {
      const key = `${match.date}|${match.home}|${match.away}`;
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      rows.push({
        date: match.date,
        home: match.home,
        away: match.away,
        result: match.result,
        matchday,
        page_title: title,
      });
    }
  }
  process.stdout.write(`${JSON.stringify(rows)}\n`);
} finally {
  await browser.close();
}
