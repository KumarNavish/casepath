(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const list = $('#corpus-list');
  const packet = $('#corpus-packet');
  const search = $('#corpus-search');
  const language = $('#corpus-language');
  const files = $('#corpus-files');
  const more = $('#corpus-more');
  const count = $('#corpus-count');
  const rows = [];
  let selected = null;
  let visible = 20;
  let workbenchAvailable = false;

  const el = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value != null) node.textContent = value;
    return node;
  };
  const fileLabel = n => n === 0 ? 'Message only' : `${n} attachment${n === 1 ? '' : 's'}`;
  const languageLabel = code => code === 'de-CH' ? 'German' : code === 'en' ? 'English' : code;
  const date = value => new Intl.DateTimeFormat('en-GB', {dateStyle:'medium'}).format(new Date(value));
  const shortTitle = subject => subject.replace(/^(?:Please help me decide what to do|Request for (?:a detailed review|an initial view|review)|Unusual circumstances|Several details remain unclear|Documents still missing|Chronology still unclear|Dates still need confirmation|Question about my documents|Besonderer Umstand|Bitte um (?:Prüfung|erste Einschätzung)|Unterlagen fehlen|Mehrere Angaben sind unklar|Datumsangaben noch zu klären|Zeitliche Abfolge unklar|Sichere Einordnung erbeten|Dringende vertiefte Prüfung|Frage zu meinen Unterlagen):\s*/i, '').replace(/^./, char => char.toUpperCase());
  const matches = row => {
    const term = search.value.trim().toLocaleLowerCase();
    const haystack = `${row.subject} ${row.message} ${row.attachments.map(a => a.name).join(' ')}`.toLocaleLowerCase();
    return (!term || haystack.includes(term)) && (language.value === 'all' || language.value === row.language)
      && (files.value === 'all' || (files.value === 'with') === (row.attachments.length > 0));
  };

  function showPacket(row) {
    selected = row.claim_id;
    packet.replaceChildren();
    packet.setAttribute('aria-labelledby', 'corpus-packet-title');
    const top = el('div', 'corpus-packet-top');
    top.append(el('span', 'corpus-overline', 'Original intake packet'));
    const heading = el('h3', '', shortTitle(row.subject));
    heading.id = 'corpus-packet-title';
    heading.tabIndex = -1;
    top.append(heading);
    top.append(el('p', 'corpus-meta', `${languageLabel(row.language)} · Received ${date(row.received_at)} · ${fileLabel(row.attachments.length)}`));
    packet.append(top);
    const body = el('section', 'corpus-message');
    body.append(el('h4', '', 'Customer message'));
    body.append(el('p', '', row.message));
    packet.append(body);
    const attachments = el('section', 'corpus-attachments');
    attachments.append(el('h4', '', 'Files received'));
    if (!row.attachments.length) attachments.append(el('p', 'corpus-empty', 'No file was attached to this message.'));
    for (const file of row.attachments) {
      const item = el('div', 'corpus-attachment');
      item.append(el('strong', '', file.name));
      item.append(el('span', '', `${file.media_type === 'application/pdf' ? 'PDF' : file.media_type === 'image/jpeg' ? 'JPEG' : file.media_type} · ${Math.round(file.size_bytes / 1024)} KB`));
      attachments.append(item);
    }
    packet.append(attachments);
    const end = el('div', 'corpus-packet-end');
    const note = el('p', '', 'This view shows received material, not verified facts or a decision.');
    end.append(note);
    if (workbenchAvailable) {
      const link = el('a', 'corpus-open', 'Inspect originals in the workbench ↗');
      link.href = `/#claim=${encodeURIComponent(row.claim_id)}`;
      end.append(link);
    } else end.append(el('p', 'corpus-local', 'Run the local workbench to inspect original files and follow the handling path.'));
    const digest = el('details', 'corpus-binding');
    digest.append(el('summary', '', 'Source identity'));
    digest.append(el('p', '', `Original subject: ${row.subject}`));
    digest.append(el('code', '', `${row.claim_id} · binding SHA-256 ${row.binding_sha256}`));
    end.append(digest);
    packet.append(end);
    for (const button of list.querySelectorAll('button[data-claim-id]')) button.setAttribute('aria-current', String(button.dataset.claimId === selected));
  }

  function render() {
    const filtered = rows.filter(matches);
    count.textContent = `${filtered.length} of ${rows.length} claims`;
    list.replaceChildren();
    if (!filtered.length) {
      const empty = el('p', 'corpus-no-results', 'No claims match those filters.');
      list.append(empty);
      packet.replaceChildren(el('p', 'corpus-no-results', 'Change the search or filters to read a packet.'));
      packet.removeAttribute('aria-labelledby');
      more.hidden = true;
      return;
    }
    for (const row of filtered.slice(0, visible)) {
      const item = el('div', 'corpus-item');
      item.setAttribute('role', 'listitem');
      const button = el('button', '', '');
      button.type = 'button';
      button.dataset.claimId = row.claim_id;
      button.setAttribute('aria-current', String(row.claim_id === selected));
      button.append(el('strong', '', shortTitle(row.subject)));
      button.append(el('span', '', `${row.language === 'de-CH' ? 'DE' : 'EN'} · ${date(row.received_at)} · ${fileLabel(row.attachments.length)}`));
      button.addEventListener('click', () => {
        history.replaceState(null, '', `#${encodeURIComponent(row.claim_id)}`);
        showPacket(row);
        if (matchMedia('(max-width: 600px)').matches) {
          packet.scrollIntoView({block:'start'});
          packet.querySelector('#corpus-packet-title').focus({preventScroll:true});
        }
      });
      item.append(button);
      list.append(item);
    }
    more.hidden = filtered.length <= visible;
    const chosen = filtered.find(row => row.claim_id === selected) || filtered[0];
    showPacket(chosen);
  }

  async function start() {
    try {
      const response = await fetch('assets/corpus-index.json', {cache:'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.contract !== 'casepath.observable-corpus-index/1.0.0' || data.contains_reference_labels !== false || data.claims.length !== 150) throw new Error('Unexpected corpus index');
      rows.push(...data.claims);
      const featured = 'clm_f69b1747447bc221';
      rows.sort((a, b) => a.claim_id === featured ? -1 : b.claim_id === featured ? 1 : a.subject.localeCompare(b.subject));
      selected = rows.some(row => row.claim_id === location.hash.slice(1)) ? location.hash.slice(1) : featured;
      $('#corpus-browser').hidden = false;
      render();
      fetch('/api/claim-loops/v1/workspace/claims', {cache:'no-store'}).then(async response => {
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
        const queue = await response.json();
        if (queue.contract === 'casepath.claim-queue-projection/2.0.0') {
          workbenchAvailable = true;
          const row = rows.find(item => item.claim_id === selected);
          if (row) showPacket(row);
        }
      }).catch(() => {});
    } catch (_) {
      count.textContent = 'Unavailable';
      $('#corpus-error').hidden = false;
    }
  }
  search.addEventListener('input', () => {visible = 20; render();});
  language.addEventListener('change', () => {visible = 20; render();});
  files.addEventListener('change', () => {visible = 20; render();});
  more.addEventListener('click', () => {visible += 20; render();});
  void start();
})();
