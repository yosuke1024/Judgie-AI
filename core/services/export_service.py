import io
import json
import os
import urllib.request
import zipfile
import pandas as pd
from fpdf import FPDF
from sqlalchemy.orm import Session
from core.db import (
    SessionLocal,
    Hackathon,
    User,
    Evaluation,
    TeamChat,
    AdminChat,
    get_ai_response_languages,
    get_criteria,
    get_personas,
    normalize_lang_to_key
)

# IPAexゴシックフォントの安定したCTANミラーURL（約4.5MB）
FONT_URL = "https://mirrors.ctan.org/fonts/ipaex/ipaexg.ttf"
FONT_DIR = "data"
FONT_PATH = os.path.join(FONT_DIR, "ipaexg.ttf")


def download_japanese_font():
    """Downloads a stable Japanese font if not already present."""
    if not os.path.exists(FONT_PATH):
        os.makedirs(FONT_DIR, exist_ok=True)
        try:
            # Set a standard user agent to avoid HTTP 403
            req = urllib.request.Request(
                FONT_URL,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(FONT_PATH, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            # Log error and ensure we don't crash next time
            print(f"[Export Service] Failed to download Japanese font: {str(e)}")


class JudgiePDF(FPDF):
    def __init__(self, hackathon_name, team_name, font_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hackathon_name = hackathon_name
        self.team_name = team_name
        self.font_path = font_path
        self.font_loaded = False
        
    def header(self):
        # Dynamically load the IPAexGothic font if it exists on disk
        if not self.font_loaded and os.path.exists(self.font_path):
            try:
                self.add_font("IPAexGothic", "", self.font_path)
                self.font_loaded = True
            except Exception as e:
                print(f"[Export Service] Error registering IPAexGothic font: {e}")
            
        if self.font_loaded:
            self.set_font("IPAexGothic", size=9)
        else:
            self.set_font("Helvetica", size=9)
            
        self.set_text_color(100, 116, 139) # Slate color
        header_text = self.safe_text(f"{self.hackathon_name}  |  {self.team_name} Report")
        self.cell(0, 10, header_text, border=0, align="L")
        self.ln(10)
        self.line(10, 18, 200, 18)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        if self.font_loaded:
            self.set_font("IPAexGothic", size=9)
        else:
            self.set_font("Helvetica", size=9)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def safe_text(self, text: str) -> str:
        """
        Sanitizes text output to prevent FPDFUnicodeEncodingException when
        the Japanese font isn't loaded and Helvetica is active.
        """
        if not self.font_loaded:
            # Replace non-latin-1 characters with '?' to prevent crashing
            return str(text).encode("latin-1", "replace").decode("latin-1")
        return str(text)


def export_hackathon_to_markdown(hackathon_id: int) -> str:
    """
    Generates a single comprehensive markdown document containing all teams, profiles,
    evaluations, Q&As, and full ZIP source texts for NotebookLM.
    """
    db = SessionLocal()
    try:
        hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        if not hackathon:
            return "# Project Not Found"

        md = []
        md.append(f"# Project Data Export: {hackathon.name}")
        md.append(f"- **Export Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append("")

        # Criteria
        criteria = get_criteria(hackathon_id)
        md.append("## Evaluation Criteria")
        for c in criteria:
            md.append(f"- **{c['name']}** (Weight: {c['weight']}%): {c['description']}")
        md.append("")

        # Teams
        users = db.query(User).filter(User.hackathon_id == hackathon_id, User.role == 'team').order_by(User.team_id).all()
        
        if not users:
            md.append("No teams registered in this project.")
            return "\n".join(md)

        for u in users:
            md.append("---")
            md.append(f"# Team: {u.team_name or u.team_id} (ID: {u.team_id})")
            md.append(f"- **Product Name:** {u.product_name or 'N/A'}")
            md.append(f"- **One-liner:** {u.one_liner or 'N/A'}")
            md.append("")

            # Retrieve all evaluations for this team
            evaluations = db.query(Evaluation).filter(
                Evaluation.hackathon_id == hackathon_id,
                Evaluation.team_id == u.team_id
            ).order_by(Evaluation.id.asc()).all()

            if not evaluations:
                md.append("No submissions or evaluations recorded for this team.")
                md.append("")
                continue

            for idx, ev in enumerate(evaluations):
                eval_type = "Final Submission" if ev.is_final else f"Consultation {idx+1}"
                md.append(f"## {eval_type} (ID: {ev.id})")
                md.append(f"- **Evaluated At:** {ev.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}")

                scores = json.loads(ev.scores_json)
                total_weight = sum(c['weight'] for c in criteria) if criteria else 1
                total_score = sum(scores.get(c['name'], 0) * 20.0 * (c['weight'] / total_weight) for c in criteria)

                md.append(f"### Scores (Total: {total_score:.1f} / 100.0)")
                md.append("- **Criteria Breakdown:**")
                for c in criteria:
                    md.append(f"  - {c['name']}: {scores.get(c['name'], 0)} / 5.0 (Weight: {c['weight']}%)")
                md.append("")

                # Detail Feedbacks in all configured languages
                fb = json.loads(ev.strengths_risks_json)
                languages = get_ai_response_languages(hackathon_id)
                compat_map = {
                    "english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"
                }

                for lang in languages:
                    lang_key = normalize_lang_to_key(lang)
                    compat_key = compat_map.get(lang_key, "en")

                    md.append(f"### Evaluation in {lang}")
                    
                    # Product Understanding
                    pu = fb.get(f"product_understanding_{lang_key}") or fb.get(f"product_understanding_{compat_key}") or fb.get(f"summary_{lang_key}") or fb.get(f"summary_{compat_key}")
                    md.append(f"#### Product Understanding")
                    md.append(pu or "No product understanding text.")
                    md.append("")

                    # Action items / Next Steps
                    action_items = fb.get(f"action_items_{lang_key}") or fb.get(f"action_items_{compat_key}")
                    md.append(f"#### Next Steps / Action Items")
                    if action_items:
                        for item in action_items:
                            md.append(f"- {item}")
                    else:
                        md.append("No action items provided.")
                    md.append("")

                    # Judges Details
                    md.append(f"#### Judges Detailed Feedback")
                    judges_fb = fb.get("judges_feedback", [])
                    for j in judges_fb:
                        j_name = j.get("judge_name", "Judge")
                        j_role = j.get("judge_role", "")
                        j_text = j.get(f"feedback_{lang_key}") or j.get(f"feedback_{compat_key}")
                        md.append(f"- **{j_name} ({j_role}):**")
                        md.append(f"  {j_text}")
                    md.append("")

                # Team Chat Q&A History
                team_chats = db.query(TeamChat).filter(TeamChat.evaluation_id == ev.id).order_by(TeamChat.created_at.asc()).all()
                if team_chats:
                    md.append("### Discussion Q&A History")
                    for tc in team_chats:
                        msg = json.loads(tc.message_json)
                        if tc.sender == 'team':
                            md.append(f"- **Team Question:** {msg.get('user_objection', '')}")
                        else:
                            md.append("- **AI Judges Panel Response:**")
                            for lang in languages:
                                lang_key = normalize_lang_to_key(lang)
                                compat_key = compat_map.get(lang_key, "en")
                                qa_summary = msg.get(f"qa_summary_{lang_key}") or msg.get(f"qa_summary_{compat_key}")
                                if qa_summary:
                                    md.append(f"  - *[{lang}] Summary:* {qa_summary}")
                            
                            for jr in msg.get('judges_responses', []):
                                jr_name = jr.get('judge_name', 'Judge')
                                md.append(f"  - **{jr_name}:**")
                                for lang in languages:
                                    lang_key = normalize_lang_to_key(lang)
                                    compat_key = compat_map.get(lang_key, "en")
                                    jr_resp = jr.get(f"response_{lang_key}") or jr.get(f"response_{compat_key}")
                                    if jr_resp:
                                        md.append(f"    - *[{lang}]:* {jr_resp}")
                    md.append("")

                # Admin Chat (Private Query History)
                admin_chats = db.query(AdminChat).filter(AdminChat.evaluation_id == ev.id).order_by(AdminChat.created_at.asc()).all()
                if admin_chats:
                    md.append("### Admin Private Q&A History")
                    for ac in admin_chats:
                        qa_data = json.loads(ac.qa_json) if ac.qa_json else {}
                        md.append(f"- **Admin Question:** {ac.question_ja or ac.question_en}")
                        for lang in languages:
                            lang_key = normalize_lang_to_key(lang)
                            compat_key = compat_map.get(lang_key, "en")
                            ans = qa_data.get(f"answer_{lang_key}") or qa_data.get(f"answer_{compat_key}") or (ac.answer_ja if lang_key == 'japanese' else ac.answer_en)
                            if ans:
                                md.append(f"  - **AI Panel Response [{lang}]:** {ans}")
                    md.append("")

                # ZIP Source Text Content Embed (Crucial for NotebookLM)
                if ev.source_text:
                    md.append("### Submitted Source Code & Documents Text")
                    md.append("Below is the plain text content extracted from the ZIP submission and evaluated by the AI:")
                    md.append("```text")
                    md.append(ev.source_text)
                    md.append("```")
                    md.append("")

        return "\n".join(md)
    finally:
        db.close()


def generate_team_pdf_report(hackathon_id: int, team_id: str) -> bytes:
    """
    Generates a single multilingual PDF report for a team.
    Contains evaluation scores, and sections for all configured languages sequentially.
    """
    download_japanese_font()

    db = SessionLocal()
    try:
        hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        hackathon_name = hackathon.name if hackathon else "Judgie Project"

        user = db.query(User).filter(User.hackathon_id == hackathon_id, User.team_id == team_id).first()
        team_display_name = user.team_name or team_id

        # Get latest evaluation for this team
        latest_eval = db.query(Evaluation).filter(
            Evaluation.hackathon_id == hackathon_id,
            Evaluation.team_id == team_id
        ).order_by(Evaluation.id.desc()).first()

        if not latest_eval:
            # Return a simple placeholder PDF if no evaluations exist
            pdf = JudgiePDF(hackathon_name, team_display_name, FONT_PATH)
            pdf.alias_nb_pages()
            pdf.add_page()
            font_name = "IPAexGothic" if pdf.font_loaded else "Helvetica"
            pdf.set_font(font_name, size=14)
            pdf.cell(0, 10, pdf.safe_text("評価データがまだありません。" if pdf.font_loaded else "No evaluation data available."), align="C")
            pdf.ln(10)
            return bytes(pdf.output())

        scores = json.loads(latest_eval.scores_json)
        fb = json.loads(latest_eval.strengths_risks_json)
        criteria = get_criteria(hackathon_id)
        languages = get_ai_response_languages(hackathon_id)

        # Calculate total score
        total_weight = sum(c['weight'] for c in criteria) if criteria else 1
        total_score = sum(scores.get(c['name'], 0) * 20.0 * (c['weight'] / total_weight) for c in criteria)

        # Initialize PDF
        pdf = JudgiePDF(hackathon_name, team_display_name, FONT_PATH)
        pdf.alias_nb_pages()
        pdf.add_page()

        font_name = "IPAexGothic" if pdf.font_loaded else "Helvetica"

        # --- Report Title ---
        pdf.set_font(font_name, size=20)
        pdf.set_text_color(15, 23, 42) # Slate-900
        pdf.cell(0, 15, pdf.safe_text(f"{team_display_name} - Evaluation Report"), align="L")
        pdf.ln(15)
        
        pdf.set_font(font_name, size=11)
        pdf.set_text_color(71, 85, 105) # Slate-600
        pdf.cell(0, 6, pdf.safe_text(f"Product Name: {user.product_name or 'N/A'}"))
        pdf.ln(6)
        pdf.cell(0, 6, pdf.safe_text(f"One-liner: {user.one_liner or 'N/A'}"))
        pdf.ln(6)
        pdf.cell(0, 6, pdf.safe_text(f"Evaluation Date: {latest_eval.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}"))
        pdf.ln(14)

        # --- Score Banner ---
        pdf.set_fill_color(30, 41, 59) # Slate-800
        pdf.rect(10, pdf.get_y(), 190, 20, style="F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_font(font_name, size=12)
        pdf.cell(95, 10, pdf.safe_text("   TOTAL EVALUATION SCORE"), align="L")
        pdf.set_font(font_name, size=16)
        pdf.cell(95, 10, pdf.safe_text(f"{total_score:.1f} / 100.0   "), align="R")
        pdf.ln(15)

        # --- Score Table ---
        pdf.set_font(font_name, size=12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, pdf.safe_text("Score Breakdown / 評価軸ごとのスコア"))
        pdf.ln(10)

        pdf.set_font(font_name, size=10)
        with pdf.table(col_widths=(90, 50, 50), text_align=("LEFT", "CENTER", "CENTER"), first_row_as_headings=False) as table:
            row = table.row()
            row.cell(pdf.safe_text("Criteria / 評価軸"))
            row.cell(pdf.safe_text("Score / スコア"))
            row.cell(pdf.safe_text("Weight / 比重"))
            for c in criteria:
                row = table.row()
                row.cell(pdf.safe_text(c['name']))
                row.cell(pdf.safe_text(f"{scores.get(c['name'], 0):.1f} / 5.0"))
                row.cell(pdf.safe_text(f"{c['weight']}%"))
        pdf.ln(10)

        # --- Lang-specific Feedback Sections ---
        compat_map = {
            "english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"
        }

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            compat_key = compat_map.get(lang_key, "en")

            # Page break for clean section separation per language
            pdf.add_page()
            
            pdf.set_font(font_name, size=14)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 10, pdf.safe_text(f"=== Feedback in {lang} ==="), align="L")
            pdf.ln(12)

            # Product Understanding
            pdf.set_font(font_name, size=12)
            pdf.cell(0, 8, pdf.safe_text("Product Understanding / プロダクト理解"))
            pdf.ln(8)
            pdf.set_font(font_name, size=10)
            pdf.set_text_color(71, 85, 105)
            pu = fb.get(f"product_understanding_{lang_key}") or fb.get(f"product_understanding_{compat_key}") or fb.get(f"summary_{lang_key}") or fb.get(f"summary_{compat_key}")
            pdf.multi_cell(0, 6, pdf.safe_text(pu or "No product understanding text."))
            pdf.ln(5)

            # Next Steps / Action Items
            pdf.set_font(font_name, size=12)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 8, pdf.safe_text("Next Steps / 最優先アクション"))
            pdf.ln(8)
            pdf.set_font(font_name, size=10)
            pdf.set_text_color(71, 85, 105)
            action_items = fb.get(f"action_items_{lang_key}") or fb.get(f"action_items_{compat_key}")
            if action_items:
                for item in action_items:
                    pdf.multi_cell(0, 6, pdf.safe_text(f"- {item}"))
            else:
                pdf.cell(0, 6, pdf.safe_text("No action items provided."))
                pdf.ln(6)
            pdf.ln(5)

            # Judges Details
            pdf.set_font(font_name, size=12)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 8, pdf.safe_text("Judges Feedback / 審査員個別フィードバック"))
            pdf.ln(8)

            judges_fb = fb.get("judges_feedback", [])
            for j in judges_fb:
                j_name = j.get("judge_name", "Judge")
                j_role = j.get("judge_role", "")
                j_text = j.get(f"feedback_{lang_key}") or j.get(f"feedback_{compat_key}")
                
                pdf.set_font(font_name, size=10)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 6, pdf.safe_text(f"• {j_name} ({j_role})"))
                pdf.ln(6)
                
                pdf.set_font(font_name, size=9.5)
                pdf.set_text_color(71, 85, 105)
                pdf.multi_cell(0, 5.5, pdf.safe_text(f"  {j_text}"))
                pdf.ln(3)

        # --- Q&A History Section (Multilingual) ---
        team_chats = db.query(TeamChat).filter(TeamChat.evaluation_id == latest_eval.id).order_by(TeamChat.created_at.asc()).all()
        if team_chats:
            pdf.add_page()
            pdf.set_font(font_name, size=14)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 10, pdf.safe_text("Discussion Q&A History / 質問・反論スレッド"))
            pdf.ln(12)

            for tc in team_chats:
                msg = json.loads(tc.message_json)
                if tc.sender == 'team':
                    pdf.set_font(font_name, size=10)
                    pdf.set_text_color(15, 23, 42)
                    pdf.cell(0, 6, pdf.safe_text("Team Question / チームからの質問:"))
                    pdf.ln(6)
                    pdf.set_font(font_name, size=9.5)
                    pdf.set_text_color(71, 85, 105)
                    pdf.multi_cell(0, 5.5, pdf.safe_text(f"  {msg.get('user_objection', '')}"))
                    pdf.ln(2)
                else:
                    pdf.set_font(font_name, size=10)
                    pdf.set_text_color(15, 23, 42)
                    pdf.cell(0, 6, pdf.safe_text("AI Judges Panel Response / 審査員からの回答:"))
                    pdf.ln(6)

                    # Output summary for each language
                    pdf.set_font(font_name, size=9.5)
                    pdf.set_text_color(71, 85, 105)
                    for lang in languages:
                        lang_key = normalize_lang_to_key(lang)
                        compat_key = compat_map.get(lang_key, "en")
                        qa_summary = msg.get(f"qa_summary_{lang_key}") or msg.get(f"qa_summary_{compat_key}")
                        if qa_summary:
                            pdf.multi_cell(0, 5.5, pdf.safe_text(f"  [{lang} Summary] {qa_summary}"))
                    pdf.ln(2)

                    # Output responses per judge
                    for jr in msg.get('judges_responses', []):
                        jr_name = jr.get('judge_name', 'Judge')
                        pdf.set_font(font_name, size=9.5)
                        pdf.set_text_color(15, 23, 42)
                        pdf.cell(0, 6, pdf.safe_text(f"  - {jr_name}:"))
                        pdf.ln(6)
                        
                        pdf.set_font(font_name, size=9)
                        pdf.set_text_color(71, 85, 105)
                        for lang in languages:
                            lang_key = normalize_lang_to_key(lang)
                            compat_key = compat_map.get(lang_key, "en")
                            jr_resp = jr.get(f"response_{lang_key}") or jr.get(f"response_{compat_key}")
                            if jr_resp:
                                pdf.multi_cell(0, 5, pdf.safe_text(f"    [{lang}] {jr_resp}"))
                        pdf.ln(2)
            pdf.ln(5)

        return bytes(pdf.output())
    finally:
        db.close()


def generate_all_teams_pdf_zip(hackathon_id: int) -> bytes:
    """
    Generates PDF reports for all teams in a hackathon, and packages them into a ZIP archive.
    """
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.hackathon_id == hackathon_id, User.role == 'team').all()
        if not users:
            # Return an empty ZIP if no teams
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                zip_file.writestr("info.txt", "No team evaluation data available.")
            return zip_buffer.getvalue()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for u in users:
                pdf_bytes = generate_team_pdf_report(hackathon_id, u.team_id)
                # Clean team name to prevent directory traversal or invalid characters in file path
                safe_team_id = "".join([c for c in u.team_id if c.isalnum() or c in ("-", "_", " ")])
                zip_file.writestr(f"report_{safe_team_id}.pdf", pdf_bytes)

        return zip_buffer.getvalue()
    finally:
        db.close()
