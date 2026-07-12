#!/usr/bin/env node
/**
 * fetch-kuaishou.mjs — standalone 快手 hot-board fetcher
 *
 * Fetches https://www.kuaishou.com/hot-board with User-Agent rotation,
 * parses window.__APOLLO_STATE__ from the HTML, extracts visionHotRank
 * items, and writes the result as a JSON array to stdout.
 *
 * No npm dependencies.  Requires Node 18+ (built-in fetch).
 *
 * Usage:
 *   node tools/fetch-kuaishou.mjs          → print JSON to stdout
 *   node tools/fetch-kuaishou.mjs 2>/dev/null  → suppress error log
 */

// ---------------------------------------------------------------------------
// User-Agent rotation — no npm package needed
// ---------------------------------------------------------------------------
const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0',
];

function randomUA() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

// ---------------------------------------------------------------------------
// HTML fetch with retry
// ---------------------------------------------------------------------------
async function fetchHTML(url, signal) {
  const headers = {
    'User-Agent': randomUA(),
    Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    Referer: 'https://www.kuaishou.com/',
    'Cache-Control': 'no-cache',
    Pragma: 'no-cache',
  };

  const resp = await fetch(url, { headers, signal });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} ${resp.statusText}`);
  }
  return await resp.text();
}

// ---------------------------------------------------------------------------
// Apollo state extraction
// ---------------------------------------------------------------------------
function extractApolloState(html) {
  // window.__APOLLO_STATE__ appears inside a <script> tag
  // Use [\s\S] to match across newlines; stop at </script>
  const re = /window\.__APOLLO_STATE__\s*=\s*([\s\S]*?)<\/script>/;
  const match = html.match(re);
  if (!match) return null;

  let raw = match[1].trim();
  // Strip trailing semicolons and whitespace
  raw = raw.replace(/;\s*$/, '');
  return JSON.parse(raw);
}

// ---------------------------------------------------------------------------
// Hot items extraction from Apollo normalized cache
// ---------------------------------------------------------------------------
function extractHotItems(state) {
  const items = [];
  const root = state?.ROOT_QUERY;
  if (!root) return items;

  // The hot-rank key is dynamic (includes query params), search by prefix
  const hotRankKey = Object.keys(root).find((k) => k.startsWith('visionHotRank'));
  if (!hotRankKey) return items;

  const rawItems = root[hotRankKey]?.items ?? [];
  if (!Array.isArray(rawItems)) return items;

  for (const entry of rawItems) {
    // name is the actual field in Apollo, but be defensive
    const title = (entry.name || entry.title || '').trim();
    if (!title) continue;

    const rawHeat = parseInt(entry.hotValue ?? entry.hot ?? 0, 10);
    const photoId = entry.photoIds ?? '';
    const poster = entry.poster ?? '';

    const link = photoId
      ? `https://www.kuaishou.com/short-video/${photoId}`
      : 'https://www.kuaishou.com/hot-board';

    items.push({
      rank: items.length + 1,
      title,
      heat: fmtHeat(rawHeat),
      raw_heat: rawHeat,
      link,
    });
  }

  return items;
}

// ---------------------------------------------------------------------------
// Heat formatter (same style as the Python version)
// ---------------------------------------------------------------------------
function fmtHeat(n) {
  if (!n || Number.isNaN(n)) return '';
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}亿`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(1)}万`;
  return String(n);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  const url = 'https://www.kuaishou.com/hot-board';
  const MAX_ATTEMPTS = 3;
  let lastError;

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    try {
      const ac = new AbortController();
      const timeout = setTimeout(() => ac.abort(), 20000);

      const html = await fetchHTML(url, ac.signal);
      clearTimeout(timeout);

      const state = extractApolloState(html);
      if (!state) {
        throw new Error('__APOLLO_STATE__ not found in page');
      }

      const items = extractHotItems(state);
      process.stdout.write(JSON.stringify(items, null, 2));
      return; // success
    } catch (err) {
      lastError = err;
      if (attempt < MAX_ATTEMPTS - 1) {
        // Brief delay before retry with a different UA
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
  }

  // All retries exhausted — emit empty array, error on stderr
  process.stderr.write(`fetch-kuaishou: ${lastError.message}\n`);
  process.stdout.write('[]');
}

main();
