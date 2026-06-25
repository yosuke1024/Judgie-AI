import json
import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.core.llm.base import BaseLLMProvider
from app.models.db import (
    get_ai_response_languages,
    get_criteria,
    get_personas,
    get_setting,
    normalize_lang_to_key,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    @property
    def supports_video(self) -> bool:
        return False

    def _get_client(self, api_key_override: Optional[str] = None) -> Anthropic:
        from app.config import ANTHROPIC_API_KEY

        api_key = api_key_override if api_key_override else (get_setting("anthropic_api_key") or ANTHROPIC_API_KEY)
        if not api_key:
            raise ValueError(
                "Anthropic API Key has not been set. Please configure ANTHROPIC_API_KEY in environment variables or system settings."
            )
        return Anthropic(api_key=api_key)

    def list_models(self, api_key_override: Optional[str] = None) -> List[str]:
        if api_key_override:
            self._get_client(api_key_override)
            if not api_key_override.startswith("sk-ant-"):
                raise ValueError("Invalid Anthropic API key format. Must start with 'sk-ant-'.")
        return ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]

    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        logger.info(f"Anthropic: Skipping upload for {file_path}. Media files are not supported.")
        return {"name": file_path, "state": "DUMMY"}

    def wait_for_files(self, files: List[Any]) -> None:
        pass

    def _call_anthropic_forced_tool(
        self, client: Anthropic, model: str, prompt: str, tool_name: str, tool_schema: dict, temp: float = 0.4
    ) -> Dict[str, Any]:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_name},
            temperature=temp,
        )
        tool_use = [block for block in response.content if block.type == "tool_use"][0]
        return tool_use.input

    def analyze_submission(
        self,
        model_name: str,
        text_content: str,
        media_files: Optional[List[Any]] = None,
        previous_evaluations_json: Optional[str] = None,
        is_final: bool = False,
    ) -> Dict[str, Any]:
        client = self._get_client()
        model = model_name if model_name else (get_setting("anthropic_model") or "claude-3-5-sonnet-20241022")

        criteria = [c for c in get_criteria() if c.get("active", True)]
        active_personas = [p for p in get_personas() if p.get("active", True)]

        criteria_str = "\n".join(
            [f"- {c['name']} (Weight: {c['weight']}%): {c.get('description', '')}" for c in criteria]
        )
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

        # Build dynamic tool schema properties based on languages
        properties = {}
        required = []

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            pu_key = f"product_understanding_{lang_key}"
            ai_key = f"action_items_{lang_key}"

            properties[pu_key] = {
                "type": "string",
                "description": f"Detailed explanation of product problem, solution, and core value in {lang}.",
            }
            properties[ai_key] = {
                "type": "array",
                "items": {"type": "string"},
                "description": f"Top 3 priority action items in {lang}.",
            }
            required.extend([pu_key, ai_key])

        # Overall scores properties (each criteria name is a key)
        score_props = {}
        for c in criteria:
            score_props[c["name"]] = {"type": "number", "description": f"Consensus score for {c['name']} (0.0 to 5.0)"}

        properties["scores"] = {
            "type": "object",
            "properties": score_props,
            "required": [c["name"] for c in criteria],
            "description": "Consensus float score (0.0 to 5.0) for each criteria",
        }
        properties["impact_score"] = {"type": "number", "description": "Overall project impact score (0.0 to 5.0)"}
        required.extend(["scores", "impact_score"])

        # Judges feedback item properties
        judge_feedback_props = {
            "judge_name": {"type": "string"},
            "judge_role": {"type": "string"},
            "judge_persona": {"type": "string", "description": "1-sentence summary of what this judge cares about"},
            "judge_scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"criteria_name": {"type": "string"}, "score": {"type": "number"}},
                    "required": ["criteria_name", "score"],
                },
            },
        }
        judge_req = ["judge_name", "judge_role", "judge_persona", "judge_scores"]

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            fb_key = f"feedback_{lang_key}"
            judge_feedback_props[fb_key] = {
                "type": "string",
                "description": f"Deeply detailed, highly informative feedback in {lang} based on persona and context.",
            }
            judge_req.append(fb_key)

        properties["judges_feedback"] = {
            "type": "array",
            "items": {"type": "object", "properties": judge_feedback_props, "required": judge_req},
            "description": "List of evaluations from each expert judge",
        }
        required.append("judges_feedback")

        tool_schema = {
            "name": "submit_evaluation",
            "description": "Submit structured evaluation of the hackathon submission.",
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }

        prompt = f"""You are orchestrating an AI Expert Panel for a Hackathon.
Analyze the provided source code, pitch materials.

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
- Focus strictly on the source code and documents. (Note: media files / video frames are omitted on this model).
</critical_instructions>

<source_code_and_documents>
{text_content}
</source_code_and_documents>
"""
        return self._call_anthropic_forced_tool(client, model, prompt, "submit_evaluation", tool_schema, temp=0.4)

    def object_to_judges(
        self,
        model_name: str,
        text_content: str,
        media_files: Optional[List[Any]] = None,
        previous_evaluation_json: Optional[str] = None,
        chat_history_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        client = self._get_client()
        model = model_name if model_name else (get_setting("anthropic_model") or "claude-3-5-sonnet-20241022")

        active_personas = [p for p in get_personas() if p.get("active", True)]
        personas_str = "\n".join(
            [
                f"Name: {p['name']}\nRole: {p.get('role', 'Expert')}\nPersona Definition: {p['prompt']}\n"
                for p in active_personas
            ]
        )

        languages = get_ai_response_languages()
        properties = {}
        required = []

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            qa_key = f"qa_summary_{lang_key}"
            properties[qa_key] = {
                "type": "string",
                "description": f"A brief 2-3 sentence summary of the panel's overall stance on the latest objection in {lang}.",
            }
            required.append(qa_key)

        judge_resp_props = {"judge_name": {"type": "string"}}
        judge_req = ["judge_name"]

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            resp_key = f"response_{lang_key}"
            judge_resp_props[resp_key] = {
                "type": "string",
                "description": f"Direct, persona-driven response to the team's latest point in {lang}.",
            }
            judge_req.append(resp_key)

        properties["judges_responses"] = {
            "type": "array",
            "items": {"type": "object", "properties": judge_resp_props, "required": judge_req},
            "description": "Direct response from each active judge",
        }
        required.append("judges_responses")

        tool_schema = {
            "name": "submit_objection_response",
            "description": "Submit the judges panel's response to the team's objection.",
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }

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

<source_code_and_documents>
{text_content}
</source_code_and_documents>
"""
        return self._call_anthropic_forced_tool(
            client, model, prompt, "submit_objection_response", tool_schema, temp=0.4
        )

    def admin_chat(
        self,
        model_name: str,
        source_text: str,
        file_ids_json: Optional[str] = None,
        previous_evaluation_json: Optional[str] = None,
        admin_question: str = "",
    ) -> Dict[str, Any]:
        client = self._get_client()
        model = model_name if model_name else (get_setting("anthropic_model") or "claude-3-5-sonnet-20241022")

        languages = get_ai_response_languages()
        properties = {}
        required = []

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            q_key = f"question_{lang_key}"
            a_key = f"answer_{lang_key}"

            properties[q_key] = {
                "type": "string",
                "description": f"Translation or original of the administrator's question in {lang}",
            }
            properties[a_key] = {
                "type": "string",
                "description": f"Detailed response in {lang} based on the source code and files",
            }
            required.extend([q_key, a_key])

        tool_schema = {
            "name": "submit_admin_chat_response",
            "description": "Submit response to admin's question regarding submission.",
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }

        prompt = f"""You are an AI Expert Panelist assisting a Hackathon Administrator.
The Admin has a specific question regarding a team's submission.

<submission_context_guidance>
Please reference the attached source code and documents for ground truth to avoid hallucination.
</submission_context_guidance>

<previous_evaluation_data format="json">
{previous_evaluation_json}
</previous_evaluation_data>

<admin_question>
{admin_question}
</admin_question>

<critical_instructions>
- Answer the Admin's question directly, clearly, and honestly.
- Base your answer strictly on the provided source code and previous evaluation.
- If the answer cannot be found in the provided context, state clearly that you don't know or the information is missing. DO NOT hallucinate.
- Translate the original question and write the answer in the following languages: {", ".join(languages)}.
</critical_instructions>

<source_code_and_documents>
{source_text}
</source_code_and_documents>
"""
        return self._call_anthropic_forced_tool(
            client, model, prompt, "submit_admin_chat_response", tool_schema, temp=0.4
        )

    def translate(self, text: str, target_languages: List[str]) -> Dict[str, str]:
        client = self._get_client()
        model = get_setting("anthropic_model") or "claude-3-5-sonnet-20241022"

        properties = {}
        required = []

        for lang in target_languages:
            lang_key = normalize_lang_to_key(lang)
            t_key = f"user_objection_{lang_key}"
            properties[t_key] = {"type": "string", "description": f"The translated text in {lang}"}
            required.append(t_key)

        tool_schema = {
            "name": "submit_translation",
            "description": "Submit translation result.",
            "input_schema": {"type": "object", "properties": properties, "required": required},
        }

        prompt = f"""You are a professional translator.
Translate the following input text into these languages: {", ".join(target_languages)}.

<input_text>
{text}
</input_text>
"""
        return self._call_anthropic_forced_tool(client, model, prompt, "submit_translation", tool_schema, temp=0.2)
