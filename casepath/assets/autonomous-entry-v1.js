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
  try {
    if (document.documentElement.dataset.autonomousWorkspace === 'true') {
      await load('casepath-autonomous-script');
      let recordedPacket, savedSnapshot;
      if (window.CASEPATH_PUBLIC_READ_ONLY === true) {
        try { recordedPacket = JSON.parse(document.querySelector('meta[name="casepath-recorded-opening"]')?.content || 'null'); }
        catch (_) { /* A missing replay asset leaves the verified API path available. */ }
        try { savedSnapshot = JSON.parse(document.querySelector('meta[name="casepath-saved-history"]')?.content || 'null'); }
        catch (_) { /* Saved content can still arrive from the normal GET. */ }
      }
      window.CasePathAutonomous.mount(document.getElementById('autonomousWorkspace'), {recordedPacket, savedSnapshot});
      window.addEventListener('pagehide', event => { if (!event.persisted) window.CasePathAutonomous.destroy(); });
    } else {
      await load('casepath-review-workspace-script');
      await load('casepath-review-desk-script');
    }
  } catch (error) {
    const container = document.getElementById('autonomousWorkspace');
    if (document.documentElement.dataset.autonomousWorkspace === 'true') {
      container.textContent = 'The workspace could not open. ';
      const retry = document.createElement('button');
      retry.type = 'button'; retry.textContent = 'Retry';
      retry.addEventListener('click', () => location.reload());
      container.append(retry);
    }
  }
})();
