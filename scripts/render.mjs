// Renders the skyline scene frame by frame in headless Chrome (software WebGL works on CI).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer';

const theme = process.argv[2] || 'dark';
const outDir = process.argv[3] || `frames_${theme}`;
const root = process.cwd();
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;

const args = ['--no-sandbox', '--ignore-gpu-blocklist', '--enable-webgl'];
args.push(process.env.USE_GPU ? '--use-angle=metal' : '--use-angle=swiftshader', ...(process.env.USE_GPU ? [] : ['--enable-unsafe-swiftshader']));
const browser = await puppeteer.launch({ headless: 'new', executablePath: process.env.CHROME_PATH || undefined, args, protocolTimeout: 0 });
const page = await browser.newPage();
page.on('pageerror', e => { console.error('[page error]', e.message); process.exitCode = 1; });
await page.goto(`http://localhost:${port}/web/scene.html?theme=${theme}`);
await page.waitForFunction('window.setup', { timeout: 120000 });
const { frames } = await page.evaluate('window.setup()');
const n = Math.min(frames, Number(process.env.MAXF || frames));
fs.mkdirSync(outDir, { recursive: true });
const t0 = Date.now();
for (let i = 0; i < n; i++) {
  const d = await page.evaluate(i => window.frame(i), i);
  fs.writeFileSync(path.join(outDir, String(i).padStart(4, '0') + '.png'), Buffer.from(d.split(',')[1], 'base64'));
  if (i % 30 === 0) console.log(`${theme}: frame ${i}/${n} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
await browser.close(); server.close();
