(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  if (new URLSearchParams(location.search).get('foundation') === 'live-v1') return;

  const uniqueClasses = [
    'v17-law-map',
    'v17-law-details',
    'v17-build-state',
    'v17-evidence-chain',
    'v17-experience-note',
    'v17-reuse-thread',
    'v18-ready-artifacts',
    'v18-review-propagation',
    'v18-review-applied',
    'v18-memory-boundary',
    'v18-reuse-proof',
  ];
  const originalInsertBefore = Node.prototype.insertBefore;
  const originalInsertAdjacentHTML = Element.prototype.insertAdjacentHTML;

  Node.prototype.insertBefore = function guardedInsertBefore(newNode, referenceNode) {
    if (newNode instanceof Element) {
      const uniqueClass = uniqueClasses.find(className => newNode.classList.contains(className));
      if (uniqueClass) {
        const existing = [...this.children].find(child => child instanceof Element && child.classList.contains(uniqueClass));
        if (existing) return existing;
      }
    }
    return originalInsertBefore.call(this, newNode, referenceNode);
  };

  Element.prototype.insertAdjacentHTML = function guardedInsertAdjacentHTML(position, markup) {
    if (typeof markup === 'string' && markup.includes('data-event-source="presented-backend-event"')) return;
    return originalInsertAdjacentHTML.call(this, position, markup);
  };

  const nativeFetch = window.fetch.bind(window);
  const pendingRunReads = new Map();
  const pendingRunMutations = new Map();

  function effectiveSessionId(request, init) {
    const headers = new Headers(init.headers !== undefined ? init.headers : request?.headers);
    return (headers.get('X-CasePath-Session') || '').trim();
  }

  function runResourceKey(url, request, init) {
    const match = url.pathname.match(/^(.*\/api\/runs\/[^/]+)(?:\/review)?$/);
    return match ? `${url.origin}${match[1]}\n${effectiveSessionId(request, init)}` : '';
  }

  window.fetch = async function stableFetch(input, init = {}) {
    const request = typeof input === 'string' || input instanceof URL ? null : input;
    const method = String(init.method || request?.method || 'GET').toUpperCase();
    let url;
    try {
      url = new URL(typeof input === 'string' || input instanceof URL ? String(input) : input.url, location.href);
    } catch (_) {
      return nativeFetch(input, init);
    }

    const resourceKey = runResourceKey(url, request, init);
    const isRunRead = method === 'GET' && Boolean(resourceKey) && !url.pathname.endsWith('/review');
    const isReviewMutation = method === 'POST' && Boolean(resourceKey) && url.pathname.endsWith('/review');
    if (isReviewMutation) {
      pendingRunReads.delete(resourceKey);
      const mutation = nativeFetch(input, init);
      pendingRunMutations.set(resourceKey, mutation);
      try {
        return await mutation;
      } finally {
        if (pendingRunMutations.get(resourceKey) === mutation) pendingRunMutations.delete(resourceKey);
        pendingRunReads.delete(resourceKey);
      }
    }
    if (!isRunRead) return nativeFetch(input, init);

    const activeMutation = pendingRunMutations.get(resourceKey);
    if (activeMutation) {
      try {
        await activeMutation;
      } catch (_) {
        // The caller still receives a fresh authoritative run read after a
        // failed review mutation; no pre-mutation response may be reused.
      }
    }

    const existing = pendingRunReads.get(resourceKey);
    if (existing) {
      const response = await existing;
      return response.clone();
    }

    const promise = nativeFetch(input, init);
    pendingRunReads.set(resourceKey, promise);
    try {
      const response = await promise;
      return response.clone();
    } finally {
      if (pendingRunReads.get(resourceKey) === promise) pendingRunReads.delete(resourceKey);
    }
  };

  const innerHTML = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  if (innerHTML?.get && innerHTML?.set) {
    Object.defineProperty(Element.prototype, 'innerHTML', {
      configurable: innerHTML.configurable,
      enumerable: innerHTML.enumerable,
      get: innerHTML.get,
      set(value) {
        if (this.classList?.contains('v19-team-rail') && innerHTML.get.call(this) === String(value)) return;
        innerHTML.set.call(this, value);
      },
    });
  }

  window.CASEPATH_INSERTION_GUARD = '19.0.2';
  window.CASEPATH_RUNTIME_STABILITY = '19.0.0';
})();
