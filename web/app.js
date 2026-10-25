/*
 * Beyond Your Circle UI (Find / Browse all / Usage). Plain ES2020, no dependencies, no build step.
 *
 * Sections: constants -> helpers -> markdown -> api -> state -> header -> ask form
 * -> cost card -> timeline -> result -> run lifecycle -> usage tab -> tabs -> init.
 *
 * Safety rule: model/tool text is only ever inserted with textContent, except the
 * markdown renderer, which HTML-escapes every fragment before adding its own tags.
 */
'use strict';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_MAX_CHARS = 8000;
const AGENT_PALETTE_SIZE = 6;

const STOP_REASONS = {
  final: { label: 'Completed', tone: 'ok' },
  incomplete: { label: 'The answer was cut off', tone: 'warn' },
  max_steps: { label: 'Stopped at the step limit', tone: 'warn' },
  budget: { label: 'Stopped by the budget cap', tone: 'warn' },
  timeout: { label: 'Stopped by the time limit', tone: 'warn' },
  blocked: { label: 'Blocked by safety screening', tone: 'danger' },
  error: { label: 'Failed with an error', tone: 'danger' },
};

const STOP_EXPLANATIONS = {
  incomplete: 'The AI stopped before finishing its answer (for example at its output limit), so nothing is shown as a recommendation. Try a shorter, more specific request.',
  max_steps: 'The AI used all of its allowed steps before finishing, so nothing is shown as a recommendation.',
  budget: 'A spending limit stopped this request, so no recommendation is shown. Nothing you entered was lost.',
  timeout: 'The whole search took longer than this app allows, so it was stopped and no recommendation is shown. Nothing you entered was lost.',
  blocked: 'The safety layer stopped this request. Please describe the kind of event or community you are looking for. Details are under “Run details”.',
  error: 'The AI step failed, so no recommendation is shown. Nothing you entered was lost. Details are under “Run details”.',
};
// When a run does not finish, the user can try again (same words and conditions) unless retrying cannot help.
const NO_RETRY = new Set(['setup', 'bad_request', 'blocked']);
const LONG_WAIT_MS = 45000;

const SAFETY_KINDS = {
  prompt_injection: 'Prompt injection',
  canary_leak: 'Canary leak',
  secret_leak: 'Secret leak',
  exfil_url: 'Suspicious URL',
  input_too_long: 'Input too long',
  tool_not_allowed: 'Tool not allowed',
  model_refusal: 'Model refusal',
  loop_cap: 'Step limit',
  tool_call_cap: 'Tool-call limit',
  depth_cap: 'Delegation depth limit',
  budget: 'Budget cap',
  run_timeout: 'Time limit',
  rate_limited: 'Rate limited',
};
const DANGER_ACTIONS = new Set(['blocked', 'stopped']);

const ERROR_COPY = {
  setup: {
    title: 'Add your Portkey API key',
    hint: 'After saving the .env file, restart the app and run your question again.',
  },
  rate_limited: {
    title: 'Too many runs in a short time',
    hint: 'The server limits how often runs can start. Wait a few minutes, then try again.',
  },
  network: {
    title: 'Can’t reach the server',
    hint: 'Make sure the app is still running (start.bat on Windows, ./start.sh on Mac/Linux). Your request stays in the box; press Try again.',
  },
  bad_request: { title: 'The request was rejected', hint: 'Edit your request and press Find again.' },
  server: { title: 'The AI step failed', hint: 'Nothing you entered was lost. Try again, or browse the listings without AI.' },
  timeout: { title: 'The AI model did not answer in time', hint: 'Nothing you entered was lost. Try again in a minute, or browse the listings without AI.' },
  stream: { title: 'The connection ended before the search finished', hint: 'Nothing you entered was lost. Try again, or browse the listings without AI.' },
};

const USAGE_KEYS = ['input_tokens', 'cached_tokens', 'cache_write_tokens', 'output_tokens', 'reasoning_tokens'];

// 24x24 stroke icons, drawn with createElementNS (no innerHTML).
const ICONS = {
  play: ['M8 5.5v13l10.5-6.5z'],
  stop: ['M7 7h10v10H7z'],
  message: ['M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-5 4v-4H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'],
  spark: ['M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9-1.9 5.1-1.9-5.1-5.1-1.9 5.1-1.9z', 'M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z'],
  tool: ['M14.5 5.5a4 4 0 0 0-5 5L4 16v4h4l5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-3-1-1-3z'],
  arrow: ['M4 12h15', 'M13 6l6 6-6 6'],
  shield: ['M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6z', 'M12 8.5v4', 'M12 15.5h.01'],
  check: ['M5 12.5l4.5 4.5L19 7.5'],
  checkCircle: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z', 'M8 12.5l2.7 2.7L16.5 9.5'],
  flag: ['M5 21V4', 'M5 4h12l-2.5 4.5L17 13H5'],
  alert: ['M12 3.5L2.5 20h19z', 'M12 10v4.5', 'M12 17.5h.01'],
  info: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z', 'M12 11v5', 'M12 8h.01'],
  x: ['M6 6l12 12', 'M18 6L6 18'],
  book: ['M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z', 'M4 19V5', 'M8 7h7'],
  refresh: ['M20 11a8 8 0 1 0-2.3 5.7', 'M20 4v7h-7'],
};

// ---------------------------------------------------------------------------
// Helpers: DOM, numbers, text
// ---------------------------------------------------------------------------

const byId = (id) => document.getElementById(id);
const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

/** Create an element. String children become text nodes, so they are never parsed as HTML. */
function el(tag, props, ...children) {
  const node = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value == null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = String(value);
      else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : String(value));
    }
  }
  appendChildren(node, children);
  return node;
}

function appendChildren(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false || child === '') continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/** Like replaceChildren, but skips null/false instead of inserting the text "null". */
function setChildren(node, ...children) {
  node.replaceChildren();
  return appendChildren(node, children);
}

function icon(name) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  for (const d of ICONS[name] || ICONS.info) {
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', d);
    svg.append(path);
  }
  return svg;
}

const spinner = () => el('span', { class: 'spinner', 'aria-hidden': 'true' });
const badge = (text, tone = 'info', iconName = null) =>
  el('span', { class: `badge badge-${tone}` }, iconName ? icon(iconName) : null, text);
const metaChip = (text, mono = false) => el('span', { class: mono ? 'meta-chip mono' : 'meta-chip', text });

const intFormat = new Intl.NumberFormat('en-US');
const fmtInt = (v) => intFormat.format(Math.round(num(v)));
const fmtUsd6 = (v) => (v == null ? "cost not measured" : `$${num(v).toFixed(6)}`);
const fmtPct = (ratio) => `${(num(ratio) * 100).toFixed(1)}%`;
const fmtSeconds = (ms) => `${(Math.max(0, num(ms)) / 1000).toFixed(1)} s`;
const fmtDuration = (ms) => (num(ms) < 1000 ? `${Math.round(num(ms))} ms` : fmtSeconds(ms));
const plural = (n, word, many = `${word}s`) => `${fmtInt(n)} ${Math.round(num(n)) === 1 ? word : many}`;
const humanize = (s) => String(s || '').replace(/_/g, ' ');

