(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const api = async (path, options = {}) => {
    const response = await fetch(path, {cache:'no-store', ...options,
      headers:{'Content-Type':'application/json', ...(options.headers || {})}});
    const value = await response.json().catch(() => ({detail:`HTTP ${response.status}`}));
    if (!response.ok) throw new Error(value.detail || `HTTP ${response.status}`);
    return value;
  };
  const shortHash = value => value ? `${value.slice(0,8)}…${value.slice(-6)}` : 'unbound';
  const ensurePanel = status => {
    const host = document.querySelector('#startState .start-copy') || document.querySelector('.work-pane');
    if (!host) return null;
    let panel = document.getElementById('paperMethodPanel');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'paperMethodPanel';
    panel.className = 'paper-method-panel';
    panel.setAttribute('aria-labelledby','paperMethodTitle');
    panel.innerHTML = `<div class="paper-method-head"><div><span class="paper-method-kicker">Exact paper method</span><h3 id="paperMethodTitle">Source → process → evidence → next action</h3><p>The installed research pack drives this view directly. Every requested document must come through an active source-grounded requirement chain.</p></div><button class="paper-method-run" type="button">Run exact method</button></div><div class="paper-method-meta"><span class="paper-method-chip">${esc(status.scope || 'frozen scope')}</span><span class="paper-method-chip">method ${esc(shortHash(status.method_freeze_sha256))}</span><span class="paper-method-chip">pack ${esc(shortHash(status.pack_manifest_sha256))}</span></div><div class="paper-method-result" hidden></div>`;
    host.appendChild(panel);
    return panel;
  };
  const renderPlan = (root, plan) => {
    const requests = plan.requests || [];
    const active = Object.values(plan.guard_verdicts || {}).filter(v => v.verdict === 'true').length;
    const unresolved = Object.values(plan.guard_verdicts || {}).filter(v => v.verdict === 'unresolved').length;
    const action = plan.next_action;
    const requestHtml = requests.length ? requests.map(request => {
      const docs = (request.still_missing || request.document_types || []).map(esc).join(' + ');
      const chains = (request.justified_by || []).map(chain => {
        const sources = (chain.sources || []).map(source => `<div class="paper-method-source"><strong>${esc(source.citation || source.authority_id)}</strong><br>${esc(source.quote || source.exact_text || '')}</div>`).join('');
        return `<div class="paper-method-chain"><strong>${esc(chain.purpose === 'resolve_process_state' ? 'Resolve branch' : 'Active requirement')}</strong> · ${esc(chain.process_node || chain.rule_id || '')}<br>${esc(chain.must_show || chain.fact || '')}${sources}</div>`;
      }).join('');
      return `<div class="paper-method-request"><div class="paper-method-doc">${docs}</div>${chains}</div>`;
    }).join('') : '<p>No additional catalogue document is currently justified.</p>';
    root.innerHTML = `<div class="paper-method-grid"><article class="paper-method-card"><h4>Active case path</h4><strong>${active} source guard${active===1?'':'s'} active · ${unresolved} unresolved</strong><p>${esc(plan.counts?.active_requirement_chains || 0)} active evidence chains; ${esc(plan.counts?.resolver_chains || 0)} resolver chains; ${esc(plan.counts?.evidence_gaps || 0)} explicit evidence gaps.</p></article><article class="paper-method-card"><h4>Justified next action</h4><strong>${esc(action?.type ? action.type.replaceAll('_',' ') : 'No further action')}</strong><p>${esc(action?.why || 'No source-grounded action is currently justified.')}</p></article></div><article class="paper-method-card" style="margin-top:14px"><h4>Process-derived document checklist</h4>${requestHtml}</article>`;
    root.hidden = false;
  };

  const activate = async () => {
    if (!/^https?:$/.test(location.protocol)) return;
    let status;
    try { status = await api('/api/paper-method/status'); } catch (_) { return; }
    if (!status?.ready || !status.demo_case) return;
    const panel = ensurePanel(status); if (!panel) return;
    const button = panel.querySelector('.paper-method-run');
    const result = panel.querySelector('.paper-method-result');
    button.addEventListener('click', async () => {
      button.disabled = true; button.textContent = 'Running exact method…';
      result.hidden = true; result.innerHTML = '';
      const demo = status.demo_case || {};
      const customerMessage = demo.customer_message || demo.case?.customer_message;
      try {
        const plan = await api('/api/paper-method/plan', {method:'POST', body:JSON.stringify({customer_message:customerMessage, already_held:demo.already_held || []})});
        renderPlan(result, plan);
      } catch (error) {
        result.innerHTML = `<p class="paper-method-error">${esc(error.message || 'Paper method unavailable.')}</p>`;
        result.hidden = false;
      } finally { button.disabled = false; button.textContent = 'Run exact method'; }
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', activate, {once:true});
  else activate();
})();
