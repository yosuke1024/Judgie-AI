from unittest.mock import ANY

from core.services.submission_service import process_submission, sanitize_evaluation_response


def test_sanitize_evaluation_response():
    # Normal case
    input_data = {
        "product_understanding_en": "understanding",
        "product_understanding_ja": "理解",
        "action_items_en": ["item1"],
        "action_items_ja": ["アイテム1"],
        "scores": {"Innovation": 4.5},
        "impact_score": 4.0,
        "judges_feedback": [
            {
                "judge_name": "Lisa",
                "judge_role": "Designer",
                "judge_persona": "UX focused",
                "judge_scores": [{"criteria_name": "Product & UX", "score": 4.0}],
                "feedback_en": "Great UI",
                "feedback_ja": "素晴らしいUI"
            }
        ]
    }

    res = sanitize_evaluation_response(input_data)
    assert res["product_understanding_english"] == "understanding"
    assert res["action_items_english"] == ["item1"]
    assert res["judges_feedback"][0]["judge_name"] == "Lisa"
    assert res["judges_feedback"][0]["feedback_english"] == "Great UI"

    # Sanitize invalid or missing values
    bad_input = {
        "action_items_english": "not_a_list",
        "judges_feedback": [
            "not_a_dict",
            {"judge_name": "David"}  # Partial missing keys
        ]
    }
    res_bad = sanitize_evaluation_response(bad_input)
    assert isinstance(res_bad["action_items_english"], list)
    assert res_bad["action_items_english"] == ["not_a_list"]
    assert len(res_bad["judges_feedback"]) == 1
    assert res_bad["judges_feedback"][0]["judge_name"] == "David"
    assert res_bad["judges_feedback"][0]["judge_role"] == "Expert Panelist" # Default fallback

    # Dynamic multi-language case
    custom_langs = ["English", "Spanish", "French"]
    input_multilang = {
        "product_understanding_en": "understanding",
        "product_understanding_es": "comprehension",
        "product_understanding_french": "comprendre",
        "action_items_en": ["item1"],
        "action_items_es": ["item1_es"],
        "action_items_french": ["item1_fr"],
        "scores": {"Innovation": 4.5},
        "impact_score": 4.0,
        "judges_feedback": [
            {
                "judge_name": "Lisa",
                "feedback_en": "Great UI",
                "feedback_es": "Buen UI",
                "feedback_french": "Bon UI"
            }
        ]
    }
    res_multi = sanitize_evaluation_response(input_multilang, custom_langs)
    assert res_multi["product_understanding_english"] == "understanding"
    assert res_multi["product_understanding_spanish"] == "comprehension"
    assert res_multi["product_understanding_french"] == "comprendre"
    assert res_multi["action_items_french"] == ["item1_fr"]
    assert res_multi["judges_feedback"][0]["feedback_spanish"] == "Buen UI"
    assert res_multi["judges_feedback"][0]["feedback_french"] == "Bon UI"

def test_process_submission_with_zip_and_media(mocker):
    # Simulate uploading a ZIP file and an MP4 video file
    mock_zip = mocker.MagicMock()
    mock_zip.name = "code.zip"

    mock_media = mocker.MagicMock()
    mock_media.name = "demo.mp4"
    mock_media.read.return_value = b"video_data"

    # Mocking related utility functions
    mock_extract = mocker.patch("core.services.submission_service.extract_text_from_zip", return_value="print('hello')")

    mock_file_obj = mocker.MagicMock()
    mock_file_obj.name = "files/mock-media-id"
    mock_upload = mocker.patch("core.services.submission_service.upload_to_gemini", return_value=mock_file_obj)

    mock_wait = mocker.patch("core.services.submission_service.wait_for_files_active")

    mock_analysis = mocker.patch("core.services.submission_service.analyze_submission", return_value={
        "product_understanding_en": "nice",
        "scores": {},
        "impact_score": 4.0,
        "judges_feedback": []
    })

    mock_save = mocker.patch("core.services.submission_service.save_evaluation")

    # Execute submission workflow processing
    res = process_submission(
        hackathon_id=1,
        team_id="teamA",
        uploaded_files=[mock_zip, mock_media],
        prev_evaluations_json="{}",
        is_final=False
    )

    # Verify each processing step is executed with correct arguments
    mock_extract.assert_called_once_with(mock_zip)
    mock_upload.assert_called_once_with(1, ANY, mime_type="video/mp4")
    mock_wait.assert_called_once_with(1, [mock_file_obj])
    mock_analysis.assert_called_once_with(1, "print('hello')", [mock_file_obj], previous_evaluations_json="{}", is_final=False)
    mock_save.assert_called_once_with(1, "teamA", ANY, is_final=False, source_text="print('hello')", gemini_file_ids=["files/mock-media-id"])

    assert res["product_understanding_english"] == "nice"
