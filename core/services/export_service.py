import base64
import io
import json
import os
import tempfile
import urllib.request
import zipfile

# Ensure matplotlib uses a non-GUI backend before importing pyplot
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF
from matplotlib import font_manager

from core.db import (
    AdminChat,
    Evaluation,
    Hackathon,
    SessionLocal,
    TeamChat,
    User,
    get_ai_response_languages,
    get_criteria,
    get_personas,
    normalize_lang_to_key,
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
            req = urllib.request.Request(FONT_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response, open(FONT_PATH, "wb") as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"[Export Service] Failed to download Japanese font: {str(e)}")


def configure_matplotlib_font():
    """Registers the downloaded Japanese font with matplotlib to avoid encoding blocks."""
    if os.path.exists(FONT_PATH):
        try:
            font_manager.fontManager.addfont(FONT_PATH)
            prop = font_manager.FontProperties(fname=FONT_PATH)
            plt.rcParams["font.family"] = prop.get_name()
            plt.rcParams["axes.unicode_minus"] = False
        except Exception as e:
            print(f"[Export Service] Failed to configure matplotlib font: {e}")


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

        self.set_text_color(100, 116, 139)  # Slate color
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
            return str(text).encode("latin-1", "replace").decode("latin-1")
        return str(text)


def get_temp_avatar_image(base64_str: str) -> str:
    """Decodes a base64 avatar image and writes it to a temporary file."""
    if not base64_str or not isinstance(base64_str, str) or not base64_str.strip():
        return None
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        img_data = base64.b64decode(base64_str)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        temp_file.write(img_data)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"[Export Service] Failed to decode avatar image: {e}")
        return None


def generate_history_chart_img(evaluations, criteria, total_weight) -> str:
    """Generates a progression line chart of total scores and returns the file path."""
    configure_matplotlib_font()
    try:
        scores_list = []
        labels = []
        for idx, ev in enumerate(evaluations):
            ev_scores = json.loads(ev.scores_json)
            total_score = sum(ev_scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria)
            scores_list.append(total_score)

            label = "Final" if ev.is_final else f"Cons. {idx + 1}"
            labels.append(label)

        # Matplotlib Styling
        plt.figure(figsize=(7, 3), facecolor="#0f172a")  # Dark slate
        ax = plt.axes()
        ax.set_facecolor("#1e293b")  # Slate-800

        # Plot score line
        ax.plot(labels, scores_list, marker="o", color="#38bdf8", linewidth=2.5, markersize=8, label="Total Score")

        # Title and labels
        ax.set_title("Score Progression / スコア推移", color="#f8fafc", fontsize=11, pad=10)
        ax.set_ylim(0, 105)
        ax.set_ylabel("Score / 点数", color="#94a3b8", fontsize=9)
        ax.tick_params(colors="#94a3b8", which="both", labelsize=8)
        ax.grid(True, color="#334155", linestyle="--", linewidth=0.5)

        for spine in ax.spines.values():
            spine.set_color("#334155")

        plt.tight_layout()

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(temp.name, format="png", dpi=150, facecolor=plt.gcf().get_facecolor(), edgecolor="none")
        plt.close()
        return temp.name
    except Exception as e:
        print(f"[Export Service] Error generating history chart: {e}")
        return None


