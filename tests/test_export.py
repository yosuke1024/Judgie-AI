import io
import zipfile

from app.models.db import User, init_db, save_evaluation, set_ai_response_languages, set_setting
from app.services.export_service import (
    export_project_to_markdown,
    export_project_to_markdown_zip,
    generate_all_teams_markdown_zip,
    generate_team_markdown_report,
)


def test_export_service_logic(db_session_fixture):
    db = db_session_fixture
    init_db()

    # 1. Configure settings
    set_setting("project_name", "Test Export Project", db=db)
    set_setting("template_id", "hackathon", db=db)
    set_ai_response_languages(["English", "Japanese"])

    # 2. Register a team
    team_user = User(
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
        team_id="team_alpha",
        result_json=result_json,
        is_final=True,
        source_text="print('Hello Alpha App!')",
    )

    # Verify Markdown export
    md_content = export_project_to_markdown()
    assert "Test Export Project" in md_content
    assert "Alpha Team" in md_content
    assert "Alpha App" in md_content
    assert "Alpha AppはXを解決します。" in md_content
    assert "Great pitch" in md_content
    assert "print('Hello Alpha App!')" in md_content

    # Verify Markdown report generation (without source code)
    rep_md = generate_team_markdown_report("team_alpha")
    assert "Alpha Team" in rep_md
    assert "Alpha AppはXを解決します。" in rep_md
    assert "print('Hello Alpha App!')" not in rep_md  # Code should not be in human report

    # Verify ZIP batch export
    zip_bytes = generate_all_teams_markdown_zip()
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    # Ensure it's a valid ZIP and contains the correct report
    zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
    file_list = zip_file.namelist()
    assert "report_team_alpha.md" in file_list

    # Verify Markdown ZIP export
    zip_md_bytes = export_project_to_markdown_zip()
    assert isinstance(zip_md_bytes, bytes)
    assert len(zip_md_bytes) > 0

    zip_md_file = zipfile.ZipFile(io.BytesIO(zip_md_bytes))
    md_file_list = zip_md_file.namelist()
    assert "00_project_meta.md" in md_file_list
    assert "team_team_alpha_markdown.md" in md_file_list

    meta_content = zip_md_file.read("00_project_meta.md").decode("utf-8")
    assert "Test Export Project" in meta_content

    team_md_content = zip_md_file.read("team_team_alpha_markdown.md").decode("utf-8")
    assert "Alpha Team" in team_md_content
    assert "Alpha AppはXを解決します。" in team_md_content
    assert "print('Hello Alpha App!')" in team_md_content
