(async () => {
  'use strict';
  if (location.protocol === 'file:') return;
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
      window.CasePathAutonomous.mount(document.getElementById('autonomousWorkspace'));
      window.addEventListener('pagehide', () => window.CasePathAutonomous.destroy());
    } else {
      await load('casepath-review-workspace-script');
      await load('casepath-review-desk-script');
    }
  } catch (error) {
    const container = document.getElementById('autonomousWorkspace');
    if (document.documentElement.dataset.autonomousWorkspace === 'true') container.textContent = `${error.message} Reload to try again.`;
  }
})();
