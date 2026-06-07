import pytest
import json
from core.gemini import (
    configure_gemini, upload_to_gemini, wait_for_files_active,
    analyze_submission, object_to_judges, admin_chat_about_submission
)

def test_configure_gemini_success(mocker):
    # Case where API key is correctly configured
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mock_config = mocker.patch("google.generativeai.configure")
    
    configure_gemini(1)
    
    mock_config.assert_called_once_with(api_key="test_api_key")

def test_configure_gemini_missing_key(mocker):
    # Case where API key is missing
    mocker.patch("core.gemini.get_setting", return_value=None)
    
    with pytest.raises(ValueError) as excinfo:
        configure_gemini(1)
        
    assert "Gemini API Key has not been set" in str(excinfo.value)

def test_upload_to_gemini(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("google.generativeai.configure")
    mock_upload = mocker.patch("google.generativeai.upload_file", return_value="mock_file_obj")
    
    res = upload_to_gemini(1, "dummy_path.mp4", mime_type="video/mp4")
    
    assert res == "mock_file_obj"
    mock_upload.assert_called_once_with("dummy_path.mp4", mime_type="video/mp4")

def test_wait_for_files_active_success(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("google.generativeai.configure")
    mocker.patch("time.sleep")  # Mock sleep to accelerate test runs
    
    # Mocking file states: 
    # Return PROCESSING on the first call, and ACTIVE on the second call.
    mock_file_processing = mocker.MagicMock()
    mock_file_processing.state.name = "PROCESSING"
    mock_file_active = mocker.MagicMock()
    mock_file_active.state.name = "ACTIVE"
    
    mocker.patch("google.generativeai.get_file", side_effect=[mock_file_processing, mock_file_active])
    
    mock_file_input = mocker.MagicMock()
    mock_file_input.name = "files/testfile"
    
    # Verify execution completes without exceptions
    wait_for_files_active(1, [mock_file_input])

def test_wait_for_files_active_failed(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("google.generativeai.configure")
    mocker.patch("time.sleep")
    
    mock_file_failed = mocker.MagicMock()
    mock_file_failed.state.name = "FAILED"
    mock_file_failed.name = "files/testfile"
    
    mocker.patch("google.generativeai.get_file", return_value=mock_file_failed)
    
    mock_file_input = mocker.MagicMock()
    mock_file_input.name = "files/testfile"
    
    with pytest.raises(ValueError) as excinfo:
        wait_for_files_active(1, [mock_file_input])
        
    assert "File processing failed" in str(excinfo.value)

def test_analyze_submission(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("google.generativeai.configure")
    
    # Mock criteria & personas settings
    mocker.patch("core.gemini.get_criteria", return_value=[{"name": "Innovation", "weight": 50, "description": "desc"}])
    mocker.patch("core.gemini.get_personas", return_value=[
        {"name": "Alex", "active": True, "prompt": "prompt1"},
        {"name": "David", "active": False, "prompt": "prompt2"} # Inactive judge
    ])
    
    # Mock GenerativeModel instance
    mock_response = mocker.MagicMock()
    mock_response.text = '{"scores": {"Innovation": 4.5}, "impact_score": 4.5}'
    mock_model = mocker.MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    res = analyze_submission(
        hackathon_id=1,
        text_content="print('hello')",
        gemini_media_files=["media_mock"],
        previous_evaluations_json='{"prev": "data"}',
        is_final=True
    )
    
    assert res["scores"]["Innovation"] == 4.5
    assert res["impact_score"] == 4.5
    mock_model.generate_content.assert_called_once()

def test_object_to_judges(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("google.generativeai.configure")
    mocker.patch("core.gemini.get_personas", return_value=[{"name": "Alex", "active": True, "prompt": "prompt1"}])
    
    mock_response = mocker.MagicMock()
    mock_response.text = '{"qa_summary_en": "Objection rejected", "judges_responses": []}'
    mock_model = mocker.MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    res = object_to_judges(
        hackathon_id=1,
        text_content="print('hello')",
        gemini_media_files=None,
        previous_evaluation_json="{}",
        objection_text="I objection"
    )
    
    assert res["qa_summary_en"] == "Objection rejected"

def test_admin_chat_about_submission(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("google.generativeai.configure")
    
    # Mock genai.get_file API
    mock_file = mocker.MagicMock()
    mock_file.name = "files/test"
    mocker.patch("google.generativeai.get_file", return_value=mock_file)
    
    mock_response = mocker.MagicMock()
    mock_response.text = '{"question_en": "Q?", "question_ja": "Q_ja?", "answer_en": "Ans", "answer_ja": "Ans_ja"}'
    mock_model = mocker.MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    res = admin_chat_about_submission(
        hackathon_id=1,
        source_text="source",
        gemini_file_ids_json='["files/test"]',
        previous_evaluation_json="{}",
        admin_question="what is this?"
    )
    
    assert res["answer_en"] == "Ans"
    assert res["answer_ja"] == "Ans_ja"
