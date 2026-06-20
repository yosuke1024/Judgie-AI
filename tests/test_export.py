import io
import zipfile

from core.db import User, create_hackathon, save_evaluation, set_ai_response_languages
from core.services.export_service import (
    export_hackathon_to_markdown,
    generate_all_teams_pdf_zip,
    generate_team_pdf_report,
)


def test_export_service_logic(db_session_fixture):
    db = db_session_fixture

    # 1. Create a hackathon and configure language settings
    h_id = create_hackathon(
        name="Test Export Hackathon", admin_id="test_export_admin", admin_pass="admin123", template_id="hackathon"
    )

    set_ai_response_languages(h_id, ["English", "Japanese"])

    # 2. Register a team
    team_user = User(
        hackathon_id=h_id,
        team_id="team_alpha",
        passcode="pass123",
        role="team",
        team_name="Alpha Team",
        product_name="Alpha App",
        one_liner="Best app ever",
    )
    db.add(team_user)
    db.commit()

    # 3. Create a mock evaluation result conforming to the sanitize structure
    result_json = {
        "scores": {
            "Innovation & Creativity": 4.0,
            "Technical Implementation": 3.0,
            "Problem Solving & Impact": 5.0,
            "Product & UX": 4.0,
            "Working Prototype": 4.0,
            "Presentation": 4.0,
        },
        "impact_score": 4.0,
        "product_understanding_english": "Alpha App solves X.",
        "product_understanding_japanese": "Alpha AppはXを解決します。",
        "action_items_english": ["Improve UI", "Add testing"],
        "action_items_japanese": ["UIを改善する", "テストを追加する"],
        "judges_feedback": [
            {
                "judge_name": "Alex",
                "judge_role": "VC",
                "feedback_english": "Great pitch",
                "feedback_japanese": "素晴らしいピッチ",
            }
        ],
    }

    save_evaluation(
        hackathon_id=h_id,
        team_id="team_alpha",
        result_json=result_json,
        is_final=True,
        source_text="print('Hello Alpha App!')",
    )

    # Verify Markdown export
    md_content = export_hackathon_to_markdown(h_id)
    assert "Test Export Hackathon" in md_content
    assert "Alpha Team" in md_content
    assert "Alpha App" in md_content
    assert "Alpha AppはXを解決します。" in md_content
    assert "Great pitch" in md_content
    assert "print('Hello Alpha App!')" in md_content

    # Verify PDF report generation
    pdf_bytes = generate_team_pdf_report(h_id, "team_alpha")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")

    # Verify ZIP batch export
    zip_bytes = generate_all_teams_pdf_zip(h_id)
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    # Ensure it's a valid ZIP and contains the correct report
    zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
    file_list = zip_file.namelist()
    assert "report_team_alpha.pdf" in file_list
