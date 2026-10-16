"use strict";
let token = "", state = null, sessionEpoch = 0, pending = false, savingForm = null;
const drafts = new Map();
function hasDrafts(exceptKey) { return [...drafts.keys()].some(key => key !== exceptKey); }
function controlValue(control) { return control.multiple ? selected(control) : control.type === "checkbox" ? control.checked : control.value; }
function setControlValue(control, value) { if (control.multiple) for (const option of control.options) option.selected = value.includes(option.value); else if (control.type === "checkbox") control.checked = value; else control.value = value; }
function bindForm(form, key) {
  form.dataset.draftKey = key;
  const controls = [...form.querySelectorAll("input, select, textarea")];
  controls.forEach((control, index) => {
    control.id = `edit-${key.replaceAll(":", "-")}-${index}`;
    const baseline = JSON.stringify(controlValue(control));
    if (drafts.get(key)?.has(index)) setControlValue(control, drafts.get(key).get(index));
    const track = () => {
      const values = drafts.get(key) || new Map(), value = controlValue(control);
      if (JSON.stringify(value) === baseline) values.delete(index); else values.set(index, value);
      if (values.size) drafts.set(key, values); else drafts.delete(key);
      updateControls();
    };
    control.addEventListener("input", track); control.addEventListener("change", track);
  });
}
function clearAcknowledgement() { const values = drafts.get("final"); if (values) { values.delete(2); if (!values.size) drafts.delete("final"); } }
function updateControls() {
  document.querySelectorAll("button, input, select, textarea").forEach(control => {
    if (control.id === "lock") return;
    control.disabled = pending || (control.dataset.export === "true" && hasDrafts()) || (control.dataset.approve === "true" && (hasDrafts("final") || !state?.draft_classification));
  });
  const approvalStatus = $("approval-status");
  if (approvalStatus) approvalStatus.textContent = hasDrafts("final") ? "Save your fact, answer, evidence, and extraction edits before approving." : !state?.draft_classification ? "Approval is unavailable until all exceptions are resolved and the access profile and target are supported." : "Ready for your final review. Choose a classification and tick the approval checkbox before approving.";
  const status = $("draft-status");
  if (status) status.textContent = hasDrafts() ? "Unsaved edits in this review. Save them before exporting; save fact and answer edits before approval." : state?.final ? "Assessment approved. Export is available for this saved revision." : "Changes are saved locally. Final approval is still required.";
}
function discardDrafts() { if (hasDrafts() && !window.confirm("Discard unsaved edits in this review?")) return false; return true; }
window.addEventListener("beforeunload", event => { if (hasDrafts()) { event.preventDefault(); event.returnValue = ""; } });
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
  if (!response.ok) { let body; try { body = await response.json(); } catch { body = { error: "Local request failed" }; } const error = new Error(body.error); error.status = response.status; throw error; }
  return response.headers.get("Content-Type").includes("application/json") ? response.json() : response.text();
}
async function run(button, fn) {
  if (pending) return;
  // Capture focus before disabling controls: browsers blur disabled elements.
  const epoch = sessionEpoch, focusId = document.activeElement?.id || button?.id;
  pending = true; updateControls();
  try { await fn(); }
  catch (e) { if (epoch === sessionEpoch) { message(e.message, "error"); if (e.status === 409 && state) { const reload = el("button", "Reload latest and keep my edits", "secondary"); reload.id = "reload-latest"; reload.onclick = () => run(reload, reloadLatest); $("message").append(reload); } } }
  finally { if (epoch === sessionEpoch) { pending = false; updateControls(); if (focusId) { const target = $(focusId) || $("message"); if (!target.disabled) { if (target.id === "message") target.tabIndex = -1; target.focus({preventScroll: true}); } } } }
}
async function refreshLibraryAfterSave(epoch) {
  try { await library(); } catch (e) { if (epoch === sessionEpoch) message(`Saved locally. The review list could not refresh: ${e.message}`, "warning"); }
}
async function mutate(action, data) {
  if (action === "finalize" && hasDrafts("final")) throw new Error("Save your fact, answer, and evidence edits before approving.");
  const id = state.id, epoch = sessionEpoch, key = savingForm;
  const result = await api(`/api/reviews/${id}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision: state.revision, ...data }) });
  if (epoch !== sessionEpoch || state?.id !== id) return;
  const detailState = [...$("review").querySelectorAll("details[id]")].map(node => [node.id, node.open]);
  if (key) drafts.delete(key);
  clearAcknowledgement(); state = result; render();
  for (const [id, open] of detailState) if ($(id)) $(id).open = open;
  message("Saved locally."); await refreshLibraryAfterSave(epoch);
}
async function reloadLatest() {
  const id = state.id, epoch = sessionEpoch;
  const result = await api(`/api/reviews/${id}`);
  if (epoch !== sessionEpoch || state?.id !== id) return;
  clearAcknowledgement(); state = result; render(); message("Latest saved revision loaded. Your unsaved edits are retained; check them against the updated evidence before saving.", "banner");
}
function submit(form, text, fn, key) {
  const b = el("button", text); if (key) b.id = `save-${key.replaceAll(":", "-")}`; form.append(b); if (key) bindForm(form, key);
  form.addEventListener("submit", event => { event.preventDefault(); run(b, async () => { savingForm = key; try { await fn(); } finally { savingForm = null; } }); }); return b;
}
function evidenceSelect(ids = []) {
  const picker = el("select"); picker.multiple = true; picker.required = true;
  for (const ev of state.document.evidence.filter(e => e.scope !== "assessment")) { const o = el("option", `${ev.id} · p. ${ev.page} · ${ev.text.slice(0, 100)}`); o.value = ev.id; o.selected = ids.includes(ev.id); picker.append(o); }
  return picker;
}
function selected(picker) { return Array.from(picker.selectedOptions, o => o.value); }
function evidenceCard(ev) { const box = el("div", undefined, "evidence"); box.append(el("small", `${ev.id} · Page ${ev.page} · ${ev.section}${ev.scope === "assessment" ? " · Reviewer form — excluded from proposal evidence" : ""}`), el("p", ev.text)); return box; }
async function library() {
  const epoch = sessionEpoch; const records = await api("/api/reviews"); if (epoch !== sessionEpoch) return; $("reviews").replaceChildren();
  for (const review of records) { const b = el("button", `${review.finalized ? "✓ " : "○ "}${review.id.slice(0, 8)} · ${new Date(review.created_at).toLocaleDateString()}`, "review-link"); b.onclick = () => run(b, async () => { if (!discardDrafts()) return; const epoch = sessionEpoch; const result = await api(`/api/reviews/${review.id}`); if (epoch !== sessionEpoch) return; drafts.clear(); state = result; render(); message("Saved review opened."); }); b.id = `open-${review.id}`; b.dataset.reviewId = review.id; b.setAttribute("aria-current", String(state?.id === review.id)); $("reviews").append(b); } updateControls();
}
$("login").addEventListener("submit", event => { event.preventDefault(); run(event.submitter, async () => {
  const epoch = sessionEpoch; token = $("key").value.trim(); const config = await api("/api/config"); if (epoch !== sessionEpoch) return; $("key").value = "";
  $("login").hidden = true; $("library").hidden = false; $("workspace").hidden = false; $("welcome").hidden = true;
  $("identity").textContent = `Reviewer: ${config.reviewer}`;
  $("runtime").textContent = `${config.policy.mode.toUpperCase()} · Backend: ${config.backend} · ${config.policy.approved ? "Approved policy" : "Provisional policy — validate before production"}`;
  await library(); if (epoch === sessionEpoch) message("Workspace unlocked. Access key stays in this tab's memory.");
}); });
$("lock").onclick = () => { if (!discardDrafts()) return; sessionEpoch++; drafts.clear(); pending = false; savingForm = null; token = ""; state = null; $("review").replaceChildren(); $("reviews").replaceChildren(); $("workspace").hidden = true; $("library").hidden = true; $("login").hidden = false; $("welcome").hidden = false; message(""); updateControls(); $("key").focus(); };
$("upload").addEventListener("submit", event => { event.preventDefault(); run(event.submitter, async () => {
  if (!discardDrafts()) return; const epoch = sessionEpoch; const file = $("pdf").files[0]; if (!file || file.size > 20 * 1024 * 1024) throw new Error("Choose a PDF of at most 20 MiB");
  message("Extracting evidence and running configured local review checks…", "banner");
  const result = await api("/api/reviews", { method: "POST", headers: { "Content-Type": "application/pdf" }, body: file });
  if (epoch !== sessionEpoch) return; drafts.clear(); state = result; $("pdf").value = ""; render(); message("Draft ready. Resolve the highlighted exceptions, then approve the assessment."); await refreshLibraryAfterSave(epoch);
}); });
function render() {
  const root = $("review"); root.replaceChildren();
  for (const button of $("reviews").querySelectorAll("button")) button.setAttribute("aria-current", String(button.dataset.reviewId === state.id));
  const heading = el("div", undefined, "row"); heading.append(el("h2", `Review ${state.id.slice(0, 8)}`), el("span", `Revision ${state.revision}`, "badge")); root.append(heading);
  root.append(el("small", `Proposal hash: ${state.document.document_id}`));
  if (state.facts.access_mode.value && !["FAST_LANE", "PLAYGROUND"].includes(state.facts.access_mode.value)) root.append(el("p", `Detected access mode: ${state.facts.access_mode.value}. Evidence inspection is available; Fast Lane model recommendations, rules and final export do not apply.`, "banner warning"));
  if (state.registry.profile === "PLAYGROUND") root.append(el("p", "Playground onboarding review: a named AMD-capable stack and a concrete trial or onboarding task are sufficient. Detailed job budgets and measured scaling are not required.", "banner"));
  const exceptions = state.exceptions || {facts: [], decisions: []};
  root.append(el("p", `${exceptions.facts.length} fact gaps · ${exceptions.decisions.length} decision exceptions. Clear facts and supported answers are prefilled for final approval.`, "banner"));
  const status = el("p", "", "banner"); status.id = "draft-status"; status.setAttribute("role", "status"); root.append(status);
  const nav = el("nav", undefined, "review-nav"); nav.setAttribute("aria-label", "Review actions");
  const jump = (text, target) => { const link = el("a", text); link.href = `#${target}`; link.onclick = event => { event.preventDefault(); const node = $(target); if (!node) return; for (let parent = node; parent; parent = parent.parentElement) if (parent.tagName === "DETAILS") parent.open = true; const focus = node.querySelector("summary") || node; focus.focus(); node.scrollIntoView({block: "start"}); }; nav.append(link); };
  if (exceptions.extraction) jump("Check extraction warnings", "extraction");
  for (const field of exceptions.facts) jump(`Fact: ${field.replaceAll("_", " ")}`, `fact-${field}`);
  for (const qid of exceptions.decisions) jump(state.registry.questions[qid].title, `decision-${qid}`);
  jump("AI workload assessment", "workload-assessment");
  jump("All evidence / add passage", "all-evidence"); jump(state.draft_classification ? "Review assessment" : "Assessment — resolve exceptions first", "assessment"); root.append(nav);
  if (state.document.warnings.length) {
    const box = el("div", undefined, "card warning"); box.id = "extraction"; box.tabIndex = -1; box.append(el("h3", "Extraction needs attention"));
    for (const text of state.document.warnings) box.append(el("p", text));
    box.append(el("p", state.extraction_resolved ? "Reviewer marked extraction checked." : "Add manual evidence below for unreadable pages, then record how you checked all gaps."));
    const f = el("form"), n = noteBox(); f.append(label("Verification note", n)); submit(f, "Mark extraction checked", () => mutate("resolve-extraction", { note: n.value }), "extraction"); box.append(f); root.append(box);
  }
  if (state.workload) {
    const workload = el("section", undefined, "card"); workload.id = "workload-assessment"; workload.tabIndex = -1;
    workload.append(el("h2", "AI workload assessment"), el("p", "Advisory findings for your judgment. Verify potential material concerns before using them as a reason for rejection. Routine setup and exploratory uncertainty can be addressed in comments.", "muted"));
    if (state.workload.stale) workload.append(el("p", "Workload findings are out of date after evidence/fact changes or reference expiry. The previous findings remain below for inspection, not as current advice. Re-run suggestions; expired references need a maintained configuration update. Revise any findings already copied into Global technical comments.", "banner warning"));
    for (const finding of state.workload.findings) {
      workload.append(el("h3", `${finding.title} · ${finding.finding}${state.workload.stale ? " · Out of date" : ""}`), el("p", finding.explanation), el("small", `Assessment status: ${finding.decision.status} · evidence: ${finding.decision.evidence_ids.join(", ") || "none"}`));
      const support = el("details"); support.append(el("summary", "Inspect evidence used for this finding"));
      for (const ev of state.document.evidence.filter(e => finding.decision.evidence_ids.includes(e.id))) support.append(evidenceCard(ev));
      workload.append(support);
    }
    const summary = el("details"); summary.append(el("summary", "Workload summary — proposal excerpts, not verified facts"));
    for (const item of state.workload.summary) {
      summary.append(el("h3", item.label));
      if (!item.passages.length) summary.append(el("p", "Not identified in the relevant proposal passages."));
      for (const passage of item.passages) summary.append(el("p", `${passage.text} [${passage.evidence_id}, p. ${passage.page}]`));
    }
    workload.append(summary);
    const references = el("details"); references.append(el("summary", "Dated official LUMI reference facts"));
    for (const reference of state.workload.references) references.append(el("p", reference.claim), el("small", `${reference.source} · checked ${reference.checked}; expires ${reference.expires}`));
    workload.append(references); root.append(workload);
  } else {
    const workload = el("section", undefined, "card"); workload.id = "workload-assessment"; workload.tabIndex = -1;
    workload.append(el("h2", "AI workload assessment"), el("p", "This saved review has no structured workload assessment. Previously entered global comments are not live findings. Upload the proposal again to use the current workload assessment.")); root.append(workload);
  }
  const facts = el("details"); facts.id = "facts"; facts.open = exceptions.facts.length > 0; facts.append(el("summary", "1. Extracted facts — resolve gaps or inspect prefills"));
  facts.append(el("p", "Required facts are marked *. Clearly sourced values need no individual confirmation. Corrections invalidate model answers. Units follow each field name: GPU hours and node hours are distinct, as are GB, TB and TBh.", "muted"));
  const grid = el("div", undefined, "fact-grid");
  for (const [field, fact] of Object.entries(state.facts)) {
    if (fact.derived || (fact.optional_resource_field && !fact.source && fact.status !== "CONFLICT")) continue;
    const card = el("details", undefined, "card"), form = el("form"); card.id = `fact-${field}`; card.open = requiredFacts.has(field) && !fact.ready;
    card.append(el("summary", `${field.replaceAll("_", " ")}: ${fact.value ?? "Missing"} · ${fact.confirmed ? "Reviewed" : fact.ready ? "Prefilled" : "Needs review"}`));
    card.append(el("h3", `${requiredFacts.has(field) ? "* " : ""}${field.replaceAll("_", " ")}`), el("span", fact.confirmed ? "Confirmed" : fact.ready ? "Automatically prefilled" : fact.status, fact.confirmed ? "badge success" : "badge"));
    if (fact.source) card.append(el("p", `p. ${fact.source.page}: ${fact.source.text}`, "muted"));
    if (fact.status === "CONFLICT") for (const c of fact.candidates) card.append(el("p", `p. ${c.source.page}: ${c.source.text}`, "warning"));
    const value = input(typeof fact.value === "boolean" ? (fact.value ? "yes" : "no") : (fact.value ?? ""));
    const status = select(field === "vat_number" ? ["PRESENT", "ABSENT"] : ["PRESENT"], fact.status);
    const sourceIds = fact.reviewer_evidence_ids || state.document.evidence.filter(e => fact.source && e.page === fact.source.page && e.text.includes(fact.source.text)).map(e => e.id);
    const picker = evidenceSelect(sourceIds), note = noteBox(); note.value = fact.reviewer_note || "";
    form.append(label("Verified value", value), label("Status", status), label("Supporting evidence (multiple selection allowed)", picker), label("Note (required for corrections)", note));
    submit(form, fact.ready ? "Save correction" : "Resolve fact", () => mutate("fact", { field, value: value.value, status: status.value, evidence_ids: selected(picker), note: note.value }), `fact:${field}`); card.append(form); grid.append(card);
  }
  facts.append(grid); root.append(facts);
  root.append(el("h2", "2. Resolve decision exceptions"));
  for (const [qid, d] of Object.entries(state.decisions)) {
    const card = el("details", undefined, "card"); card.id = `decision-${qid}`; card.open = !d.ready; card.append(el("summary", `${state.registry.questions[qid].title} · ${d.confirmed ? "Reviewed" : d.ready ? "Prefilled" : "Needs review"}`));
    if (state.registry.questions[qid].manual_only && !d.ready) card.append(el("p", "Manual verification required. Record the reference or justification in your note.", "banner"));
    card.append(el("p", d.confirmed ? `Confirmed answer: ${d.reviewer_answer} · Confirmed by reviewer; no further action required.` : `${state.registry.questions[qid].manual_only ? "Eligibility check" : d.checks ? "Combined answer" : "Model suggestion"}: ${d.answer} · ${d.ready ? "Included for final approval" : "Confirmation needed"}`));
    if (!d.ready && !d.confirmed) for (const reason of d.review_reasons || []) card.append(el("p", `Why confirmation is needed: ${reason}`, "warning"));
    if (d.checks) {
      card.append(el("p", (d.confirmed ? "Original automated assessment: " : "") + d.aggregation_reason));
      const checks = el("details"); checks.id = `checks-${qid}`; checks.open = !d.ready; checks.append(el("summary", "Evidence checks behind this answer"));
      for (const [cid, check] of Object.entries(d.checks)) {
        const basis = check.inference_mode === "source_claim" ? "source evidence" : `${(check.confidence * 100).toFixed(1)}% top score`;
        checks.append(el("p", `${check.check_title}: ${check.answer} · ${check.status} · ${basis} · sources: ${check.evidence_ids.join(", ") || "none"}`));
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
    else if (state.registry.questions[qid].manual_only) card.append(el("small", qid === "country_eligible" ? `Declared country: ${state.facts.country?.value || "not resolved"}. Country eligibility is checked against a dated reference list, not by the model. Automatic matching uses the verified country subset saved with this review. If the country is outside that subset, the reference has expired, or the country evidence is unresolved, verify the applicable eligible-country list and record your answer with its reference.` : "Organisation eligibility requires a source-backed rule match or reviewer verification; the model does not decide it. Review the declared category and applicable criteria, then record your answer and reference."));
    else if (!d.confirmed) card.append(el("small", noInference ? "No valid model inference is available. Review the evidence and record your answer." : d.checks ? `${d.model} · combined using explicit rules; minimum supporting check score ${(d.confidence * 100).toFixed(1)}%. This is not a probability of the combined answer.` : `${d.model} / ${d.model_version} · top score for ${d.model_answer || d.answer}: ${(d.confidence * 100).toFixed(1)}% · margin ${d.margin.toFixed(2)} · ${d.latency_ms} ms. Scores are advisory and not calibrated accuracy.`));
    if (d.status === "EVIDENCE_NOT_DEMONSTRATED") card.append(el("p", "NO: supporting evidence is not sufficient to establish this criterion. This is an evidence gap, not proof of incompatibility or impossibility.", "muted"));
    if (d.contradiction && !d.confirmed) card.append(el("p", "Possible evidence/decision contradiction. Explain your resolution in the note.", "banner warning"));
    for (const id of d.evidence_ids) { const ev = state.document.evidence.find(e => e.id === id); if (ev) card.append(evidenceCard(ev)); }
    if (!d.evidence_ids.length) card.append(el("p", "No relevant evidence retrieved. Inspect all passages or add a page transcription.", "warning"));
    const form = el("form"), answer = select(["UNKNOWN", "YES", "NO"], d.reviewer_answer || d.answer), picker = evidenceSelect(d.reviewer_evidence_ids || d.evidence_ids), note = noteBox(); note.value = d.reviewer_note;
    form.append(label("Your answer", answer), label("Evidence supporting your answer", picker), label("Reviewer note (required for overrides)", note));
    submit(form, d.confirmed ? "Update confirmed answer" : "Save reviewer answer", () => mutate("decision", { question_id: qid, answer: answer.value, evidence_ids: selected(picker), note: note.value }), `decision:${qid}`); card.append(form); root.append(card);
  }
  const all = el("details"); all.id = "all-evidence"; all.append(el("summary", "Inspect all proposal passages / add manual evidence"));
  for (const ev of state.document.evidence) all.append(evidenceCard(ev));
  const manual = el("form"), page = input("1", "number"), text = noteBox(), note = noteBox(); text.maxLength = 5000;
  manual.append(label("Proposal page", page), label("Passage transcribed from the proposal", text), label("Source / transcription note", note));
  submit(manual, "Add evidence", () => mutate("evidence", { page: Number(page.value), text: text.value, note: note.value }), "evidence");
  all.append(manual); const rerun = el("button", "Re-run suggestions (clears confirmations)", "secondary"); rerun.id = "rerun-suggestions"; rerun.onclick = () => run(rerun, () => mutate("analyze", {})); all.append(rerun); root.append(all);
  root.append(el("h2", "3. Inspect deterministic checks"));
  const rules = el("div", undefined, "card"); rules.append(el("p", `Suggested classification: ${state.rules.suggested} · ${state.rules.version}`));
  for (const f of state.rules.findings) { const row = el("div", undefined, "finding"); row.append(el("strong", f.severity), el("span", f.message)); if (f.source_ref) row.append(el("p", `Guidance: ${f.source_ref}`, "muted")); if (Object.keys(f.calculation).length) row.append(el("pre", JSON.stringify(f.calculation, null, 2))); rules.append(row); } root.append(rules);
  const final = el("section", undefined, "card"); final.id = "assessment"; final.tabIndex = -1; final.append(el("h2", "4. Confirm the final assessment"));
  final.append(el("p", "Review the draft and approve it once. Your approval includes the automatically prefilled facts and answers. Resolve highlighted exceptions first; you can edit any prefill.", "muted"));
  const approvalStatus = el("p", "", "banner"); approvalStatus.id = "approval-status"; final.append(approvalStatus);
  final.append(el("pre", state.draft || "Resolve exceptions to prepare the draft."));
  const f = el("form"), classification = select(["Choose classification", "ACCEPT", "REJECT"], state.final?.classification || state.draft_classification), rationale = noteBox(), ack = input("", "checkbox"); rationale.maxLength = 4000; rationale.value = state.final?.rationale || state.draft_rationale || ""; ack.checked = false;
  const category = select(["NOT_FEASIBLE", "OUT_OF_RESOURCES"], state.final?.rejection_category || "NOT_FEASIBLE"), globalComment = noteBox(), exception = noteBox(); globalComment.maxLength = 4000; exception.maxLength = 4000;
  globalComment.value = state.final?.global_comment ?? state.draft_global_comment ?? ""; exception.value = state.final?.exception_note || "";
  const rejectionDetails = el("select"); rejectionDetails.multiple = true;
  for (const [value,text] of [["custom_software","Request core dependency details"],["workplan","Request a more detailed workplan"],["resource_capacity","Request amended resource amounts"]]) { const option = el("option",text); option.value = value; option.selected = state.final?.rejection_details?.includes(value) || false; rejectionDetails.append(option); }
  const reasonField = el("div"); reasonField.append(label("Reason for classification", rationale));
  f.append(label("Final classification", classification), reasonField); const check = label("I approve this assessment, including its prefilled facts and answers, and have reviewed the warnings.", ack); check.className = "check"; f.append(check);
  f.append(label("Rejection category (ineligibility uses NOT_FEASIBLE)", category), label("Additional rejection wording (optional; deselect for acceptance)", rejectionDetails), label("Global technical comments — visible in the portal", globalComment), label("Evidence supporting exceptions to blocking guidance (required when accepting despite blockers)", exception));
  reasonField.append(el("small", "The draft combines relevant workload findings. Check the evidence and edit this reason before approval."));
  // Previous versions copied internal diagnostics into comments. Removal is explicit
  // so saved reviewer wording and approved exports are never silently rewritten.
  const internalWorkloadLine = /^(?:Technical fit|Resource fit|Plan credibility) — (?:Needs clarification|Plausible|Potential material concern):[^\n]*\[proposal evidence: [^\n]*\]\s*$/gm;
  if (globalComment.value.match(internalWorkloadLine)) {
    const cleanComments = el("button", "Remove previous internal workload text from comments", "secondary"); cleanComments.type = "button"; cleanComments.id = "clean-workload-comments";
    cleanComments.onclick = () => { globalComment.value = globalComment.value.replace(internalWorkloadLine, "").trim(); globalComment.dispatchEvent(new Event("input")); ack.checked = false; ack.dispatchEvent(new Event("input")); message("Internal workload lines removed from editable comments. Review and approve to update the assessment."); };
    final.append(cleanComments);
  }
  const approve = submit(f, state.policy.mode === "shadow" ? "Approve shadow assessment" : "Approve assessment", () => mutate("finalize", { classification: classification.value, rationale: rationale.value, acknowledge_findings: ack.checked, rejection_category: category.value, rejection_details: selected(rejectionDetails), global_comment: globalComment.value, exception_note: exception.value }), "final"); approve.dataset.approve = "true"; final.append(f);
  for (const followUp of state.final?.follow_up || []) final.append(el("p", followUp, "banner warning"));
  if (state.final) { final.append(el("pre", state.final.text)); const download = el("button", "Download assessment", "secondary"); download.id = "download-assessment"; download.onclick = () => run(download, async () => { if (hasDrafts()) throw new Error("Save your edits before exporting."); const id = state.id, epoch = sessionEpoch; const text = await api(`/api/reviews/${id}/export`); if (epoch === sessionEpoch && state?.id === id) saveFile(text, `review-${id.slice(0, 8)}.txt`, "text/plain"); }); download.dataset.export = "true"; final.append(download); }
  root.append(final);
  const tools = el("div", undefined, "row"), audit = el("button", "Download audit metadata", "secondary"), remove = el("button", "Delete this review and audit", "danger");
  audit.id = "download-audit"; remove.id = "delete-review";
  audit.onclick = () => run(audit, async () => { const id = state.id, epoch = sessionEpoch; const result = await api(`/api/reviews/${id}/audit`); if (epoch === sessionEpoch) saveFile(JSON.stringify(result, null, 2), "audit.json", "application/json"); });
  remove.onclick = () => { if (window.confirm("Permanently delete this review and its audit records?")) run(remove, async () => { const id = state.id, epoch = sessionEpoch; await api(`/api/reviews/${id}`, { method: "DELETE" }); if (epoch !== sessionEpoch) return; drafts.clear(); state = null; root.replaceChildren(); await library(); if (epoch === sessionEpoch) message("Review and audit deleted."); }); }; tools.append(audit, remove); root.append(tools); updateControls();
}
function saveFile(text, name, type) { const url = URL.createObjectURL(new Blob([text], { type })); const a = el("a"); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); }
