import io
import json
import zipfile

import pandas as pd

from app.models.db import (
    AdminChat,
    Evaluation,
    SessionLocal,
    Team,
    TeamChat,
    get_ai_response_languages,
    get_criteria,
    get_setting,
    normalize_lang_to_key,
)


def export_project_to_markdown() -> str:
    """
    Generates a single comprehensive markdown document containing all teams, profiles,
    evaluations, Q&As, and full ZIP source texts for NotebookLM.
    """
    db = SessionLocal()
    try:
        project_name = get_setting("project_name") or "Judgie Project"

        md = []
        md.append(f"# Project Data Export: {project_name}")
        md.append(f"- **Export Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append("")

        # Criteria
        criteria = get_criteria()
        md.append("## Evaluation Criteria")
        for c in criteria:
            md.append(f"- **{c['name']}** (Weight: {c['weight']}%): {c['description']}")
        md.append("")

        # Teams
        users = db.query(Team).order_by(Team.team_id).all()

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
                db.query(Evaluation).filter(Evaluation.team_id == u.team_id).order_by(Evaluation.id.asc()).all()
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
                languages = get_ai_response_languages()
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


def generate_team_markdown_report(team_id: str) -> str:
    """
    Generates a high-quality Markdown evaluation report for a team.
    Includes team profile, milestone overview table, and all chronological evaluation histories
    (consultations + final submission) with detailed feedback and Q&A discussion, without source code.
    """
    db = SessionLocal()
    try:
        project_name = get_setting("project_name") or "Judgie Project"

        user = db.query(Team).filter(Team.team_id == team_id).first()
        if not user:
            return "# Team Not Found"
        team_display_name = user.team_name or team_id

        # Get all evaluations for this team in chronological order
        evaluations = db.query(Evaluation).filter(Evaluation.team_id == team_id).order_by(Evaluation.id.asc()).all()

        md = []
        md.append(f"# Team Evaluation Report: {team_display_name}")
        md.append(f"- **Project:** {project_name}")
        md.append(f"- **Product Name:** {user.product_name or 'N/A'}")
        md.append(f"- **One-liner:** {user.one_liner or 'N/A'}")
        md.append(f"- **Report Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append("")

        if not evaluations:
            md.append("No evaluation data recorded for this team yet.")
            return "\n".join(md)

        criteria = get_criteria()
        total_weight = sum(c["weight"] for c in criteria) if criteria else 1
        languages = get_ai_response_languages()

        # Overview Table
        md.append("## Submission History / 提出履歴一覧")
        md.append("| Milestone / マイルストーン | Score / スコア | Evaluated At / 評価日時 |")
        md.append("| --- | --- | --- |")
        for idx, ev in enumerate(evaluations):
            eval_type = "Final Submission" if ev.is_final else f"Consultation {idx + 1}"
            ev_scores = json.loads(ev.scores_json)
            ev_total = sum(ev_scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria)
            md.append(f"| {eval_type} | {ev_total:.1f} / 100.0 | {ev.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')} |")
        md.append("")

        # Detailed Sections
        for ev_idx, ev in enumerate(evaluations):
            ev_scores = json.loads(ev.scores_json)
            ev_fb = json.loads(ev.strengths_risks_json)
            ev_total = sum(ev_scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria)
            eval_type_title = "Final Submission" if ev.is_final else f"Consultation {ev_idx + 1}"

            md.append("---")
            md.append(f"## Detailed Results: {eval_type_title}")
            md.append(f"- **Evaluation ID:** {ev.id}")
            md.append(f"- **Evaluated At:** {ev.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            md.append(f"- **Total Score:** **{ev_total:.1f} / 100.0**")
            md.append("")

            # Score Breakdown
            md.append("### Score Breakdown / 評価基準別内訳")
            md.append("| Criteria / 評価基準 | Score / スコア (5.0 Max) | Weight / 比重 |")
            md.append("| --- | --- | --- |")
            for c in criteria:
                md.append(f"| {c['name']} | {ev_scores.get(c['name'], 0):.1f} / 5.0 | {c['weight']}% |")
            md.append("")

            # Languages Feedback Loops
            compat_map = {"english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"}
            for lang in languages:
                lang_key = normalize_lang_to_key(lang)
                compat_key = compat_map.get(lang_key, "en")

                md.append(f"### Feedback / 評価結果 [{lang}]")

                # Product Understanding
                pu = (
                    ev_fb.get(f"product_understanding_{lang_key}")
                    or ev_fb.get(f"product_understanding_{compat_key}")
                    or ev_fb.get(f"summary_{lang_key}")
                    or ev_fb.get(f"summary_{compat_key}")
                )
                md.append("#### 💡 Product Understanding / プロダクト理解")
                md.append(pu or "No product understanding text.")
                md.append("")

                # Next Steps
                action_items = ev_fb.get(f"action_items_{lang_key}") or ev_fb.get(f"action_items_{compat_key}")
                md.append("#### 🚀 Next Steps (Action Items) / 最優先アクション")
                if action_items:
                    for item in action_items:
                        md.append(f"- 👉 {item}")
                else:
                    md.append("No action items provided.")
                md.append("")

                # Judges feedback
                md.append("#### ⚖️ Judges Detailed Feedback / 審査員個別コメント")
                judges_fb = ev_fb.get("judges_feedback", [])
                for j in judges_fb:
                    j_name = j.get("judge_name", "Judge")
                    j_role = j.get("judge_role", "")
                    j_text = j.get(f"feedback_{lang_key}") or j.get(f"feedback_{compat_key}")
                    md.append(f"- **{j_name} ({j_role}):** {j_text}")
                md.append("")

            # Discussion Q&A History
            team_chats = (
                db.query(TeamChat).filter(TeamChat.evaluation_id == ev.id).order_by(TeamChat.created_at.asc()).all()
            )
            if team_chats:
                md.append("### Q&A Discussion History / 質問・反論スレッド")
                for tc in team_chats:
                    msg = json.loads(tc.message_json)
                    if tc.sender == "team":
                        md.append(f"- 🙋 **Team Question:** {msg.get('user_objection', '')}")
                    else:
                        md.append("- ⚖️ **AI Judges Panel Responses:**")
                        for lang in languages:
                            lang_key = normalize_lang_to_key(lang)
                            compat_key = compat_map.get(lang_key, "en")
                            qa_summary = msg.get(f"qa_summary_{lang_key}") or msg.get(f"qa_summary_{compat_key}")
                            if qa_summary:
                                md.append(f"  - *[{lang} Summary]* {qa_summary}")
                md.append("")

            # Admin Private Q&A
            admin_chats = (
                db.query(AdminChat).filter(AdminChat.evaluation_id == ev.id).order_by(AdminChat.created_at.asc()).all()
            )
            if admin_chats:
                md.append("### Admin Private Q&A History / 管理者非公開スレッド")
                for ac in admin_chats:
                    qa_data = json.loads(ac.qa_json) if ac.qa_json else {}
                    md.append(f"- 🔒 **Admin Question:** {ac.question_ja or ac.question_en}")
                    for lang in languages:
                        lang_key = normalize_lang_to_key(lang)
                        compat_key = compat_map.get(lang_key, "en")
                        ans = (
                            qa_data.get(f"answer_{lang_key}")
                            or qa_data.get(f"answer_{compat_key}")
                            or (ac.answer_ja if lang_key == "japanese" else ac.answer_en)
                        )
                        if ans:
                            md.append(f"  - **AI Response [{lang}]:** {ans}")
                md.append("")

        return "\n".join(md)
    finally:
        db.close()


def generate_all_teams_markdown_zip() -> bytes:
    """
    Generates Markdown reports for all teams in a project, and packages them into a ZIP archive.
    """
    db = SessionLocal()
    try:
        users = db.query(Team).all()
        if not users:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                zip_file.writestr("info.txt", "No team evaluation data available.")
            return zip_buffer.getvalue()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for u in users:
                report_md = generate_team_markdown_report(u.team_id)
                safe_team_id = "".join([c for c in u.team_id if c.isalnum() or c in ("-", "_", " ")])
                zip_file.writestr(f"report_{safe_team_id}.md", report_md)

        return zip_buffer.getvalue()
    finally:
        db.close()


def export_project_to_markdown_zip() -> bytes:
    """
    Generates team-specific markdown files and bundles them into a single ZIP archive
    for NotebookLM ingestion.
    """
    db = SessionLocal()
    try:
        project_name = get_setting("project_name") or "Judgie Project"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Add evaluation metadata
            criteria = get_criteria()
            meta_md = []
            meta_md.append(f"# Project Evaluation Meta: {project_name}")
            meta_md.append(f"- **Export Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
            meta_md.append("")
            meta_md.append("## Evaluation Criteria")
            for c in criteria:
                meta_md.append(f"- **{c['name']}** (Weight: {c['weight']}%): {c['description']}")
            meta_md.append("")
            zip_file.writestr("00_project_meta.md", "\n".join(meta_md))

            # 2. Add team markdowns
            users = db.query(Team).order_by(Team.team_id).all()

            for u in users:
                team_md = []
                team_md.append(f"# Team: {u.team_name or u.team_id} (ID: {u.team_id})")
                team_md.append(f"- **Product Name:** {u.product_name or 'N/A'}")
                team_md.append(f"- **One-liner:** {u.one_liner or 'N/A'}")
                team_md.append("")

                evaluations = (
                    db.query(Evaluation).filter(Evaluation.team_id == u.team_id).order_by(Evaluation.id.asc()).all()
                )

                if not evaluations:
                    team_md.append("No submissions or evaluations recorded for this team.")
                    team_md.append("")
                else:
                    for idx, ev in enumerate(evaluations):
                        eval_type = "Final Submission" if ev.is_final else f"Consultation {idx + 1}"
                        team_md.append(f"## {eval_type} (ID: {ev.id})")
                        team_md.append(f"- **Evaluated At:** {ev.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}")

                        scores = json.loads(ev.scores_json)
                        total_weight = sum(c["weight"] for c in criteria) if criteria else 1
                        total_score = sum(
                            scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight) for c in criteria
                        )

                        team_md.append(f"### Scores (Total: {total_score:.1f} / 100.0)")
                        team_md.append("- **Criteria Breakdown:**")
                        for c in criteria:
                            team_md.append(
                                f"  - {c['name']}: {scores.get(c['name'], 0)} / 5.0 (Weight: {c['weight']}%)"
                            )
                        team_md.append("")

                        fb = json.loads(ev.strengths_risks_json)
                        languages = get_ai_response_languages()
                        compat_map = {"english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"}

                        for lang in languages:
                            lang_key = normalize_lang_to_key(lang)
                            compat_key = compat_map.get(lang_key, "en")

                            team_md.append(f"### Evaluation in {lang}")

                            pu = (
                                fb.get(f"product_understanding_{lang_key}")
                                or fb.get(f"product_understanding_{compat_key}")
                                or fb.get(f"summary_{lang_key}")
                                or fb.get(f"summary_{compat_key}")
                            )
                            team_md.append("#### Product Understanding")
                            team_md.append(pu or "No product understanding text.")
                            team_md.append("")

                            action_items = fb.get(f"action_items_{lang_key}") or fb.get(f"action_items_{compat_key}")
                            team_md.append("#### Next Steps / Action Items")
                            if action_items:
                                for item in action_items:
                                    team_md.append(f"- {item}")
                            else:
                                team_md.append("No action items provided.")
                            team_md.append("")

                            team_md.append("#### Judges Detailed Feedback")
                            judges_fb = fb.get("judges_feedback", [])
                            for j in judges_fb:
                                j_name = j.get("judge_name", "Judge")
                                j_role = j.get("judge_role", "")
                                j_text = j.get(f"feedback_{lang_key}") or j.get(f"feedback_{compat_key}")
                                team_md.append(f"- **{j_name} ({j_role}):**")
                                team_md.append(f"  {j_text}")
                            team_md.append("")

                        team_chats = (
                            db.query(TeamChat)
                            .filter(TeamChat.evaluation_id == ev.id)
                            .order_by(TeamChat.created_at.asc())
                            .all()
                        )
                        if team_chats:
                            team_md.append("### Discussion Q&A History")
                            for tc in team_chats:
                                msg = json.loads(tc.message_json)
                                if tc.sender == "team":
                                    team_md.append(f"- **Team Question:** {msg.get('user_objection', '')}")
                                else:
                                    team_md.append("- **AI Judges Panel Response:**")
                                    for lang in languages:
                                        lang_key = normalize_lang_to_key(lang)
                                        compat_key = compat_map.get(lang_key, "en")
                                        qa_summary = msg.get(f"qa_summary_{lang_key}") or msg.get(
                                            f"qa_summary_{compat_key}"
                                        )
                                        if qa_summary:
                                            team_md.append(f"  - *[{lang}] Summary:* {qa_summary}")

                                    for jr in msg.get("judges_responses", []):
                                        jr_name = jr.get("judge_name", "Judge")
                                        team_md.append(f"  - **{jr_name}:**")
                                        for lang in languages:
                                            lang_key = normalize_lang_to_key(lang)
                                            compat_key = compat_map.get(lang_key, "en")
                                            jr_resp = jr.get(f"response_{lang_key}") or jr.get(f"response_{compat_key}")
                                            if jr_resp:
                                                team_md.append(f"    - *[{lang}]:* {jr_resp}")
                            team_md.append("")

                        admin_chats = (
                            db.query(AdminChat)
                            .filter(AdminChat.evaluation_id == ev.id)
                            .order_by(AdminChat.created_at.asc())
                            .all()
                        )
                        if admin_chats:
                            team_md.append("### Admin Private Q&A History")
                            for ac in admin_chats:
                                qa_data = json.loads(ac.qa_json) if ac.qa_json else {}
                                team_md.append(f"- **Admin Question:** {ac.question_ja or ac.question_en}")
                                for lang in languages:
                                    lang_key = normalize_lang_to_key(lang)
                                    compat_key = compat_map.get(lang_key, "en")
                                    ans = (
                                        qa_data.get(f"answer_{lang_key}")
                                        or qa_data.get(f"answer_{compat_key}")
                                        or (ac.answer_ja if lang_key == "japanese" else ac.answer_en)
                                    )
                                    if ans:
                                        team_md.append(f"  - **AI Panel Response [{lang}]:** {ans}")
                            team_md.append("")

                        if ev.source_text:
                            team_md.append("### Submitted Source Code & Documents Text")
                            team_md.append(
                                "Below is the plain text content extracted from the ZIP submission and evaluated by the AI:"
                            )
                            team_md.append("```text")
                            team_md.append(ev.source_text)
                            team_md.append("```")
                            team_md.append("")

                safe_team_id = "".join([c for c in u.team_id if c.isalnum() or c in ("-", "_", " ")])
                zip_file.writestr(f"team_{safe_team_id}_markdown.md", "\n".join(team_md))

        return zip_buffer.getvalue()
    finally:
        db.close()
