import json
import logging
import time
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types

from app.core.llm.base import BaseLLMProvider
from app.models.db import (
    get_ai_response_languages,
    get_criteria,
    get_personas,
    get_setting,
    normalize_lang_to_key,
)

logger = logging.getLogger(__name__)

class GeminiProvider(BaseLLMProvider):
    def _get_client(self, api_key_override: Optional[str] = None):
        """Returns initialized Gemini client using database settings or key override."""
        api_key = api_key_override if api_key_override else get_setting("gemini_api_key")
        if not api_key:
            raise ValueError("Gemini API Key has not been set by the Admin yet. Please contact the organizer.")
        return genai.Client(api_key=api_key)

    def list_models(self, api_key_override: Optional[str] = None) -> List[str]:
        try:
            client = self._get_client(api_key_override=api_key_override)
            models = client.models.list()
            gemini_models = []
            for m in models:
                if m.supported_actions and "generateContent" in m.supported_actions:
                    name = m.name.replace("models/", "")
                    if name.startswith("gemini-"):
                        name_lower = name.lower()
                        if ("flash" in name_lower or "pro" in name_lower) and not any(
                            x in name_lower for x in ["embed", "vision", "aqa", "thinking"]
                        ):
                            gemini_models.append(name)
            gemini_models.sort()
            return gemini_models
        except Exception as e:
            raise ValueError(f"Failed to fetch models from Gemini API: {str(e)}")

    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        client = self._get_client()
        config = types.UploadFileConfig(mime_type=mime_type) if mime_type else None
        return client.files.upload(file=file_path, config=config)

    def wait_for_files(self, files: List[Any]) -> None:
        client = self._get_client()
        for name in (file.name for file in files):
            file = client.files.get(name=name)
            while file.state.name == "PROCESSING":
                time.sleep(2)
                file = client.files.get(name=name)
            if file.state.name == "FAILED":
                raise ValueError(f"File processing failed: {file.name}")

    def analyze_submission(
        self,
        model_name: str,
        text_content: str,
        media_files: Optional[List[Any]] = None,
        previous_evaluations_json: Optional[str] = None,
        is_final: bool = False
    ) -> Dict[str, Any]:
        client = self._get_client()
        model = model_name if model_name else (get_setting("gemini_model") or "gemini-2.5-flash")

        criteria = [c for c in get_criteria() if c.get("active", True)]
        active_personas = [p for p in get_personas() if p.get("active", True)]

        criteria_str = "\n".join([f"- {c['name']} (Weight: {c['weight']}%): {c.get('description', '')}" for c in criteria])
        personas_str = "\n".join(
            [
                f"Name: {p['name']}\nRole: {p.get('role', 'Expert')}\nPersona Definition: {p['prompt']}\n"
                for p in active_personas
            ]
        )

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

        languages = get_ai_response_languages()
        pu_fields = []
        ai_fields = []
        fb_fields = []

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            pu_fields.append(
                f'    "product_understanding_{lang_key}": "Detailed explanation of how the AI understands the product\'s problem, solution, and core value in {lang}."'
            )
            ai_fields.append(
                f'    "action_items_{lang_key}": [\n        "Top priority action item 1 in {lang}",\n        "Top priority action item 2 in {lang}",\n        "Top priority action item 3 in {lang}"\n    ]'
            )
            fb_fields.append(
                f'            "feedback_{lang_key}": "Deeply detailed, highly informative feedback in {lang} based on their persona and previous context."'
            )

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
        if media_files:
            contents.extend(media_files)
        if text_content:
            contents.append(f"<source_code_and_documents>\n{text_content}\n</source_code_and_documents>")

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
        return json.loads(response.text)

    def object_to_judges(
        self,
        model_name: str,
        text_content: str,
        media_files: Optional[List[Any]] = None,
        previous_evaluation_json: Optional[str] = None,
        chat_history_list: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        client = self._get_client()
        model = model_name if model_name else (get_setting("gemini_model") or "gemini-2.5-flash")

        active_personas = [p for p in get_personas() if p.get("active", True)]
        personas_str = "\n".join(
            [
                f"Name: {p['name']}\nRole: {p.get('role', 'Expert')}\nPersona Definition: {p['prompt']}\n"
                for p in active_personas
            ]
        )

        languages = get_ai_response_languages()
        qa_summary_fields = []
        response_fields = []

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            qa_summary_fields.append(
                f'    "qa_summary_{lang_key}": "A brief 2-3 sentence summary of the panel\'s overall stance on the latest objection in {lang}."'
            )
            response_fields.append(
                f'            "response_{lang_key}": "Direct, persona-driven response to the team\'s latest point in {lang}."'
            )

        qa_summary_str = ",\n".join(qa_summary_fields)
        response_fields_str = ",\n".join(response_fields)

        chat_thread_str = ""
        if chat_history_list:
            chat_thread_str = "\n<chat_history>\n"
            for msg in chat_history_list:
                sender_label = "Team (User)" if msg.get("sender") == "team" else "Judges Panel (AI)"
                msg_data = msg.get("message_json")
                if isinstance(msg_data, str):
                    try:
                        msg_data = json.loads(msg_data)
                    except Exception:
                        pass

                if msg.get("sender") == "team":
                    text = msg_data.get("user_objection") if isinstance(msg_data, dict) else msg_data
                    chat_thread_str += f"- [{sender_label}]: {text}\n"
                else:
                    if isinstance(msg_data, dict):
                        summary = (
                            msg_data.get("qa_summary_english")
                            or msg_data.get("qa_summary_en")
                            or msg_data.get("qa_summary_japanese")
                            or msg_data.get("qa_summary_ja")
                            or "Response provided."
                        )
                        chat_thread_str += f"- [{sender_label}]: {summary}\n"
                    else:
                        chat_thread_str += f"- [{sender_label}]: {msg_data}\n"
            chat_thread_str += "</chat_history>\n"

        prompt = f"""You are orchestrating an AI Expert Panel.
The team has been evaluated and is now in a Q&A / discussion session with you regarding their evaluation.

<previous_evaluation_data format="json">
{previous_evaluation_json}
</previous_evaluation_data>

Here is the dialogue history. The last message from the 'Team (User)' is the active question or objection you MUST address:
{chat_thread_str}

<expert_judges>
{personas_str}
</expert_judges>

<critical_instructions>
- Address the latest question or objection raised by the team (the very last item in the chat history).
- Take the context of the previous Q&A exchanges into account.
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
        if media_files:
            contents.extend(media_files)
        if text_content:
            contents.append(f"<source_code_and_documents>\n{text_content}\n</source_code_and_documents>")

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
        return json.loads(response.text)

    def admin_chat(
        self,
        model_name: str,
        source_text: str,
        file_ids_json: Optional[str] = None,
        previous_evaluation_json: Optional[str] = None,
        admin_question: str = ""
    ) -> Dict[str, Any]:
        client = self._get_client()
        model = model_name if model_name else (get_setting("gemini_model") or "gemini-2.5-flash")

        # Reconstruct Gemini File objects
        gemini_media_files = []
        if file_ids_json:
            try:
                file_names = json.loads(file_ids_json)
                for name in file_names:
                    try:
                        f = client.files.get(name=name)
                        gemini_media_files.append(f)
                    except Exception as e:
                        logger.warning(f"Could not retrieve Gemini file {name}: {e}")
            except Exception:
                pass

        languages = get_ai_response_languages()
        question_fields = []
        answer_fields = []

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            question_fields.append(
                f'  "question_{lang_key}": "Translation or original of the administrator\'s question in {lang}"'
            )
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
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
        return json.loads(response.text)

    def translate(self, text: str, target_languages: List[str]) -> Dict[str, str]:
        client = self._get_client()
        model = get_setting("gemini_model") or "gemini-2.5-flash"

        fields = []
        for lang in target_languages:
            lang_key = normalize_lang_to_key(lang)
            fields.append(f'    "user_objection_{lang_key}": "The translated text in {lang}"')

        fields_str = ",\n".join(fields)

        prompt = f"""You are a professional translator.
Translate the following input text into these languages: {", ".join(target_languages)}.

<input_text>
{text}
</input_text>

<output_instructions format="json">
Output a strictly valid JSON object with the following structure:
{{
{fields_str}
}}
</output_instructions>
"""

        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
