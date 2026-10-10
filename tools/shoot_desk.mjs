/** Screenshot the static planning page's tabs, to check they render. */
import { mkdirSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { resolve } from 'node:path'
import puppeteer from 'puppeteer'

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
mkdirSync('output/screenshots', { recursive: true })

const b = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox'],
  defaultViewport: { width: 1400, height: 1000, deviceScaleFactor: 2 },
})
const p = await b.newPage()
const errs = []
p.on('pageerror', (e) => errs.push(String(e)))
p.on('console', (m) => m.type() === 'error' && errs.push(m.text()))

await p.goto(pathToFileURL(resolve('output/desk_tickets.html')).href, { waitUntil: 'networkidle0' })
await new Promise((r) => setTimeout(r, 900))

for (const [tab, name] of [['tab-101', 'desk-101'], ['tab-cash', 'desk-cash'], ['tab-reflect', 'desk-reflection']]) {
  await p.click(`#${tab}`)
  await new Promise((r) => setTimeout(r, 600))
  await p.screenshot({ path: `output/screenshots/${name}.png`, fullPage: true })
  const h = await p.evaluate(() => document.documentElement.scrollHeight)
  console.log(`  ${name}.png  (height ${h})`)
}

console.log(errs.length ? `errors: ${errs.slice(0, 5).join(' | ')}` : 'no console errors')
await b.close()
