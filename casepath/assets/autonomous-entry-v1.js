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
      let recordedPacket;
      if (window.CASEPATH_PUBLIC_READ_ONLY === true) {
        try { recordedPacket = JSON.parse(document.querySelector('meta[name="casepath-recorded-opening"]')?.content || 'null'); }
        catch (_) { /* A missing replay asset leaves the verified API path available. */ }
      }
      window.CasePathAutonomous.mount(document.getElementById('autonomousWorkspace'), {recordedPacket});
      window.addEventListener('pagehide', event => { if (!event.persisted) window.CasePathAutonomous.destroy(); });
    } else {
      await load('casepath-review-workspace-script');
      await load('casepath-review-desk-script');
    }
  } catch (error) {
    const container = document.getElementById('autonomousWorkspace');
    if (document.documentElement.dataset.autonomousWorkspace === 'true') container.textContent = `${error.message} Reload to try again.`;
  }
})();
