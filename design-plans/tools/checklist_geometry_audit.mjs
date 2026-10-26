// Serialized into the browser by the film recorder and deterministic tests.
// Keep every dependency inside this function. Original (unclipped) rectangles
// are essential: intersecting them with overflow boxes hides truncated rows.
export function auditChecklistGeometry(options = {}) {
  const limit = Math.max(1, Math.min(200, options.maxFailures || 60));
  const tolerance = options.tolerance ?? 1;
  const overlapTolerance = options.overlapTolerance ?? 2;
  const root = [...document.querySelectorAll('dialog[open]')].at(-1)
    || document.querySelector('.au-workspace');
  const result = {
    contract: 'casepath.checklist-geometry/1.0.0',
    passed: true,
    checked: { rows: 0, facts: 0, labels: 0, panels: 0, textFragments: 0 },
    labelViews: {}, failures: [], totalFailures: 0, truncated: false
  };
  if (!root) return result;
  const excluded = '.au-executive-transition,.au-executive-ink,.au-ns-cursor,.au-ns-slip,.au-shelf-card[data-flying=true],.au-case-opener,.au-tab-tip,.au-file-zoom,'
    + '.au-ns-memory-flight,.au-ns-fact-connector,.au-ns-memory-link,.au-ns-node-badge,svg,'
    + '[hidden],dialog:not([open]),.au-ns-source-scroll,.au-ns-page pre';
  const styles = new Map(), bounds = new Map(), visibility = new Map();
  const style = element => {
    if (!styles.has(element)) styles.set(element, getComputedStyle(element));
    return styles.get(element);
  };
  const rect = element => {
    if (!bounds.has(element)) bounds.set(element, element.getBoundingClientRect());
    return bounds.get(element);
  };
  const visible = element => {
    if (visibility.has(element)) return visibility.get(element);
    let yes = !element.closest(excluded)
      && !(element.closest('details:not([open])') && !element.closest('summary'));
    for (let parent = element; yes && parent; parent = parent.parentElement) {
      const css = style(parent);
      if (css.display === 'none' || css.visibility === 'hidden'
          || css.visibility === 'collapse' || Number(css.opacity) === 0) yes = false;
    }
    visibility.set(element, yes);
    return yes;
  };
  const identify = element => {
    const name = ['data-au-ns-plan-row', 'data-au-ns-plan-summary',
      'data-au-ns-fact', 'data-au-ns-node', 'data-au-ns-role']
      .find(attribute => element.hasAttribute(attribute));
    return (name ? `[${name}="${element.getAttribute(name)}"]` :
      element.tagName.toLowerCase() + (typeof element.className === 'string'
        ? '.' + element.className.trim().split(/\s+/).filter(Boolean).join('.') : ''))
      + ' ' + element.textContent.trim().replace(/\s+/g, ' ').slice(0, 90);
  };
  const snapshot = box => Object.fromEntries(['left', 'top', 'right', 'bottom']
    .map(key => [key, Math.round(box[key] * 100) / 100]));
  const reported = new Set();
  const fail = (reason, element, box, other, boundary) => {
    const subject = identify(element), against = other ? identify(other) : 'viewport';
    const key = reason + '\n' + subject + '\n' + against;
    if (reported.has(key)) return;
    reported.add(key);
    result.totalFailures++;
    if (result.failures.length < limit) result.failures.push({
      reason, subject, against, rect: snapshot(box), boundary: snapshot(boundary)
    });
  };
  const outside = (box, boundary, x = true, y = true) =>
    x && (box.left < boundary.left - tolerance || box.right > boundary.right + tolerance)
    || y && (box.top < boundary.top - tolerance || box.bottom > boundary.bottom + tolerance);
  const viewport = { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
  const clipPattern = /^(?:auto|scroll|hidden|clip)$/;
  const clipBox = element => {
    const box = rect(element);
    // Axis-aligned scale/translation is what the presentation uses. Client
    // bounds exclude the border and any occupied scrollbar gutter.
    const sx = element.offsetWidth ? box.width / element.offsetWidth : 1;
    const sy = element.offsetHeight ? box.height / element.offsetHeight : 1;
    const left = box.left + element.clientLeft * sx;
    const top = box.top + element.clientTop * sy;
    return { left, top, right: left + element.clientWidth * sx,
      bottom: top + element.clientHeight * sy };
  };
  const checkClip = (element, box, isText = false, owner = element) => {
    if (box.width <= 0 || box.height <= 0) return;
    if (outside(box, viewport)) fail(isText ? 'text outside viewport' : 'box outside viewport',
      owner, box, null, viewport);
    for (let parent = isText ? element : element.parentElement;
      parent; parent = parent.parentElement) {
      const css = style(parent), x = clipPattern.test(css.overflowX),
        y = clipPattern.test(css.overflowY);
      if (!x && !y) continue;
      const boundary = clipBox(parent);
      if (outside(box, boundary, x, y)) fail(isText ? 'text clipped by ancestor' : 'box clipped by ancestor',
        owner, box, parent, boundary);
    }
  };
  const strictLabels = '.au-ns-plan h2,.au-ns-plan ol > li > span:not(.au-ns-plan-status),'
      + '.au-ns-fact > span,.au-ns-node-label,.au-ns-step-status,.au-ns-log p,'
      + '.au-ns-log button,.au-ns-tabs [data-au-ns-role],'
      + '.au-ns-completed-spine [data-au-desk-select],'
      + '.au-ns-completed-spine .au-ns-test-verdict,'
      + '.au-ns-memory-spine [data-au-ns-memory-select],'
      + '.au-ns-chain-column,.au-ns-memory-target,.au-executive-step-label';
  // Audit the other film views as text-bearing leaves, not whole scrollable
  // sections. Their source/document bodies remain outside this label contract.
  const filmLabels = '.au-desk-answer > h2,.au-desk-test-status,.au-executive-test-context,'
    + '.au-desk-tests > li > button,.au-desk-tests > li > .au-desk-law,'
    + '.au-desk-lead,.au-desk-open,.au-desk-actions > *,.au-desk-why > summary,'
    + '.au-desk-next > p,.au-desk-next > ul > li,'
    + '.au-executive-roster-heading > *, .au-executive-cases .au-claim-row > h2,'
    + '.au-executive-cases .au-claim-row > p,.au-executive-wordmark,'
    + '.au-ns-sources > h1,.au-ns-sources > h2,.au-ns-sources > p,'
    + '.au-ns-sources > ul > li > button,.au-ns-source-bottom > *,'
    + '.au-executive-documents,.au-ns-purpose > *,.au-ns-secondary button,'
    + '.au-ns-source-fields dt,.au-ns-source-fields dd,.au-ns-paper > header button,'
    + '.au-ns-passage-group > h3,.au-ns-page > h3,.au-ns-page-controls > button,'
    + '.au-ns-view-content > h2,.au-ns-role-purpose,.au-ns-reader-source h3 > button,'
    + '.au-ns-reader-request,.au-ns-document-row > h3,.au-ns-document-row > p,'
    + '.au-ns-document-row > button,.au-ns-missing > span,'
    + '.au-executive-transport > span,.au-executive-transport button,'
    + '.au-ns-memory header button,.au-ns-memory footer,[data-au-memory-origin],'
    + '.au-ns-memory-chain > p,.au-ns-memory-cards h3,.au-ns-memory-cards p,'
    + '.au-ns-memory-cards li,.au-ns-memory-cards strong,.au-ns-memory-cards blockquote,'
    + '.au-ns-memory-cards button,.au-ns-law-source h2,.au-ns-law-source h3,'
    + '.au-ns-law-source > p,.au-ns-draft-content > p,.au-ns-draft-content > h3,'
    + '.au-ns-initial-date > h3,.au-ns-initial-date > p,.au-ns-initial-date > blockquote,'
    + '.au-ns-procedure > h2,.au-ns-procedure > h3,.au-ns-procedure > p,.au-ns-procedure li,'
    + '.au-executive-checklist > h2,.au-executive-checklist li,'
    + '.au-library .au-page-heading,.au-library-index button > *,.au-procedure-stage > h3,'
    + '.au-ns-shelf h2,.au-shelf-card h3,.au-shelf-card li,.au-shelf-origin,'
    + '.au-km-head h1,.au-km-counters dt,.au-km-case p,.au-km-card h3,.au-km-card li';
  const outsideScrollport = (element, box) => {
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      const css = style(parent), boundary = clipBox(parent);
      const x = /^(?:auto|scroll)$/.test(css.overflowX)
        && parent.scrollWidth > parent.clientWidth + tolerance;
      const y = /^(?:auto|scroll)$/.test(css.overflowY)
        && parent.scrollHeight > parent.clientHeight + tolerance;
      if (x && (box.right <= boundary.left || box.left >= boundary.right)
          || y && (box.bottom <= boundary.top || box.top >= boundary.bottom)) return true;
    }
    return false;
  };
  const selectors = {
    rows: '.au-ns-plan ol > li',
    facts: '.au-ns-fact',
    labels: strictLabels + ',' + filmLabels,
    panels: '.au-ns-plan,.au-ns-paper,.au-ns-log,.au-ns-sources,'
      + '.au-ns-completed-spine,.au-ns-chain,.au-ns-missing,'
      + '.au-ns-memory-spine,.au-ns-memory-cards > article,'
      + '.au-executive-transport,.au-identity-header'
  };
  const units = [], seen = new Set();
  for (const [kind, selector] of Object.entries(selectors)) {
    for (const element of root.querySelectorAll(selector)) {
      if (seen.has(element) || !visible(element)) continue;
      seen.add(element);
      const box = rect(element);
      if (box.width <= 0 || box.height <= 0) continue;
      // A scrolled-away answer is not visible content. This exception never
      // applies to checklist rows/facts or their original strict labels, and
      // never forgives a partially clipped label or an overflow:hidden crop.
      if (kind === 'labels' && !element.matches(strictLabels)
          && outsideScrollport(element, box)) continue;
      result.checked[kind]++;
      if (kind === 'labels') {
        const view = document.querySelector('[data-au-presentation-act]')
          ?.dataset.auPresentationAct || 'other';
        result.labelViews[view] = (result.labelViews[view] || 0) + 1;
      }
      const fragments = kind === 'labels' && style(element).display === 'inline'
        ? [...element.getClientRects()] : [box];
      units.push({ element, kind, fragments });
      if (kind !== 'panels') {
        for (const fragment of fragments) checkClip(element, fragment);
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const node = walker.currentNode, parent = node.parentElement;
          if (!node.textContent.trim() || !visible(parent)) continue;
          // The recorded verdict is deliberately positioned below its node.
          // It has its own audited label box, rather than inheriting the node
          // button's containment boundary. Its clip/viewport checks remain.
          const verdict = parent.closest('.au-ns-test-verdict');
          const externalVerdict = element.matches('.au-ns-completed-spine [data-au-desk-select]')
            && verdict && element.contains(verdict) && style(verdict).position === 'absolute';
          const range = document.createRange();
          range.selectNodeContents(node);
          for (const fragment of range.getClientRects()) {
            if (fragment.width <= 0 || fragment.height <= 0) continue;
            result.checked.textFragments++;
            // A label/row's own box is a containment contract even if it uses
            // overflow:visible; its words must not spill into neighbouring rows.
            if (!externalVerdict && outside(fragment, box)) fail('text exceeds its label or row',
              element, fragment, element, box);
            checkClip(parent, fragment, true, element);
          }
          range.detach();
        }
      }
    }
  }
  for (let i = 0; i < units.length; i++) {
    const a = units[i];
    for (let j = i + 1; j < units.length; j++) {
      const b = units[j];
      // Panels establish obstacles; their nested text/cards are intentionally
      // contained. Only independent content can overlap accidentally.
      if (a.element.contains(b.element) || b.element.contains(a.element)) continue;
      if (a.kind === 'panels' && b.kind === 'panels') continue;
      let hit;
      for (const first of a.fragments) {
        for (const second of b.fragments) {
          if (Math.min(first.right, second.right) - Math.max(first.left, second.left) > overlapTolerance
              && Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top) > overlapTolerance) {
            hit = [first, second]; break;
          }
        }
        if (hit) break;
      }
      if (hit) fail('independent content overlap', a.element, hit[0], b.element, hit[1]);
    }
  }
  result.passed = result.totalFailures === 0;
  result.truncated = result.totalFailures > result.failures.length;
  return result;
}
