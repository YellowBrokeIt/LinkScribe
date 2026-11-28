// Exercise the actual inline editor closure. Only its transport and DOM are
// controlled here; this is not a browser, HTTP, SQLite, or highlight-quality test.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const A = 'a'.repeat(32), B = 'b'.repeat(32);

class Element {
  constructor() {
    this.listeners = {}; this.children = []; this.value = ''; this.textContent = '';
    this.hidden = false; this.disabled = false;
    this.classList = {add() {}, remove() {}, toggle() {}};
  }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  setAttribute() {}
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  scrollIntoView() {}
}

function fixture(id, title, text) {
  return {id, title, language: 'en', method: 'owned',
    segments: [{start: 0, end: 3, text, speaker: 'Reader'}],
    translations: {}, summary: null, highlights: null};
}

function setup(html) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const db = {[A]: fixture(A, 'Source A', 'Original A.'),
    [B]: fixture(B, 'Source B', 'Original B.')};
  const writes = [];
  let pauseB = false, finishB, confirmations = 0;
  const context = {
    document: {getElementById: get, createElement: () => new Element()},
    confirm: () => { confirmations++; return true; },
    fakeApi: async (url, options = {}) => {
      const id = url.split('/')[3];
      if (options.method === 'POST') {
        // A controlled response shape only; no claim to execute the selector.
        db[id].highlights = {source_segment_count: 1, selected_segment_count: 1,
          excerpts: [{segment_indices: [0], start: 0, end: 3,
            text: db[id].segments[0].text}], warnings: []};
        return structuredClone(db[id]);
      }
      if (options.method === 'PUT') {
        const body = JSON.parse(options.body);
        writes.push({id, body});
        db[id] = {...db[id], title: body.title,
          segments: body.segments.map((item, index) => ({...db[id].segments[index], ...item})),
          summary: null, translations: {}, highlights: null};
        return {ok: true};
      }
      if (id === B && pauseB) {
        return await new Promise(resolve => {
          finishB = () => resolve(structuredClone(db[B]));
        });
      }
      return structuredClone(db[id]);
    },
  };
  let script = html.match(/<script>([\s\S]*)<\/script>/)[1];
  script = script.replace(/\}\)\(\);\s*$/,
    'api=globalThis.fakeApi;globalThis.probe={openEditor,snapshot:()=>' +
    '({id:editing?.id,text:editing?.segments[0].text,dirty:editorDirty})};})();');
  vm.runInNewContext(script, context);
  return {get, db, writes, context,
    first: () => get('editor-rows').children[0].children[2],
    edit: text => {
      const input = get('editor-rows').children[0].children[2];
      input.value = text; input.listeners.input();
    },
    pauseOpen: () => { pauseB = true; },
    releaseOpen: () => { pauseB = false; return finishB(); },
    confirmations: () => confirmations};
}

async function examine(filename) {
  const bytes = fs.readFileSync(filename), html = bytes.toString('utf8');
  const afterHighlights = setup(html);
  await afterHighlights.context.probe.openEditor(A);
  await afterHighlights.get('editor-highlights').listeners.click();
  const correction = 'New correction after highlights.';
  afterHighlights.edit(correction);
  const beforeSave = {displayed: afterHighlights.first().value,
    model: afterHighlights.context.probe.snapshot().text};
  await afterHighlights.get('editor-save').listeners.click();
  const highlights = {before_save: beforeSave,
    persisted: afterHighlights.db[A].segments[0].text,
    displayed_after_save: afterHighlights.first().value,
    notice: afterHighlights.get('editor-message').textContent,
    passes: afterHighlights.db[A].segments[0].text === correction &&
      afterHighlights.first().value === correction};

  const opening = setup(html);
  await opening.context.probe.openEditor(A);
  const otherBefore = JSON.stringify(opening.db[B]);
  opening.pauseOpen();
  const pending = opening.context.probe.openEditor(B);
  const newer = 'Correction typed while B loads.';
  opening.edit(newer); opening.releaseOpen(); await pending;
  const kept = opening.context.probe.snapshot();
  const notice = opening.get('editor-message').textContent;
  await opening.get('editor-save').listeners.click();
  const open = {editor_after_response: kept, notice,
    confirmations: opening.confirmations(),
    saved_target_ids: opening.writes.map(write => write.id),
    persisted_original: opening.db[A].segments[0].text,
    other_record_unchanged: JSON.stringify(opening.db[B]) === otherBefore,
    passes: kept.id === A && kept.text === newer && kept.dirty &&
      opening.db[A].segments[0].text === newer &&
      opening.writes.length === 1 && opening.writes[0].id === A &&
      JSON.stringify(opening.db[B]) === otherBefore};

  const discard = setup(html);
  await discard.context.probe.openEditor(A);
  discard.edit('Earlier unsaved edit deliberately discarded.');
  discard.pauseOpen();
  const confirmedOpen = discard.context.probe.openEditor(B);
  discard.releaseOpen(); await confirmedOpen;
  const allowed = discard.context.probe.snapshot();
  const control = {editor: allowed, confirmations: discard.confirmations(),
    passes: allowed.id === B && !allowed.dirty && discard.confirmations() === 1};

  return {file: filename, sha256: sha(bytes),
    edit_after_highlight_generation: highlights, edit_during_pending_open: open,
    confirmed_discard_without_further_typing: control,
    all_expected_behaviors_hold: highlights.passes && open.passes && control.passes};
}

(async () => {
  if (!process.argv.slice(2).length) throw new Error('Supply HTML source snapshots.');
  const comparisons = [];
  for (const file of process.argv.slice(2)) comparisons.push(await examine(file));
  console.log(JSON.stringify({schema_version: 1, recorded_at: new Date().toISOString(),
    observer_sha256: sha(fs.readFileSync(__filename)),
    scope: 'Actual inline editor logic with controlled DOM and transport; not Chromium, HTTP or SQLite evidence.',
    comparisons}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
