import json
import time

from google import genai
from google.genai import types

from core.db import get_criteria, get_personas, get_setting, get_ai_response_languages, normalize_lang_to_key


def get_gemini_client(hackathon_id, api_key_override=None):
    """Returns an initialized Gemini client using the database or key override."""
    api_key = api_key_override if api_key_override else get_setting(hackathon_id, 'gemini_api_key')
    if not api_key:
        raise ValueError("Gemini API Key has not been set by the Admin yet. Please contact the organizer.")
    return genai.Client(api_key=api_key)

def configure_gemini(hackathon_id, api_key_override=None):
    """
    Deprecated in favor of get_gemini_client.
    Kept for backward compatibility and testing.
    """
    # Verify that we can obtain a client (will raise ValueError if missing)
    get_gemini_client(hackathon_id, api_key_override=api_key_override)

def list_available_gemini_models(hackathon_id, api_key_override=None):
    """
    Fetches the dynamically available Gemini models from the API.
    Optionally overrides the API key (used for validation before saving).
    """
    try:
        client = get_gemini_client(hackathon_id, api_key_override=api_key_override)
        models = client.models.list()
        gemini_models = []
        for m in models:
            if m.supported_actions and 'generateContent' in m.supported_actions:
                name = m.name.replace("models/", "")
                if name.startswith("gemini-"):
                    gemini_models.append(name)
        gemini_models.sort()
        return gemini_models
    except Exception as e:
        raise ValueError(f"Failed to fetch models from Gemini API: {str(e)}")

def upload_to_gemini(hackathon_id, file_path, mime_type=None):
    """Uploads the given file to Gemini."""
    client = get_gemini_client(hackathon_id)
    config = types.UploadFileConfig(mime_type=mime_type) if mime_type else None
    file = client.files.upload(file=file_path, config=config)
    return file

def wait_for_files_active(hackathon_id, files):
    """Waits for the given files to be active in Gemini."""
    client = get_gemini_client(hackathon_id)
    for name in (file.name for file in files):
        file = client.files.get(name=name)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = client.files.get(name=name)
        if file.state.name == "FAILED":
            raise ValueError(f"File processing failed: {file.name}")

