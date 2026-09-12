(() => {
  'use strict';

  const nativeFetch = window.fetch.bind(window);
  const pendingRunReads = new Map();
  const runReadWindowMs = 350;

  window.fetch = async function stableFetch(input, init = {}) {
    const request = typeof input === 'string' || input instanceof URL ? null : input;
    const method = String(init.method || request?.method || 'GET').toUpperCase();
    let url = '';
    try {
      url = new URL(typeof input === 'string' || input instanceof URL ? String(input) : input.url, location.href).href;
    } catch (_) {
      return nativeFetch(input, init);
    }

    const isRunRead = method === 'GET' && /\/api\/runs\/[^/?#]+(?:[?#]|$)/.test(new URL(url).pathname);
    if (!isRunRead) return nativeFetch(input, init);

    const now = performance.now();
    const existing = pendingRunReads.get(url);
    if (existing && now - existing.startedAt < runReadWindowMs) {
      const response = await existing.promise;
      return response.clone();
    }

    const promise = nativeFetch(input, init);
    pendingRunReads.set(url, { promise, startedAt: now });
    try {
      const response = await promise;
      return response.clone();
    } finally {
      window.setTimeout(() => {
        const current = pendingRunReads.get(url);
        if (current?.promise === promise) pendingRunReads.delete(url);
      }, runReadWindowMs);
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

  window.CASEPATH_RUNTIME_STABILITY = '19.0.0';
})();
