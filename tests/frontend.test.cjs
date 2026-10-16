// State/DOM regression tests for the shipped script; no browser or dependencies.
// This deliberately models only DOM operations used by these tests. Visual and
// keyboard behavior require the separate real-browser verification.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag, document) {
    this.tagName = tag.toUpperCase(); this.ownerDocument = document;
    this.children = []; this.dataset = {}; this.attributes = {}; this.listeners = {};
    this.value = ''; this.type = ''; this.checked = false; this.disabled = false;
    this.hidden = false; this.selected = false; this.open = false; this._text = '';
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...children) { for (const child of children) { child.parentElement = this; this.children.push(child); } }
  replaceChildren(...children) { this.children = []; this._text = ''; this.append(...children); }
  setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'id') this.id = value; }
  getAttribute(key) { return this.attributes[key] ?? null; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  dispatchEvent(event) { event.target ||= this; for (const fn of this.listeners[event.type] || []) fn(event); if (event.bubbles && this.parentElement) this.parentElement.dispatchEvent(event); return true; }
  matches(selector) {
    selector = selector.trim();
    if (selector.includes(',')) return selector.split(',').some(s => this.matches(s));
    if (selector.startsWith('#')) return this.id === selector.slice(1);
    const attr = selector.match(/^(\w+)?\[([^=\]]+)(?:=["']?([^"'\]]*)["']?)?\]$/);
    if (attr) { const value = attr[2].startsWith('data-') ? this.dataset[attr[2].slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] : this[attr[2]] ?? this.getAttribute(attr[2]); return (!attr[1] || this.tagName === attr[1].toUpperCase()) && (attr[3] === undefined ? value != null : String(value) === attr[3]); }
    return this.tagName === selector.toUpperCase();
  }
  querySelectorAll(selector) { return this.children.flatMap(c => [...(c.matches(selector) ? [c] : []), ...c.querySelectorAll(selector)]); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { return this.matches(selector) ? this : this.parentElement?.closest(selector) || null; }
  get elements() { return this.querySelectorAll('input,textarea,select,button'); }
  get options() { return this.children; }
  get selectedOptions() { return this.options.filter(o => o.selected); }
  set disabled(value) { this._disabled = value; if (value && this.ownerDocument.activeElement === this) this.ownerDocument.activeElement = this.ownerDocument.body; }
  get disabled() { return this._disabled; }
  focus() { if (!this.disabled) this.ownerDocument.activeElement = this; }
  scrollIntoView() {}
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(c => c !== this); }
  click() { if (!this.disabled) return this.onclick?.({ target: this, preventDefault() {} }); }
}
function harness() {
  const document = { activeElement: null, createElement(tag) { return new Element(tag, this); } };
  document.body = document.createElement('body');
  const ids = ['login','key','library','workspace','welcome','identity','runtime','reviews','lock','upload','pdf','review','message'];
  for (const id of ids) { const e = document.createElement(['login','upload'].includes(id) ? 'form' : id === 'lock' ? 'button' : 'div'); e.id = id; document.body.append(e); }
  document.querySelectorAll = selector => document.body.querySelectorAll(selector);
  document.querySelector = selector => document.body.querySelector(selector);
  document.getElementById = id => document.querySelector('#' + id);
  const window = { confirm: () => true, addEventListener() {}, scrollY: 0, scrollTo() {} };
  const requests = []; let respond = () => { throw Error('Unexpected fetch'); };
  const context = vm.createContext({ document, window, console, URL, Blob, setTimeout, clearTimeout,
    Event: class { constructor(type) { this.type = type; } },
    requestAnimationFrame: fn => fn(), fetch: (...args) => { requests.push(args); return respond(...args); } });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
  return { document, context, requests, run: code => vm.runInContext(code, context), respond: fn => { respond = fn; } };
}
const response = (data, status = 200) => ({ ok: status < 400, status, headers: { get: () => 'application/json' }, json: async () => data });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function fixture() {
  const fact = value => ({ value, ready: true, confirmed: false, status: 'PRESENT', source: { page: 1, text: 'Synthetic evidence' } });
  return { id: 'synthetic-review-01', revision: 1, document: { document_id: 'synthetic-hash', warnings: [], evidence: [{ id: 'e1', page: 1, section: 'Proposal', text: 'Synthetic evidence' }] },
    facts: { access_mode: fact('FAST_LANE'), target_machine: fact('LUMI-G'), requested_gpu_hours: fact(100) },
    registry: { profile: 'FAST_LANE', questions: { software: { title: 'Software support' } } },
    decisions: { software: { ready: true, confirmed: false, answer: 'YES', band: 'high', status: 'OK', confidence: .99, margin: .9, evidence_ids: ['e1'], reviewer_note: '' } },
    exceptions: { facts: [], decisions: [], extraction: false }, rules: { suggested: 'ACCEPT', version: 'fixture', findings: [] },
    policy: { mode: 'shadow' }, draft: 'Synthetic draft', draft_classification: 'ACCEPT', draft_rationale: 'Synthetic rationale', final: null };
}
function load(h, state = fixture()) { h.context.initialState = state; h.run("token = 'synthetic'; state = initialState; render()"); }
function edit(h, id, value) { const e = h.document.getElementById(id); assert.ok(e, id); if (e.type === 'checkbox') e.checked = value; else e.value = value; e.dispatchEvent({ type: 'input', bubbles: true }); return e; }