def generate_radar_chart_img(scores, criteria) -> str:
    """Generates a spider radar chart for a single evaluation and returns the file path."""
    configure_matplotlib_font()
    try:
        labels = [c["name"] for c in criteria]
        values = [scores.get(c["name"], 0) for c in criteria]

        # Close the polar loop
        labels = [*labels, labels[0]]
        values = [*values, values[0]]

        num_vars = len(criteria)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles = [*angles, angles[0]]

        fig, ax = plt.subplots(figsize=(3.5, 3.5), subplot_kw=dict(polar=True), facecolor="#0f172a")
        ax.set_facecolor("#1e293b")

        ax.plot(angles, values, color="#38bdf8", linewidth=2)
        ax.fill(angles, values, color="#38bdf8", alpha=0.25)

        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)

        # Abbreviate labels if too long
        short_labels = [lbl[:10] + ".." if len(lbl) > 10 else lbl for lbl in labels]
        ax.set_thetagrids(np.degrees(angles), short_labels, color="#94a3b8", fontsize=7.5)

        ax.set_rgrids([1, 2, 3, 4, 5], angle=0, color="#334155", fontsize=7)
        ax.set_ylim(0, 5)

        ax.spines["polar"].set_color("#334155")
        ax.grid(color="#334155", linestyle="--")

        plt.tight_layout()

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(temp.name, format="png", dpi=150, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close()
        return temp.name
    except Exception as e:
        print(f"[Export Service] Error generating radar chart: {e}")
        return None


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
        users = (
            db.query(User).filter(User.hackathon_id == hackathon_id, User.role == "team").order_by(User.team_id).all()
        )

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
            evaluations = (
                db.query(Evaluation)
                .filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == u.team_id)
                .order_by(Evaluation.id.asc())
                .all()
            )

            if not evaluations:
                md.append("No submissions or evaluations recorded for this team.")
                md.append("")
                continue

            for idx, ev in enumerate(evaluations):
                eval_type = "Final Submission" if ev.is_final else f"Consultation {idx + 1}"
                md.append(f"## {eval_type} (ID: {ev.id})")
                md.append(f"- **Evaluated At:** {ev.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}")

                scores = json.loads(ev.scores_json)
                total_weight = sum(c["weight"] for c in criteria) if criteria else 1
                total_score = sum(scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria)

                md.append(f"### Scores (Total: {total_score:.1f} / 100.0)")
                md.append("- **Criteria Breakdown:**")
                for c in criteria:
                    md.append(f"  - {c['name']}: {scores.get(c['name'], 0)} / 5.0 (Weight: {c['weight']}%)")
                md.append("")

                # Detail Feedbacks in all configured languages
                fb = json.loads(ev.strengths_risks_json)
                languages = get_ai_response_languages(hackathon_id)
                compat_map = {"english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"}

                for lang in languages:
                    lang_key = normalize_lang_to_key(lang)
                    compat_key = compat_map.get(lang_key, "en")

                    md.append(f"### Evaluation in {lang}")

                    # Product Understanding
                    pu = (
                        fb.get(f"product_understanding_{lang_key}")
                        or fb.get(f"product_understanding_{compat_key}")
                        or fb.get(f"summary_{lang_key}")
                        or fb.get(f"summary_{compat_key}")
                    )
                    md.append("#### Product Understanding")
                    md.append(pu or "No product understanding text.")
                    md.append("")

                    # Action items / Next Steps
                    action_items = fb.get(f"action_items_{lang_key}") or fb.get(f"action_items_{compat_key}")
                    md.append("#### Next Steps / Action Items")
                    if action_items:
                        for item in action_items:
                            md.append(f"- {item}")
                    else:
                        md.append("No action items provided.")
                    md.append("")

                    # Judges Details
                    md.append("#### Judges Detailed Feedback")
                    judges_fb = fb.get("judges_feedback", [])
                    for j in judges_fb:
                        j_name = j.get("judge_name", "Judge")
                        j_role = j.get("judge_role", "")
                        j_text = j.get(f"feedback_{lang_key}") or j.get(f"feedback_{compat_key}")
                        md.append(f"- **{j_name} ({j_role}):**")
                        md.append(f"  {j_text}")
                    md.append("")

                # Team Chat Q&A History
                team_chats = (
                    db.query(TeamChat).filter(TeamChat.evaluation_id == ev.id).order_by(TeamChat.created_at.asc()).all()
                )
                if team_chats:
                    md.append("### Discussion Q&A History")
                    for tc in team_chats:
                        msg = json.loads(tc.message_json)
                        if tc.sender == "team":
                            md.append(f"- **Team Question:** {msg.get('user_objection', '')}")
                        else:
                            md.append("- **AI Judges Panel Response:**")
                            for lang in languages:
                                lang_key = normalize_lang_to_key(lang)
                                compat_key = compat_map.get(lang_key, "en")
                                qa_summary = msg.get(f"qa_summary_{lang_key}") or msg.get(f"qa_summary_{compat_key}")
                                if qa_summary:
                                    md.append(f"  - *[{lang}] Summary:* {qa_summary}")

                            for jr in msg.get("judges_responses", []):
                                jr_name = jr.get("judge_name", "Judge")
                                md.append(f"  - **{jr_name}:**")
                                for lang in languages:
                                    lang_key = normalize_lang_to_key(lang)
                                    compat_key = compat_map.get(lang_key, "en")
                                    jr_resp = jr.get(f"response_{lang_key}") or jr.get(f"response_{compat_key}")
                                    if jr_resp:
                                        md.append(f"    - *[{lang}]:* {jr_resp}")
                    md.append("")

                # Admin Chat (Private Query History)
                admin_chats = (
                    db.query(AdminChat)
                    .filter(AdminChat.evaluation_id == ev.id)
                    .order_by(AdminChat.created_at.asc())
                    .all()
                )
                if admin_chats:
                    md.append("### Admin Private Q&A History")
                    for ac in admin_chats:
                        qa_data = json.loads(ac.qa_json) if ac.qa_json else {}
                        md.append(f"- **Admin Question:** {ac.question_ja or ac.question_en}")
                        for lang in languages:
                            lang_key = normalize_lang_to_key(lang)
                            compat_key = compat_map.get(lang_key, "en")
                            ans = (
                                qa_data.get(f"answer_{lang_key}")
                                or qa_data.get(f"answer_{compat_key}")
                                or (ac.answer_ja if lang_key == "japanese" else ac.answer_en)
                            )
                            if ans:
                                md.append(f"  - **AI Panel Response [{lang}]:** {ans}")
                    md.append("")

                # ZIP Source Text Content Embed (Crucial for NotebookLM)
                if ev.source_text:
                    md.append("### Submitted Source Code & Documents Text")
                    md.append(
                        "Below is the plain text content extracted from the ZIP submission and evaluated by the AI:"
                    )
                    md.append("```text")
                    md.append(ev.source_text)
                    md.append("```")
                    md.append("")

        return "\n".join(md)
    finally:
        db.close()