def analyze_submission(hackathon_id, text_content, gemini_media_files=None, previous_evaluations_json=None, is_final=False):
    """
    Calls Gemini API with multimodal input and returns structured JSON.
    Uses 'gemini-3.1-pro' to handle large contexts (code + video).
    """
    client = get_gemini_client(hackathon_id)

    model_name = get_setting(hackathon_id, 'gemini_model') or "gemini-2.5-flash"

    criteria = get_criteria(hackathon_id)
    active_personas = [p for p in get_personas(hackathon_id) if p.get('active', False)]

    criteria_str = "\n".join([f"- {c['name']} (Weight: {c['weight']}%): {c.get('description', '')}" for c in criteria])
    personas_str = "\n".join([f"Name: {p['name']}\nRole: {p.get('role', 'Expert')}\nPersona Definition: {p['prompt']}\n" for p in active_personas])

    context_str = ""
    if previous_evaluations_json:
        context_str = f"""
<previous_evaluation_data format="json">
{previous_evaluations_json}
</previous_evaluation_data>

<critical_instructions>
This team is submitting a revised version. You MUST carefully review the action items and feedback provided in the previous evaluation.
1. For each action item and piece of advice from the previous evaluation, explicitly check whether the team has addressed it or not.
2. If they have addressed a previous concern, treat it as a POSITIVE factor when scoring the relevant criteria. Acknowledge their effort and progress in your feedback.
3. However, you must ALSO evaluate the submission holistically. If new problems or regressions have been introduced in other areas, reflect that honestly in the scores. Improvement on previous advice does NOT guarantee a higher overall score.
4. In your feedback, clearly state which previous advice items were addressed and which were not.
</critical_instructions>
"""

    final_str = ""
    if is_final:
        final_str = "<submission_type>This is their FINAL SUBMISSION for the hackathon. Provide a definitive, conclusive evaluation and scoring.</submission_type>"
    else:
        final_str = "<submission_type>This is a CONSULTATION (work in progress). Provide constructive, coaching-focused feedback to help them improve before the final deadline.</submission_type>"

    # AIレスポンス言語設定を取得
    languages = get_ai_response_languages(hackathon_id)
    
    # 動的にJSONスキーマ指示文を構築
    pu_fields = []
    ai_fields = []
    fb_fields = []
    
    for lang in languages:
        lang_key = normalize_lang_to_key(lang)
        pu_fields.append(f'    "product_understanding_{lang_key}": "Detailed explanation of how the AI understands the product\'s problem, solution, and core value in {lang}."')
        ai_fields.append(f'    "action_items_{lang_key}": [\n        "Top priority action item 1 in {lang}",\n        "Top priority action item 2 in {lang}",\n        "Top priority action item 3 in {lang}"\n    ]')
        fb_fields.append(f'            "feedback_{lang_key}": "Deeply detailed, highly informative feedback in {lang} based on their persona and previous context."')
        
    pu_fields_str = ",\n".join(pu_fields)
    ai_fields_str = ",\n".join(ai_fields)
    fb_fields_str = ",\n".join(fb_fields)

    prompt = f"""You are orchestrating an AI Expert Panel for a Hackathon.
Analyze the provided source code, pitch materials, and demo video.

{final_str}

<evaluation_criteria>
{criteria_str}
</evaluation_criteria>
{context_str}
<expert_judges>
You must evaluate the submission from the perspectives of the following judges. Provide deeply detailed, highly informative, and encouraging feedback from each judge based on their specific persona.
{personas_str}
</expert_judges>

<critical_instructions>
- You MUST evaluate the submission and provide all explanation texts in the following languages: {", ".join(languages)}.
</critical_instructions>

<output_instructions format="json">
Output a strictly valid JSON object with the following structure:
{{
{pu_fields_str},
{ai_fields_str},
    "scores": {{
        // Provide an OVERALL consensus float score (0.0 to 5.0) for each criteria listed above. The keys must exactly match the criteria names.
    }},
    "impact_score": <float 0.0 to 5.0>,
    "judges_feedback": [
        {{
            "judge_name": "<Name of the judge>",
            "judge_role": "<Role of the judge>",
            "judge_persona": "<A brief 1-sentence summary of what this judge cares about>",
            "judge_scores": [
                {{
                    "criteria_name": "<Exact Criteria Name>",
                    "score": <float 0.0 to 5.0>
                }}
                // Provide a score for EVERY criteria from this specific judge's perspective
            ],
{fb_fields_str}
        }}
        // Repeat for EACH active judge
    ]
}}
</output_instructions>
"""

    contents = [prompt]
    if gemini_media_files:
        contents.extend(gemini_media_files)
    if text_content:
        contents.append(f"<source_code_and_documents>\n{text_content}\n</source_code_and_documents>")

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        )
    )
    return json.loads(response.text)

