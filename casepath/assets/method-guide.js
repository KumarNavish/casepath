(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = document.querySelector('form');
  const stateLabels = {true: 'Active', false: 'Inactive', unresolved: 'Unresolved'};
  const actions = {
    resolve_applicability: 'Resolve whether the repair qualifies.',
    resolve_acquisition: 'Resolve permission to acquire evidence.',
    acquisition_not_permitted: 'Resolve the acquisition restriction.',
    action_ready: 'Repair authorization is eligible.',
    review_evidence_gap: 'Review the uncovered evidence need.'
  };
  fetch('assets/method-guide-data.json', {cache: 'no-cache'})
    .then(response => { if (!response.ok) throw new Error('data unavailable'); return response.json(); })
    .then(data => {
      if (data.schema !== 'casepath.teaching-explorer/1' || Object.keys(data.scenarios).length !== 45) throw new Error('example invalid');
      const name = id => data.documents[id] || id;
      function render() {
        const fields = new FormData(form);
        const key = ['branch', 'permission', 'held'].map(field => fields.get(field)).join(':');
        const row = data.scenarios[key];
        const p = row.planning;
        const duty = p.control.obligations.establish_cause;
        const selected = p.capabilities.cause_proof.selected;
        $('scope-text').textContent = `${stateLabels[duty.applicability]} — ${duty.applicability === 'true' ? 'the qualifying-repair branch applies.' : duty.applicability === 'false' ? 'this repair falls outside the branch.' : 'the branch condition still needs an answer.'}`;
        $('obligation-text').textContent = duty.applicability === 'false' ? 'No active cause obligation on this branch.' : `${duty.applicability === 'unresolved' ? 'If the branch applies: establish' : 'Establish'} the cause of the equipment fault.`;
        $('route-text').textContent = duty.applicability === 'false' ? 'No evidence demand is activated.' : `${selected.document_ids.map(name).join(' + ')}. ${selected.satisfaction === 'true' ? 'This route already establishes the fact.' : 'The rule also permits ' + (selected.route_id === 'report' ? 'a service note and photo that jointly establish the cause.' : 'a complete inspection report.')}`;
        $('request-text').textContent = p.documents_now.length ? p.documents_now.map(name).join(' + ') : 'No immediate request';
        $('reason-text').textContent = duty.applicability === 'false' ? 'An inactive obligation creates no demand.' : p.documents_now.length ? 'The obligation is active, acquisition is permitted, and this evidence is missing.' : p.documents_conditional.length ? 'The document need remains conditional until the controlling question is resolved.' : p.reviews.length ? 'Inspect the evidence already held before requesting more.' : p.capabilities.cause_proof.satisfaction === 'true' ? 'Available evidence already satisfies the capability.' : 'Resolve the case state before acting.';
        const action = p.next_action;
        $('next-action-text').textContent = !action ? 'No action on this branch.' : action.kind === 'request_document' ? `Request the ${name(action.document_id).toLowerCase()}.` : action.kind === 'review_evidence' ? action.document_id ? `Review the ${name(action.document_id).toLowerCase()}.` : 'Review what the documents establish together.' : actions[action.kind] || action.kind;
        $('raw-trace').textContent = JSON.stringify(row, null, 2);
        $('explorer-body').dataset.state = key;
      }
      $('policy-text').textContent = data.policy;
      form.addEventListener('change', render);
      form.addEventListener('submit', event => event.preventDefault());
      // The reset event precedes the browser's default control reset.
      form.addEventListener('reset', () => requestAnimationFrame(render));
      render();
      $('load-status').hidden = true;
      $('explorer-body').hidden = false;
    })
    .catch(() => {
      $('load-status').textContent = 'The example could not be loaded. Reload this page to try again; the method explanation below remains available.';
    });
})();
