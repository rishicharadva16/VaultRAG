// Smoke test against REAL VaultRAG API (FastAPI backend at http://127.0.0.1:8000)
// Tests:
// 1. Health check & CORS headers from http://localhost:5173
// 2. Login as u_karan (karan.mehta@northwind.example)
// 3. Ask Apex monthly fee as u_karan -> verify answer, citations, and verified status
// 4. Fetch first citation as u_karan -> verify passage and highlights
// 5. Login as u_asha (asha.patel@northwind.example)
// 6. Ask Apex monthly fee as u_asha -> verify refusal (refused: true, citations empty)
// 7. Fetch nonexistent citation -> verify 404 response

const BASE_URL = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function run() {
  console.log(`Starting VaultRAG smoke test against ${BASE_URL}...`);
  const results = {};

  // 1. Health check & CORS
  console.log('\n--- 1. Health & CORS Check ---');
  const healthRes = await fetch(`${BASE_URL}/health`, {
    headers: { 'Origin': 'http://localhost:5173' }
  });
  const corsHeader = healthRes.headers.get('access-control-allow-origin');
  const healthData = await healthRes.json();
  console.log(`Status: ${healthRes.status}`);
  console.log(`CORS Access-Control-Allow-Origin: ${corsHeader}`);
  console.log(`Health:`, JSON.stringify(healthData));
  if (corsHeader !== 'http://localhost:5173') {
    throw new Error(`Expected CORS header 'http://localhost:5173', got '${corsHeader}'`);
  }
  results.health = { status: healthRes.status, cors: corsHeader, data: healthData };

  // 2. Login as u_karan
  console.log('\n--- 2. Login as u_karan ---');
  const karanLoginRes = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'karan.shah@northwind.example',
      password: 'changeme123'
    })
  });
  if (!karanLoginRes.ok) {
    throw new Error(`Login u_karan failed: ${karanLoginRes.status} ${await karanLoginRes.text()}`);
  }
  const karanTokenData = await karanLoginRes.json();
  const karanToken = karanTokenData.access_token;
  console.log(`u_karan logged in successfully. Token received (length ${karanToken.length}).`);

  // Verify /auth/me for karan
  const karanMeRes = await fetch(`${BASE_URL}/auth/me`, {
    headers: { 'Authorization': `Bearer ${karanToken}` }
  });
  const karanMe = await karanMeRes.json();
  console.log(`u_karan profile:`, JSON.stringify(karanMe));
  results.karanProfile = karanMe;

  // 3. Ask Apex monthly fee as u_karan
  console.log('\n--- 3. Ask Apex Monthly Fee as u_karan ---');
  const question = 'What is the monthly service fee under the Apex contract?';
  const karanAskRes = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${karanToken}`
    },
    body: JSON.stringify({ question })
  });
  if (!karanAskRes.ok) {
    throw new Error(`Ask u_karan failed: ${karanAskRes.status} ${await karanAskRes.text()}`);
  }
  const karanAnswer = await karanAskRes.json();
  console.log(`u_karan Ask response:`);
  console.log(`- Refused: ${karanAnswer.refused}`);
  console.log(`- Answer: ${karanAnswer.answer}`);
  console.log(`- Verified: ${karanAnswer.verified}`);
  console.log(`- Citations count: ${karanAnswer.citations?.length}`);
  results.karanAnswer = karanAnswer;

  if (karanAnswer.refused) {
    throw new Error(`Expected u_karan to receive an answer, but was refused: ${karanAnswer.answer}`);
  }
  if (!karanAnswer.citations || karanAnswer.citations.length === 0) {
    throw new Error(`Expected citations for u_karan, but got 0`);
  }

  // 4. Fetch first citation as u_karan
  const firstCitation = karanAnswer.citations[0];
  console.log(`\n--- 4. Fetch First Citation: ${firstCitation.chunk_id} ---`);
  const encodedChunkId = encodeURIComponent(firstCitation.chunk_id);
  const citationRes = await fetch(`${BASE_URL}/citation/${encodedChunkId}`, {
    headers: { 'Authorization': `Bearer ${karanToken}` }
  });
  if (!citationRes.ok) {
    throw new Error(`Citation fetch failed: ${citationRes.status} ${await citationRes.text()}`);
  }
  const citationData = await citationRes.json();
  console.log(`Citation fetched successfully:`);
  console.log(`- File: ${citationData.file}, Page: ${citationData.page}`);
  console.log(`- Text preview: ${citationData.text?.slice(0, 120)}...`);
  console.log(`- Highlights from /ask citation:`, JSON.stringify(firstCitation.highlights));
  console.log(`- Highlight text from /ask citation: "${firstCitation.highlight_text}"`);
  results.firstCitation = { ...citationData, highlights: firstCitation.highlights, highlight_text: firstCitation.highlight_text };
  if (!firstCitation.highlights || firstCitation.highlights.length === 0) {
    throw new Error(`Expected highlights on firstCitation, got: ${JSON.stringify(firstCitation.highlights)}`);
  }

  // 5. Login as u_asha
  console.log('\n--- 5. Login as u_asha ---');
  const ashaLoginRes = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'asha.patel@northwind.example',
      password: 'changeme123'
    })
  });
  if (!ashaLoginRes.ok) {
    throw new Error(`Login u_asha failed: ${ashaLoginRes.status} ${await ashaLoginRes.text()}`);
  }
  const ashaTokenData = await ashaLoginRes.json();
  const ashaToken = ashaTokenData.access_token;
  console.log(`u_asha logged in successfully. Token received.`);

  // 6. Ask Apex monthly fee as u_asha (should be refused)
  console.log('\n--- 6. Ask Apex Monthly Fee as u_asha (Refusal Expected) ---');
  const ashaAskRes = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${ashaToken}`
    },
    body: JSON.stringify({ question })
  });
  if (!ashaAskRes.ok) {
    throw new Error(`Ask u_asha failed: ${ashaAskRes.status} ${await ashaAskRes.text()}`);
  }
  const ashaAnswer = await ashaAskRes.json();
  console.log(`u_asha Ask response:`);
  console.log(`- Refused: ${ashaAnswer.refused}`);
  console.log(`- Answer: ${ashaAnswer.answer}`);
  console.log(`- Citations:`, JSON.stringify(ashaAnswer.citations));
  results.ashaAnswer = ashaAnswer;

  if (!ashaAnswer.refused) {
    throw new Error(`Expected u_asha to be refused, but refused was false!`);
  }
  if (ashaAnswer.citations && ashaAnswer.citations.length > 0) {
    throw new Error(`Expected u_asha citations to be empty, but got ${ashaAnswer.citations.length}`);
  }

  // 7. Request nonexistent citation -> confirm 404
  console.log('\n--- 7. Request Nonexistent Citation ---');
  const notFoundRes = await fetch(`${BASE_URL}/citation/nonexistent_chunk_id_999`, {
    headers: { 'Authorization': `Bearer ${karanToken}` }
  });
  console.log(`Nonexistent citation status: ${notFoundRes.status}`);
  results.notFoundStatus = notFoundRes.status;
  if (notFoundRes.status !== 404) {
    throw new Error(`Expected status 404 for nonexistent citation, got ${notFoundRes.status}`);
  }

  console.log('\n========================================');
  console.log('ALL SMOKE TEST CHECKS PASSED SUCCESSFULLY!');
  console.log('========================================');
}

run().catch((err) => {
  console.error('Smoke test failed:', err);
  process.exit(1);
});