test('saving one form retains only edited fields of other forms and accepts fresh server defaults', async () => {
  const h = harness(); load(h);
  edit(h, 'edit-decision-software-2', 'Keep this unsaved note');
  edit(h, 'edit-fact-requested_gpu_hours-0', '120');
  const next = fixture(); next.revision = 2; next.facts.requested_gpu_hours.value = 120; next.draft_rationale = 'Fresh server rationale';
  h.respond(path => Promise.resolve(response(path === '/api/reviews' ? [] : next)));
  await h.run("savingForm = 'fact:requested_gpu_hours'; run(null, () => mutate('fact', {}))");
  assert.equal(h.document.getElementById('edit-decision-software-2').value, 'Keep this unsaved note');
  assert.equal(h.document.getElementById('edit-final-1').value, 'Fresh server rationale');
  assert.equal(h.run("drafts.has('fact:requested_gpu_hours')"), false);
  assert.equal(h.run("drafts.has('decision:software')"), true);
});

test('saving another form resets approval acknowledgement but retains the edited rationale', async () => {
  const h = harness(); load(h);
  edit(h, 'edit-final-1', 'My rationale'); edit(h, 'edit-final-2', true);
  const next = fixture(); next.revision++;
  h.respond(path => Promise.resolve(response(path === '/api/reviews' ? [] : next)));
  await h.run("savingForm = 'decision:software'; run(null, () => mutate('decision', {}))");
  assert.equal(h.document.getElementById('edit-final-2').checked, false);
  assert.equal(h.document.getElementById('edit-final-1').value, 'My rationale');
});

test('pending requests reject duplicate operations and freeze fields while leaving lock available', async () => {
  const h = harness(); load(h); const gate = deferred(); h.context.gate = gate.promise; h.context.calls = 0;
  const first = h.run('run(null, async () => { calls++; await gate; })');
  await h.run('run(null, async () => { calls++; })');
  assert.equal(h.context.calls, 1);
  assert.equal(h.document.getElementById('edit-final-1').disabled, true);
  assert.equal(h.document.getElementById('lock').disabled, false);
  gate.resolve(); await first;
  assert.equal(h.document.getElementById('edit-final-1').disabled, false);
});

test('late mutation response after locking cannot restore review or drafts', async () => {
  const h = harness(); load(h); edit(h, 'edit-final-1', 'Private draft');
  const gate = deferred(); h.respond(() => gate.promise);
  const pending = h.run("run(null, () => mutate('decision', {}))");
  h.document.getElementById('lock').click();
  gate.resolve(response(fixture())); await pending;
  assert.equal(h.run('state'), null); assert.equal(h.run('drafts.size'), 0);
  assert.equal(h.document.getElementById('review').children.length, 0);
  assert.equal(h.document.getElementById('workspace').hidden, true);
  assert.equal(h.requests.length, 1);
});