def generate_team_pdf_report(hackathon_id: int, team_id: str) -> bytes:
    """
    Generates a high-quality portfolio PDF report for a team.
    Includes team profile, progression line chart, and all evaluation histories (consultations + final submission)
    sequentially with radar charts and premium card UI stylings.
    """
    download_japanese_font()

    db = SessionLocal()
    temp_images_to_delete = []

    try:
        hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        hackathon_name = hackathon.name if hackathon else "Judgie Project"

        user = db.query(User).filter(User.hackathon_id == hackathon_id, User.team_id == team_id).first()
        team_display_name = user.team_name or team_id

        # Get all evaluations for this team in chronological order
        evaluations = (
            db.query(Evaluation)
            .filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id)
            .order_by(Evaluation.id.asc())
            .all()
        )

        pdf = JudgiePDF(hackathon_name, team_display_name, FONT_PATH)
        pdf.alias_nb_pages()
        pdf.add_page()

        font_name = "IPAexGothic" if pdf.font_loaded else "Helvetica"

        if not evaluations:
            pdf.set_font(font_name, size=14)
            pdf.cell(
                0,
                10,
                pdf.safe_text("評価データがまだありません。" if pdf.font_loaded else "No evaluation data available."),
                align="C",
            )
            pdf.ln(10)
            return bytes(pdf.output())

        criteria = get_criteria(hackathon_id)
        total_weight = sum(c["weight"] for c in criteria) if criteria else 1
        languages = get_ai_response_languages(hackathon_id)

        # --- Cover Page: Team Profile & Progression Chart ---
        pdf.set_font(font_name, size=24)
        pdf.set_text_color(15, 23, 42)  # Slate-900
        pdf.cell(0, 15, pdf.safe_text(f"{team_display_name}"), align="L")
        pdf.ln(12)

        pdf.set_font(font_name, size=12)
        pdf.set_text_color(71, 85, 105)  # Slate-600
        pdf.cell(0, 6, pdf.safe_text(f"Product Name: {user.product_name or 'N/A'}"))
        pdf.ln(6)
        pdf.cell(0, 6, pdf.safe_text(f"One-liner: {user.one_liner or 'N/A'}"))
        pdf.ln(15)

        # Generate progression chart if multiple submissions exist
        history_chart_path = generate_history_chart_img(evaluations, criteria, total_weight)
        if history_chart_path:
            temp_images_to_delete.append(history_chart_path)
            pdf.image(history_chart_path, x=15, y=pdf.get_y(), w=180)
            pdf.set_y(pdf.get_y() + 85)

        # Overview Table
        pdf.ln(5)
        pdf.set_font(font_name, size=12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, pdf.safe_text("Submission History / 提出履歴一覧"))
        pdf.ln(8)

        pdf.set_font(font_name, size=10)
        with pdf.table(
            col_widths=(60, 60, 70), text_align=("LEFT", "CENTER", "CENTER"), first_row_as_headings=False
        ) as table:
            row = table.row()
            row.cell(pdf.safe_text("Milestone / マイルストーン"))
            row.cell(pdf.safe_text("Score / スコア"))
            row.cell(pdf.safe_text("Evaluated At / 評価日時"))
            for idx, ev in enumerate(evaluations):
                row = table.row()
                eval_type = "Final Submission / 最終提出" if ev.is_final else f"Consultation {idx + 1} / 相談 {idx + 1}"
                ev_scores = json.loads(ev.scores_json)
                ev_total = sum(ev_scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria)

                row.cell(pdf.safe_text(eval_type))
                row.cell(pdf.safe_text(f"{ev_total:.1f} / 100.0"))
                row.cell(pdf.safe_text(ev.evaluated_at.strftime("%Y-%m-%d %H:%M:%S")))

        # --- Detailed Section for Each Evaluation ---
        for ev_idx, ev in enumerate(evaluations):
            pdf.add_page()

            ev_scores = json.loads(ev.scores_json)
            ev_fb = json.loads(ev.strengths_risks_json)
            ev_total = sum(ev_scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria)
            eval_type_title = "Final Submission" if ev.is_final else f"Consultation {ev_idx + 1}"

            # Milestone Header
            pdf.set_font(font_name, size=18)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 12, pdf.safe_text(f"{eval_type_title} Details"))
            pdf.ln(12)

            pdf.set_font(font_name, size=10)
            pdf.set_text_color(148, 163, 184)
            pdf.cell(0, 5, pdf.safe_text(f"ID: {ev.id}  |  Evaluated: {ev.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}"))
            pdf.ln(10)

            # Score Banner
            pdf.set_fill_color(30, 41, 59)  # Slate-800
            pdf.rect(10, pdf.get_y(), 190, 15, style="F")
            pdf.set_text_color(255, 255, 255)
            pdf.set_y(pdf.get_y() + 2)
            pdf.set_font(font_name, size=11)
            pdf.cell(95, 10, pdf.safe_text("   TOTAL SCORE FOR THIS RUN"), align="L")
            pdf.set_font(font_name, size=14)
            pdf.cell(95, 10, pdf.safe_text(f"{ev_total:.1f} / 100.0   "), align="R")
            pdf.ln(18)

            # Two Column Layout: Left=Score Breakdown Table, Right=Radar Chart Image
            # Prepare Radar Chart
            radar_img_path = generate_radar_chart_img(ev_scores, criteria)
            start_y = pdf.get_y()

            # Left: Table
            pdf.set_y(start_y)
            pdf.set_x(10)
            pdf.set_font(font_name, size=9)
            with pdf.table(col_widths=(60, 45), text_align=("LEFT", "CENTER"), first_row_as_headings=False) as table:
                row = table.row()
                row.cell(pdf.safe_text("Criteria"))
                row.cell(pdf.safe_text("Score"))
                for c in criteria:
                    row = table.row()
                    row.cell(pdf.safe_text(c["name"]))
                    row.cell(pdf.safe_text(f"{ev_scores.get(c['name'], 0):.1f} / 5.0"))

            table_height = pdf.get_y() - start_y

            # Right: Image
            if radar_img_path:
                temp_images_to_delete.append(radar_img_path)
                # Place radar chart to the right of the table
                pdf.image(radar_img_path, x=120, y=start_y - 8, w=75)

            # Move Y below the two-column block
            pdf.set_y(max(start_y + table_height, start_y + 65))
            pdf.ln(5)

            # Languages Feedback Loops
            compat_map = {"english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"}

            for lang in languages:
                lang_key = normalize_lang_to_key(lang)
                compat_key = compat_map.get(lang_key, "en")

                pdf.ln(5)
                pdf.set_font(font_name, size=13)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 8, pdf.safe_text(f"[{lang}] Feedback / 評価結果"))
                pdf.ln(8)

                # Product Understanding Card
                pdf.set_font(font_name, size=10)
                pdf.set_text_color(15, 23, 42)
                pu = (
                    ev_fb.get(f"product_understanding_{lang_key}")
                    or ev_fb.get(f"product_understanding_{compat_key}")
                    or ev_fb.get(f"summary_{lang_key}")
                    or ev_fb.get(f"summary_{compat_key}")
                )
                with pdf.table(col_widths=(190,), borders_layout="NONE", fill_color=(248, 250, 252)) as table:
                    row = table.row()
                    row.cell(
                        pdf.safe_text(
                            f"💡 Product Understanding / プロダクト理解:\n\n{pu or 'No product understanding.'}"
                        )
                    )
                pdf.ln(5)

                # Next Steps Card
                action_items = ev_fb.get(f"action_items_{lang_key}") or ev_fb.get(f"action_items_{compat_key}")
                if action_items:
                    items_str = "\n".join([f"👉 {item}" for item in action_items])
                    with pdf.table(
                        col_widths=(190,), borders_layout="NONE", fill_color=(239, 246, 255)
                    ) as table:  # Tinted blue card
                        row = table.row()
                        row.cell(pdf.safe_text(f"🚀 Next Steps (Action Items) / 最優先アクション:\n\n{items_str}"))
                    pdf.ln(5)

                # Judges Detailed Card Layout
                pdf.set_font(font_name, size=11)
                pdf.set_text_color(30, 41, 59)
                pdf.cell(0, 8, pdf.safe_text("Judges Feedback / 審査員個別コメント"))
                pdf.ln(8)

                # Cache and map active personas for matching custom avatars
                personas = get_personas(hackathon_id)
                avatar_map = {p["name"]: p.get("avatar_image") or p.get("avatar", "🧑‍⚖️") for p in personas}

                judges_fb = ev_fb.get("judges_feedback", [])
                for j in judges_fb:
                    j_name = j.get("judge_name", "Judge")
                    j_role = j.get("judge_role", "")
                    j_text = j.get(f"feedback_{lang_key}") or j.get(f"feedback_{compat_key}")

                    raw_avatar = avatar_map.get(j_name)
                    avatar_img_path = None
                    # If avatar is a Base64 image, extract it
                    if raw_avatar and isinstance(raw_avatar, str) and raw_avatar.startswith("data:image"):
                        avatar_img_path = get_temp_avatar_image(raw_avatar)
                        if avatar_img_path:
                            temp_images_to_delete.append(avatar_img_path)

                    pdf.set_font(font_name, size=9.5)
                    with pdf.table(col_widths=(45, 145), borders_layout="NONE", fill_color=(248, 250, 252)) as table:
                        row = table.row()

                        # Left Cell: Avatar image or initials, Judge Info
                        left_content = f"{j_name}\n({j_role})"
                        cell_1 = row.cell()
                        if avatar_img_path:
                            cell_1.image(avatar_img_path, width=15)
                        cell_1.write(pdf.safe_text(left_content))

                        # Right Cell: Feedback Comment
                        row.cell(pdf.safe_text(j_text))
                    pdf.ln(4)

            # Q&A Discussion Thread for this specific evaluation
            team_chats = (
                db.query(TeamChat).filter(TeamChat.evaluation_id == ev.id).order_by(TeamChat.created_at.asc()).all()
            )
            if team_chats:
                pdf.ln(5)
                pdf.set_font(font_name, size=13)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 8, pdf.safe_text("Discussion Q&A History / 質問・反論スレッド"))
                pdf.ln(8)

                for tc in team_chats:
                    msg = json.loads(tc.message_json)
                    if tc.sender == "team":
                        pdf.set_font(font_name, size=10)
                        with pdf.table(
                            col_widths=(190,), borders_layout="NONE", fill_color=(254, 243, 199)
                        ) as table:  # Tinted yellow for user questions
                            row = table.row()
                            row.cell(pdf.safe_text(f"🙋 Team Question:\n{msg.get('user_objection', '')}"))
                        pdf.ln(3)
                    else:
                        pdf.set_font(font_name, size=10)
                        qa_summary_list = []
                        for lang in languages:
                            lang_key = normalize_lang_to_key(lang)
                            compat_key = compat_map.get(lang_key, "en")
                            qa_summary = msg.get(f"qa_summary_{lang_key}") or msg.get(f"qa_summary_{compat_key}")
                            if qa_summary:
                                qa_summary_list.append(f"[{lang} Summary] {qa_summary}")

                        summary_txt = "\n".join(qa_summary_list)

                        with pdf.table(
                            col_widths=(190,), borders_layout="NONE", fill_color=(241, 245, 249)
                        ) as table:  # Slate-100 card
                            row = table.row()
                            row.cell(pdf.safe_text(f"⚖️ Judges Panel Responses:\n\n{summary_txt}"))
                        pdf.ln(3)

        return bytes(pdf.output())
    finally:
        db.close()
        # Clean up all generated temporary chart and avatar images
        for temp_img in temp_images_to_delete:
            if temp_img and os.path.exists(temp_img):
                try:
                    os.unlink(temp_img)
                except Exception:
                    pass


def generate_all_teams_pdf_zip(hackathon_id: int) -> bytes:
    """
    Generates PDF reports for all teams in a hackathon, and packages them into a ZIP archive.
    """
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.hackathon_id == hackathon_id, User.role == "team").all()
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
