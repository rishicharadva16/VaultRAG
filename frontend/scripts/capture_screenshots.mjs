import { chromium } from 'playwright-core';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const SCREENSHOT_DIR = path.resolve(__dirname, '..', 'docs', 'screenshots');
const ROOT_SCREENSHOT_DIR = path.resolve(__dirname, '..', '..', 'docs', 'screenshots');
const BASE_URL = 'http://127.0.0.1:5173';

async function main() {
  console.log('Launching Edge for UI verification and Step 4c screenshots...');
  const browser = await chromium.launch({
    executablePath: EDGE_PATH,
    headless: true
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 }
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
    console.log('Logging in as Karan Shah (finance_admin)...');
    await page.click('button:has-text("Karan Shah")');
    await page.waitForURL('**/chat', { timeout: 10000 });
    await page.waitForSelector('textarea[placeholder*="Ask a question"]');

    // 3. Ask question: Apex monthly fee
    console.log('Submitting question: Apex monthly fee...');
    const apexExample = page.locator('button:has-text("Apex monthly service fee")');
    if (await apexExample.isVisible()) {
      await apexExample.click();
    } else {
      await page.fill('textarea', 'What is the monthly service fee under the Apex contract?');
      await page.click('button:has-text("Send")');
    }

    // Wait for the AnswerCard to appear
    console.log('Waiting for answer...');
    await page.waitForSelector('[data-testid="answer-card"]', { timeout: 60000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'chat_answer.png') });
    console.log('Saved chat_answer.png');

    // 4. Open Citation Panel for PDF source viewer with highlight overlay
    console.log('Opening citation panel for Apex fee (PDF viewer with highlight)...');
    const citationChip = page.locator('button:has-text("[1]")').first();
    await citationChip.click();
    await page.waitForSelector('[data-testid="citation-panel"]', { timeout: 15000 });
    // Wait for highlight rectangle overlay to be rendered
    await page.waitForSelector('[data-testid="highlight-rect"]', { timeout: 15000 });
    await page.waitForTimeout(2000); // allow pulse animation and zoom positioning
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'step4c_pdf_highlight.png') });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'citation_panel.png') });
    console.log('Saved step4c_pdf_highlight.png and citation_panel.png');

    // 5. Switch to Meera Iyer for DB row card verification
    console.log('Switching user to Meera Iyer (hr_admin)...');
    await page.click('button:has-text("Switch demo user")');
    await page.click('button:has-text("Meera Iyer")');
    await page.waitForTimeout(1500);

    // Ask DB question: Asha CTC / salary
    console.log('Submitting question: Asha Patel CTC / salary...');
    await page.fill('textarea', "What is Asha Patel's salary and role?");
    await page.click('button:has-text("Send")');

    // Wait for AnswerCard
    await page.waitForSelector('[data-testid="answer-card"]', { timeout: 60000 });
    await page.waitForTimeout(1000);

    // Open citation chip for DB record
    console.log('Opening citation panel for DB record card...');
    const dbCitationChip = page.locator('button:has-text("[1]")').first();
    await dbCitationChip.click();
    await page.waitForSelector('[data-testid="citation-panel"]', { timeout: 15000 });
    await page.waitForSelector('[data-testid="db-row-card"]', { timeout: 15000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'step4c_db_row.png') });
    console.log('Saved step4c_db_row.png');

    // 6. Switch to Asha Patel (demo switch) to verify refusal on Apex contract
    console.log('Switching user to Asha Patel...');
    await page.click('button:has-text("Switch demo user")');
    await page.click('button:has-text("Asha Patel")');
    await page.waitForTimeout(1500);

    // Ask Apex question as Asha (expecting refusal)
    console.log('Asking Apex question as Asha Patel (expecting refusal)...');
    await page.fill('textarea', 'What is the monthly service fee under the Apex contract?');
    await page.click('button:has-text("Send")');

    // Wait for RefusalNotice
    await page.waitForSelector('[data-testid="refusal-notice"]', { timeout: 60000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'refusal.png') });
    console.log('Saved refusal.png');

    // ── Part 2 Screenshots ──

    // 7. My Documents Page
    console.log('Navigating to My Documents page...');
    const docNav = page.locator('[data-testid="nav-documents"]');
    if (await docNav.isVisible()) {
      await docNav.click();
    } else {
      await page.goto(`${BASE_URL}/documents`, { waitUntil: 'networkidle' });
    }
    await page.waitForSelector('[data-testid="tab-my-uploads"]', { timeout: 10000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'my_documents.png') });
    console.log('Saved my_documents.png');

    // 8. Share Dialog Modal
    console.log('Opening Share Dialog on first available document...');
    const shareBtn = page.locator('[data-testid^="share-doc-button-"]').first();
    if (await shareBtn.isVisible()) {
      await shareBtn.click();
      await page.waitForSelector('[data-testid="share-people-search"]', { timeout: 10000 });
      await page.waitForTimeout(1000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'share_dialog.png') });
      console.log('Saved share_dialog.png');

      // Close share dialog
      const closeBtn = page.locator('button:has-text("Done")').first();
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
      }
    } else {
      console.log('No share button visible on current user, skipping share_dialog.png');
    }

    // 9. Admin Dashboard Page
    console.log('Switching user to Platform Admin...');
    await page.click('button:has-text("Switch demo user")');
    await page.click('button:has-text("Platform Admin")');
    await page.waitForTimeout(1500);

    console.log('Navigating to Admin Dashboard...');
    const adminNav = page.locator('[data-testid="nav-admin"]');
    if (await adminNav.isVisible()) {
      await adminNav.click();
    } else {
      await page.goto(`${BASE_URL}/admin`, { waitUntil: 'networkidle' });
    }
    await page.waitForSelector('[data-testid="kpi-total-asks"]', { timeout: 15000 });
    await page.waitForTimeout(2000); // Allow SVG chart and table rendering
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'admin_dashboard.png') });
    console.log('Saved admin_dashboard.png');

    // Copy all screenshots to ROOT_SCREENSHOT_DIR as well
    const fs = await import('fs');
    if (fs.existsSync(SCREENSHOT_DIR)) {
      if (!fs.existsSync(ROOT_SCREENSHOT_DIR)) {
        fs.mkdirSync(ROOT_SCREENSHOT_DIR, { recursive: true });
      }
      const files = fs.readdirSync(SCREENSHOT_DIR);
      for (const f of files) {
        if (f.endsWith('.png')) {
          fs.copyFileSync(path.join(SCREENSHOT_DIR, f), path.join(ROOT_SCREENSHOT_DIR, f));
        }
      }
      console.log(`Synced ${files.length} screenshots to root docs/screenshots.`);
    }

    console.log('All screenshots captured successfully!');
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error('Failed to capture screenshots:', err);
  process.exit(1);
});