test('409 keeps entered note and offers reload retaining edits while refreshing untouched fields', async () => {
  const h = harness(); load(h); edit(h, 'edit-decision-software-2', 'Reconcile me'); edit(h, 'edit-final-2', true);
  h.respond(() => Promise.resolve(response({ error: 'Review changed; reload before saving' }, 409)));
  await h.run("savingForm = 'decision:software'; run(null, () => mutate('decision', {}))");
  assert.equal(h.document.getElementById('edit-decision-software-2').value, 'Reconcile me');
  const reload = h.document.getElementById('message').querySelector('button'); assert.ok(reload);
  const next = fixture(); next.revision = 8; next.draft_rationale = 'Updated saved rationale';
  h.respond(() => Promise.resolve(response(next))); await reload.click();
  assert.equal(h.run('state.revision'), 8);
  assert.equal(h.document.getElementById('edit-decision-software-2').value, 'Reconcile me');
  assert.equal(h.document.getElementById('edit-final-1').value, 'Updated saved rationale');
  assert.equal(h.document.getElementById('edit-final-2').checked, false);
});

test('library refresh failure after commit reports saved state rather than failed mutation', async () => {
  const h = harness(); load(h); const next = fixture(); next.revision = 2;
  h.respond(path => path === '/api/reviews' ? Promise.reject(Error('List unavailable')) : Promise.resolve(response(next)));
  await h.run("run(null, () => mutate('decision', {}))");
  assert.equal(h.run('state.revision'), 2);
  assert.match(h.document.getElementById('message').textContent, /Saved locally.*could not refresh/);
  assert.equal(h.document.getElementById('message').className, 'warning');
});

test('unsaved fact edits block approval and export including direct handler invocation', async () => {
  const h = harness(); const state = fixture(); state.final = { classification: 'ACCEPT', text: 'Approved', rationale: 'Approved rationale' }; load(h, state);
  const download = h.document.querySelectorAll('button').find(b => b.dataset.export === 'true');
  const approve = h.document.querySelectorAll('button').find(b => b.dataset.approve === 'true');
  assert.equal(download.disabled, false); edit(h, 'edit-fact-requested_gpu_hours-0', '121');
  assert.equal(download.disabled, true); assert.equal(approve.disabled, true);
  await download.onclick(); assert.equal(h.requests.length, 0);
  await h.run("run(null, () => mutate('finalize', {}))"); assert.equal(h.requests.length, 0);
});

test('late library response after lock cannot repopulate the review list', async () => {
  const h = harness(); load(h); const gate = deferred(); h.respond(() => gate.promise);
  const pending = h.run('run(null, library)'); h.document.getElementById('lock').click();
  gate.resolve(response([{ id: 'other-review', created_at: '2026-10-12', finalized: false }])); await pending;
  assert.equal(h.document.getElementById('reviews').children.length, 0);
  assert.equal(h.document.getElementById('message').textContent, '');
});

test('locking during export prevents a late download', async () => {
  const h = harness(); const state = fixture(); state.final = { classification: 'ACCEPT', text: 'Approved', rationale: 'Approved' }; load(h, state);
  h.context.downloads = []; h.run('saveFile = (...args) => downloads.push(args)');
  const gate = deferred(); h.respond(() => gate.promise);
  const download = h.document.querySelectorAll('button').find(b => b.dataset.export === 'true');
  const pending = download.click(); h.document.getElementById('lock').click();
  gate.resolve(response('Approved')); await pending;
  assert.equal(h.context.downloads.length, 0); assert.equal(h.run('state'), null);
});