/** Money with sensible precision: $1,234.56 / $0.05 / $0.0123 / $0.000123. */
function fmtMoney(v) {
  const x = num(v);
  const abs = Math.abs(x);
  if (abs === 0) return '$0.00';
  if (abs >= 1) return `$${x.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (abs >= 0.01) {
    const trimmed = x.toFixed(4).replace(/0+$/, ''); // 0.0500 -> 0.05, 0.1250 -> 0.125
    return `$${(trimmed.split('.')[1] || '').length < 2 ? x.toFixed(2) : trimmed}`;
  }
  return `$${x.toFixed(6)}`;
}

/** Per-1M-token price: $0.10, $0.01, $0.125. */
const fmtPrice = (v) => `$${num(v).toFixed(3).replace(/0$/, '')}`;

function parseTs(iso) {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
}

/** Times are shown in America/New_York, like the listings (not in the browser's own zone). */
function fmtDateTime(iso) {
  const t = parseTs(iso);
  if (t == null) return String(iso || '');
  try {
    return `${new Date(t).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} ET`;
  } catch (err) {
    return new Date(t).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
}

function clip(text, limit) {
  const s = String(text ?? '');
  return s.length > limit ? `${s.slice(0, limit - 1)}…` : s;
}

function normalizeUsage(raw) {
  const src = isObj(raw) ? raw : {};
  const usage = {};
  for (const key of USAGE_KEYS) usage[key] = num(src[key]);
  usage.uncached_input_tokens = Math.max(0, usage.input_tokens - usage.cached_tokens - usage.cache_write_tokens);
  usage.total_tokens = usage.input_tokens + usage.output_tokens;
  return usage;
}

const cacheHitRate = (usage) => (usage.input_tokens > 0 ? usage.cached_tokens / usage.input_tokens : null);

function stopReasonInfo(reason) {
  return STOP_REASONS[reason] || { label: humanize(reason) || 'Unknown', tone: 'info' };
}

function prettyJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch (err) {
    return String(value);
  }
}

// ---------------------------------------------------------------------------
// Tiny safe markdown: headings, bold, italics, inline code, lists, paragraphs.
// The whole source is HTML-escaped FIRST; the parser then only adds its own tags.
// (Escaping touches & < > " ' only, so the markdown markers survive it.)
// ---------------------------------------------------------------------------

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

/** `escaped` must already be HTML-escaped. */
function renderInline(escaped) {
  const codes = [];
  let html = escaped.replace(/`([^`\n]+)`/g, (_, code) => {
    codes.push(code);
    return `\u0000${codes.length - 1}\u0000`;
  });
  html = html
    .replace(/\*\*(?=\S)([^\n]*?\S)\*\*/g, '<strong>$1</strong>')
    .replace(/__(?=\S)([^\n]*?\S)__/g, '<strong>$1</strong>')
    .replace(/(^|[^\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])/g, '$1<em>$2</em>')
    .replace(/(^|[^\w])_(?=\S)([^_\n]*?\S)_(?!\w)/g, '$1<em>$2</em>');
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[Number(i)]}</code>`);
}

function renderMarkdown(source) {
  const text = String(source ?? '').replace(/\u0000/g, '').replace(/\r\n?/g, '\n');
  const lines = escapeHtml(text).split('\n');
  const out = [];
  let paragraph = [];
  let list = null; // { tag: 'ul' | 'ol', items: [] }

  const flushParagraph = () => {
    if (paragraph.length) out.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (list) out.push(`<${list.tag}>${list.items.map((item) => `<li>${renderInline(item)}</li>`).join('')}</${list.tag}>`);
    list = null;
  };
  const pushItem = (tag, text) => {
    flushParagraph();
    if (!list || list.tag !== tag) {
      flushList();
      list = { tag, items: [] };
    }
    list.items.push(text);
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '');
    let m;
    if (!line.trim()) {
      flushParagraph();
      flushList();
    } else if ((m = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*$/.exec(line))) {
      flushParagraph();
      flushList();
      const level = Math.min(6, m[1].length + 2); // the card already owns h2
      out.push(`<h${level}>${renderInline(m[2])}</h${level}>`);
    } else if (/^\s{0,3}([-*_])(\s*\1){2,}\s*$/.test(line)) {
      flushParagraph();
      flushList();
      out.push('<hr>');
    } else if ((m = /^\s*[-*+•]\s+(.*)$/.exec(line))) {
      pushItem('ul', m[1]);
    } else if ((m = /^\s*\d{1,3}[.)]\s+(.*)$/.exec(line))) {
      pushItem('ol', m[1]);
    } else if (list && /^\s{2,}\S/.test(raw)) {
      list.items[list.items.length - 1] += ` ${line.trim()}`; // wrapped list item
    } else {
      flushList();
      paragraph.push(line.trim());
    }
  }
  flushParagraph();
  flushList();
  return out.join('');
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(kind, message, status, retryAfterS = 0) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status || 0;
    this.retryAfterS = retryAfterS;
  }
}

function errorMessageFrom(body) {
  if (!isObj(body)) return '';
  if (typeof body.error === 'string') return body.error;
  if (isObj(body.error) && typeof body.error.message === 'string') return body.error.message;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((d) => (isObj(d) ? d.msg : '')).filter(Boolean).join('; ');
  if (typeof body.message === 'string') return body.message;
  return '';
}

const api = {
  async json(path) {
    let res;
    try {
      res = await fetch(path, { headers: { Accept: 'application/json' }, cache: 'no-store' });
    } catch (err) {
      throw new ApiError('network', 'Could not reach the server.');
    }
    const body = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError('http', errorMessageFrom(body) || `Request failed (HTTP ${res.status}).`, res.status);
    return body;
  },

  health: () => api.json('/api/health'),
  meta: () => api.json('/api/meta'),
  stats: () => api.json('/api/stats'),
  runs: () => api.json('/api/runs'),
  trace: (runId) => api.json(`/api/runs/${encodeURIComponent(runId)}`),

  /** POST /api/run (with the form conditions, only if any is set) and call onEvent for every NDJSON line. */
  async streamRun(input, options, signal, onEvent) {
    let res;
    try {
      res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
        body: JSON.stringify(options ? { input, options } : { input }),
        signal,
      });
    } catch (err) {
      if (err && err.name === 'AbortError') throw err;
      throw new ApiError('network', 'Could not reach the server.');
    }

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const message = errorMessageFrom(body);
      if (res.status === 429) throw new ApiError('rate_limited', message || 'Rate limit reached.', 429, num(body && body.retry_after_s));
      if (res.status === 400 || res.status === 413) throw new ApiError('bad_request', message || 'The question was empty or invalid.', res.status);
      throw new ApiError('server', message || `The server answered with HTTP ${res.status}.`, res.status);
    }

    const handleLine = (line) => {
      const text = line.trim();
      if (!text) return;
      try {
        const event = JSON.parse(text);
        if (isObj(event) && typeof event.type === 'string') onEvent(event);
      } catch (err) {
        console.warn('Skipping a malformed event line from the server.');
      }
    };

    if (!res.body || typeof res.body.getReader !== 'function') {
      (await res.text()).split('\n').forEach(handleLine);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      let chunk;
      try {
        chunk = await reader.read();
      } catch (err) {
        if (err && err.name === 'AbortError') throw err;
        throw new ApiError('stream', 'The connection was lost while the run was in progress.');
      }
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      let newline;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        handleLine(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
      }
    }
    handleLine(buffer + decoder.decode());
  },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  health: null,
  meta: null,
  agentSlots: new Map(), // agent name -> colour slot, in order of first appearance
  running: false,
  controller: null,
  run: null,
  timer: null,
  usageStale: true,
  usageLoading: false,
  lastRequest: null, // { input, options } of the latest live run, for Try again
  lastGood: null, // { nodes, input, options, at } of the latest live run that finished with results
  retryBlockedUntil: 0, // ms timestamp; set from a 429's retry_after_s
};

/** Timeline bookkeeping for the run currently on screen. */
const tl = {
  list: null,
  stack: [], // open agent groups: { name, depth, li, body, status }
  tools: new Map(), // call_id -> { li, status, result }
  openTools: 0,
  pending: null,
  active: null,
};

function newRun({ live, runId = null }) {
  return {
    live,
    runId,
    startedMs: Date.now(),
    endedMs: null,
    firstTs: null,
    lastTs: null,
    lastType: null,
    events: [],
    modelCalls: 0,
    usage: normalizeUsage(null),
    costUsd: 0,
    durationMs: null,
    inputPreview: '',
    options: null, // conditions set with the form (from run_started)
    final: null,
    error: null, // { kind, message }
    warnings: [], // non-fatal (e.g. the extra AI safety check was unavailable)
    cancelled: false,
    progress: { screened: false, searched: false, read: 0, checked: false },
  };
}

const dom = {};

function bindDom() {
  const ids = [
    'app-title', 'app-tagline', 'pill-model', 'pill-key', 'pill-spend', 'banner', 'version',
    'tab-run', 'tab-usage', 'panel-run', 'panel-usage',
    'ask-form', 'input', 'char-count', 'kbd-hint', 'run-btn', 'stop-btn', 'clear-btn',
    'ask-options', 'opt-som', 'opt-mode', 'opt-when', 'run-details', 'go-ask',
    'examples-wrap', 'examples', 'limits-note', 'status',
    'result', 'result-badges',
    'cost-state', 'cost-usd', 'cost-calls', 'cost-cache', 'cost-elapsed', 'mix-bar',
    'seg-cached', 'seg-write', 'seg-uncached',
    'tok-input', 'tok-cached', 'tok-write', 'tok-output', 'tok-reasoning', 'tok-uncached',
    'timeline', 'timeline-meta', 'expand-btn',
    'refresh-usage', 'usage-status', 'stats-tiles', 'avg-table', 'dist-table', 'proj-table', 'assumptions', 'runs-table',
  ];
  for (const id of ids) dom[id.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = byId(id);
}

function setStatus(node, text, tone = '') {
  node.textContent = text || '';
  if (tone && text) node.dataset.tone = tone;
  else delete node.dataset.tone;
}

// ---------------------------------------------------------------------------
// Agents (colour + meta lookups)
// ---------------------------------------------------------------------------

function agentSlot(name) {
  const key = String(name || '?');
  if (!state.agentSlots.has(key)) state.agentSlots.set(key, state.agentSlots.size % AGENT_PALETTE_SIZE);
  return state.agentSlots.get(key);
}

function agentInfo(name) {
  const agents = state.meta && Array.isArray(state.meta.agents) ? state.meta.agents : [];
  return agents.find((a) => isObj(a) && a.name === name) || null;
}

function agentChip(name) {
  const info = agentInfo(name);
  return el('span', { class: `agent-chip agent-c${agentSlot(name)}`, title: info && info.role ? info.role : null, text: name || 'agent' });
}

// ---------------------------------------------------------------------------
// Header: title, status pills, setup banner
// ---------------------------------------------------------------------------

function setPill(node, label, value, tone = 'neutral', extra = null) {
  setChildren(node, el('span', { class: 'pill-label', text: label }), ' ', el('span', { class: 'pill-value', text: value }), extra);
  node.dataset.tone = tone;
}

function showBanner(tone, title, text) {
  dom.banner.replaceChildren(callout(tone, title, text));
  dom.banner.hidden = false;
}

function renderHealth() {
  const health = state.health;
  if (!health) {
    setPill(dom.pillModel, 'Server', 'offline', 'bad');
    setPill(dom.pillKey, 'API key', 'unknown');
    showBanner('danger', ERROR_COPY.network.title, ERROR_COPY.network.hint);
    return;
  }
  setPill(dom.pillModel, 'Model', health.model || 'unknown');
  const ok = Boolean(health.key_configured);
  setPill(dom.pillKey, 'API key', ok ? '✓ configured' : '✗ missing', ok ? 'neutral' : 'bad');
  const files = Array.isArray(health.env_files) ? health.env_files : [];
  dom.pillKey.title = files.length ? `Loaded from: ${files.join(', ')}` : 'No .env file found';
  dom.version.textContent = health.version ? ` · v${health.version}` : '';
  if (health.simulated_llm) {
    // Labelled demo mode: every screenshot of this server shows that AI failures are simulated.
    setPill(dom.pillModel, 'Model', 'TEST MODE (simulated)', 'warn');
    showBanner(
      'warn',
      'TEST MODE: AI failures are simulated on this server',
      `It was started with LLM_SIMULATE=${health.simulated_llm}: every AI search fails on purpose after a short delay and no real model is called. Browsing the listings works normally.`
    );
    return;
  }
  if (ok) {
    dom.banner.hidden = true;
    dom.banner.replaceChildren();
  } else {
    showBanner(
      'warn',
      'Setup needed: add your Portkey API key',
      'Create a file named .env in the project folder (or the folder above it) with the line PORTKEY_API_KEY=your-key, ' +
        'then restart the app. The key stays on the server and is never shown on this page.'
    );
  }
}

function renderMeta() {
  const meta = state.meta || {};
  const title = meta.title || 'Beyond Your Circle';
  document.title = title;
  dom.appTitle.textContent = title;
  dom.appTagline.textContent = meta.tagline || 'Public Yale and New Haven events, programs and communities, with sources.';
  (Array.isArray(meta.agents) ? meta.agents : []).forEach((a) => isObj(a) && agentSlot(a.name));

  const examples = Array.isArray(meta.examples) ? meta.examples.filter((x) => typeof x === 'string' && x.trim()) : [];
  dom.examples.replaceChildren(
    ...examples.map((text) =>
      el('li', null, el('button', { type: 'button', class: 'chip', title: 'Use this example', onclick: () => useExample(text) }, text))
    )
  );
  dom.examplesWrap.hidden = examples.length === 0;

  const limits = isObj(meta.limits) ? meta.limits : {};
  const parts = [];
  if (limits.run_budget_usd != null) parts.push(`${fmtMoney(limits.run_budget_usd)} max per run`);
  if (limits.daily_budget_usd != null) parts.push(`${fmtMoney(limits.daily_budget_usd)} daily cap`);
  dom.limitsNote.textContent = parts.join(' · ');
  updateCounter();
  if (!state.run) renderTimelineEmpty();
}

/**
 * Today's spend comes from the server's today_cost_usd (/api/meta, /api/stats): the same ledger
 * figure the daily cap is checked against. /api/runs is capped at 50 runs, so summing it would
 * under-report.
 */
function renderSpend(spent) {
  if (typeof spent !== 'number' || !Number.isFinite(spent)) {
    setPill(dom.pillSpend, 'Today', '–');
    return;
  }
  const limits = state.meta && isObj(state.meta.limits) ? state.meta.limits : {};
  const cap = num(limits.daily_budget_usd);
  if (!cap) {
    setPill(dom.pillSpend, 'Today', fmtMoney(spent), limits.daily_budget_usd === 0 ? 'warn' : 'neutral');
    if (limits.daily_budget_usd === 0 && !state.running && !state.run) {
      setStatus(dom.status, 'AI matching is switched off on this server (daily AI budget $0): Find will stop before calling the AI. Browse all still works.', 'warn');
    }
    return;
  }
  if (spent >= cap && !state.running && !state.run) {
    // The server check is authoritative (Find still works and stops before any model call); just warn early.
    setStatus(dom.status, 'Today’s AI budget for this app is used up, so Find will stop before calling the AI. Browse all still works.', 'warn');
  }
  const ratio = Math.min(1, spent / cap);
  const tone = ratio >= 0.9 ? 'bad' : ratio >= 0.6 ? 'warn' : 'neutral';
  const meter = el('span', { class: 'pill-meter', 'aria-hidden': 'true' }, el('span', { style: `width:${(ratio * 100).toFixed(1)}%` }));
  setPill(dom.pillSpend, 'Today', `${fmtMoney(spent)} / ${fmtMoney(cap)}`, tone, meter);
  dom.pillSpend.title = `Spent today (UTC) across all runs: ${fmtUsd6(spent)} of the ${fmtMoney(cap)} daily cap`;
}

async function refreshSpend() {
  try {
    const data = await api.meta();
    renderSpend(isObj(data) ? data.today_cost_usd : null);
  } catch (err) {
    renderSpend(null);
  }
}

async function refreshHealth() {
  try {
    state.health = await api.health();
  } catch (err) {
    state.health = null;
  }
  renderHealth();
}

// ---------------------------------------------------------------------------
// Ask form
// ---------------------------------------------------------------------------

function maxChars() {
  const limits = state.meta && isObj(state.meta.limits) ? state.meta.limits : {};
  return num(limits.max_input_chars) || DEFAULT_MAX_CHARS;
}

function updateCounter() {
  const n = dom.input.value.length;
  const max = maxChars();
  dom.charCount.textContent = `${fmtInt(n)} / ${fmtInt(max)}${n > max ? ' – too long' : ''}`;
  dom.charCount.classList.toggle('is-near', n > max * 0.9 && n <= max);
  dom.charCount.classList.toggle('is-over', n > max);
}

function useExample(text) {
  if (state.running) return;
  dom.input.value = text;
  updateCounter();
  dom.input.focus();
  setStatus(dom.status, 'Example added. Press Find when you are ready (each search is one AI run).');
}

/** The form conditions the user actually set (enums only), or null. "Not set" fields are left out. */
function readOptions() {
  const options = {};
  if (dom.optSom.checked) options.som_student = true;
  if (dom.optMode.value) options.participation = dom.optMode.value;
  if (dom.optWhen.value) options.time_window = dom.optWhen.value;
  return Object.keys(options).length ? options : null;
}

const OPTION_TEXT = {
  som_student: () => 'Yale SOM graduate student',
  participation: (v) => ({ in_person: 'in person', online: 'online', either: 'in person or online' }[v] || humanize(v)),
  time_window: (v) => ({ this_week: 'next 7 days', next_few_weeks: 'next 4 weeks' }[v] || humanize(v)),
};

function describeOptions(options) {
  if (!isObj(options)) return '';
  return Object.entries(options).map(([k, v]) => (OPTION_TEXT[k] ? OPTION_TEXT[k](v) : `${humanize(k)}: ${v}`)).join(' · ');
}

function setRunningUi(running) {
  dom.runBtn.disabled = running || Date.now() < state.retryBlockedUntil;
  dom.runBtn.replaceChildren(...(running ? [spinner(), 'Searching…'] : [icon('spark'), 'Find']));
  dom.stopBtn.hidden = !running;
  dom.clearBtn.disabled = running;
  dom.askOptions.disabled = running;
  dom.askForm.setAttribute('aria-busy', String(running));
  dom.examples.querySelectorAll('button').forEach((b) => {
    b.disabled = running;
  });
}

/** Results on screen were made with other conditions than the form now shows: say so (no automatic re-run). */
function onOptionsChanged() {
  const run = state.run;
  if (state.running || !run || !run.live || !run.final) return;
  const now = JSON.stringify(readOptions());
  const then = JSON.stringify(run.options || null);
  if (now !== then) setStatus(dom.status, 'Conditions changed. The results below still use the earlier ones; press Find to search again (a new AI run).', 'warn');
  else setStatus(dom.status, '');
}

// ---------------------------------------------------------------------------
// Cost card (live from model_call.data.run_usage / run_cost_usd, final from final.data)
// ---------------------------------------------------------------------------

function elapsedMs(run) {
  if (!run) return 0;
  if (run.durationMs != null) return run.durationMs;
  if (run.live) return (run.endedMs || Date.now()) - run.startedMs;
  return run.firstTs != null && run.lastTs != null ? run.lastTs - run.firstTs : 0;
}

function renderCost() {
  const run = state.run;
  const usage = run ? run.usage : normalizeUsage(null);
  dom.costUsd.textContent = fmtUsd6(run ? run.costUsd : 0);
  dom.costCalls.textContent = fmtInt(run ? run.modelCalls : 0);
  const hit = cacheHitRate(usage);
  dom.costCache.textContent = hit == null ? '–' : fmtPct(hit);
  dom.costElapsed.textContent = fmtSeconds(elapsedMs(run));

  dom.tokInput.textContent = fmtInt(usage.input_tokens);
  dom.tokCached.textContent = fmtInt(usage.cached_tokens);
  dom.tokWrite.textContent = fmtInt(usage.cache_write_tokens);
  dom.tokOutput.textContent = fmtInt(usage.output_tokens);
  dom.tokReasoning.textContent = fmtInt(usage.reasoning_tokens);
  dom.tokUncached.textContent = fmtInt(usage.uncached_input_tokens);

  const total = usage.input_tokens;
  const share = (n) => (total > 0 ? (Math.min(n, total) / total) * 100 : 0);
  const segments = [
    [dom.segCached, usage.cached_tokens, 'cached'],
    [dom.segWrite, usage.cache_write_tokens, 'cache write'],
    [dom.segUncached, usage.uncached_input_tokens, 'uncached'],
  ];
  for (const [node, value, label] of segments) {
    node.style.width = `${share(value).toFixed(2)}%`;
    node.title = `${label}: ${fmtInt(value)} tokens (${share(value).toFixed(1)}%)`;
  }
  dom.mixBar.setAttribute(
    'aria-label',
    total > 0
      ? `Input tokens: ${segments.map(([, value, label]) => `${share(value).toFixed(0)}% ${label}`).join(', ')}`
      : 'No input tokens yet'
  );
  renderCostState();
}

function renderCostState() {
  const run = state.run;
  let node;
  if (!run) node = badge('Idle', 'muted');
  else if (!run.live) node = badge('Replay', 'info');
  else if (state.running && !run.final) node = el('span', { class: 'badge badge-info badge-live' }, 'Live');
  else if (run.cancelled) node = badge('Cancelled', 'warn');
  else if (run.final && run.final.ok !== false) node = badge('Final', 'ok', 'check');
  else node = badge(run.final ? 'Stopped' : 'Failed', 'danger');
  node.id = 'cost-state';
  dom.costState.replaceWith(node);
  dom.costState = node;
}

function startTimer() {
  stopTimer();
  state.timer = window.setInterval(() => {
    const run = state.run;
    dom.costElapsed.textContent = fmtSeconds(elapsedMs(run));
    if (run && run.live && state.running && !run.final && !run.longWaitShown && elapsedMs(run) > LONG_WAIT_MS) {
      run.longWaitShown = true;
      setStatus(dom.status, 'Still searching: this is taking longer than usual. You can press Stop and try again.', 'busy');
      renderResult();
    }
  }, 200);
}

function stopTimer() {
  if (state.timer) window.clearInterval(state.timer);
  state.timer = null;
}

// ---------------------------------------------------------------------------
// Timeline
// ---------------------------------------------------------------------------

function renderTimelineEmpty() {
  const meta = state.meta || {};
  const agents = Array.isArray(meta.agents) ? meta.agents.filter(isObj) : [];
  const team = agents.length
    ? el(
        'ul',
        { class: 'team', 'aria-label': 'Agent team' },
        agents.map((a) => {
          const tools = Array.isArray(a.tools) ? a.tools : [];
          const subs = Array.isArray(a.sub_agents) ? a.sub_agents : [];
          const caps = [];
          if (subs.length) caps.push(`delegates to ${subs.join(', ')}`);
          if (tools.length) caps.push(`tools: ${tools.join(', ')}`);
          return el(
            'li',
            null,
            agentChip(a.name),
            el('span', null, el('span', { class: 'team-role', text: a.role || '' }), caps.length ? el('span', { class: 'team-sub', text: caps.join(' · ') }) : null)
          );
        })
      )
    : null;

  dom.timeline.replaceChildren(
    el(
      'div',
      { class: 'empty' },
      el('div', { class: 'empty-icon' }, icon('spark')),
      el('h3', { text: 'Run a search to see each step' }),
      el('p', { text: 'Each step appears here live: the safety check, the AI matcher and the listing tools it calls, the code checks, and what every model call cost.' }),
      team
    )
  );
  dom.timelineMeta.replaceChildren();
  dom.expandBtn.hidden = true;
  tl.list = null;
  tl.stack = [];
  tl.tools = new Map();
  tl.openTools = 0;
  tl.pending = null;
  tl.active = null;
}

function resetTimeline() {
  tl.list = el('ol', { class: 'tl' });
  tl.stack = [];
  tl.tools = new Map();
  tl.openTools = 0;
  tl.pending = null;
  tl.active = null;
  dom.timeline.replaceChildren(tl.list);
  dom.timeline.scrollTop = 0;
  dom.expandBtn.hidden = false;
  setExpandState(false);
}

function renderTimelineMeta() {
  const run = state.run;
  if (!run) {
    dom.timelineMeta.replaceChildren();
    return;
  }
  setChildren(dom.timelineMeta, run.live ? null : badge('Replay', 'info', 'refresh'), run.runId ? metaChip(run.runId, true) : null);
}

function timeOffset(ev) {
  const run = state.run;
  const t = parseTs(ev && ev.ts);
  if (t == null || !run || run.firstTs == null) return '';
  return `+${(Math.max(0, t - run.firstTs) / 1000).toFixed(1)}s`;
}

/** One timeline row: icon, content, relative time. */
function tlItem({ kind, iconName, tone = null, title = null, body = null, ev = null }) {
  return el(
    'li',
    { class: `tl-item tl-${kind}${tone ? ` tone-${tone}` : ''}` },
    el('span', { class: 'tl-icon' }, icon(iconName)),
    el('div', { class: 'tl-main' }, title ? el('div', { class: 'tl-title' }, title) : null, body),
    el('time', { class: 'tl-time', datetime: ev && ev.ts ? ev.ts : null, text: timeOffset(ev) })
  );
}

function detailsBlock(summary, bodyNodes, extraClass = '') {
  return el('details', { class: `tl-details ${extraClass}`.trim() }, el('summary', null, summary), el('div', { class: 'tl-detail-body' }, bodyNodes));
}

/** Innermost open group for this agent, or the root list. */
function containerFor(agent) {
  for (let i = tl.stack.length - 1; i >= 0; i -= 1) {
    if (tl.stack[i].name === agent) return { body: tl.stack[i].body, grouped: true };
  }
  return { body: tl.list, grouped: false };
}

function setGroupStatus(group, kind, label) {
  const content = {
    running: [spinner(), 'working'],
    done: [icon('check'), 'done'],
    stopped: [icon('stop'), label || 'stopped'],
    error: [icon('x'), label || 'error'],
    interrupted: [icon('stop'), label || 'interrupted'],
  }[kind];
  group.status.className = `g-status g-${kind}`;
  group.status.replaceChildren(...content);
  group.li.dataset.state = kind;
}

/** Close every open group above index `from` (inclusive) with the given status. */
function closeGroups(from, kind, label) {
  for (let i = tl.stack.length - 1; i >= from; i -= 1) setGroupStatus(tl.stack[i], kind, label);
  tl.stack.length = Math.max(0, from);
}

function onRunStarted(ev, d) {
  tl.list.append(
    tlItem({
      kind: 'run',
      iconName: 'play',
      ev,
      title: ['Run started', ev.run_id ? metaChip(ev.run_id, true) : null],
      body: d.input_preview ? el('p', { class: 'tl-quote', text: d.input_preview }) : null,
    })
  );
}

function onAgentStarted(ev, d) {
  const name = ev.agent || 'agent';
  const depth = Math.max(0, Math.round(num(d.depth)));
  const parent = depth > 0 && tl.stack.length ? tl.stack[tl.stack.length - 1].body : tl.list;
  const info = agentInfo(name);
  const status = el('span', { class: 'g-status' });
  const body = el('ol', { class: 'tl-body' });
  const li = el(
    'li',
    { class: `tl-group agent-c${agentSlot(name)}`, 'data-depth': depth, 'aria-label': `Agent ${name}, depth ${depth}` },
    el(
      'div',
      { class: 'tl-group-head' },
      agentChip(name),
      info && info.role ? el('span', { class: 'tl-role', text: info.role }) : null,
      depth > 0 ? metaChip(`depth ${depth}`) : null,
      status
    ),
    body
  );
  parent.append(li);

  const tools = Array.isArray(d.tools) ? d.tools : [];
  const subs = info && Array.isArray(info.sub_agents) ? info.sub_agents : [];
  const caps = [];
  caps.push(tools.length ? `Allowed tools: ${tools.join(', ')}` : 'No direct tools');
  if (subs.length) caps.push(`can delegate to ${subs.join(', ')}`);
  body.append(
    tlItem({
      kind: 'task',
      iconName: 'message',
      ev,
      title: 'Task received',
      body: [d.task_preview ? el('p', { class: 'tl-quote', text: d.task_preview }) : null, el('p', { class: 'tl-sub', text: caps.join(' · ') })],
    })
  );

  const group = { name, depth, li, body, status };
  tl.stack.push(group);
  setGroupStatus(group, 'running');
}

function onModelCall(ev, d, where) {
  const usage = normalizeUsage(d.usage);
  const hit = cacheHitRate(usage);
  const nCalls = num(d.n_function_calls);
  const summary = [
    where.grouped || !ev.agent ? null : agentChip(ev.agent),
    'Model call',
    d.step != null ? metaChip(`step ${d.step}`) : null,
    metaChip(`${fmtInt(usage.total_tokens)} tok`),
    hit ? metaChip(`${Math.round(hit * 100)}% cached`) : null,
    d.latency_ms != null ? metaChip(fmtDuration(d.latency_ms)) : null,
    metaChip(fmtUsd6(d.cost_usd)),
    metaChip(nCalls ? `→ ${plural(nCalls, 'tool call')}` : '→ answer'),
  ];
  const rows = [
    ['Input', usage.input_tokens],
    ['Cached', usage.cached_tokens],
    ['Cache write', usage.cache_write_tokens],
    ['Uncached', usage.uncached_input_tokens],
    ['Output', usage.output_tokens],
    ['Reasoning', usage.reasoning_tokens],
  ];
  const dl = el('dl', { class: 'usage-dl' }, rows.map(([label, value]) => el('div', null, el('dt', { text: label }), el('dd', { text: fmtInt(value) }))));
  where.body.append(tlItem({ kind: 'model', iconName: 'spark', ev, body: detailsBlock(summary, [el('h4', { text: 'Tokens for this call' }), dl]) }));
}

function summarizeArgs(args) {
  return Object.entries(args)
    .map(([key, value]) => `${key}=${typeof value === 'string' ? JSON.stringify(clip(value, 60)) : clip(JSON.stringify(value), 60)}`)
    .join(', ');
}

function onToolCall(ev, d, where) {
  const args = isObj(d.arguments) ? d.arguments : {};
  const status = badge('running', 'info');
  status.prepend(spinner());
  const result = el('p', { class: 'tl-sub', text: 'Waiting for the result…' });
  const summary = [
    where.grouped || !ev.agent ? null : agentChip(ev.agent),
    el('span', { class: 'mono', text: d.tool || 'tool' }),
    el('span', { class: 'tl-args', text: clip(summarizeArgs(args), 90) }),
    status,
  ];
  const li = tlItem({
    kind: 'tool',
    iconName: 'tool',
    ev,
    body: detailsBlock(summary, [el('h4', { text: 'Arguments' }), el('pre', { class: 'code', text: prettyJson(args) }), el('h4', { text: 'Result' }), result]),
  });
  where.body.append(li);
  tl.openTools += 1;
  if (d.call_id) tl.tools.set(d.call_id, { li, status, result });
}

function onToolResult(ev, d, where) {
  const entry = d.call_id ? tl.tools.get(d.call_id) : null;
  const ok = d.ok !== false;
  tl.openTools = Math.max(0, tl.openTools - 1);
  const status = badge(`${ok ? 'ok' : 'error'}${d.duration_ms != null ? ` · ${fmtDuration(d.duration_ms)}` : ''}`, ok ? 'ok' : 'danger', ok ? 'check' : 'x');
  const preview = [
    el('pre', { class: 'code', text: d.preview != null && d.preview !== '' ? String(d.preview) : '(empty result)' }),
    d.truncated ? el('p', { class: 'tl-sub', text: 'Output was truncated before it reached the model.' }) : null,
  ];
  if (!entry) {
    where.body.append(
      tlItem({ kind: 'tool', iconName: 'tool', ev, body: detailsBlock([el('span', { class: 'mono', text: d.tool || 'tool' }), 'result', status], preview) })
    );
    return;
  }
  tl.tools.delete(d.call_id);
  entry.status.replaceWith(status);
  entry.status = status;
  entry.result.replaceWith(...preview.filter(Boolean));
  entry.li.classList.toggle('is-error', !ok);
}

function onHandoff(ev, d) {
  const from = d.from_agent || ev.agent;
  const where = containerFor(from);
  where.body.append(
    tlItem({
      kind: 'handoff',
      iconName: 'arrow',
      ev,
      title: [where.grouped || !from ? null : agentChip(from), 'Delegates to', agentChip(d.to_agent || 'agent')],
      body: d.task_preview ? el('p', { class: 'tl-quote', text: d.task_preview }) : null,
    })
  );
}

function onSafety(ev, d, where) {
  const action = String(d.action || 'flagged');
  const tone = DANGER_ACTIONS.has(action) ? 'danger' : 'warn';
  const kind = SAFETY_KINDS[d.kind] || humanize(d.kind) || 'Safety event';
  const facts = [d.source ? `source: ${d.source}` : '', d.severity ? `severity: ${d.severity}` : ''].filter(Boolean).join(' · ');
  where.body.append(
    tlItem({
      kind: 'safety',
      iconName: 'shield',
      tone,
      ev,
      title: [where.grouped || !ev.agent ? null : agentChip(ev.agent), kind, badge(action, tone)],
      body: [d.detail ? el('p', { class: 'tl-text', text: d.detail }) : null, facts ? el('p', { class: 'tl-sub', text: facts }) : null],
    })
  );
}

function onAgentFinished(ev, d) {
  let index = -1;
  for (let i = tl.stack.length - 1; i >= 0; i -= 1) {
    if (tl.stack[i].name === ev.agent) {
      index = i;
      break;
    }
  }
  const reason = d.stopped_reason || 'final';
  const info = stopReasonInfo(reason);
  const done = reason === 'final';
  const item = tlItem({
    kind: 'finish',
    iconName: done ? 'checkCircle' : 'stop',
    tone: done ? 'ok' : info.tone,
    ev,
    title: [
      index < 0 && ev.agent ? agentChip(ev.agent) : null,
      done ? 'Finished' : info.label,
      d.steps != null ? metaChip(plural(d.steps, 'step')) : null,
      d.tool_calls != null ? metaChip(plural(d.tool_calls, 'tool call')) : null,
      d.cost_usd != null ? metaChip(fmtUsd6(d.cost_usd)) : null,
    ],
    body: d.output_preview ? detailsBlock('Output preview', el('pre', { class: 'code', text: String(d.output_preview) })) : null,
  });

  if (index < 0) {
    tl.list.append(item);
    return;
  }
  tl.stack[index].body.append(item);
  closeGroups(index + 1, 'interrupted');
  setGroupStatus(tl.stack[index], done ? 'done' : info.tone === 'danger' ? 'error' : 'stopped', done ? null : humanize(reason));
  tl.stack.length = index;
}

function onFinal(ev, d) {
  const reason = d.stopped_reason || (d.ok === false ? 'error' : 'final');
  const info = stopReasonInfo(reason);
  const ok = d.ok !== false && reason === 'final';
  closeGroups(0, info.tone === 'danger' ? 'error' : 'stopped', humanize(reason));
  const findings = num(d.safety_findings);
  tl.list.append(
    tlItem({
      kind: 'final',
      iconName: ok ? 'flag' : 'alert',
      tone: ok ? 'ok' : info.tone,
      ev,
      title: ok ? 'Run complete' : info.label,
      body: el(
        'div',
        { class: 'chip-row' },
        d.duration_ms != null ? metaChip(fmtSeconds(d.duration_ms)) : null,
        metaChip(fmtUsd6(d.cost_usd)),
        d.n_model_calls != null ? metaChip(plural(d.n_model_calls, 'model call')) : null,
        num(d.n_failed_attempts) ? badge(`${plural(d.n_failed_attempts, 'failed attempt')} (in the ledger, usage unknown)`, 'warn') : null,
        metaChip(`${fmtInt(normalizeUsage(d.usage).total_tokens)} tokens`),
        findings ? badge(plural(findings, 'safety finding'), 'warn', 'shield') : null,
        isObj(d.output) ? detailsBlock('Structured output (JSON)', el('pre', { class: 'code', text: prettyJson(d.output) })) : null
      ),
    })
  );
}

/** The verifier is code (no model call): show what it checked instead of raw JSON. */
function onVerification(ev, d) {
  const dropped = Array.isArray(d.dropped_picks) ? d.dropped_picks.filter(isObj) : [];
  const excluded = Array.isArray(d.excluded_picks) ? d.excluded_picks.filter(isObj) : [];
  tl.list.append(
    tlItem({
      kind: 'verify',
      iconName: 'checkCircle',
      tone: 'ok',
      ev,
      title: [agentChip(ev.agent || 'verifier'), 'Checked by code (no model call)'],
      body: [
        el('p', { class: 'tl-sub', text: `kept ${fmtInt(d.kept)} of ${fmtInt(d.checked)} picks · ${fmtInt(d.excluded || 0)} not a fit · ` +
          `${fmtInt(d.dropped || 0)} removed · quotes found word for word ${fmtInt(d.quotes_verified)}/${fmtInt(d.quotes_total)} · ` +
          `unsupported details removed ${fmtInt(d.details_redacted || 0)}` }),
        dropped.length || excluded.length
          ? detailsBlock('Removed or ruled out', el('ul', { class: 'claims' },
            dropped.map((x) => el('li', { text: `Removed ${x.record_id}: ${x.reason}` })),
            excluded.map((x) => el('li', { text: `Not a fit ${x.record_id}: ${(x.reasons || []).join(' ')}` }))))
          : null,
      ],
    })
  );
}

function onError(ev, d, where) {
  where.body.append(
    tlItem({
      kind: 'error',
      iconName: 'alert',
      tone: ev.agent === 'guard' ? 'warn' : 'danger',
      ev,
      title: [where.grouped || !ev.agent ? null : agentChip(ev.agent), 'Error'],
      body: el('p', { class: 'tl-text', text: d.message || 'Unknown error' }),
    })
  );
}

function onUnknown(ev, d, where) {
  where.body.append(
    tlItem({ kind: 'other', iconName: 'info', ev, body: detailsBlock(humanize(ev.type), el('pre', { class: 'code', text: prettyJson(d) })) })
  );
}

const TIMELINE_HANDLERS = {
  run_started: onRunStarted,
  agent_started: onAgentStarted,
  model_call: onModelCall,
  tool_call: onToolCall,
  tool_result: onToolResult,
  handoff: onHandoff,
  safety: onSafety,
  agent_finished: onAgentFinished,
  verification: onVerification,
  final: onFinal,
  error: onError,
};

function renderTimelineEvent(ev, data) {
  if (!tl.list) resetTimeline();
  const scroller = dom.timeline;
  const stick = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 120;
  const handler = TIMELINE_HANDLERS[ev.type] || onUnknown;
  handler(ev, data, containerFor(ev.agent));
  updateActiveGroup();
  updatePending();
  if (state.run && state.run.live && stick) scroller.scrollTop = scroller.scrollHeight;
}

/** Pulse the innermost agent that is currently working. */
function updateActiveGroup() {
  const run = state.run;
  const live = run && run.live && state.running && !run.final;
  const top = live && tl.stack.length ? tl.stack[tl.stack.length - 1].li : null;
  if (tl.active && tl.active !== top) tl.active.classList.remove('is-active');
  if (top) top.classList.add('is-active');
  tl.active = top;
}

/** A "thinking…" row at the end of the active group while we wait for the next event. */
function updatePending() {
  const run = state.run;
  const show = run && run.live && state.running && !run.final && !run.cancelled && tl.openTools === 0 && tl.list;
  if (!show) {
    if (tl.pending) tl.pending.remove();
    return;
  }
  if (!tl.pending) {
    tl.pending = el(
      'li',
      { class: 'tl-item tl-pending', 'aria-hidden': 'true' },
      el('span', { class: 'tl-icon' }, spinner()),
      el('div', { class: 'tl-main' }, el('div', { class: 'tl-title' }, el('span', { class: 'pending-text' }))),
      el('span')
    );
  }
  const top = tl.stack[tl.stack.length - 1];
  const labels = {
    run_started: 'Screening the input…',
    handoff: 'Handing off…',
    tool_result: 'Reading the tool results…',
    agent_finished: top ? 'Continuing…' : 'Finishing up…',
  };
  const label = run.lastType ? labels[run.lastType] || 'Thinking…' : 'Connecting…';
  tl.pending.querySelector('.pending-text').textContent = label;
  (top ? top.body : tl.list).append(tl.pending);
}

function setExpandState(expanded) {
  dom.expandBtn.setAttribute('aria-pressed', String(expanded));
  dom.expandBtn.textContent = expanded ? 'Collapse all' : 'Expand all';
}

function toggleExpandAll() {
  const expand = dom.expandBtn.getAttribute('aria-pressed') !== 'true';
  dom.timeline.querySelectorAll('details').forEach((d) => {
    d.open = expand;
  });
  setExpandState(expand);
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------

/** Coloured notice box. Announcements go through the status line, so no live role here. */
function callout(tone, title, text, hint = '', extra = null) {
  const iconName = tone === 'danger' ? 'alert' : tone === 'warn' ? 'shield' : 'info';
  return el(
    'div',
    { class: `callout callout-${tone}` },
    icon(iconName),
    el(
      'div',
      null,
      el('p', { class: 'callout-title', text: title }),
      text ? el('p', { class: 'pre-wrap', text }) : null,
      hint ? el('p', { class: 'callout-hint', text: hint }) : null,
      extra
    )
  );
}

function errorKind(kind, message) {
  if (/PORTKEY_API_KEY/i.test(message || '')) return 'setup';
  if (/timed out/i.test(message || '')) return 'timeout';
  if (state.health && state.health.key_configured === false && /api key/i.test(message || '')) return 'setup';
  return kind;
}

const fmtClock = (ms) => fmtDateTime(new Date(ms).toISOString());

/** Buttons offered when a search does not finish. Never retries automatically (each search is a paid AI run). */
function browseButton() {
  return el('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => selectTab('discover', { focus: true }) },
    icon('book'), 'Browse all listings (no AI)');
}

function editButton() {
  return el('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: () => { selectTab('run'); dom.input.focus(); } },
    'Edit my request');
}

function retryButton() {
  const wait = Math.max(0, Math.ceil((state.retryBlockedUntil - Date.now()) / 1000));
  const btn = el('button', { type: 'button', class: 'btn btn-primary btn-sm', onclick: retryRun },
    icon('refresh'), wait ? `Try again in ${wait} s` : 'Try again');
  if (wait) {
    btn.disabled = true;
    window.setTimeout(() => {
      if (!btn.isConnected) return;
      btn.disabled = false;
      btn.replaceChildren(icon('refresh'), 'Try again');
    }, wait * 1000);
  }
  return btn;
}

/** A live run that finished with server-verified results (what 'Previous results' may keep). */
const isGoodRun = (r) => Boolean(r && r.live && r.final && r.final.ok !== false && (r.final.stopped_reason || 'final') === 'final'
  && isObj(r.final.output) && Array.isArray(r.final.output.picks));

function recoveryActions(kind) {
  const canRetry = state.run && state.run.live && state.lastRequest && !NO_RETRY.has(kind);
  return el('div', { class: 'actions recovery' }, canRetry ? retryButton() : null, state.run && state.run.live ? editButton() : null, browseButton());
}

/** Same words and conditions as the search that did not finish (the box is only refilled if it is empty). */
function retryRun() {
  if (state.running) return;
  if (!dom.input.value.trim() && state.lastRequest) {
    dom.input.value = state.lastRequest.input;
    updateCounter();
  }
  startRun();
}

function renderResultEmpty() {
  dom.resultBadges.replaceChildren();
  dom.result.replaceChildren(
    el(
      'div',
      { class: 'empty' },
      el('div', { class: 'empty-icon' }, icon('spark')),
      el('h3', { text: 'Your matches will appear here' }),
      el('p', { text: 'Describe what you want in a sentence, or start from an example, and press Find. Results are grouped into this week, coming weeks and ongoing programs & communities, and each one links to its source page.' }),
      el('div', { class: 'actions recovery center' }, browseButton())
    )
  );
}

function renderResultLoading() {
  const run = state.run;
  const p = run.progress;
  const steps = [
    ['Checking your request', p.screened],
    ['Searching the stored listings', p.searched],
    [p.read ? `Reading ${plural(p.read, 'listing')} in detail` : 'Reading the most promising listings', p.read > 0],
    ['Checking conditions against the source pages (code, no AI)', p.checked],
  ];
  const long = elapsedMs(run) > LONG_WAIT_MS;
  return el(
    'div',
    { class: 'loading' },
    el('div', { class: 'loading-head' }, spinner(), 'Searching for you…'),
    el('ol', { class: 'progress-steps small' }, steps.map(([text, done]) => el('li', { class: done ? 'is-done' : null }, el('span', { 'aria-hidden': 'true', text: done ? '✓ ' : '· ' }), text, el('span', { class: 'sr-only', text: done ? ' (done)' : ' (pending)' })))),
    el('p', {
      class: long ? 'small long-wait' : 'muted small',
      text: long
        ? 'This is taking longer than usual: the AI service may be slow. You can press Stop and try again; your request and conditions stay in the box.'
        : 'Most searches take 10–40 seconds. Press Stop to cancel.',
    })
  );
}

function renderFinal(final) {
  const nodes = [];
  const run = state.run;
  const reason = final.stopped_reason || (final.ok === false ? 'error' : 'final');
  const info = stopReasonInfo(reason);
  const out = isObj(final.output) ? final.output : null; // server-verified object only
  const hasPicks = reason === 'final' && Boolean(out && Array.isArray(out.picks));

  if (reason !== 'final' && !(reason === 'error' && run.error)) {
    // The server's own message (e.g. which spending limit) first, then what it means for the user.
    const serverText = typeof final.output_text === 'string' ? final.output_text.trim() : '';
    const retryKind = reason === 'blocked' || reason === 'budget' ? 'blocked' : 'server'; // a cap or a block is hit again on retry
    nodes.push(callout(info.tone === 'danger' ? 'danger' : 'warn', info.label, serverText || STOP_EXPLANATIONS[reason] || '',
      serverText ? STOP_EXPLANATIONS[reason] || '' : '', recoveryActions(retryKind)));
  }

  if (hasPicks) nodes.push(...renderMatches(out));
  else if (reason === 'final') {
    const text = String(final.output_text || '').trim();
    nodes.push(callout('warn', 'The AI answer could not be checked, so nothing is shown as a recommendation',
      text ? `AI text (not checked by code): ${clip(text, 400)}` : '', 'Try again, or browse the listings without AI.', recoveryActions('server')));
  }

  setChildren(
    dom.resultBadges,
    run.live ? null : badge('Saved run (replay)', 'info', 'refresh'),
    badge(info.label, info.tone, reason === 'final' ? 'check' : null)
  );
  return nodes;
}

const PURPOSE_LABELS = {
  meet_people_or_join_community: 'meet people / join a community',
  learn_or_discuss_topic: 'learn or discuss a topic',
  do_the_activity: 'do the activity',
  watch_or_spectate: 'watch / spectate',
  not_stated: 'not stated',
};
const VALUE_TEXT = { in_person: 'in person', online: 'online', either: 'in person or online', this_week: 'next 7 days', next_few_weeks: 'next 4 weeks' };
const STATUS_LABEL = { match: ['Match', 'solid'], conditional: ['Check first', 'warn'], exploratory: ['Exploratory', 'info'] };
const SECTION_ORDER = ['this_week', 'coming', 'ongoing', 'date_unknown'];
const COND_ICON = { met: '✓', not_met: '✗', to_confirm: '?', info: 'i' };
const COND_WORD = { met: 'met', not_met: 'not met', to_confirm: 'to confirm', info: 'note' };

function condList(conditions) {
  return el('ul', { class: 'conds small' }, conditions.map((c) => el('li', { class: `cond cond-${c.status}` },
    el('span', { class: 'cond-icon', role: 'img', 'aria-label': COND_WORD[c.status] || humanize(c.status), text: COND_ICON[c.status] || '·' }), ' ', c.text)));
}

/** What the code checked against: the AI's reading of the user's words, plus the form choices (marked). */
function requestPanel(u) {
  if (!isObj(u)) return null;
  const prov = isObj(u.provenance) ? u.provenance : {};
  const notStated = (v) => v == null || v === '' || v === 'not_stated';
  const show = (name, value) => {
    const p = isObj(prov[name]) ? prov[name] : null;
    const text = notStated(value) ? 'not stated' : VALUE_TEXT[value] || humanize(value);
    if (p && p.source === 'form') {
      const read = p.ai_reading != null && !notStated(p.ai_reading) ? `; the AI read your words as “${VALUE_TEXT[p.ai_reading] || humanize(p.ai_reading)}”, the form wins` : '';
      return [text, ` (you set this${read})`];
    }
    if (p && p.source === 'dropped') return ['not stated', ` (the AI guessed “${p.ai_reading}”, which is not in your words, so it is ignored)`];
    return [text, ''];
  };
  const rows = [
    ['Interests', Array.isArray(u.interests) && u.interests.length ? [u.interests.join(', '), ''] : ['not stated', '']],
    ['Purpose', [u.purpose ? `${u.purpose} (${PURPOSE_LABELS[u.purpose_type] || humanize(u.purpose_type)})` : PURPOSE_LABELS[u.purpose_type] || 'not stated', '']],
    ['Taking part', show('participation', u.participation)],
    ['When', (() => { const [t, n] = show('time_window', u.time_window); return [t, `${n}${u.time_preference ? ` · you also said “${u.time_preference}”` : ''}`]; })()],
    ['About you', show('identity', u.identity)],
    ['Experience', show('experience_level', u.experience_level)],
    ['Play or watch', [notStated(u.play_or_watch) || u.play_or_watch === 'not_applicable' ? 'not stated' : humanize(u.play_or_watch), '']],
  ];
  return el('details', { class: 'request-panel' },
    el('summary', null, 'Your request as the code checked it ', el('span', { class: 'muted small', text: '(AI reading of your words, plus conditions you set)' })),
    el('dl', { class: 'understood-dl' }, rows.map(([k, [v, note]]) => el('div', null, el('dt', { text: k }),
      el('dd', { class: v === 'not stated' ? 'muted' : null }, v, note ? el('span', { class: 'muted small', text: note }) : null)))));
}

function dataLine(out) {
  const BYC = window.BYC || {};
  const modes = BYC.MODE_TEXT || {};
  const sources = (Array.isArray(out.sources) ? out.sources : []).filter(isObj);
  if (!sources.length) return null;
  const warn = sources.some((s) => s.data_mode !== 'cached' && s.data_mode !== 'live') || sources.some((s) => s.last_outcome === 'failed');
  return el('p', { class: `small data-line${warn ? ' dc-warn' : ' muted'}` },
    `Searched ${out.n_listings != null ? plural(out.n_listings, 'stored listing') : 'the stored listings'} from ${plural(sources.length, 'public source')}: `,
    sources.map((s, i) => [
      i ? '; ' : '',
      `${s.name} — ${(modes[s.data_mode] || [s.data_mode])[0]}${s.collected_at_text ? `, collected ${s.collected_at_text}` : ''}`,
      s.last_outcome === 'failed' ? ` (last refresh failed ${s.last_attempt_text || ''}${s.simulated ? ', simulated' : ''}; showing earlier data)` : '',
    ]),
    '. Only these sources are connected, so other campus activities will not appear here.');
}

function linkList(title, rows) {
  const BYC = window.BYC || {};
  return el('details', { class: 'result-section link-list' }, el('summary', null, title),
    el('ul', { class: 'claims' }, rows.map(([url, name, text]) => el('li', null,
      BYC.extLink ? BYC.extLink(url, name) : el('b', { text: name }), text ? ` — ${text}` : ''))));
}

function alsoReadText(a) {
  const reasons = (a.reasons || []).join(' ');
  if (a.verdict === 'not_a_fit') return `Not a fit: ${reasons}`;
  if (a.verdict === 'check_first') return `The AI did not pick it for your purpose. To confirm if you consider it: ${reasons}`;
  return 'The AI did not pick it for your purpose.';
}

function factsTable(facts) {
  return el('div', { class: 'table-wrap' }, el('table', { class: 'data-table compact facts' },
    el('thead', null, el('tr', null, el('th', { text: 'Field' }), el('th', { text: 'Value shown' }), el('th', { text: 'Page wording' }), el('th', { text: 'Basis' }))),
    el('tbody', null, facts.map((f) => el('tr', null, el('td', { text: f.field }), el('td', { text: f.value == null ? 'not stated' : String(f.value) }),
      el('td', { text: f.page_wording || '—' }), el('td', { text: f.basis || '' }))))));
}

/** One verified pick: the shared listing card (facts from the stored record) with the AI reason and code checks inside. */
function pickCard(p) {
  const BYC = window.BYC || {};
  const r = isObj(p.reasoning) ? p.reasoning : {};
  const [label, tone] = STATUS_LABEL[p.status];
  const conds = (p.conditions || []).filter(isObj);
  const byStatus = (s) => conds.filter((c) => c.status === s);
  const quotes = [
    ...(r.verified_quotes || []).map((q) => el('li', { class: 'quote-ok' }, '✓ “', q, '”')),
    ...(r.unverified_quotes || []).map((q) => el('li', { class: 'quote-bad' }, '✗ “', q, '” — not found on the page, ignored')),
  ];
  const why = el('div', { class: 'pick-why' },
    el('p', { class: 'match-label', text: p.status === 'exploratory' ? 'Why it might still interest you (AI · gpt-6-luna)' : 'Why it fits (AI · gpt-6-luna)' }),
    el('p', { text: r.why || '' }),
    r.exploration_link ? el('p', null, el('b', { text: 'Connection to your interest: ' }), r.exploration_link) : null,
    r.interaction_grounded
      ? el('p', null, el('b', { text: 'How people take part: ' }), r.interaction)
      : el('p', { class: 'small muted', text: r.interaction || '' }));
  const checks = el('div', { class: 'pick-checks' },
    byStatus('to_confirm').length ? el('div', null, el('p', { class: 'match-label dc-warn', text: 'Not confirmed for you yet: check before you go' }), condList(byStatus('to_confirm'))) : null,
    byStatus('met').length ? el('div', null, el('p', { class: 'match-label', text: 'Checked against the page (code)' }), condList(byStatus('met'))) : null,
    byStatus('info').length ? el('div', null, el('p', { class: 'match-label', text: 'Good to know' }), condList(byStatus('info'))) : null);
  const facts = (p.facts || []).filter(isObj);
  const evidence = detailsBlock('Evidence: AI quotes checked word for word, and page wording behind each fact', [
    quotes.length ? el('ul', { class: 'match-quotes small' }, quotes) : el('p', { class: 'small muted', text: 'The AI gave no quote for this pick.' }),
    (r.rejected_details || []).length ? el('p', { class: 'small quote-bad', text: `Removed from the AI text (not on the page): ${r.rejected_details.join('; ')}` }) : null,
    (p.relevance || []).length ? el('p', { class: 'small muted', text: `Your interest words found on the page: ${p.relevance.map((m) => `${m.term} (${m.field})`).join(', ')}` }) : null,
    facts.length ? factsTable(facts) : null,
  ], 'pick-evidence');
  const status = badge(label, tone);
  if (!BYC.renderCard) {
    return el('div', { class: 'pick card' }, status, BYC.extLink ? BYC.extLink(p.card.url, p.card.title) : el('b', { text: p.card.title }), why, checks, evidence);
  }
  return el('div', { class: 'pick' },
    BYC.renderCard(p.card, { compact: true, headingLevel: 'h4', badges: [status], slot: [why, checks], after: [evidence] }));
}

/** Matcher output after the code verifier, grouped by the server's own date windows. */
function renderMatches(out) {
  const nodes = [];
  const run = state.run;
  const BYC = window.BYC || {};
  const all = out.picks.filter(isObj);
  const picks = all.filter((p) => isObj(p.card) && STATUS_LABEL[p.status]);
  const excluded = Array.isArray(out.excluded) ? out.excluded.filter(isObj) : [];
  const alsoRead = Array.isArray(out.also_read) ? out.also_read.filter(isObj) : [];
  const dropped = Array.isArray(out.dropped) ? out.dropped.filter(isObj) : [];
  const v = isObj(out.verification) ? out.verification : null;

  if (!run.live) {
    nodes.push(el('p', { class: 'small replay-note', text: `Saved run${run.savedAt ? ` from ${fmtDateTime(run.savedAt)}` : ''} (no new AI call): listings, dates and the “this week” window are as of that run. Check Browse all for current listings.` }));
  }

  const n = (s) => picks.filter((p) => p.status === s).length;
  const proposed = v && num(v.checked) > picks.length
    ? ` The AI proposed ${fmtInt(v.checked)}; ${fmtInt(picks.length)} shown after the checks (${fmtInt(excluded.length)} not a fit, ${fmtInt(dropped.length)} removed).` : '';
  nodes.push(el('div', { class: 'headline' },
    el('p', { class: 'headline-main' }, picks.length
      ? `${plural(n('match'), 'match', 'matches')} · ${fmtInt(n('conditional'))} to check first · ${fmtInt(n('exploratory'))} exploratory`
      : 'No verified match in the stored listings'),
    el('p', { class: 'small muted', text: `Status is set by code: it checks the source pages against your request as the AI read it, plus any conditions you set; the AI cannot override it.${proposed}` }),
    picks.length ? el('p', { class: 'small muted legend-line', text: 'Match: no open condition. Check first: something on the page must be confirmed for you. Exploratory: a different topic with a quoted link to your interest.' }) : null));
  const data = dataLine(out);
  if (data) nodes.push(data);
  const request = requestPanel(out.understood);
  if (request) nodes.push(request);
  if (typeof out.summary === 'string' && out.summary.trim()) {
    nodes.push(el('div', { class: 'ai-summary' },
      el('p', { class: 'match-label', text: 'AI summary (gpt-6-luna; not checked by code, the cards below are authoritative)' }),
      el('p', { text: out.summary })));
  }
  if (typeof out.follow_up_question === 'string' && out.follow_up_question.trim()) {
    nodes.push(callout('info', 'One question back', out.follow_up_question,
      'The app does not keep a conversation: add your answer to your request above and press Find again.', run.live ? el('div', { class: 'actions recovery' }, editButton()) : null));
  }

  if (picks.length) {
    const windows = isObj(out.windows) ? out.windows : null;
    const grouped = windows && BYC.sectionSub && picks.every((p) => SECTION_ORDER.includes(p.section));
    if (grouped) {
      for (const key of SECTION_ORDER) {
        const items = picks.filter((p) => p.section === key);
        if (!items.length) continue;
        const title = (BYC.SECTION_INFO && BYC.SECTION_INFO[key] && BYC.SECTION_INFO[key].title) || humanize(key);
        nodes.push(el('section', { class: 'dc-section pick-group', 'aria-labelledby': `pg-${key}` },
          el('div', { class: 'dc-section-head' },
            el('h3', { id: `pg-${key}` }, title, el('span', { class: 'dc-count', text: String(items.length) })),
            el('span', { class: 'small muted', text: BYC.sectionSub(windows, key) })),
          el('div', { class: 'pick-list' }, items.map(pickCard))));
      }
    } else {
      nodes.push(el('p', { class: 'small muted', text: 'This saved run predates the time grouping, so its results are listed in order.' }));
      nodes.push(el('div', { class: 'pick-list' }, picks.map(pickCard)));
    }
  } else {
    nodes.push(callout('info', 'Nothing in the stored listings passed the checks for this request',
      'Only the connected public sources are searched. Try other words or fewer conditions, or browse everything.', '',
      el('div', { class: 'actions recovery' }, run.live ? editButton() : null, browseButton())));
  }
  if (all.length > picks.length) nodes.push(el('p', { class: 'small muted', text: `${all.length - picks.length} AI pick(s) could not be checked and are not shown.` }));
  if (excluded.length) {
    nodes.push(linkList(`Not a fit for you (${excluded.length}): ruled out by what the page says vs. what you told us`,
      excluded.map((e) => [e.url, e.title, (e.reasons || []).join(' ')])));
  }
  if (alsoRead.length) nodes.push(linkList(`Read by the AI but not recommended (${alsoRead.length})`, alsoRead.map((a) => [a.url, a.title, alsoReadText(a)])));
  const removed = dropped.filter((d) => typeof d.url === 'string' && /^https?:\/\//i.test(d.url));
  if (removed.length) nodes.push(linkList(`Suggested by the AI but removed by the code check (${removed.length})`, removed.map((d) => [d.url, d.title || d.record_id, `Removed: ${d.reason}`])));
  if (v) {
    nodes.push(el('p', { class: 'small muted verification', text: `Checked by code (no model call): ${fmtInt(v.quotes_verified)} of ${fmtInt(v.quotes_total)} AI quotes found word for word on the pages; ${fmtInt(v.details_redacted || 0)} unsupported details removed. Steps and cost are under “Run details”.` }));
  }
  return nodes;
}

function questionBlock(run) {
  return el('p', { class: 'question' }, el('b', { text: 'Request' }), run.inputPreview || '',
    run.options ? el('span', { class: 'q-opts', text: `Conditions set with the form: ${describeOptions(run.options)}` }) : null);
}

function previousResult() {
  const g = state.lastGood;
  return el('section', { class: 'result-section previous' },
    el('h3', { text: `Previous results (${fmtClock(g.at)}), kept because the new search did not finish` }),
    el('p', { class: 'small muted', text: `For: “${clip(g.input, 160)}”${g.options ? ` · conditions: ${describeOptions(g.options)}` : ''}` }),
    ...g.nodes);
}

function renderResult() {
  const run = state.run;
  if (!run) {
    renderResultEmpty();
    return;
  }
  const nodes = [];
  if (!run.live && (run.inputPreview || run.options)) nodes.push(questionBlock(run));
  if (run.warnings.length && !(run.live && state.running)) {
    const sim = run.warnings.some((w) => w.includes('SIMULATED'));
    nodes.push(el('p', { class: 'small muted warn-note', text: `Note: the extra AI safety check was unavailable for this request${sim ? ' (SIMULATED, test mode: no real model call was made)' : ''}; the rule-based screening still ran.` }));
  }

  if (run.error) {
    const copy = ERROR_COPY[run.error.kind] || ERROR_COPY.server;
    const nonFatal = run.final && run.final.ok !== false;
    // An error event is not terminal (the server always follows it with "final"), so while the
    // stream is still open show it as a warning instead of a failure.
    const pending = !run.final && run.live && state.running;
    nodes.push(
      nonFatal
        ? callout('warn', 'A non-fatal error was logged', run.error.message)
        : pending
        ? callout('warn', 'An error was logged', run.error.message, 'The search is still going; its result will appear here.')
        : callout(run.error.kind === 'setup' || run.error.kind === 'rate_limited' ? 'warn' : 'danger', copy.title, run.error.message, copy.hint,
          recoveryActions(run.error.kind))
    );
  }

  dom.resultBadges.replaceChildren();
  if (run.final) nodes.push(...renderFinal(run.final));
  else if (run.cancelled) {
    nodes.push(callout('info', 'Search cancelled',
      'You stopped this search. The cost under “Run details” is what was measured before you stopped; a model call that was in progress may still be billed by the provider.',
      '', recoveryActions('cancelled')));
  } else if (run.live && state.running) nodes.push(renderResultLoading());
  else if (!run.error) nodes.push(callout('info', 'No final result', 'This saved run ended before it produced a final answer.'));

  // A new search that failed or was cancelled never hides results that already succeeded.
  const unfinished = run.live && !state.running && !isGoodRun(run) && Boolean(run.cancelled || run.error || run.final);
  if (unfinished && state.lastGood) nodes.push(previousResult());
  dom.result.replaceChildren(...nodes);
}

// ---------------------------------------------------------------------------
// Run lifecycle (shared by live streaming and trace replay)
// ---------------------------------------------------------------------------

function beginRun({ live, runId = null }) {
  state.run = newRun({ live, runId });
  resetTimeline();
  renderTimelineMeta();
  renderCost();
  renderResult();
  if (live) {
    startTimer();
    updatePending();
  }
}

const PROGRESS_EVENTS = new Set(['agent_started', 'model_call', 'tool_call', 'tool_result', 'verification']);

/** Apply one event to state, then to the timeline, cost card and result card. */
function applyEvent(ev) {
  const run = state.run;
  if (!run || !isObj(ev) || typeof ev.type !== 'string') return;
  const data = isObj(ev.data) ? ev.data : {};
  const ts = parseTs(ev.ts);

  run.events.push(ev);
  if (ts != null) {
    if (run.firstTs == null) run.firstTs = ts;
    run.lastTs = ts;
  }
  if (!run.runId && ev.run_id) {
    run.runId = ev.run_id;
    renderTimelineMeta();
  }
  run.lastType = ev.type;

  switch (ev.type) {
    case 'run_started':
      run.inputPreview = String(data.input_preview || '');
      run.options = isObj(data.options) ? data.options : null;
      break;
    case 'agent_started':
      run.progress.screened = true;
      if (run.live) setStatus(dom.status, 'Searching the stored listings…', 'busy');
      break;
    case 'model_call':
      if (ev.agent === 'guard') run.progress.screened = true;
      run.modelCalls += 1;
      if (isObj(data.run_usage)) run.usage = normalizeUsage(data.run_usage);
      if (data.run_cost_usd != null) run.costUsd = num(data.run_cost_usd);
      renderCost();
      break;
    case 'tool_call':
      if (data.tool === 'get_listing') run.progress.read += 1;
      break;
    case 'tool_result':
      if (data.tool === 'search_listings') run.progress.searched = true;
      break;
    case 'verification':
      run.progress.checked = true;
      break;
    case 'final':
      run.final = data;
      if (isObj(data.usage)) run.usage = normalizeUsage(data.usage);
      if (data.cost_usd != null) run.costUsd = num(data.cost_usd);
      if (data.n_model_calls != null) run.modelCalls = num(data.n_model_calls);
      if (data.duration_ms != null) run.durationMs = num(data.duration_ms);
      stopTimer();
      break;
    case 'error': {
      const message = String(data.message || 'The server reported an error.');
      if (ev.agent === 'guard') {
        // The extra AI guard fails open: the search continues, so this is a note, not a failure.
        run.warnings.push(message);
        break;
      }
      run.error = { kind: errorKind('server', message), message };
      if (run.live) setStatus(dom.status, run.error.kind === 'setup' ? `${ERROR_COPY.setup.title}.` : message.split('\n')[0], 'error');
      break;
    }
    default:
      break;
  }

  renderTimelineEvent(ev, data);
  if (ev.type === 'final' || ev.type === 'error') {
    renderCost();
    renderResult();
  } else if (run.live && state.running && PROGRESS_EVENTS.has(ev.type)) {
    renderResult(); // progress steps on the loading view
  }
  if (ev.type === 'final' && run.live) announceFinal(data);
}

function announceFinal(data) {
  const reason = data.stopped_reason || (data.ok === false ? 'error' : 'final');
  if (data.ok !== false && reason === 'final') {
    const out = isObj(data.output) ? data.output : {};
    const n = Array.isArray(out.picks) ? out.picks.length : 0;
    const secs = fmtSeconds(data.duration_ms != null ? data.duration_ms : elapsedMs(state.run));
    setStatus(dom.status, `Done in ${secs}: ${n ? `${plural(n, 'result')} below` : 'no verified match'}. Steps and cost are under “Run details”.`, 'ok');
  } else {
    const info = stopReasonInfo(reason);
    setStatus(dom.status, `${info.label}.`, info.tone === 'danger' ? 'error' : 'warn');
  }
}

async function startRun() {
  if (state.running) return;
  const input = dom.input.value.trim();
  if (!input) {
    setStatus(dom.status, 'Type what you are looking for first, or pick an example.', 'warn');
    dom.input.focus();
    return;
  }
  if (input.length > maxChars()) {
    setStatus(dom.status, `Your request is ${fmtInt(input.length)} characters; the limit is ${fmtInt(maxChars())}. Please shorten it.`, 'warn');
    dom.input.focus();
    return;
  }
  if (Date.now() < state.retryBlockedUntil) {
    setStatus(dom.status, `Too many searches in a short time. Please wait ${Math.ceil((state.retryBlockedUntil - Date.now()) / 1000)} s.`, 'warn');
    return;
  }
  const options = readOptions();

  // Keep the last finished results in case this search fails or is cancelled.
  const prev = state.run;
  if (isGoodRun(prev)) {
    state.lastGood = { nodes: [...dom.result.childNodes], input: prev.inputPreview || (state.lastRequest || {}).input || '', options: prev.options, at: prev.endedMs || Date.now() };
  }
  state.lastRequest = { input, options };

  selectTab('run');
  const moveFocus = document.activeElement !== dom.input;
  const controller = new AbortController();
  state.running = true;
  state.controller = controller;
  setRunningUi(true);
  if (moveFocus) dom.stopBtn.focus(); // keyboard users can cancel right away
  beginRun({ live: true });
  state.run.options = options;
  setStatus(dom.status, 'Starting the search…', 'busy');

  try {
    await api.streamRun(input, options, controller.signal, applyEvent);
    if (!state.run.final && !state.run.error) {
      failRun('stream', 'The connection closed before the search finished.');
    }
  } catch (err) {
    if (err && err.name === 'AbortError') {
      state.run.cancelled = true;
      setStatus(dom.status, 'Search cancelled.', 'warn');
    } else {
      const kind = err instanceof ApiError ? err.kind : 'network';
      if (err instanceof ApiError && err.retryAfterS > 0) {
        state.retryBlockedUntil = Date.now() + err.retryAfterS * 1000;
        window.setTimeout(() => setRunningUi(state.running), err.retryAfterS * 1000 + 50);
      }
      failRun(kind, err && err.message ? err.message : 'Unexpected error.');
    }
  } finally {
    finishRun();
  }
}

function failRun(kind, message) {
  const run = state.run;
  run.error = { kind: errorKind(kind, message), message };
  setStatus(dom.status, (ERROR_COPY[run.error.kind] || ERROR_COPY.server).title, 'error');
}

function finishRun() {
  const run = state.run;
  state.running = false;
  state.controller = null;
  state.usageStale = true;
  run.endedMs = Date.now();
  stopTimer();
  const refocus = document.activeElement === dom.stopBtn || document.activeElement === document.body;
  setRunningUi(false);
  if (refocus) (dom.runBtn.disabled ? dom.input : dom.runBtn).focus();
  if (tl.stack.length) closeGroups(0, run.cancelled ? 'interrupted' : 'stopped', run.cancelled ? 'cancelled' : null);
  for (const entry of tl.tools.values()) {
    const status = badge(run.cancelled ? 'cancelled' : 'no result', 'muted');
    entry.status.replaceWith(status);
    entry.status = status;
  }
  tl.tools.clear();
  tl.openTools = 0;
  updateActiveGroup();
  updatePending();
  renderCost();
  if (isGoodRun(run)) state.lastGood = null; // the new results are on screen
  renderResult();
  refreshSpend();
  if (run.error && (run.error.kind === 'setup' || run.error.kind === 'network')) refreshHealth();
}

function stopRun() {
  if (state.controller) state.controller.abort();
}

function clearAll() {
  if (state.running) return;
  dom.input.value = '';
  dom.optSom.checked = false;
  dom.optMode.value = '';
  dom.optWhen.value = '';
  updateCounter();
  state.run = null;
  state.lastGood = null;
  stopTimer();
  renderTimelineEmpty();
  renderCost();
  renderResult();
  setStatus(dom.status, '');
  dom.input.focus();
}

// ---------------------------------------------------------------------------
// Usage tab: /api/stats + /api/runs, replay a saved trace
// ---------------------------------------------------------------------------

function tableHead(...cols) {
  return el('thead', null, el('tr', null, cols.map(([label, numeric]) => el('th', { scope: 'col', class: numeric ? 'num' : null, text: label }))));
}

/** rows: [label, value, rowClass?] where rowClass is 'is-sub' (indented) or 'is-total'. */
function kvRows(rows) {
  return el(
    'tbody',
    null,
    rows.map(([label, value, rowClass]) => el('tr', { class: rowClass || null }, el('th', { scope: 'row', text: label }), el('td', { class: 'num', text: value })))
  );
}

function renderStats(raw) {
  const stats = isObj(raw) ? raw : {};
  const avg = isObj(stats.avg_per_run) ? stats.avg_per_run : {};
  const dist = isObj(stats.cost_per_run) ? stats.cost_per_run : {};
  const assumptions = isObj(stats.assumptions) ? stats.assumptions : {};
  const projections = Array.isArray(stats.projections) ? stats.projections.filter(isObj) : [];
  const runsPerUser = num(assumptions.runs_per_user_per_month);
  const biggest = projections.reduce((best, p) => (!best || num(p.users) > num(best.users) ? p : best), null);
  const meanCost = dist.mean != null ? dist.mean : avg.cost_usd;

  const tiles = [
    ['Runs logged', fmtInt(stats.runs), plural(stats.calls, 'model call'), false],
    ['Avg cost per run', fmtUsd6(meanCost), `p90 ${fmtUsd6(dist.p90)}`, true],
    ['Cache hit rate', fmtPct(stats.cache_hit_rate), 'cached ÷ input tokens', false],
    ['Per user per month', fmtMoney(stats.per_user_month_usd), runsPerUser ? `at ${fmtInt(runsPerUser)} runs per user` : '', false],
  ];
  if (biggest) tiles.push([`${fmtInt(biggest.users)} users / month`, fmtMoney(biggest.monthly_usd), `${fmtMoney(biggest.yearly_usd)} per year`, false]);
  dom.statsTiles.replaceChildren(
    ...tiles.map(([label, value, hint, accent]) =>
      el(
        'div',
        { class: accent ? 'tile tile-accent' : 'tile' },
        el('div', { class: 'tile-label', text: label }),
        el('div', { class: 'tile-value', text: value }),
        hint ? el('div', { class: 'tile-hint', text: hint }) : null
      )
    )
  );

  const avgUsage = normalizeUsage(avg);
  const uncached = avg.uncached_input_tokens != null ? avg.uncached_input_tokens : avgUsage.uncached_input_tokens;
  dom.avgTable.replaceChildren(
    tableHead(['Measure', false], ['Per run', true]),
    kvRows([
      ['Input tokens', fmtInt(avgUsage.input_tokens)],
      ['cached', fmtInt(avgUsage.cached_tokens), 'is-sub'],
      ['cache write', fmtInt(avgUsage.cache_write_tokens), 'is-sub'],
      ['uncached', fmtInt(uncached), 'is-sub'],
      ['Output tokens', fmtInt(avgUsage.output_tokens)],
      ['reasoning (inside output)', fmtInt(avgUsage.reasoning_tokens), 'is-sub'],
      ['Cost', fmtUsd6(avg.cost_usd), 'is-total'],
    ])
  );

  dom.distTable.replaceChildren(
    tableHead(['Statistic', false], ['USD', true]),
    kvRows([
      ['Mean', fmtUsd6(meanCost)],
      ['Median (p50)', fmtUsd6(dist.p50)],
      ['p90', fmtUsd6(dist.p90)],
      ['Max', fmtUsd6(dist.max)],
    ])
  );

  dom.projTable.replaceChildren(
    tableHead(['Users', false], ['Monthly', true], ['Yearly', true]),
    el(
      'tbody',
      null,
      projections.length
        ? projections.map((p) => el('tr', null, el('th', { scope: 'row', text: fmtInt(p.users) }), el('td', { class: 'num', text: fmtMoney(p.monthly_usd) }), el('td', { class: 'num', text: fmtMoney(p.yearly_usd) })))
        : el('tr', null, el('td', { colspan: '3', class: 'muted', text: 'No projections yet.' }))
    )
  );

  const prices = isObj(assumptions.prices_per_m) ? assumptions.prices_per_m : null;
  const parts = [];
  if (runsPerUser) parts.push(`Assumes ${fmtInt(runsPerUser)} runs per user per month at the current average cost per run.`);
  if (prices) {
    const model = state.health && state.health.model ? ` (${state.health.model})` : '';
    parts.push(
      `Prices per 1M tokens${model}: input ${fmtPrice(prices.input)}, cached input ${fmtPrice(prices.cached_input)}, ` +
        `cache write ${fmtPrice(prices.cache_write)}, output ${fmtPrice(prices.output)}.`
    );
  }
  dom.assumptions.textContent = parts.join(' ');
}

function renderRuns(runs) {
  const head = tableHead(['Started', false], ['Run', false], ['Agents', false], ['Calls', true], ['Tokens', true], ['Cache hit', true], ['Cost', true]);
  if (!runs.length) {
    dom.runsTable.replaceChildren(
      head,
      el(
        'tbody',
        null,
        el('tr', { class: 'empty-row' }, el('td', { colspan: '7' }, el('div', { class: 'empty' }, el('h3', { text: 'No runs yet' }), el('p', { text: 'Run a search on the Find tab and its usage will show up here.' }))))
      )
    );
    return;
  }
  const currentId = state.run ? state.run.runId : null;
  const rows = runs.filter(isObj).map((r) => {
    const usage = normalizeUsage(r.usage);
    const total = isObj(r.usage) && r.usage.total_tokens != null ? num(r.usage.total_tokens) : usage.total_tokens;
    const hit = cacheHitRate(usage);
    const open = () => replayRun(r.run_id);
    return el(
      'tr',
      { class: r.run_id === currentId ? 'is-current' : null, onclick: open },
      el('td', { title: r.started_at || '', text: fmtDateTime(r.started_at) }),
      el(
        'td',
        null,
        el('button', {
          type: 'button',
          class: 'link-btn',
          'aria-label': `Replay run ${r.run_id}`,
          text: r.run_id,
          onclick: (e) => {
            e.stopPropagation();
            open();
          },
        })
      ),
      el('td', null, (Array.isArray(r.agents) ? r.agents : []).map(agentChip)),
      el('td', { class: 'num', text: fmtInt(r.n_calls) }),
      el('td', { class: 'num', text: fmtInt(total) }),
      el('td', { class: 'num', text: hit == null ? '–' : fmtPct(hit) }),
      el('td', { class: 'num', text: fmtUsd6(r.cost_usd) })
    );
  });
  dom.runsTable.replaceChildren(head, el('tbody', null, rows));
}

async function loadUsage() {
  if (state.usageLoading) return;
  state.usageLoading = true;
  dom.refreshUsage.disabled = true;
  setStatus(dom.usageStatus, 'Loading usage…', 'busy');
  try {
    const [stats, runsBody] = await Promise.all([api.stats(), api.runs()]);
    const runs = isObj(runsBody) && Array.isArray(runsBody.runs) ? runsBody.runs : [];
    renderStats(stats);
    renderRuns(runs);
    renderSpend(isObj(stats) ? stats.today_cost_usd : null);
    state.usageStale = false;
    const count = isObj(stats) ? num(stats.runs) : 0;
    setStatus(dom.usageStatus, count ? `Based on ${plural(count, 'run')} and ${plural(stats.calls, 'model call')} in the usage ledger.` : '');
  } catch (err) {
    setStatus(dom.usageStatus, `Couldn’t load usage: ${err && err.message ? err.message : 'unknown error'}`, 'error');
  } finally {
    state.usageLoading = false;
    dom.refreshUsage.disabled = false;
  }
}

async function replayRun(runId) {
  if (!runId) return;
  const out = dom.panelUsage.hidden ? dom.status : dom.usageStatus; // the status line the user can see
  const busyMessage = 'Wait for the current search to finish before replaying a saved run.';
  if (state.running) {
    setStatus(out, busyMessage, 'warn');
    return;
  }
  setStatus(out, `Loading saved run ${runId}…`, 'busy');
  let trace;
  try {
    trace = await api.trace(runId);
  } catch (err) {
    const missing = err instanceof ApiError && err.status === 404;
    setStatus(
      out,
      missing ? `No saved trace for ${runId}. Only runs that reached the agents or the safety screen are saved.` : `Couldn’t load ${runId}: ${err.message}`,
      'error'
    );
    return;
  }
  if (state.running) {
    setStatus(out, busyMessage, 'warn');
    return;
  }
  setStatus(out, '');

  const events = isObj(trace) && Array.isArray(trace.events) ? trace.events : [];
  state.lastGood = null;
  beginRun({ live: false, runId: (isObj(trace) && trace.run_id) || runId });
  state.run.savedAt = isObj(trace) ? trace.started_at || null : null;
  events.forEach(applyEvent);
  dom.runDetails.open = true; // a replay is shown as evidence: steps and cost visible
  if (!state.run.final && tl.stack.length) closeGroups(0, 'interrupted', 'incomplete');
  renderCost();
  renderResult();
  selectTab('run');
  dom.timeline.scrollTop = 0;
  const started = isObj(trace) && trace.started_at ? ` from ${fmtDateTime(trace.started_at)}` : '';
  setStatus(dom.status, `Showing saved run ${state.run.runId}${started}.`, 'ok');
  dom.runsTable.querySelectorAll('tbody tr').forEach((tr) => {
    const btn = tr.querySelector('.link-btn');
    tr.classList.toggle('is-current', Boolean(btn && btn.textContent === state.run.runId));
  });
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = ['run', 'discover', 'usage'];

function selectTab(name, { focus = false } = {}) {
  for (const key of TABS) {
    const tab = byId(`tab-${key}`);
    const panel = byId(`panel-${key}`);
    const selected = key === name;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    panel.hidden = !selected;
    if (selected && focus) tab.focus();
  }
  if (name === 'usage' && state.usageStale) loadUsage();
}

function onTabKeydown(event) {
  const current = TABS.indexOf(event.currentTarget.dataset.tab);
  let next = null;
  if (event.key === 'ArrowRight') next = (current + 1) % TABS.length;
  else if (event.key === 'ArrowLeft') next = (current - 1 + TABS.length) % TABS.length;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = TABS.length - 1;
  if (next == null) return;
  event.preventDefault();
  selectTab(TABS[next], { focus: true });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

function wireEvents() {
  dom.askForm.addEventListener('submit', (event) => {
    event.preventDefault();
    startRun();
  });
  dom.input.addEventListener('input', updateCounter);
  dom.stopBtn.addEventListener('click', stopRun);
  dom.clearBtn.addEventListener('click', clearAll);
  dom.expandBtn.addEventListener('click', toggleExpandAll);
  dom.refreshUsage.addEventListener('click', loadUsage);
  dom.goAsk.addEventListener('click', () => {
    selectTab('run');
    dom.input.focus();
  });
  for (const node of [dom.optSom, dom.optMode, dom.optWhen]) node.addEventListener('change', onOptionsChanged);

  // Ctrl/Cmd+Enter searches from anywhere on the Find tab.
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !dom.panelRun.hidden) {
      event.preventDefault();
      startRun();
    }
  });

  for (const key of TABS) {
    const tab = byId(`tab-${key}`);
    tab.addEventListener('click', () => selectTab(key));
    tab.addEventListener('keydown', onTabKeydown);
  }
}

async function init() {
  bindDom();
  if (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '')) {
    dom.kbdHint.replaceChildren(el('kbd', { text: '⌘' }), ' + ', el('kbd', { text: 'Enter' }), ' to search');
  }
  wireEvents();
  dom.stopBtn.replaceChildren(icon('stop'), 'Stop');
  setRunningUi(false);
  renderTimelineEmpty();
  renderCost();
  renderResult();

  const [health, meta] = await Promise.allSettled([api.health(), api.meta()]);
  state.health = health.status === 'fulfilled' && isObj(health.value) ? health.value : null;
  state.meta = meta.status === 'fulfilled' && isObj(meta.value) ? meta.value : null;
  renderHealth();
  renderMeta();
  if (state.health && !state.meta) setStatus(dom.status, 'Couldn’t load the app description; you can still ask questions.', 'warn');
  renderSpend(state.meta ? state.meta.today_cost_usd : null);

  // ?run=<run_id> replays a saved trace (no model call), e.g. for report screenshots.
  // ?tab=browse|usage, or Browse filters (?interest=&mode=&when=&q=), open that tab instead of Find.
  const params = new URLSearchParams(location.search);
  const replayId = params.get('run');
  if (replayId && /^r_[0-9a-f]{12}$/.test(replayId)) replayRun(replayId);
  else if (params.get('tab') === 'usage') selectTab('usage');
  else if (params.get('tab') === 'browse' || ['q', 'interest', 'mode', 'when'].some((k) => params.has(k))) selectTab('discover');
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
