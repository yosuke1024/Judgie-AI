"""
Pydantic schemas for request/response validation.
"""


from pydantic import BaseModel

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    team_id: str
    passcode: str
    hackathon_id: int | None = None


class LoginResponse(BaseModel):
    team_id: str
    role: str
    hackathon_id: int | None


class UserInfo(BaseModel):
    team_id: str
    role: str
    hackathon_id: int | None
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None
    max_consultations: int = -1
    consultation_count: int = 0


# ──────────────────────────────────────────────
# Hackathon
# ──────────────────────────────────────────────

class HackathonCreate(BaseModel):
    name: str
    admin_id: str
    admin_pass: str
    template_id: str | None = None


class HackathonResponse(BaseModel):
    id: int
    name: str
    template_id: str | None
    admin_id: str | None = None
    team_count: int = 0
    created_at: str | None = None


class HackathonInitialize(BaseModel):
    template_id: str
    custom_template_data: dict | None = None


# ──────────────────────────────────────────────
# Team
# ──────────────────────────────────────────────

class TeamCreate(BaseModel):
    team_id: str
    passcode: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


class TeamBulkCreate(BaseModel):
    csv_content: str


class TeamProfileUpdate(BaseModel):
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


class PasscodeChange(BaseModel):
    current_passcode: str | None = None
    new_passcode: str


class RoleUpdate(BaseModel):
    new_role: str


class TeamResponse(BaseModel):
    team_id: str
    role: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


# ──────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────

class EvaluationResponse(BaseModel):
    id: int
    team_id: str
    scores_json: str
    impact_score: float
    strengths_risks_json: str
    qa_json: str | None = None
    is_final: bool
    source_text: str | None = None
    gemini_file_ids: str | None = None
    evaluated_at: str | None = None


class ScoreboardEntry(BaseModel):
    team_id: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None
    total_score: float = 0.0
    status: str = "Not Submitted"
    consults: int = 0


# ──────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────

class TeamObjection(BaseModel):
    objection_text: str


class AdminQuestion(BaseModel):
    question: str


class ChatMessage(BaseModel):
    id: int
    sender: str
    message_json: dict | str
    created_at: str | None = None


class AdminChatResponse(BaseModel):
    id: int
    question_en: str | None = None
    question_ja: str | None = None
    answer_en: str | None = None
    answer_ja: str | None = None
    qa_json: dict | None = None
    created_at: str | None = None


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────

class CriteriaUpdate(BaseModel):
    criteria: list[dict]


class PersonasUpdate(BaseModel):
    personas: list[dict]


class GeminiConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    api_tier: str | None = None


class ProjectSettings(BaseModel):
    re_evaluation_context_mode: str | None = None
    max_qa_turns: int | None = None
    max_consultations: int | None = None
    video_upload_enabled: bool | None = None


class LanguageSettings(BaseModel):
    languages: list[str]


# ──────────────────────────────────────────────
# Export / Import
# ──────────────────────────────────────────────

class TemplateImport(BaseModel):
    url: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