test('declining navigation discard preserves review and draft without a fetch', async () => {
  const h = harness(); load(h);
  h.respond(() => Promise.resolve(response([{ id: 'other-review', created_at: '2026-10-12', finalized: false }])));
  await h.run('library()'); edit(h, 'edit-final-1', 'Keep me'); h.run('window.confirm = () => false');
  const count = h.requests.length; await h.document.getElementById('reviews').querySelector('button').click();
  assert.equal(h.requests.length, count); assert.equal(h.run('state.id'), 'synthetic-review-01');
  assert.equal(h.document.getElementById('edit-final-1').value, 'Keep me'); assert.equal(h.run('hasDrafts()'), true);
});

test('keyboard focus returns to the rebuilt save button after controls are re-enabled', async () => {
  const h = harness(); load(h);
  const button = h.document.getElementById('save-decision-software'); button.focus();
  const next = fixture(); next.revision++;
  h.respond(path => Promise.resolve(response(path === '/api/reviews' ? [] : next)));
  h.context.button = button;
  await h.run("savingForm = 'decision:software'; run(button, () => mutate('decision', {}))");
  assert.notEqual(h.document.activeElement, button);
  assert.equal(h.document.activeElement.id, 'save-decision-software');
  assert.equal(h.document.activeElement.disabled, false);
});

test('edited multiple evidence selection survives saving another form', async () => {
  const h = harness(); const original = fixture();
  original.document.evidence.push({id:'e2',page:2,section:'Proposal',text:'More synthetic evidence'});
  load(h, original);
  const picker = h.document.getElementById('edit-decision-software-1');
  picker.options[0].selected = false; picker.options[1].selected = true;
  picker.dispatchEvent({type:'change',bubbles:true});
  const next = structuredClone(original); next.revision++;
  h.respond(path => Promise.resolve(response(path === '/api/reviews' ? [] : next)));
  await h.run("savingForm = 'fact:requested_gpu_hours'; run(null, () => mutate('fact', {}))");
  assert.deepEqual(h.document.getElementById('edit-decision-software-1').selectedOptions.map(o=>o.value), ['e2']);
});

test('conflict reload moves focus to the recovery message when its button is removed', async () => {
  const h = harness(); load(h); edit(h, 'edit-decision-software-2', 'Retain me');
  h.respond(() => Promise.resolve(response({error:'Review changed'},409)));
  await h.run("run(null, () => mutate('decision', {}))");
  const reload = h.document.getElementById('reload-latest'); reload.focus();
  const next = fixture(); next.revision = 4;
  h.respond(() => Promise.resolve(response(next))); await reload.click();
  assert.equal(h.document.activeElement.id,'message');
  assert.equal(h.document.activeElement.tabIndex,-1);
  assert.equal(h.document.getElementById('edit-decision-software-2').value,'Retain me');
});

test('manual country check explains reference coverage instead of a model failure', () => {
  const h = harness(); const s = fixture();
  s.facts.country = {value:'Norway',ready:true,confirmed:false,status:'PRESENT'};
  s.registry.questions.country_eligible = {title:'Country eligibility',manual_only:true};
  s.decisions.country_eligible = {...s.decisions.software,ready:false,answer:'UNKNOWN',status:'MANUAL_REQUIRED'};
  load(h,s);
  const text = h.document.getElementById('decision-country_eligible').textContent;
  assert.match(text,/Declared country: Norway/);
  assert.match(text,/Automatic matching uses the verified country subset saved with this review/);
  assert.doesNotMatch(text,/No valid model inference|Model suggestion/);
});



test('old diagnostic comments are removed only explicitly and preserve other reviewer text', () => {
  const h = harness(), s = fixture();
  s.final = {classification:'REJECT',text:'Old export',global_comment:'My comment.\nTechnical fit — Needs clarification: Clarify memory. [proposal evidence: ev-1]\nFurther advice.'};
  load(h,s);
  assert.match(h.document.getElementById('edit-final-5').value,/ev-1/);
  h.document.getElementById('clean-workload-comments').click();
  const value = h.document.getElementById('edit-final-5').value;
  assert.doesNotMatch(value,/ev-1|Needs clarification/);
  assert.match(value,/My comment/); assert.match(value,/Further advice/);
  assert.equal(s.final.text,'Old export');
});

