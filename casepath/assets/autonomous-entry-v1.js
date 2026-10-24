(async () => {
  'use strict';
  if (location.protocol === 'file:') return;
  if (window.CASEPATH_PUBLIC_READ_ONLY === true) {
    document.documentElement.dataset.autonomousWorkspace = 'true';
    delete document.documentElement.dataset.claimsWorkspace;
  }
  function load(name) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = document.querySelector(`meta[name="${name}"]`).content;
      script.onload = resolve;
      script.onerror = () => reject(new Error('The workspace script could not be loaded.'));
      document.body.append(script);
    });
  }
  let knowledgeOpening;
  try {
    if (document.documentElement.dataset.autonomousWorkspace === 'true') {
      if (window.CASEPATH_PUBLIC_READ_ONLY === true && (location.hash === '#autonomous/knowledge' || location.hash.startsWith('#autonomous/knowledge?'))) {
        const url = '/api/claim-loops/v1/autonomous/knowledge', controller = new AbortController(), timeout = setTimeout(() => controller.abort(new DOMException('No response within 15 seconds. Try again.','TimeoutError')),15000);
        const response = fetch(url,{method:'GET',headers:{Accept:'application/json'},signal:controller.signal,cache:'no-store'});
        response.catch(() => {});
        knowledgeOpening = {url,fragment:location.hash,controller,timeout,response};
      }
      await load('casepath-autonomous-script');
      let recordedPacket, savedSnapshot;
      if (window.CASEPATH_PUBLIC_READ_ONLY === true) {
        try { recordedPacket = JSON.parse(document.querySelector('meta[name="casepath-recorded-opening"]')?.content || 'null'); }
        catch (_) { /* A missing replay asset leaves the verified API path available. */ }
        try { savedSnapshot = JSON.parse(document.querySelector('meta[name="casepath-saved-history"]')?.content || 'null'); }
        catch (_) { /* Saved content can still arrive from the normal GET. */ }
      }
      window.CasePathAutonomous.mount(document.getElementById('autonomousWorkspace'), {recordedPacket, savedSnapshot, knowledgeOpening});
      knowledgeOpening = null;
      window.addEventListener('pagehide', event => { if (!event.persisted) window.CasePathAutonomous.destroy(); });
    } else {
      if(new URLSearchParams(location.search).get('view')==='northstar')await load('casepath-review-northstar-script');
      await load('casepath-review-workspace-script');
      await load('casepath-review-desk-script');
    }
  } catch (error) {
    if (knowledgeOpening) { knowledgeOpening.controller.abort(); clearTimeout(knowledgeOpening.timeout); }
    const container = document.getElementById('autonomousWorkspace');
    if (document.documentElement.dataset.autonomousWorkspace === 'true') {
      container.textContent = 'The workspace could not open. ';
      const retry = document.createElement('button');
      retry.type = 'button'; retry.textContent = 'Retry';
      retry.addEventListener('click', () => location.reload());
      container.append(retry);
    } else {
      const recovery=document.createElement('main');recovery.id='reviewStartupError';recovery.setAttribute('role','alert');recovery.style.cssText='display:block!important;max-width:560px;margin:80px auto;padding:24px;font:16px/1.6 sans-serif';
      const heading=document.createElement('h1');heading.textContent='The review workspace could not open';
      const explanation=document.createElement('p');explanation.textContent='A required part of the workspace did not load. Retry to read the saved claim.';
      const retry=document.createElement('button');retry.type='button';retry.textContent='Retry';retry.addEventListener('click',()=>location.reload());
      recovery.append(heading,explanation,retry);document.body.append(recovery);
    }
  }
})();
