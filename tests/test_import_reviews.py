import csv
import json

from app.import_reviews import HEADINGS, parse_review, build
from tests.helpers import pdf_bytes, TEXT


def description(answers=("YES", "NO", "YES"), classification="Accepted"):
    parts = []
    for (key, title), answer in zip(list(HEADINGS.items())[:3], answers):
        parts.append(f"_{title}_ \\[YES/NO\\]\n\n{answer}. Explanation.")
    parts.append(f"_Classification:_ [Accepted OR Rejected]\n{classification}")
    parts.append("_Reason for classification:_\nEvidence checked.")
    return "\n\n".join(parts)


def test_explicit_answers_and_escaped_newlines():
    result = parse_review(description().replace("\n", "\\n"))
    assert not result["issues"]
    assert result["gold"] == dict(software_gpu_capable="YES", code_previously_installed="NO", workplan_sufficient="YES", classification="ACCEPT")


def test_template_options_are_not_labels():
    result = parse_review(description(answers=("[YES/NO]",) * 3, classification="[Accepted OR Rejected]"))
    assert not result["gold"]
    assert len(result["issues"]) == 4


def test_duplicate_review_sections_are_flagged():
    result = parse_review(description() + "\n_Classification:_ Rejected")
    assert "duplicate_review_section:classification" in result["issues"]


def test_version_ambiguity_is_not_guessed(tmp_path):
    app_id = "EHPC-AIF-2026FL01-999"
    proposals = tmp_path / "pdfs"
    proposals.mkdir()
    (proposals / f"{app_id}_Example.pdf").write_bytes(pdf_bytes(TEXT.replace("synthetic-001", app_id)))
    (proposals / f"{app_id}_Example_EDITED.pdf").write_bytes(pdf_bytes(TEXT.replace("synthetic-001", app_id).replace("50000", "60000")))
    source = tmp_path / "reviews.csv"
    with source.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['Title','Description','State','IID'])
        writer.writeheader()
        writer.writerow(dict(Title=app_id, Description=description(), State='Closed', IID='1'))
    result = build(source, proposals, tmp_path / "output")
    assert result['fast_lane_candidates'] == 0
    assert result['issues']['multiple_pdf_versions'] == 1


def test_duplicate_bytes_keep_one_record_and_strip_assessment(tmp_path):
    app_id = "EHPC-AIF-2026FL01-999"
    proposals = tmp_path / "pdfs"
    proposals.mkdir()
    content = pdf_bytes(TEXT.replace("synthetic-001", app_id) + '\nTechnical Assessment\nReviewer gold answer: NO\n')
    for suffix in ('Example', 'Example (1)'):
        (proposals / f"{app_id}_{suffix}.pdf").write_bytes(content)
    source = tmp_path / "reviews.csv"
    with source.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['Title','Description','State','IID'])
        writer.writeheader()
        writer.writerow(dict(Title=app_id, Description=description(), State='Closed', IID='1'))
    result = build(source, proposals, tmp_path / "output", exposed=[app_id])
    assert result['fast_lane_candidates'] == 1
    record = json.loads((tmp_path/'output/gold-candidates.jsonl').read_text())
    assert record['split'] == 'development'
    assert 'Reviewer gold answer' not in str(record['pages'])
    assert not record['narrow_gold']


def test_unbracketed_classification_options_are_not_a_decision():
    parsed = parse_review(description(classification="Accepted OR Rejected"))
    assert 'classification' not in parsed['gold']


def test_related_projects_cannot_cross_evaluation_splits():
    from app.historical_evaluation import benchmark
    import pytest
    with pytest.raises(ValueError, match="cross"):
        benchmark([dict(application_id='a',group_id='same',split='development'),dict(application_id='b',group_id='same',split='heldout')], None, {})


def test_gold_review_text_never_enters_model_input():
    from app.historical_evaluation import benchmark
    from app.configuration import load_policy
    class Backend:
        name, version = 'fixture', '1'
        def decide(self, state, question):
            assert 'PRIVATE_GOLD_REVIEW' not in state
            return {'YES':.9,'NO':.05,'UNKNOWN':.05}
    record = dict(application_id='synthetic', group_id='one', split='development',
                  pages=[dict(page=1,text=TEXT)],
                  review_reference={'rationale':'PRIVATE_GOLD_REVIEW'},
                  gold=dict(software_gpu_capable='YES',code_previously_installed='NO',workplan_sufficient='YES'))
    result = benchmark([record], Backend(), load_policy())
    assert result['applications'] == 1 and not result['classification_evaluated']
