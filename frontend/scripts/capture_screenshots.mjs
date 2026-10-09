import { chromium } from 'playwright-core';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const SCREENSHOT_DIR = path.resolve(__dirname, '..', 'docs', 'screenshots');
const BASE_URL = 'http://localhost:5173';

async function main() {
  console.log('Launching Edge for UI verification and screenshots...');
  const browser = await chromium.launch({
    executablePath: EDGE_PATH,
    headless: true
  });

  const context = await browser.newContext({
    viewport: { width: 1366, height: 850 }
  });
  const page = await context.newPage();

  try {
    // 1. Login Page
    console.log('Navigating to login page...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.waitForSelector('text=Sign in to VaultRAG');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login.png') });
    console.log('Saved login.png');

    // 2. Click Karan Shah quick login chip
    console.log('Logging in as Karan Shah...');
    await page.click('button:has-text("Karan Shah")');
    await page.waitForURL('**/chat', { timeout: 10000 });
    await page.waitForSelector('textarea[placeholder*="Ask a question"]');

    // 3. Ask question: click the Apex example question
    console.log('Submitting question: Apex monthly fee...');
    const apexExample = page.locator('button:has-text("Apex monthly service fee")');
    if (await apexExample.isVisible()) {
      await apexExample.click();
    } else {
      await page.fill('textarea', 'What is the monthly service fee under the Apex contract?');
      await page.click('button:has-text("Send")');
    }

    // Wait for the AnswerCard to appear (real LLM inference takes ~5-15s)
    console.log('Waiting for answer...');
    await page.waitForSelector('[data-testid="answer-card"]', { timeout: 45000 });
    await page.waitForTimeout(1000); // allow layout transition
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'chat_answer.png') });
    console.log('Saved chat_answer.png');

    // 4. Open Citation Panel
    console.log('Opening citation panel...');
    const citationChip = page.locator('button:has-text("[1]")').first();
    await citationChip.click();
    await page.waitForSelector('[data-testid="citation-panel"]', { timeout: 10000 });
    await page.waitForSelector('mark', { timeout: 10000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'citation_panel.png') });
    console.log('Saved citation_panel.png');

    // 5. Switch to Asha Patel (demo switch)
    console.log('Switching user to Asha Patel...');
    await page.click('button:has-text("Switch demo user")');
    await page.click('button:has-text("Asha Patel")');
    await page.waitForTimeout(1500);

    // Ask the same question as Asha
    console.log('Asking Apex question as Asha Patel (expecting refusal)...');
    await page.fill('textarea', 'What is the monthly service fee under the Apex contract?');
    await page.click('button:has-text("Send")');

    // Wait for RefusalNotice
    await page.waitForSelector('[data-testid="refusal-notice"]', { timeout: 45000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'refusal.png') });
    console.log('Saved refusal.png');

    console.log('All screenshots captured successfully!');
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error('Failed to capture screenshots:', err);
  process.exit(1);
});
