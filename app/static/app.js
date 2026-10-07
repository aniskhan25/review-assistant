"use strict";
let token = "", state = null;
const $ = id => document.getElementById(id);
const requiredFacts = new Set(["access_mode", "target_machine", "requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months", "total_storage_gb", "personal_data_declared", "vat_number", "previous_lumi_use"]);
function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }
function label(text, input) { const e = el("label", text); input.setAttribute("aria-label", text); e.append(input); return e; }
function input(value = "", type = "text") { const e = el("input"); e.type = type; e.value = value; return e; }
function select(values, chosen) { const e = el("select"); for (const v of values) { const o = el("option", v); o.value = v; o.selected = v === chosen; e.append(o); } return e; }
function noteBox() { const e = el("textarea"); e.maxLength = 2000; return e; }
function message(text, cls = "success") { $("message").textContent = text; $("message").className = cls; }
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
  if (!response.ok) { let body; try { body = await response.json(); } catch { body = { error: "Local request failed" }; } throw new Error(body.error); }
  return response.headers.get("Content-Type").includes("application/json") ? response.json() : response.text();
}
async function run(button, fn) { button.disabled = true; try { await fn(); } catch (e) { message(e.message, "error"); } finally { button.disabled = false; } }
async function mutate(action, data) {
  state = await api(`/api/reviews/${state.id}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision: state.revision, ...data }) });
  render(); message("Saved locally."); await library();
}
function submit(form, text, fn) { const b = el("button", text); form.append(b); form.addEventListener("submit", event => { event.preventDefault(); run(b, fn); }); return b; }
function evidenceSelect(ids = []) {
  const picker = el("select"); picker.multiple = true; picker.required = true;
  for (const ev of state.document.evidence.filter(e => e.scope !== "assessment")) { const o = el("option", `${ev.id} · p. ${ev.page} · ${ev.text.slice(0, 100)}`); o.value = ev.id; o.selected = ids.includes(ev.id); picker.append(o); }
  return picker;
}
function selected(picker) { return Array.from(picker.selectedOptions, o => o.value); }
function evidenceCard(ev) { const box = el("div", undefined, "evidence"); box.append(el("small", `${ev.id} · Page ${ev.page} · ${ev.section}${ev.scope === "assessment" ? " · Reviewer form — excluded from proposal evidence" : ""}`), el("p", ev.text)); return box; }
async function library() {
  const records = await api("/api/reviews"); $("reviews").replaceChildren();
  for (const review of records) { const b = el("button", `${review.finalized ? "✓ " : "○ "}${review.id.slice(0, 8)} · ${new Date(review.created_at).toLocaleDateString()}`, "review-link"); b.onclick = () => run(b, async () => { state = await api(`/api/reviews/${review.id}`); render(); }); $("reviews").append(b); }
}
$("login").addEventListener("submit", event => { event.preventDefault(); run(event.submitter, async () => {
  token = $("key").value.trim(); const config = await api("/api/config"); $("key").value = "";
  $("login").hidden = true; $("library").hidden = false; $("workspace").hidden = false; $("welcome").hidden = true;
  $("identity").textContent = `Reviewer: ${config.reviewer}`;
  $("runtime").textContent = `${config.policy.mode.toUpperCase()} · Backend: ${config.backend} · ${config.policy.approved ? "Approved policy" : "Provisional policy — validate before production"}`;
  await library(); message("Workspace unlocked. Access key stays in this tab's memory.");
}); });
$("lock").onclick = () => { token = ""; state = null; $("review").replaceChildren(); $("reviews").replaceChildren(); $("workspace").hidden = true; $("library").hidden = true; $("login").hidden = false; $("welcome").hidden = false; message(""); };
$("upload").addEventListener("submit", event => { event.preventDefault(); run(event.submitter, async () => {
  const file = $("pdf").files[0]; if (!file || file.size > 20 * 1024 * 1024) throw new Error("Choose a PDF of at most 20 MiB");
  message("Extracting proposal evidence locally…", "banner");
  state = await api("/api/reviews", { method: "POST", headers: { "Content-Type": "application/pdf" }, body: file });
  $("pdf").value = ""; render(); await library(); message("Proposal ready. Confirm the facts before recording decisions.");
}); });
function render() {
  const root = $("review"); root.replaceChildren();
  const heading = el("div", undefined, "row"); heading.append(el("h2", `Review ${state.id.slice(0, 8)}`), el("span", `Revision ${state.revision}`, "badge")); root.append(heading);
  root.append(el("small", `Proposal hash: ${state.document.document_id}`));
  const count = Object.values(state.decisions).filter(d => d.confirmed).length;
  root.append(el("p", `${count} / ${Object.keys(state.decisions).length} decisions confirmed`, "muted"));
  if (state.document.warnings.length) {
    const box = el("div", undefined, "card warning"); box.append(el("h3", "Extraction needs attention"));
    for (const text of state.document.warnings) box.append(el("p", text));
    box.append(el("p", state.extraction_resolved ? "Reviewer marked extraction checked." : "Add manual evidence below for unreadable pages, then record how you checked all gaps."));
    const f = el("form"), n = noteBox(); f.append(label("Verification note", n)); submit(f, "Mark extraction checked", () => mutate("resolve-extraction", { note: n.value })); box.append(f); root.append(box);
  }
  const facts = el("details"); facts.open = true; facts.append(el("summary", "1. Verify structured facts"));
  facts.append(el("p", "Required facts are marked *. Corrections invalidate decision confirmations. Numbers use GPU hours, GPU count, months and GB.", "muted"));
  const grid = el("div", undefined, "fact-grid");
  for (const [field, fact] of Object.entries(state.facts)) {
    if (fact.derived) continue;
    const card = el("div", undefined, "card"), form = el("form");
    card.append(el("h3", `${requiredFacts.has(field) ? "* " : ""}${field.replaceAll("_", " ")}`), el("span", fact.confirmed ? "Confirmed" : fact.status, fact.confirmed ? "badge success" : "badge"));
    if (fact.source) card.append(el("p", `p. ${fact.source.page}: ${fact.source.text}`, "muted"));
    if (fact.status === "CONFLICT") for (const c of fact.candidates) card.append(el("p", `p. ${c.source.page}: ${c.source.text}`, "warning"));
    const value = input(typeof fact.value === "boolean" ? (fact.value ? "yes" : "no") : (fact.value ?? ""));
    const status = select(field === "vat_number" ? ["PRESENT", "ABSENT"] : ["PRESENT"], fact.status);
    const sourceIds = fact.reviewer_evidence_ids || state.document.evidence.filter(e => fact.source && e.page === fact.source.page && e.text.includes(fact.source.text)).map(e => e.id);
    const picker = evidenceSelect(sourceIds), note = noteBox(); note.value = fact.reviewer_note || "";
    form.append(label("Verified value", value), label("Status", status), label("Supporting evidence (multiple selection allowed)", picker), label("Note (required for corrections)", note));
    submit(form, fact.confirmed ? "Update confirmation" : "Confirm fact", () => mutate("fact", { field, value: value.value, status: status.value, evidence_ids: selected(picker), note: note.value })); card.append(form); grid.append(card);
  }
  facts.append(grid); root.append(facts);
  root.append(el("h2", "2. Review evidence and decisions"));
  for (const [qid, d] of Object.entries(state.decisions)) {
    const card = el("section", undefined, "card"); card.append(el("h3", state.registry.questions[qid].title));
    card.append(el("p", `Model suggestion: ${d.answer} · ${d.band} · ${d.status}`));
    const noInference = ["MANUAL_REQUIRED", "NO_EVIDENCE_FOUND", "MODEL_ERROR"].includes(d.status);
    card.append(el("small", noInference ? "No valid model inference is available. Review the evidence and record your answer." : `${d.model} / ${d.model_version} · top probability ${(d.confidence * 100).toFixed(1)}% · margin ${d.margin.toFixed(2)} · ${d.latency_ms} ms. Scores are advisory and not calibrated accuracy.`));
    if (d.contradiction) card.append(el("p", "Possible evidence/decision contradiction. Explain your resolution in the note.", "banner warning"));
    for (const id of d.evidence_ids) { const ev = state.document.evidence.find(e => e.id === id); if (ev) card.append(evidenceCard(ev)); }
    if (!d.evidence_ids.length) card.append(el("p", "No relevant evidence retrieved. Inspect all passages or add a page transcription.", "warning"));
    const form = el("form"), answer = select(["UNKNOWN", "YES", "NO"], d.reviewer_answer || d.answer), picker = evidenceSelect(d.reviewer_evidence_ids || d.evidence_ids), note = noteBox(); note.value = d.reviewer_note;
    form.append(label("Your answer", answer), label("Evidence supporting your answer", picker), label("Reviewer note (required for overrides)", note));
    submit(form, d.confirmed ? "Update confirmed answer" : "Save reviewer answer", () => mutate("decision", { question_id: qid, answer: answer.value, evidence_ids: selected(picker), note: note.value })); card.append(form); root.append(card);
  }
  const all = el("details"); all.append(el("summary", "Inspect all proposal passages / add manual evidence"));
  for (const ev of state.document.evidence) all.append(evidenceCard(ev));
  const manual = el("form"), page = input("1", "number"), text = noteBox(), note = noteBox(); text.maxLength = 5000;
  manual.append(label("Proposal page", page), label("Passage transcribed from the proposal", text), label("Source / transcription note", note));
  submit(manual, "Add evidence", () => mutate("evidence", { page: Number(page.value), text: text.value, note: note.value }));
  all.append(manual); const rerun = el("button", "Re-run suggestions (clears confirmations)", "secondary"); rerun.onclick = () => run(rerun, () => mutate("analyze", {})); all.append(rerun); root.append(all);
  root.append(el("h2", "3. Inspect deterministic checks"));
  const rules = el("div", undefined, "card"); rules.append(el("p", `Suggested classification: ${state.rules.suggested} · ${state.rules.version}`));
  for (const f of state.rules.findings) { const row = el("div", undefined, "finding"); row.append(el("strong", f.severity), el("span", f.message)); if (Object.keys(f.calculation).length) row.append(el("pre", JSON.stringify(f.calculation, null, 2))); rules.append(row); } root.append(rules);
  const final = el("section", undefined, "card"); final.append(el("h2", "4. Confirm the final assessment"));
  final.append(el("p", "All required facts, evidence and decisions must be confirmed. UNKNOWN remains unresolved. You may override the suggested classification with your rationale.", "muted"));
  const f = el("form"), classification = select(["Choose classification", "ACCEPT", "REJECT"], state.final?.classification), rationale = noteBox(), ack = input("", "checkbox"); rationale.maxLength = 4000; rationale.value = state.final?.rationale || ""; ack.checked = Boolean(state.final);
  f.append(label("Final classification", classification), label("Classification rationale", rationale)); const check = label("I reviewed all blockers, warnings and unresolved policy findings.", ack); check.className = "check"; f.append(check);
  submit(f, state.policy.mode === "shadow" ? "Generate confirmed shadow draft" : "Generate confirmed assessment", () => mutate("finalize", { classification: classification.value, rationale: rationale.value, acknowledge_findings: ack.checked })); final.append(f);
  if (state.final) { final.append(el("pre", state.final.text)); const download = el("button", "Download assessment", "secondary"); download.onclick = () => run(download, async () => { const text = await api(`/api/reviews/${state.id}/export`); saveFile(text, `review-${state.id.slice(0, 8)}.txt`, "text/plain"); }); final.append(download); }
  root.append(final);
  const tools = el("div", undefined, "row"), audit = el("button", "Download audit metadata", "secondary"), remove = el("button", "Delete this review and audit", "danger");
  audit.onclick = () => run(audit, async () => saveFile(JSON.stringify(await api(`/api/reviews/${state.id}/audit`), null, 2), "audit.json", "application/json"));
  remove.onclick = () => { if (window.confirm("Permanently delete this review and its audit records?")) run(remove, async () => { await api(`/api/reviews/${state.id}`, { method: "DELETE" }); state = null; root.replaceChildren(); await library(); message("Review and audit deleted."); }); }; tools.append(audit, remove); root.append(tools);
}
function saveFile(text, name, type) { const url = URL.createObjectURL(new Blob([text], { type })); const a = el("a"); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); }
