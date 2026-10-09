"use strict";
let token = "", state = null;
const $ = id => document.getElementById(id);
const requiredFacts = new Set(["access_mode", "target_machine", "requested_gpu_hours", "maximum_number_of_gpus", "project_duration_months", "total_storage_gb", "personal_data_declared", "vat_number", "organization_type", "country"]);
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
  message("Extracting evidence and running configured local review checks…", "banner");
  state = await api("/api/reviews", { method: "POST", headers: { "Content-Type": "application/pdf" }, body: file });
  $("pdf").value = ""; render(); await library(); message("Draft ready. Resolve the highlighted exceptions, then approve the assessment.");
}); });
function render() {
  const root = $("review"); root.replaceChildren();
  const heading = el("div", undefined, "row"); heading.append(el("h2", `Review ${state.id.slice(0, 8)}`), el("span", `Revision ${state.revision}`, "badge")); root.append(heading);
  root.append(el("small", `Proposal hash: ${state.document.document_id}`));
  if (state.facts.access_mode.value && state.facts.access_mode.value !== "FAST_LANE") root.append(el("p", `Detected access mode: ${state.facts.access_mode.value}. Evidence inspection is available; Fast Lane model recommendations, rules and final export do not apply.`, "banner warning"));
  const exceptions = state.exceptions || {facts: [], decisions: []};
  root.append(el("p", `${exceptions.facts.length} fact gaps · ${exceptions.decisions.length} decision exceptions. Clear facts and supported answers are prefilled for final approval.`, "banner"));
  if (state.document.warnings.length) {
    const box = el("div", undefined, "card warning"); box.append(el("h3", "Extraction needs attention"));
    for (const text of state.document.warnings) box.append(el("p", text));
    box.append(el("p", state.extraction_resolved ? "Reviewer marked extraction checked." : "Add manual evidence below for unreadable pages, then record how you checked all gaps."));
    const f = el("form"), n = noteBox(); f.append(label("Verification note", n)); submit(f, "Mark extraction checked", () => mutate("resolve-extraction", { note: n.value })); box.append(f); root.append(box);
  }
  const facts = el("details"); facts.open = exceptions.facts.length > 0; facts.append(el("summary", "1. Extracted facts — resolve gaps or inspect prefills"));
  facts.append(el("p", "Required facts are marked *. Clearly sourced values need no individual confirmation. Corrections invalidate model answers. Units follow each field name: GPU hours and node hours are distinct, as are GB, TB and TBh.", "muted"));
  const grid = el("div", undefined, "fact-grid");
  for (const [field, fact] of Object.entries(state.facts)) {
    if (fact.derived || (fact.optional_resource_field && !fact.source && fact.status !== "CONFLICT")) continue;
    const card = el("details", undefined, "card"), form = el("form"); card.open = requiredFacts.has(field) && !fact.ready;
    card.append(el("summary", `${field.replaceAll("_", " ")}: ${fact.value ?? "Missing"} · ${fact.confirmed ? "Reviewed" : fact.ready ? "Prefilled" : "Needs review"}`));
    card.append(el("h3", `${requiredFacts.has(field) ? "* " : ""}${field.replaceAll("_", " ")}`), el("span", fact.confirmed ? "Confirmed" : fact.ready ? "Automatically prefilled" : fact.status, fact.confirmed ? "badge success" : "badge"));
    if (fact.source) card.append(el("p", `p. ${fact.source.page}: ${fact.source.text}`, "muted"));
    if (fact.status === "CONFLICT") for (const c of fact.candidates) card.append(el("p", `p. ${c.source.page}: ${c.source.text}`, "warning"));
    const value = input(typeof fact.value === "boolean" ? (fact.value ? "yes" : "no") : (fact.value ?? ""));
    const status = select(field === "vat_number" ? ["PRESENT", "ABSENT"] : ["PRESENT"], fact.status);
    const sourceIds = fact.reviewer_evidence_ids || state.document.evidence.filter(e => fact.source && e.page === fact.source.page && e.text.includes(fact.source.text)).map(e => e.id);
    const picker = evidenceSelect(sourceIds), note = noteBox(); note.value = fact.reviewer_note || "";
    form.append(label("Verified value", value), label("Status", status), label("Supporting evidence (multiple selection allowed)", picker), label("Note (required for corrections)", note));
    submit(form, fact.ready ? "Save correction" : "Resolve fact", () => mutate("fact", { field, value: value.value, status: status.value, evidence_ids: selected(picker), note: note.value })); card.append(form); grid.append(card);
  }
  facts.append(grid); root.append(facts);
  root.append(el("h2", "2. Resolve decision exceptions"));
  for (const [qid, d] of Object.entries(state.decisions)) {
    const card = el("details", undefined, "card"); card.open = !d.ready; card.append(el("summary", `${state.registry.questions[qid].title} · ${d.confirmed ? "Reviewed" : d.ready ? "Prefilled" : "Needs review"}`));
    if (state.registry.questions[qid].manual_only && !d.ready) card.append(el("p", "Manual verification required. Record the reference or justification in your note.", "banner"));
    card.append(el("p", `${d.checks ? "Combined answer" : "Model suggestion"}: ${d.answer} · ${d.band} · ${d.status}`));
    if (d.checks) {
      card.append(el("p", d.aggregation_reason));
      const checks = el("details"); checks.open = !d.ready; checks.append(el("summary", "Evidence checks behind this answer"));
      for (const [cid, check] of Object.entries(d.checks)) {
        checks.append(el("p", `${check.check_title}: ${check.answer} · ${check.status} · ${(check.confidence * 100).toFixed(1)}% top score · sources: ${check.evidence_ids.join(", ") || "none"}`));
        if (check.source_quotes) checks.append(el("p", `Source-backed claim (not a model probability): ${check.source_quotes.join("; ")}`, "muted"));
        if (check.corroboration) checks.append(el("p", `Corroborating interpretation: ${check.corroboration.answer} · ${check.corroboration.status}. Opposite resolved answers require review.`, "muted"));
        for (const reference of state.registry.questions[qid].checks[cid]?.background_references || []) {
          checks.append(el("p", `Framework reference (checked ${reference.checked}): ${reference.claim} Source: ${reference.url}`, "muted"));
        }
      }
      card.append(checks);
    }
    const noInference = ["MANUAL_REQUIRED", "NO_EVIDENCE_FOUND", "MODEL_ERROR", "UNSUPPORTED_PROFILE"].includes(d.status);
    if (d.inference_mode === "source_rule") card.append(el("p", `${d.reference_reason} Reference: ${d.reference.source || "supplied internal guide"}. This is a rule match, not a model probability.`));
    else card.append(el("small", noInference ? "No valid model inference is available. Review the evidence and record your answer." : d.checks ? `${d.model} · combined using explicit rules; minimum supporting check score ${(d.confidence * 100).toFixed(1)}%. This is not a probability of the combined answer.` : `${d.model} / ${d.model_version} · top probability ${(d.confidence * 100).toFixed(1)}% · margin ${d.margin.toFixed(2)} · ${d.latency_ms} ms. Scores are advisory and not calibrated accuracy.`));
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
  for (const f of state.rules.findings) { const row = el("div", undefined, "finding"); row.append(el("strong", f.severity), el("span", f.message)); if (f.source_ref) row.append(el("p", `Guidance: ${f.source_ref}`, "muted")); if (Object.keys(f.calculation).length) row.append(el("pre", JSON.stringify(f.calculation, null, 2))); rules.append(row); } root.append(rules);
  const final = el("section", undefined, "card"); final.append(el("h2", "4. Confirm the final assessment"));
  final.append(el("p", "Review the draft and approve it once. Your approval includes the automatically prefilled facts and answers. Resolve highlighted exceptions first; you can edit any prefill.", "muted"));
  final.append(el("pre", state.draft || "Resolve exceptions to prepare the draft."));
  const f = el("form"), classification = select(["Choose classification", "ACCEPT", "REJECT"], state.final?.classification || state.draft_classification), rationale = noteBox(), ack = input("", "checkbox"); rationale.maxLength = 4000; rationale.value = state.final?.rationale || state.draft_rationale || ""; ack.checked = Boolean(state.final);
  const category = select(["NOT_FEASIBLE", "OUT_OF_RESOURCES"], state.final?.rejection_category || "NOT_FEASIBLE"), globalComment = noteBox(), exception = noteBox(); globalComment.maxLength = 4000; exception.maxLength = 4000;
  globalComment.value = state.final?.global_comment || ""; exception.value = state.final?.exception_note || "";
  const rejectionDetails = el("select"); rejectionDetails.multiple = true;
  for (const [value,text] of [["custom_software","Request core dependency details"],["workplan","Request a more detailed workplan"],["resource_capacity","Request amended resource amounts"]]) { const option = el("option",text); option.value = value; option.selected = state.final?.rejection_details?.includes(value) || false; rejectionDetails.append(option); }
  f.append(label("Final classification", classification), label("Classification rationale", rationale)); const check = label("I approve this assessment, including its prefilled facts and answers, and have reviewed the warnings.", ack); check.className = "check"; f.append(check);
  f.append(label("Rejection category (ineligibility uses NOT_FEASIBLE)", category), label("Additional rejection wording (optional; deselect for acceptance)", rejectionDetails), label("Global technical comments", globalComment), label("Evidence supporting exceptions to blocking guidance (required when accepting despite blockers)", exception));
  submit(f, state.policy.mode === "shadow" ? "Approve shadow assessment" : "Approve assessment", () => mutate("finalize", { classification: classification.value, rationale: rationale.value, acknowledge_findings: ack.checked, rejection_category: category.value, rejection_details: selected(rejectionDetails), global_comment: globalComment.value, exception_note: exception.value })); final.append(f);
  for (const followUp of state.final?.follow_up || []) final.append(el("p", followUp, "banner warning"));
  if (state.final) { final.append(el("pre", state.final.text)); const download = el("button", "Download assessment", "secondary"); download.onclick = () => run(download, async () => { const text = await api(`/api/reviews/${state.id}/export`); saveFile(text, `review-${state.id.slice(0, 8)}.txt`, "text/plain"); }); final.append(download); }
  root.append(final);
  const tools = el("div", undefined, "row"), audit = el("button", "Download audit metadata", "secondary"), remove = el("button", "Delete this review and audit", "danger");
  audit.onclick = () => run(audit, async () => saveFile(JSON.stringify(await api(`/api/reviews/${state.id}/audit`), null, 2), "audit.json", "application/json"));
  remove.onclick = () => { if (window.confirm("Permanently delete this review and its audit records?")) run(remove, async () => { await api(`/api/reviews/${state.id}`, { method: "DELETE" }); state = null; root.replaceChildren(); await library(); message("Review and audit deleted."); }); }; tools.append(audit, remove); root.append(tools);
}
function saveFile(text, name, type) { const url = URL.createObjectURL(new Blob([text], { type })); const a = el("a"); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); }
