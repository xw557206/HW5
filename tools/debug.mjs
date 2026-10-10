import { mkdirSync } from 'node:fs'
import puppeteer from 'puppeteer'

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
mkdirSync('output/screenshots', { recursive: true })

const b = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox'],
  defaultViewport: { width: 1400, height: 900 },
})
const p = await b.newPage()
const logs = []
p.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`))
p.on('pageerror', (e) => logs.push(`[pageerror] ${e}`))
p.on('requestfailed', (r) => logs.push(`[reqfail] ${r.url()} ${r.failure()?.errorText}`))
p.on('response', (r) => { if (r.url().includes('/api/')) logs.push(`[api] ${r.status()} ${r.url()}`) })

await p.goto(process.argv[2] ?? 'http://localhost:5174', { waitUntil: 'networkidle0', timeout: 45000 })
await new Promise((r) => setTimeout(r, 3000))

const info = await p.evaluate(() => ({
  title: document.title,
  rootChildren: document.getElementById('root')?.children.length ?? -1,
  tickets: document.querySelectorAll('.ticket').length,
  cards: document.querySelectorAll('.card').length,
  bodyStart: document.body.innerText.slice(0, 400),
}))
console.log(JSON.stringify(info, null, 2))
console.log('\n--- logs ---')
logs.slice(0, 25).forEach((l) => console.log(' ', l))

await p.screenshot({ path: 'output/screenshots/_debug.png', fullPage: true })
await b.close()