def object_to_judges(hackathon_id, text_content, gemini_media_files, previous_evaluation_json, objection_text):
    """
    Handles a one-shot QA/Objection from the team based on the previous evaluation.
    """
    client = get_gemini_client(hackathon_id)

    model_name = get_setting(hackathon_id, 'gemini_model') or "gemini-2.5-flash"

    active_personas = [p for p in get_personas(hackathon_id) if p.get('active', False)]
    personas_str = "\n".join([f"Name: {p['name']}\nRole: {p.get('role', 'Expert')}\nPersona Definition: {p['prompt']}\n" for p in active_personas])

    # AIレスポンス言語設定を取得
    languages = get_ai_response_languages(hackathon_id)
    
    qa_summary_fields = []
    response_fields = []
    
    for lang in languages:
        lang_key = normalize_lang_to_key(lang)
        qa_summary_fields.append(f'    "qa_summary_{lang_key}": "A brief 2-3 sentence summary of the panel\'s overall stance on the objection in {lang}."')
        response_fields.append(f'            "response_{lang_key}": "Direct, persona-driven response to the team\'s objection in {lang}."')
        
    qa_summary_str = ",\n".join(qa_summary_fields)
    response_fields_str = ",\n".join(response_fields)

    prompt = f"""You are orchestrating an AI Expert Panel for a Hackathon.
The team has submitted a question or an objection regarding your PREVIOUS evaluation.

<previous_evaluation_data format="json">
{previous_evaluation_json}
</previous_evaluation_data>

<team_objection_or_question>
{objection_text}
</team_objection_or_question>

<expert_judges>
{personas_str}
</expert_judges>

<critical_instructions>
- You must directly address the team's objection or question based on your specific persona.
- If the team makes a valid point, acknowledge it. If they missed something, explain why your original evaluation stands.
- Provide constructive, direct, and persona-driven responses.
- You MUST answer and summarize in the following languages: {", ".join(languages)}.
</critical_instructions>

<output_instructions format="json">
Output a strictly valid JSON object with the following structure:
{{
{qa_summary_str},
    "judges_responses": [
        {{
            "judge_name": "<Name of the judge>",
{response_fields_str}
        }}
        // Repeat for EACH active judge
    ]
}}
</output_instructions>
"""

    contents = [prompt]
    if gemini_media_files:
        contents.extend(gemini_media_files)
    if text_content:
        contents.append(f"<source_code_and_documents>\n{text_content}\n</source_code_and_documents>")

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        )
    )
    return json.loads(response.text)

def admin_chat_about_submission(hackathon_id, source_text, gemini_file_ids_json, previous_evaluation_json, admin_question):
    """
    Allows Hackathon Admin to ask a specific question about a team's submission,
    using the originally uploaded source code and media files as context.
    """
    client = get_gemini_client(hackathon_id)

    model_name = get_setting(hackathon_id, 'gemini_model') or "gemini-2.5-flash"

    # Reconstruct Gemini File objects
    gemini_media_files = []
    if gemini_file_ids_json:
        try:
            file_names = json.loads(gemini_file_ids_json)
            for name in file_names:
                try:
                    f = client.files.get(name=name)
                    gemini_media_files.append(f)
                except Exception as e:
                    print(f"Warning: Could not retrieve Gemini file {name}: {e}")
        except Exception:
            pass

    # AIレスポンス言語設定を取得
    languages = get_ai_response_languages(hackathon_id)
    
    question_fields = []
    answer_fields = []
    
    for lang in languages:
        lang_key = normalize_lang_to_key(lang)
        question_fields.append(f'  "question_{lang_key}": "Translation or original of the administrator\'s question in {lang}"')
        answer_fields.append(f'  "answer_{lang_key}": "Detailed response in {lang} based on the source code and files"')
        
    question_str = ",\n".join(question_fields)
    answer_str = ",\n".join(answer_fields)

    prompt = f"""You are an AI Expert Panelist assisting a Hackathon Administrator.
The Admin has a specific question regarding a team's submission.

<submission_context_guidance>
Please reference the attached source code and media files for ground truth to avoid hallucination.
</submission_context_guidance>

<previous_evaluation_data format="json">
{previous_evaluation_json}
</previous_evaluation_data>

<admin_question>
{admin_question}
</admin_question>

<critical_instructions>
- Answer the Admin's question directly, clearly, and honestly.
- Base your answer strictly on the provided source code, media files, and previous evaluation.
- If the answer cannot be found in the provided context, state clearly that you don't know or the information is missing. DO NOT hallucinate.
- Translate the original question and write the answer in the following languages: {", ".join(languages)}.
</critical_instructions>

<output_instructions format="json">
Output a strictly valid JSON object with the following structure:
{{
{question_str},
{answer_str}
}}
</output_instructions>
"""

    contents = [prompt]
    if gemini_media_files:
        contents.extend(gemini_media_files)
    if source_text:
        contents.append(f"<source_code_and_documents>\n{source_text}\n</source_code_and_documents>")

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        )
    )
    return json.loads(response.text)


