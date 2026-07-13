#!/usr/bin/env node
/**
 * fetch-kuaishou.mjs — 快手热榜采集 (GraphQL API)
 *
 * Calls https://www.kuaishou.com/graphql with visionHotRank query.
 * No HTML scraping, no __APOLLO_STATE__ dependency.
 *
 * Usage:
 *   node tools/fetch-kuaishou.mjs          → JSON to stdout
 *   node tools/fetch-kuaishou.mjs 2>/dev/null  → suppress error log
 */

const GRAPHQL_URL = 'https://www.kuaishou.com/graphql';
const QUERY = {
  operationName: 'visionHotRank',
  variables: {},
  query: `query visionHotRank { visionHotRank { items { id name hotValue poster } } }`,
};

async function main() {
  try {
    const resp = await fetch(GRAPHQL_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Referer': 'https://www.kuaishou.com/',
      },
      body: JSON.stringify(QUERY),
      signal: AbortSignal.timeout(15000),
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }

    const json = await resp.json();
    const items = json?.data?.visionHotRank?.items ?? [];

    const result = items
      .filter(item => (item.name || '').trim())
      .map((item, i) => ({
        rank: i + 1,
        title: item.name.trim(),
        heat: item.hotValue || '',
        raw_heat: 0,
        link: `https://www.kuaishou.com/hot-board`,
      }));

    process.stdout.write(JSON.stringify(result, null, 2));
  } catch (err) {
    process.stderr.write(`fetch-kuaishou: ${err.message}\n`);
    process.stdout.write('[]');
  }
}

main();
