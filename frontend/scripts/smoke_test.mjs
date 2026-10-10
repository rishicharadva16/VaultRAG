// Smoke test against REAL VaultRAG API (FastAPI backend at http://127.0.0.1:8000)
// Tests:
// 1. Health check & CORS headers from http://localhost:5173
// 2. Login as u_karan (karan.mehta@northwind.example)
// 3. Ask Apex monthly fee as u_karan -> verify answer, citations, and verified status
// 4. Fetch first citation as u_karan -> verify passage and highlights
// 5. Login as u_asha (asha.patel@northwind.example)
// 6. Ask Apex monthly fee as u_asha -> verify refusal (refused: true, citations empty)
// 7. Fetch nonexistent citation -> verify 404 response

import { execSync } from 'child_process';

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

  // ── Step 6 & Frontend Part 2: Document Lifecycle & Sharing ──

  console.log('\n--- 8. Asha Uploads Generated PDF ---');
  const salt = Date.now().toString(36);
  const pythonCmd = `d:\\VaultRAG\\.venv\\Scripts\\python.exe -c "import pymupdf; doc = pymupdf.open(); p = doc.new_page(); p.insert_text((50, 72), 'Project Falcon secret budget is 450,000 USD for code ${salt}.'); print(doc.tobytes().hex())"`;
  const pdfHex = execSync(pythonCmd).toString().trim();
  const pdfBuffer = Buffer.from(pdfHex, 'hex');

  const uploadForm = new FormData();
  const pdfBlob = new Blob([pdfBuffer], { type: 'application/pdf' });
  uploadForm.append('file', pdfBlob, `falcon_budget_${salt}.pdf`);

  const uploadRes = await fetch(`${BASE_URL}/documents`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${ashaToken}` },
    body: uploadForm
  });

  if (uploadRes.status !== 202 && uploadRes.status !== 200) {
    throw new Error(`Upload failed with status ${uploadRes.status}: ${await uploadRes.text()}`);
  }
  const uploadData = await uploadRes.json();
  const docId = uploadData.id;
  console.log(`Document uploaded with id: ${docId}, initial status: ${uploadData.status}`);

  // Wait for processing to complete (ready)
  console.log('Waiting for document to reach ready state...');
  let isReady = false;
  for (let attempt = 0; attempt < 30; attempt++) {
    const checkRes = await fetch(`${BASE_URL}/documents/${docId}`, {
      headers: { 'Authorization': `Bearer ${ashaToken}` }
    });
    if (checkRes.ok) {
      const docDetail = await checkRes.json();
      if (docDetail.status === 'ready') {
        isReady = true;
        console.log(`Document reached ready state in ${attempt * 500}ms!`);
        break;
      }
      if (docDetail.status === 'failed') {
        throw new Error(`Document ingestion failed with reason: ${docDetail.reason_code}`);
      }
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  if (!isReady) {
    throw new Error(`Document ${docId} timed out waiting for ready state.`);
  }

  // 9. Asha asks about the document
  console.log('\n--- 9. Asha Asks About Uploaded Document ---');
  const falconQuestion = `What is the secret budget for Project Falcon code ${salt}?`;
  const ashaDocAskRes = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${ashaToken}`
    },
    body: JSON.stringify({
      question: falconQuestion,
      source_ids: [docId]
    })
  });
  if (!ashaDocAskRes.ok) {
    throw new Error(`Asha ask failed: ${ashaDocAskRes.status} ${await ashaDocAskRes.text()}`);
  }
  const ashaDocAnswer = await ashaDocAskRes.json();
  console.log(`Asha answer:`, ashaDocAnswer.answer);
  console.log(`Asha refused:`, ashaDocAnswer.refused);
  console.log(`Asha citations count:`, ashaDocAnswer.citations?.length);

  if (ashaDocAnswer.refused) {
    throw new Error(`Expected Asha to receive an answer, but got refused!`);
  }
  if (!ashaDocAnswer.citations || ashaDocAnswer.citations.length === 0) {
    throw new Error(`Expected citations for Asha, got 0.`);
  }

  // 10. Login as Neha -> Neha cannot see it and is refused
  console.log('\n--- 10. Login as Neha & Verify Access Denied Before Share ---');
  const nehaLoginRes = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'neha.desai@northwind.example',
      password: 'changeme123'
    })
  });
  if (!nehaLoginRes.ok) {
    throw new Error(`Login Neha failed: ${nehaLoginRes.status} ${await nehaLoginRes.text()}`);
  }
  const nehaToken = (await nehaLoginRes.json()).access_token;
  const nehaMeRes = await fetch(`${BASE_URL}/auth/me`, {
    headers: { 'Authorization': `Bearer ${nehaToken}` }
  });
  const nehaMe = await nehaMeRes.json();
  console.log(`Neha user profile: id=${nehaMe.id}, name=${nehaMe.name}`);

  // Neha asks -> must be refused
  const nehaAskBeforeRes = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${nehaToken}`
    },
    body: JSON.stringify({
      question: falconQuestion,
      source_ids: [docId]
    })
  });
  const nehaAskBeforeAnswer = await nehaAskBeforeRes.json();
  console.log(`Neha before share refused:`, nehaAskBeforeAnswer.refused);
  if (!nehaAskBeforeAnswer.refused) {
    throw new Error(`Expected Neha to be refused before document was shared, but was answered!`);
  }

  // Neha checks shared documents list
  const nehaSharedRes = await fetch(`${BASE_URL}/documents?scope=shared`, {
    headers: { 'Authorization': `Bearer ${nehaToken}` }
  });
  const nehaSharedDocs = await nehaSharedRes.json();
  if (nehaSharedDocs.some((d) => d.id === docId)) {
    throw new Error(`Document ${docId} unexpectedly visible in Neha's shared documents list before sharing!`);
  }
  console.log(`Verified doc ${docId} is not visible to Neha.`);

  // 11. Asha shares document with Neha
  console.log('\n--- 11. Asha Shares Document with Neha ---');
  const shareRes = await fetch(`${BASE_URL}/documents/${docId}/shares`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${ashaToken}`
    },
    body: JSON.stringify({
      grantee_type: 'user',
      value: nehaMe.id,
      include_sensitive: false
    })
  });
  if (!shareRes.ok) {
    throw new Error(`Sharing failed: ${shareRes.status} ${await shareRes.text()}`);
  }
  const shareData = await shareRes.json();
  const shareId = shareData.id;
  console.log(`Document successfully shared with Neha. Share ID: ${shareId}`);

  // 12. Neha asks about document -> now answered!
  console.log('\n--- 12. Neha Asks About Document After Share ---');
  const nehaAskAfterRes = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${nehaToken}`
    },
    body: JSON.stringify({
      question: falconQuestion,
      source_ids: [docId]
    })
  });
  const nehaAskAfterAnswer = await nehaAskAfterRes.json();
  console.log(`Neha after share refused:`, nehaAskAfterAnswer.refused);
  console.log(`Neha answer:`, nehaAskAfterAnswer.answer);
  if (nehaAskAfterAnswer.refused) {
    throw new Error(`Expected Neha to receive answer after share, but was refused!`);
  }

  // 13. Asha revokes sharing
  console.log('\n--- 13. Asha Revokes Sharing ---');
  const revokeRes = await fetch(`${BASE_URL}/documents/${docId}/shares/${shareId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${ashaToken}` }
  });
  if (revokeRes.status !== 204) {
    throw new Error(`Revoke share failed: ${revokeRes.status} ${await revokeRes.text()}`);
  }
  console.log(`Share ${shareId} revoked successfully.`);

  // 14. Neha asks again -> refused!
  console.log('\n--- 14. Neha Asks Again After Revocation (Refusal Expected) ---');
  const nehaAskRevokedRes = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${nehaToken}`
    },
    body: JSON.stringify({
      question: falconQuestion,
      source_ids: [docId]
    })
  });
  const nehaAskRevokedAnswer = await nehaAskRevokedRes.json();
  console.log(`Neha after revoke refused:`, nehaAskRevokedAnswer.refused);
  if (!nehaAskRevokedAnswer.refused) {
    throw new Error(`Expected Neha to be refused after revocation, but was answered!`);
  }

  // 15. Asha deletes document
  console.log('\n--- 15. Asha Deletes Document ---');
  const deleteRes = await fetch(`${BASE_URL}/documents/${docId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${ashaToken}` }
  });
  if (deleteRes.status !== 204) {
    throw new Error(`Delete document failed: ${deleteRes.status} ${await deleteRes.text()}`);
  }
  console.log(`Document ${docId} deleted successfully.`);

  // Verify doc is deleted (404)
  const getDeletedRes = await fetch(`${BASE_URL}/documents/${docId}`, {
    headers: { 'Authorization': `Bearer ${ashaToken}` }
  });
  if (getDeletedRes.status !== 404) {
    throw new Error(`Expected 404 after deletion, got ${getDeletedRes.status}`);
  }
  console.log(`Confirmed 404 on deleted document.`);

  // 16. Admin loads /admin/audit/summary
  console.log('\n--- 16. Admin Monitoring & Audit Summary ---');
  const adminLoginRes = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'admin@northwind.example',
      password: 'changeme123'
    })
  });
  if (!adminLoginRes.ok) {
    throw new Error(`Admin login failed: ${adminLoginRes.status} ${await adminLoginRes.text()}`);
  }
  const adminToken = (await adminLoginRes.json()).access_token;

  const summaryRes = await fetch(`${BASE_URL}/admin/audit/summary?days=7`, {
    headers: { 'Authorization': `Bearer ${adminToken}` }
  });
  if (!summaryRes.ok) {
    throw new Error(`Admin summary failed: ${summaryRes.status} ${await summaryRes.text()}`);
  }
  const summaryData = await summaryRes.json();
  console.log(`Admin audit summary retrieved:`);
  console.log(`- Total asks: ${summaryData.totals.asks}`);
  console.log(`- Total searches: ${summaryData.totals.searches}`);
  console.log(`- Refusal rate: ${(summaryData.totals.refusal_rate * 100).toFixed(1)}%`);
  console.log(`- Avg latency: ${summaryData.totals.avg_latency_ms.toFixed(1)} ms`);
  console.log(`- P95 latency: ${summaryData.totals.p95_latency_ms.toFixed(1)} ms`);
  console.log(`- Uploads: ${summaryData.totals.uploads}`);
  console.log(`- Active users: ${summaryData.totals.active_users}`);
  console.log(`- Per day series count: ${summaryData.per_day_series?.length}`);

  // Fetch recent queries
  const queriesRes = await fetch(`${BASE_URL}/admin/queries?limit=10`, {
    headers: { 'Authorization': `Bearer ${adminToken}` }
  });
  const queriesData = await queriesRes.json();
  console.log(`Admin queries count: ${queriesData.length}`);

  // Fetch admin uploads
  const uploadsRes = await fetch(`${BASE_URL}/admin/uploads`, {
    headers: { 'Authorization': `Bearer ${adminToken}` }
  });
  const uploadsData = await uploadsRes.json();
  console.log(`Admin uploads audit count: ${uploadsData.length}`);

  console.log('\n========================================');
  console.log('ALL FRONTEND PART 2 SMOKE TEST CHECKS PASSED!');
  console.log('========================================');
}

run().catch((err) => {
  console.error('Smoke test failed:', err);
  process.exit(1);
});