test('workload findings remain visible when stale, precede facts, and have navigation', () => {
  const h = harness(), s = fixture();
  s.workload = {stale:true,summary:[],references:[],findings:[{title:'Technical fit',finding:'Needs clarification',explanation:'Clarify memory strategy.',decision:{status:'OK',evidence_ids:['e1']}}]};
  load(h,s);
  const panel = h.document.getElementById('workload-assessment');
  assert.match(panel.textContent,/Technical fit · Needs clarification · Out of date/);
  assert.match(panel.textContent,/Clarify memory strategy/);
  assert.match(panel.textContent,/Global technical comments/);
  const children = h.document.getElementById('review').children;
  assert.ok(children.indexOf(panel) < children.indexOf(h.document.getElementById('facts')));
  const link = h.document.querySelectorAll('a').find(a => a.href === '#workload-assessment');
  assert.ok(link); link.click();
  assert.equal(h.document.activeElement, panel.querySelector('summary'));
  assert.equal(h.document.getElementById('add-workload-comment'),null);
});

test('legacy review explains missing workload findings instead of silently hiding the panel', () => {
  const h = harness(); load(h);
  assert.match(h.document.getElementById('workload-assessment').textContent,/no structured workload assessment/);
});


test('draft workload comments prefill approval while saved reviewer comments including empty stay authoritative', () => {
  const h = harness(), s = fixture();
  s.draft_global_comment = 'Technical fit — Needs clarification';
  load(h,s);
  assert.equal(h.document.getElementById('edit-final-5').value,s.draft_global_comment);
  assert.equal(h.run("drafts.has('final')"),false);
  s.final = {classification:'ACCEPT',global_comment:'',text:'Approved'};
  load(h,s);
  assert.equal(h.document.getElementById('edit-final-5').value,'');
  s.final.global_comment = 'My reviewed comment'; load(h,s);
  assert.equal(h.document.getElementById('edit-final-5').value,'My reviewed comment');
});

test('coherent workload reason is editable without fit controls or email preview', () => {
  const h = harness(), s = fixture();
  s.draft_rationale = 'Further detail is needed. Please explain the execution plan and resource sizing.';
  s.workload_reason_options = [{id:'technical_fit',title:'Technical fit',classification:'REJECT',text:'Old standalone wording'}];
  load(h,s);
  assert.equal(h.document.getElementById('edit-final-1').value,s.draft_rationale);
  assert.equal(h.document.getElementById('toggle-workload-reason-technical_fit'),null);
  assert.equal(h.document.getElementById('applicant-reason-preview'),null);
  edit(h,'edit-final-1','My corrected explanation.'); h.run('render()');
  assert.equal(h.document.getElementById('edit-final-1').value,'My corrected explanation.');
  assert.equal(h.run("drafts.has('final')"),true);
});


test('confirmed answers replace obsolete reviewer-required labels and unresolved positives explain the gate', () => {
  const h = harness(), s = fixture();
  s.decisions.software = {...s.decisions.software,answer:'NO',reviewer_answer:'YES',confirmed:true,ready:true,band:'reviewer required',status:'MODEL_ERROR',contradiction:true};
  load(h,s);
  let text = h.document.getElementById('decision-software').textContent;
  assert.match(text,/Confirmed answer: YES/);
  assert.match(text,/no further action required/);
  assert.doesNotMatch(text,/reviewer required|No valid model inference|Possible evidence\/decision contradiction/);
  s.decisions.software = {...s.decisions.software,answer:'YES',confirmed:false,ready:false,reviewer_answer:null,status:'AGGREGATED',contradiction:false,review_reasons:['The supporting score (70%) is below the automatic-prefill threshold (85%).']};
  load(h,s); text=h.document.getElementById('decision-software').textContent;
  assert.match(text,/YES · Confirmation needed/);
  assert.match(text,/Why confirmation is needed:.*70%/);
});
