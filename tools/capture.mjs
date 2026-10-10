/**
 * Capture real screenshots of the running React dashboard.
 *
 * Drives the actual page in headless Chrome — selecting each ticket and
 * photographing what the dashboard genuinely shows. Nothing is recreated or
 * mocked up; if the dashboard is wrong, the screenshot will be wrong too,
 * which is the point.
 *
 *   node tools/capture.mjs [frontendUrl] [outDir]
 *
 * Uses the system Chrome, because puppeteer's own Chromium download is
 * blocked in this environment.
 */

import { mkdirSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import puppeteer from 'puppeteer'

const URL = process.argv[2] ?? 'http://localhost:5174'
const OUT = process.argv[3] ?? 'output/screenshots'

const CHROME = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].find((p) => existsSync(p))

if (!CHROME) {
  console.error('No system Chrome or Edge found.')
  process.exit(1)
}

mkdirSync(OUT, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
  defaultViewport: { width: 1480, height: 1000, deviceScaleFactor: 2 },
})

const page = await browser.newPage()
const problems = []
page.on('console', (m) => m.type() === 'error' && problems.push(m.text()))
page.on('pageerror', (e) => problems.push(String(e)))

console.log(`opening ${URL}`)
await page.goto(URL, { waitUntil: 'networkidle0', timeout: 60000 })

// Wait for real data rather than a fixed sleep.
await page.waitForFunction(
  () => document.querySelectorAll('.ticket').length >= 3,
  { timeout: 30000 },
)
await new Promise((r) => setTimeout(r, 1200)) // let entry animations settle

const shots = []

async function shoot(name, note) {
  const file = join(OUT, `${name}.png`)
  await page.screenshot({ path: file, fullPage: true })
  const { w, h } = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    h: document.documentElement.scrollHeight,
  }))
  shots.push({ name, file: `screenshots/${name}.png`, note, width: w, height: h })
  console.log(`  captured ${name}.png  (${w}x${h})`)
}

// 1. The whole desk, nothing selected.
await shoot('overview', 'The operations desk as it loads: all three tickets, the approvals queue, the cash position and the full agent timeline.')

// 2. Each ticket selected, so its own activity is isolated.
const ids = await page.$$eval('.ticket .ticket-id', (els) =>
  els.map((e) => Number(e.textContent.replace(/\D/g, ''))),
)
for (const id of ids) {
  const idx = ids.indexOf(id)
  const cards = await page.$$('.ticket')
  await cards[idx].click()
  await new Promise((r) => setTimeout(r, 900))
  await shoot(`ticket-${id}`, `Ticket ${id} selected — the timeline filters to this ticket's agent activity.`)
  await cards[idx].click() // deselect
  await new Promise((r) => setTimeout(r, 300))
}

// 3. Mobile, to show the responsive layout is real.
await page.setViewport({ width: 420, height: 950, deviceScaleFactor: 2 })
await new Promise((r) => setTimeout(r, 900))
await shoot('responsive-mobile', 'The same desk at 420px — the two columns collapse to one, keeping tickets above approvals above the timeline.')

console.log(problems.length ? `\nconsole errors: ${problems.length}` : '\nno console errors')
problems.slice(0, 5).forEach((p) => console.log('  ' + p))

await browser.close()

console.log('\n' + JSON.stringify({ shots, console_errors: problems }, null, 2))
