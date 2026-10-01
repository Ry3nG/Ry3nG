// Fetches the contribution calendar (last year) and the weekday x hour commit clock.
// Needs GH_TOKEN. A PAT with `repo` + `read:user` also counts private repositories
// (only aggregate counts and timestamps are used; no repo names ever leave this script).
import fs from 'node:fs';

const TOKEN = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
const LOGIN = process.env.GH_LOGIN || process.env.GITHUB_REPOSITORY_OWNER;
const TZ = Number(process.env.TZ_OFFSET ?? 8);            // hours added to UTC commit times
if (!TOKEN || !LOGIN) { console.error('GH_TOKEN and GH_LOGIN are required'); process.exit(1); }

async function gql(query, variables = {}, tries = 5) {
  for (let i = 0; i < tries; i++) {
    const r = await fetch('https://api.github.com/graphql', {
      method: 'POST', headers: { Authorization: `bearer ${TOKEN}`, 'Content-Type': 'application/json', 'User-Agent': 'profile-skyline' },
      body: JSON.stringify({ query, variables }),
    });
    if (r.ok) { const j = await r.json(); if (!j.errors) return j.data; if (i === tries - 1) throw new Error(JSON.stringify(j.errors)); }
    await new Promise(res => setTimeout(res, 1500 * (i + 1)));
  }
  throw new Error('GraphQL request failed');
}

// 1) the contribution graph (same data GitHub shows on the profile)
const cal = await gql(`query($l:String!){user(login:$l){id contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}`, { l: LOGIN });
const uid = cal.user.id;
const days = [];
for (const w of cal.user.contributionsCollection.contributionCalendar.weeks) for (const d of w.contributionDays) days.push([d.date, 0, d.contributionCount]);

// 2) every commit timestamp of the user across owned repositories -> weekday x hour
const clock = Array.from({ length: 7 }, () => Array(24).fill(0));
let repos = [], cursor = null;
for (;;) {
  const d = await gql(`query($l:String!,$c:String){user(login:$l){repositories(first:50,after:$c,ownerAffiliations:OWNER){pageInfo{hasNextPage endCursor} nodes{name defaultBranchRef{name}}}}}`, { l: LOGIN, c: cursor });
  const r = d.user.repositories; repos.push(...r.nodes.filter(n => n.defaultBranchRef));
  if (!r.pageInfo.hasNextPage) break; cursor = r.pageInfo.endCursor;
}
let commits = 0;
for (const repo of repos) {
  let c = null;
  for (;;) {
    const d = await gql(`query($o:String!,$n:String!,$a:ID!,$c:String){repository(owner:$o,name:$n){defaultBranchRef{target{...on Commit{history(first:100,after:$c,author:{id:$a}){pageInfo{hasNextPage endCursor} nodes{committedDate}}}}}}}`, { o: LOGIN, n: repo.name, a: uid, c });
    const h = d.repository?.defaultBranchRef?.target?.history; if (!h) break;
    for (const n of h.nodes) {
      const t = new Date(new Date(n.committedDate).getTime() + TZ * 3600e3);
      clock[t.getUTCDay()][t.getUTCHours()]++; commits++;
    }
    if (!h.pageInfo.hasNextPage) break; c = h.pageInfo.endCursor;
  }
}
fs.writeFileSync('web/data.json', JSON.stringify({ days }));
fs.writeFileSync('web/clock.json', JSON.stringify(clock));
console.log(`days=${days.length} contributions=${days.reduce((a, d) => a + d[2], 0)} repos=${repos.length} commits=${commits}`);
