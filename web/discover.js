/* Discover tab: deterministic browsing of collected public records (no model calls).
 * Builds every node with textContent (page text comes from external sites and is untrusted). */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);

  function h(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (value == null || value === false) continue;
      if (key === 'text') node.textContent = value;
      else if (key === 'className') node.className = value;
      else if (key === 'dataset') Object.assign(node.dataset, value);
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children.flat()) {
      if (child == null || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  // Only http(s) URLs become links (the server already filters them; this is defence in depth).
  // Anything else is shown as plain text, so a title never disappears.
  const extLink = (href, text, className = '') =>
    typeof href === 'string' && /^https?:\/\//i.test(href)
      ? h('a', { href, target: '_blank', rel: 'noopener noreferrer', className }, text,
        h('span', { 'aria-hidden': 'true', text: ' ↗' }), h('span', { className: 'sr-only', text: ' (opens in a new tab)' }))
      : (text ? h('span', {}, text) : null);

  const state = { data: null, interest: '', busy: false, seq: 0 };

  const SECTION_INFO = {
    this_week: { title: 'This week', empty: 'Nothing dated in the next 7 days matches your filters.' },
    coming: { title: 'Coming weeks', empty: 'Nothing later on matches your filters.' },
    ongoing: { title: 'Ongoing programs & communities', empty: 'No ongoing program or community matches your filters.' },
    date_unknown: { title: 'Date not stated', empty: '' },
  };
  const MODE_TEXT = {
    cached: ['Saved from last refresh', 'badge-info'],
    snapshot: ['Fixed snapshot', 'badge-warn'],
    live: ['Just refreshed', 'badge-ok'],
    unavailable: ['No data', 'badge-danger'],
  };

  function setStatus(text, tone = '') {
    const node = $('dc-status');
    node.textContent = text || '';
    if (tone) node.dataset.tone = tone;
    else delete node.dataset.tone;
  }

  async function getJson(url, options) {
    const res = await fetch(url, options);
    let body = null;
    try { body = await res.json(); } catch (_) { /* not JSON */ }
    return { ok: res.ok, status: res.status, body };
  }

  function query() {
    const p = new URLSearchParams();
    const q = $('dc-q').value.trim();
    if (q) p.set('q', q);
    if (state.interest) p.set('interest', state.interest);
    p.set('mode', $('dc-mode').value);
    p.set('when', $('dc-when').value);
    return p.toString();
  }

  async function load() {
    const seq = ++state.seq;
    try {
      const res = await getJson(`/api/discover?${query()}`);
      if (seq !== state.seq) return; // a newer request is on its way
      if (!res.ok || !res.body) throw new Error((res.body && res.body.error) || `HTTP ${res.status}`);
      state.data = res.body;
      render();
      if (!state.busy) {
        const n = ['this_week', 'coming', 'ongoing', 'date_unknown'].reduce((k, s) => k + state.data.sections[s].length, 0);
        setStatus(`${n} listing${n === 1 ? '' : 's'} shown.`);
      }
    } catch (err) {
      // Earlier data (if any) stays on screen; offer a retry instead of an empty page.
      setStatus(`Couldn’t load listings: ${err.message}. `, 'error');
      $('dc-status').append(h('button', {
        type: 'button', className: 'btn btn-secondary btn-sm',
        onclick: async () => {
          await load();
          if (!document.activeElement || document.activeElement === document.body) {
            ($('dc-status').querySelector('button') || $('dc-q')).focus(); // the new button if it failed again, else the search box
          }
        },
      }, 'Try again'));
    }
  }

  // ------------------------------------------------------------------ rendering

  function render() {
    const d = state.data;
    const w = d.windows;
    $('dc-notice').textContent =
      `${d.notice} Times are America/New_York · now ${w.now_text}.` + (d.fixed_now_for_test ? ' (TEST: fixed reference time)' : '');
    renderInterests();
    renderSources();
    renderSections();
    renderHidden();
  }

  function renderInterests() {
    const wrap = $('dc-interests');
    const options = [['', 'All interests'], ...Object.entries(state.data.interests)];
    const refocus = wrap.contains(document.activeElement); // keep keyboard focus on the chosen chip
    wrap.replaceChildren(...options.map(([key, label]) =>
      h('button', {
        type: 'button', className: 'chip dc-chip',
        'aria-pressed': String(state.interest === key),
        onclick: () => { state.interest = key; load(); },
      }, label)));
    if (refocus) {
      const chosen = wrap.querySelector('[aria-pressed="true"]');
      if (chosen) chosen.focus();
    }
  }

  function sourceCard(s) {
    const [modeText, modeTone] = MODE_TEXT[s.data_mode] || [s.data_mode, 'badge-muted'];
    let attempt;
    if (!s.last_outcome) {
      attempt = h('p', { className: 'small muted' },
        s.data_mode === 'snapshot'
          ? 'Not refreshed on this computer yet; showing the snapshot shipped with the app.'
          : 'Not refreshed yet.');
    } else if (s.last_outcome === 'failed') {
      attempt = h('p', { className: 'small dc-bad' },
        `Last refresh failed ${s.last_attempt_text} (${s.last_errors.join(', ') || 'error'})`,
        s.simulated ? ' — simulated outage (test mode)' : '',
        s.collected_at_text ? `. Still showing items collected ${s.collected_at_text}.` : '. No earlier data to show.');
    } else if (s.last_outcome === 'partial') {
      attempt = h('p', { className: 'small dc-warn' }, `Last refresh ${s.last_attempt_text} was partial (${s.last_errors.join(', ')}); missing pages keep their earlier data.`);
    } else if (s.last_outcome === 'empty') {
      attempt = h('p', { className: 'small dc-warn' }, `Last refresh ${s.last_attempt_text} found no listed items; earlier items are kept.`);
    } else {
      attempt = h('p', { className: 'small dc-good' }, `Last refresh OK ${s.last_attempt_text}.`);
    }
    return h('article', { className: 'dc-source' },
      h('div', { className: 'dc-source-head' },
        h('strong', {}, s.name),
        h('span', { className: `badge ${modeTone}` }, modeText)),
      h('p', { className: 'small muted' },
        `${s.publisher_type} · ${s.n_records} item${s.n_records === 1 ? '' : 's'}`,
        s.collected_at_text ? ` · collected ${s.collected_at_text}` : ''),
      attempt,
      h('p', { className: 'small' }, extLink(s.listing_url, 'Source listing')));
  }

  function renderSources() {
    const d = state.data;
    const notConnected = h('details', { className: 'dc-source dc-nc' },
      h('summary', { className: 'small' }, `Checked but not connected (${d.not_connected.length})`),
      h('ul', { className: 'small muted dc-list' }, d.not_connected.map((n) => h('li', {}, extLink(n.url, new URL(n.url).hostname), ` — ${n.reason}`))));
    $('dc-sources').replaceChildren(...d.sources.map(sourceCard), notConnected);
  }

  function badge(text, tone = 'badge-muted') { return text ? h('span', { className: `badge ${tone}` }, text) : null; }

  /**
   * One listing card; facts always come from the stored record.
   * opts.compact: for AI picks: no summary or keyword line (the AI reason and code checks go in opts.slot);
   *   opts.headingLevel: title element (h4 under the Find tab's h3 groups).
   * opts.badges: nodes put first in the badge row; opts.slot: nodes after the date line;
   * opts.after: nodes at the end of the card.
   */
  function card(c, opts = {}) {
    const compact = Boolean(opts.compact);
    const isProgram = c.kind !== 'event';
    let when;
    if (c.when_text) when = h('p', { className: 'dc-when' }, c.when_text);
    else if (c.next_session) {
      const more = c.upcoming_sessions.length - 1;
      when = h('p', { className: 'dc-when' }, `Next session: ${c.next_session.when_text}`,
        c.next_session.status_text ? h('span', { className: 'muted' }, ` · page shows “${c.next_session.status_text}”`) : null,
        more > 0 ? h('span', { className: 'muted' }, ` · ${more} more date${more === 1 ? '' : 's'} listed`) : null);
    } else when = h('p', { className: 'dc-when muted' }, c.date_text ? `${c.date_text} · no fixed date on the page` : 'No date on the page');

    const facts = h('dl', { className: 'dc-facts' },
      h('dt', {}, 'Where'), h('dd', {}, c.location_label || 'Not stated on the page'),
      h('dt', {}, 'Cost'), h('dd', {}, c.cost_label || 'Not stated on the page'),
      h('dt', {}, 'Organizer'), h('dd', {}, c.organizer || 'Not stated'));

    const elig = h('div', { className: 'dc-elig' },
      c.eligibility_open.length ? h('div', {}, h('p', { className: 'dc-elig-title dc-good' }, 'Stated as open'),
        h('ul', { className: 'dc-list' }, c.eligibility_open.map((t) => h('li', {}, t)))) : null,
      c.eligibility_check.length ? h('div', {}, h('p', { className: 'dc-elig-title dc-warn' }, 'Check before you go (not confirmed for you)'),
        h('ul', { className: 'dc-list' }, c.eligibility_check.map((t) => h('li', {}, t)))) : null,
      !c.eligibility_open.length && !c.eligibility_check.length
        ? h('p', { className: 'small muted' }, 'Who can join: not stated on the page — confirm with the organizer.') : null,
      c.deadline_text ? h('p', { className: 'small dc-warn' }, `Deadline as written on the page: “${c.deadline_text}”`) : null);

    const warnings = c.warnings.length
      ? h('ul', { className: 'dc-list dc-warn small' }, c.warnings.map((t) => h('li', {}, t))) : null;

    return h('article', { className: `card dc-card${compact ? ' dc-compact' : ''}` },
      h('div', { className: 'badge-row' },
        ...(opts.badges || []),
        badge(c.kind_label, isProgram ? 'badge-info' : 'badge-solid'),
        badge(c.publisher_type),
        badge(c.format_label || 'Format not stated', c.format_label ? 'badge-muted' : 'badge-warn'),
        c.session_this_week ? badge('Session this week', 'badge-ok') : null,
        c.data_mode === 'snapshot' ? badge('Snapshot data', 'badge-warn') : null),
      h(opts.headingLevel || 'h3', { className: 'dc-title' }, extLink(c.url, c.title)),
      when,
      ...(opts.slot || []),
      !compact && c.summary ? h('p', { className: 'small dc-summary' }, c.summary) : null,
      facts,
      elig, // the page's own eligibility wording stays visible, also next to a 'Match' badge
      warnings,
      c.not_stated.length ? h('p', { className: 'small muted' }, `Not stated on the page: ${c.not_stated.join(', ')}.`) : null,
      !compact && c.matched_terms.length ? h('p', { className: 'small muted' }, `Keyword match: ${c.matched_terms.join(', ')}`) : null,
      c.format_unknown_for_filter ? h('p', { className: 'small dc-warn' }, 'Shown because the page does not say whether it is in person or online.') : null,
      h('div', { className: 'dc-actions' },
        extLink(c.url, 'View original page', 'btn btn-primary btn-sm'),
        c.registration_url ? extLink(c.registration_url, 'Registration page', 'btn btn-secondary btn-sm') : null),
      c.registration_url ? h('p', { className: 'small muted' }, c.registration_note) : null,
      h('p', { className: 'small muted dc-foot' },
        `Source: ${c.source_name} · page collected ${c.collected_at_text}`,
        c.also_at.length ? ` · also listed at ${c.also_at.length} other page(s)` : ''),
      ...(opts.after || []));
  }

  /** Sub-label for a section heading, always from the server's windows (never computed here). */
  function sectionSub(w, key) {
    return {
      this_week: `${w.this_week.label} (next 7 days)`,
      coming: w.coming.label,
      ongoing: 'Courses, series and groups; each shows its next listed session',
      date_unknown: 'These pages give no date — check the source before planning',
    }[key];
  }

  function renderSections() {
    const d = state.data;
    const w = d.windows;
    const order = ['this_week', 'coming', 'ongoing', 'date_unknown'];
    const nodes = [];
    for (const key of order) {
      const items = d.sections[key];
      if (key === 'date_unknown' && !items.length) continue;
      if (d.filters.when !== 'all' && d.filters.when !== key) continue;
      nodes.push(h('section', { className: 'dc-section', 'aria-labelledby': `dc-h-${key}` },
        h('div', { className: 'dc-section-head' },
          h('h2', { id: `dc-h-${key}` }, SECTION_INFO[key].title, h('span', { className: 'dc-count' }, String(items.length))),
          h('span', { className: 'small muted' }, sectionSub(w, key))),
        items.length
          ? h('div', { className: 'dc-grid' }, items.map(card))
          : h('div', { className: 'empty dc-empty' }, h('p', {}, SECTION_INFO[key].empty))));
    }
    const total = order.reduce((n, k) => n + d.sections[k].length, 0);
    if (!total && d.sources.every((s) => s.data_mode === 'unavailable')) {
      nodes.unshift(h('div', { className: 'callout callout-danger callout-plain' },
        h('p', {}, 'No data has been collected yet and no snapshot is available. Press “Refresh sources” (needs internet).')));
    }
    $('dc-sections').replaceChildren(...nodes);
  }

  function renderHidden() {
    const c = state.data.counts;
    const parts = [];
    if (c.past_hidden) parts.push(`${c.past_hidden} past item${c.past_hidden === 1 ? '' : 's'} hidden`);
    if (c.filtered_out) parts.push(`${c.filtered_out} hidden by your filters`);
    if (c.duplicates_merged) parts.push(`${c.duplicates_merged} duplicate${c.duplicates_merged === 1 ? '' : 's'} merged`);
    const na = state.data.not_available;
    $('dc-hidden').replaceChildren(
      parts.length ? h('p', { className: 'small muted' }, parts.join(' · ') + '.') : '',
      na.length ? h('details', { className: 'dc-source' },
        h('summary', { className: 'small' }, `Not available to you (${na.length}) — ruled out by what the page says`),
        h('ul', { className: 'dc-list small' }, na.map((n) => h('li', {}, extLink(n.url, n.title), ` — ${n.reason}`)))) : '');
  }

  // ------------------------------------------------------------------ refresh

  async function refresh() {
    if (state.busy) return;
    state.busy = true;
    const btn = $('dc-refresh');
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    setStatus('Refreshing sources. This takes about a minute because the app waits between requests to respect each site.', 'info');
    let message = '';
    let tone = 'warn';
    try {
      const res = await getJson('/api/refresh', { method: 'POST' });
      if (!res.ok) {
        message = (res.body && res.body.error) || `Refresh failed (HTTP ${res.status}). Earlier results are still shown.`;
      } else {
        const lines = res.body.results.map((r) => {
          const name = (state.data && state.data.sources.find((s) => s.id === r.source_id) || {}).name || r.source_id;
          if (r.outcome === 'ok') return `${name}: updated (${r.n_records} items).`;
          if (r.outcome === 'partial') return `${name}: partly updated (${r.errors.join(', ')}).`;
          if (r.outcome === 'empty') return `${name}: no items listed; kept earlier items.`;
          return `${name}: refresh failed (${r.errors.join(', ') || 'error'})${r.simulated ? ' [simulated outage]' : ''}; ` +
            (r.collected_at_text ? `still showing items collected ${r.collected_at_text}.` : 'no earlier data.');
        });
        message = lines.join(' ');
        tone = res.body.results.some((r) => r.outcome === 'failed') ? 'warn' : 'ok';
      }
    } catch (err) {
      message = `Refresh request failed (${err.message}). Earlier results are still shown.`;
    } finally {
      state.busy = false;
      btn.disabled = false;
      btn.textContent = 'Refresh sources';
      await load();
      setStatus(message, tone); // after the reload, so the result stays visible
    }
  }

  // ------------------------------------------------------------------ init

  let qTimer = null;
  function init() {
    // Filters can come from the URL (?interest=photography&mode=online&when=ongoing&q=darkroom).
    const p = new URLSearchParams(location.search);
    if (p.get('q')) $('dc-q').value = p.get('q').slice(0, 100);
    if (p.get('interest')) state.interest = p.get('interest');
    for (const [key, id] of [['mode', 'dc-mode'], ['when', 'dc-when']]) {
      const v = p.get(key);
      if (v && [...$(id).options].some((o) => o.value === v)) $(id).value = v;
    }
    $('dc-filters').addEventListener('submit', (e) => { e.preventDefault(); load(); });
    $('dc-q').addEventListener('input', () => { clearTimeout(qTimer); qTimer = setTimeout(load, 300); });
    $('dc-mode').addEventListener('change', load);
    $('dc-when').addEventListener('change', load);
    $('dc-refresh').addEventListener('click', refresh);
    load();
  }

  // The Find tab renders verified picks with the same card (facts from the stored record) and labels.
  window.BYC = { renderCard: card, extLink, sectionSub, SECTION_INFO, MODE_TEXT, reload: () => load() };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
