import json

import streamlit as st

from config import MAX_CONSULTATIONS
from core.db import (
    Hackathon,
    User,
    change_my_passcode,
    db_session,
    get_criteria,
    get_max_qa_turns,
    get_re_evaluation_context_mode,
    get_team_profile,
    update_team_profile,
)
from core.i18n import t
from core.services.evaluation_service import get_team_chats, get_team_evaluations, submit_team_objection
from core.services.submission_service import process_submission
from core.ui_utils import get_avatar_html
from views.components.charts import render_criteria_radar_chart, render_score_history_chart
from views.components.feedback_cards import render_judge_feedback_tab

lang = st.session_state.get('language', 'English')
role = st.session_state.role

st.set_page_config(layout="wide")

current_h_id = st.session_state.get('active_hackathon_id')
is_demo = (current_h_id == 9999)

# Determine which team we are viewing
if role == 'admin':
    with db_session() as db:
        if current_h_id:
            users = db.query(User.team_id).filter(User.role == 'team', User.hackathon_id == current_h_id).order_by(User.team_id).all()
        else:
            users = db.query(User.team_id).filter(User.role == 'team').order_by(User.team_id).all()
        all_teams = [u.team_id for u in users]

    st.info(t("Admin Mode: Read-Only View", "管理者モード: 閲覧専用"))
    view_team_id = st.selectbox(t("Select Team to View", "閲覧するチームを選択"), all_teams) if all_teams else None
else:
    view_team_id = st.session_state.team_id

if not view_team_id:
    st.warning("No teams available in this hackathon.")
    st.stop()

# Fetch all evaluations for this team via service
eval_rows = get_team_evaluations(view_team_id)

consultations_used = sum(1 for r in eval_rows if not r['is_final'])
is_final_submitted = any(r['is_final'] for r in eval_rows)
consultations_left = MAX_CONSULTATIONS - consultations_used

col1, col2 = st.columns([1, 1.5])

# --- LEFT COLUMN: UPLOAD ---
with col1:
    st.title(t("📤 Submission", "📤 成果物の提出"))

    # Show Hackathon Name
    with db_session() as db:
        result = db.query(Hackathon.name).join(User, User.hackathon_id == Hackathon.id).filter(User.team_id == view_team_id).first()
        h_row = {'name': result.name} if result else None

    if h_row:
        st.caption(f"🏆 {h_row['name']}")

    # Team Profile Section
    profile = get_team_profile(current_h_id, view_team_id)
    p_name = profile.get('product_name')
    t_name = profile.get('team_name')
    if t_name and p_name:
        display_name = f"{t_name} / {p_name}"
    elif t_name:
        display_name = t_name
    elif p_name:
        display_name = p_name
    else:
        display_name = view_team_id

    st.markdown(f"**{t('Team / Product:', 'チーム / プロダクト:')}** `{display_name}`")
    if profile.get('one_liner'):
        st.caption(f"✨ {profile['one_liner']}")

    if role == 'team':
        if is_demo:
            st.caption(t(
                "🔒 Profile editing and password change are disabled in Demo Mode.",
                "🔒 デモモードではプロフィールの編集やパスワードの変更は無効化されています。"
            ))
        else:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                with st.popover(t("⚙️ Edit Profile", "⚙️ プロフィールの編集")):
                    with st.form("profile_form"):
                        p_name = st.text_input(t("Product Name", "プロダクト名"), value=profile.get('product_name', ''))
                        t_name = st.text_input(t("Team Name", "チーム名"), value=profile.get('team_name', ''))
                        o_liner = st.text_input(t("One-liner (Catchphrase)", "一言アピール（キャッチコピー）"), value=profile.get('one_liner', ''))
                        if st.form_submit_button(t("Save", "保存"), type="primary"):
                            update_team_profile(current_h_id, view_team_id, p_name, t_name, o_liner)
                            st.success(t("Profile updated!", "プロフィールを更新しました！"))
                            st.rerun()

            with p_col2:
                with st.popover(t("🔐 Change Password", "🔐 パスワード変更")):
                    with st.form("change_team_pass_form"):
                        curr_pass = st.text_input(t("Current Password", "現在のパスワード"), type="password")
                        new_pass = st.text_input(t("New Password", "新しいパスワード"), type="password")
                        if st.form_submit_button(t("Update", "更新"), type="primary"):
                            if not curr_pass or not new_pass:
                                st.error(t("All fields required.", "すべて入力してください。"))
                            else:
                                success = change_my_passcode(current_h_id, view_team_id, curr_pass, new_pass)
                                if success:
                                    st.session_state.passcode = new_pass
                                    st.success(t("Password updated!", "パスワードを更新しました！"))
                                else:
                                    st.error(t("Incorrect current password.", "現在のパスワードが間違っています。"))

    st.divider()

    if role == 'admin':
        st.warning(t("Uploads are disabled in Admin Mode.", "管理者モードではアップロードは無効化されています。"))
    elif is_demo:
        st.info(t(
            "💡 Demo Mode: File uploading and AI evaluation are disabled. Please explore the evaluation history on the right dashboard.",
            "💡 デモモード: ファイルのアップロードや新規解析は無効化されています。右側のダッシュボードで、過去の評価履歴を切り替えて体験してください。"
        ))
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.metric(t("Consultations Left", "残り相談回数"), "0 / 3")
            st.button(t("Get AI Coaching", "AIコーチングを受ける"), type="secondary", disabled=True, key="demo_coach_btn", use_container_width=True)
        with sub_c2:
            st.metric(t("Final Submission", "最終提出"), t("Submitted", "提出済み"))
            st.button(t("Submit Final Pitch", "最終成果物として提出"), type="primary", disabled=True, key="demo_final_btn", use_container_width=True)
    elif is_final_submitted:
        st.success(t("Final pitch submitted. Good luck!", "最終成果物を提出済みです。お疲れ様でした！"))
    else:
        with st.expander(t("💡 Tips for ZIP creation (to avoid size limits)", "💡 ZIPファイル作成時のヒント (容量超過を防ぐために)"), expanded=False):
            st.markdown(t(
                "If your project includes large directories like `node_modules`, `.git`, or `venv`, please exclude them before zipping to avoid hitting the 200MB upload limit and AI context limits.\n\n**Example command (Mac/Linux):**\n```bash\nzip -r submission.zip . -x \"node_modules/*\" -x \".git/*\" -x \"venv/*\" -x \".next/*\"\n```",
                "プロジェクト内に `node_modules`, `.git`, `venv` などの巨大なディレクトリが含まれていると、アップロード制限（200MB）を超えたり、AIの解析エラーの原因になります。以下のコマンドを参考に、不要なファイルを除外してZIP化してください。\n\n**Mac/LinuxでのZIP作成例:**\n```bash\nzip -r submission.zip . -x \"node_modules/*\" -x \".git/*\" -x \"venv/*\" -x \".next/*\"\n```"
            ))

        uploaded_files = st.file_uploader(
            t("Artifacts (ZIP, MP4, MOV, PDF)", "成果物ファイル (ZIP, MP4, MOV, PDF)"),
            type=["zip", "mp4", "mov", "pdf"],
            accept_multiple_files=True,
            help=t("Max total size: 200MB.", "合計最大サイズは200MBです。")
        )

        can_consult = consultations_left > 0

        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.metric(t("Consultations Left", "残り相談回数"), f"{consultations_left} / {MAX_CONSULTATIONS}")
            if st.button(t("Get AI Coaching", "AIコーチングを受ける"), type="secondary", disabled=not can_consult or not uploaded_files):
                submit_type = "consultation"
            else:
                submit_type = None

        with sub_c2:
            st.metric(t("Final Submission", "最終提出"), t("Available", "未提出"))
            if st.button(t("Submit Final Pitch", "最終成果物として提出"), type="primary", disabled=not uploaded_files):
                submit_type = "final"

        if submit_type:
            is_final_flag = (submit_type == "final")

            # Prepare previous feedback as context
            prev_json_str = None
            context_mode = get_re_evaluation_context_mode(current_h_id)
            if context_mode == "cumulative" and eval_rows:
                last_fb = json.loads(eval_rows[-1]['strengths_risks_json'])
                prev_json_str = json.dumps(last_fb.get('judges_feedback', []))

            with st.status(t("🤖 AI Expert Panel is reviewing...", "🤖 AI専門家パネルが審査中..."), expanded=True) as status:
                try:
                    # Execute evaluation flow via service layer
                    st.write(t("📦 Processing files and running AI panel...", "📦 ファイルを処理し、AIパネルを実行中..."))

                    process_submission(
                        hackathon_id=current_h_id,
                        team_id=view_team_id,
                        uploaded_files=uploaded_files,
                        prev_evaluations_json=prev_json_str,
                        is_final=is_final_flag
                    )

                    status.update(label=t("✅ Analysis complete!", "✅ 解析完了！"), state="complete", expanded=False)
                    st.rerun()
                except Exception as e:
                    status.update(label=t("❌ Error occurred", "❌ エラーが発生しました"), state="error", expanded=True)
                    st.error(f"An error occurred: {str(e)}")

# --- RIGHT COLUMN: FEEDBACK & SCORES ---
with col2:
    st.title(t("💬 AI Feedback Dashboard", "💬 AIフィードバック・ダッシュボード"))

    if not eval_rows:
        st.info(t("No feedback history yet.", "まだフィードバック履歴がありません。"))
    else:
        # History selector
        eval_dict_map = {r['id']: r for r in eval_rows}
        history_options = []
        for i, r in enumerate(eval_rows):
            if r['is_final']:
                history_options.append((r['id'], f"⭐ {t('Final Submission', '最終提出')}"))
            else:
                history_options.append((r['id'], f"🔄 {t('Consultation', '相談')} {i+1}"))

        # Reverse to show latest first
        history_options.reverse()

        selected_eval_id = st.selectbox(
            t("Select Evaluation History", "過去の評価履歴を選択"),
            [opt[0] for opt in history_options],
            format_func=lambda x: next(opt[1] for opt in history_options if opt[0] == x),
            key="team_view_history_select"
        )

        selected_eval = eval_dict_map[selected_eval_id]
        fb = json.loads(selected_eval['strengths_risks_json'])
        scores = json.loads(selected_eval['scores_json'])

        # Identify previous evaluation for delta calculation
        current_idx = next((i for i, r in enumerate(eval_rows) if r['id'] == selected_eval['id']), 0)
        prev_scores = None
        if current_idx > 0:
            prev_scores = json.loads(eval_rows[current_idx - 1]['scores_json'])

        # Top: Score Breakdown
        criteria = get_criteria(current_h_id)
        total_weight = sum(c['weight'] for c in criteria) if criteria else 1

        # Calculate 100-point scaled total score
        total_score = sum(scores.get(crit['name'], 0) * 20.0 * (crit['weight'] / total_weight) for crit in criteria)

        # Display prominent Total Score Card
        st.markdown(
            f"""
            <div style='
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                padding: 20px;
                border-radius: 12px;
                border: 1px solid #334155;
                margin-bottom: 25px;
                text-align: center;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            '>
                <span style='font-size: 0.95em; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8;'>
                    {t('Total Score', '総合スコア')}
                </span><br>
                <span style='font-size: 2.8em; font-weight: 800; color: #38bdf8; line-height: 1.2;'>
                    {total_score:.1f}
                </span>
                <span style='font-size: 1.4em; font-weight: 600; color: #64748b;'>
                    / 100.0
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(f"#### 📊 {t('Score Breakdown & Contributions', 'スコア内訳（貢献スコア）')}")
        score_cols = st.columns(3)

        chart_data = []

        for i, crit in enumerate(criteria):
            col = score_cols[i % 3]
            s = scores.get(crit['name'], 0)
            weight_pct = crit['weight']
            contribution = s * 20.0 * (weight_pct / total_weight)
            max_contrib = 100.0 * (weight_pct / total_weight)

            delta_str = None
            if prev_scores is not None:
                prev_s = prev_scores.get(crit['name'], 0)
                diff = s - prev_s
                if diff != 0:
                    delta_str = f"{diff:+.1f} pts"
                else:
                    delta_str = "±0"

            with col:
                st.metric(crit['name'], f"{s} / 5.0", delta_str, delta_color="normal")
                st.caption(t(f"Contribution: {contribution:.1f} / {max_contrib:.1f} pts", f"貢献スコア: {contribution:.1f} / {max_contrib:.1f}点"))

            chart_data.append({
                "Criteria": crit['name'],
                "Score": s
            })

        st.markdown("---")

        # Render score history line chart (Altair Component)
        render_score_history_chart(eval_rows, criteria, total_weight)

        # Render current metrics horizontal bar chart (Altair Component)
        render_criteria_radar_chart(chart_data)

        st.markdown("---")

        # Get configured AI response languages
        from core.db import get_ai_response_languages, normalize_lang_to_key
        languages = get_ai_response_languages(current_h_id)

        emoji_map = {
            "English": "🇺🇸",
            "Japanese": "🇯🇵",
            "Spanish": "🇪🇸",
            "French": "🇫🇷",
            "German": "🇩🇪",
            "Chinese (Simplified)": "🇨🇳",
            "Chinese (Traditional)": "🇹🇼",
            "Korean": "🇰🇷",
            "Vietnamese": "🇻🇳",
            "Thai": "🇹🇭",
            "Indonesian": "🇮🇩"
        }
        tab_titles = [f"{emoji_map.get(lang, '🌐')} {lang}" for lang in languages]
        lang_tabs = st.tabs(tab_titles)

        from core.db import get_personas
        personas = get_personas(current_h_id)
        avatar_map = {p['name']: p.get('avatar_image') or p.get('avatar', '🧑‍⚖️') for p in personas}

        for idx, lang_name in enumerate(languages):
            lang_key = normalize_lang_to_key(lang_name)
            with lang_tabs[idx]:
                st.markdown(f"#### 🔥 {t('Top Priorities (Next Steps)', '最優先アクション (Next Steps)')}")
                action_items = fb.get(f'action_items_{lang_key}')
                if action_items is None:
                    compat_map = {
                        "english": "en", "japanese": "ja", "日本語": "ja", "英語": "en",
                        "spanish": "es", "french": "fr", "german": "de", "korean": "ko",
                        "chinese": "zh", "vietnamese": "vi", "thai": "th", "indonesian": "id"
                    }
                    compat_key = compat_map.get(lang_key, 'en')
                    action_items = fb.get(f'action_items_{compat_key}', [])

                if action_items:
                    for item in action_items:
                        st.info(f"👉 {item}")
                else:
                    st.write(t("No specific action items provided.", "具体的なアクションアイテムは提供されていません。"))

                st.markdown(f"#### 🧠 {t('AI Product Understanding', 'プロダクト理解')}")
                pu_text = fb.get(f'product_understanding_{lang_key}', fb.get(f'summary_{lang_key}'))
                if pu_text is None:
                    compat_map = {
                        "english": "en", "japanese": "ja", "日本語": "ja", "英語": "en",
                        "spanish": "es", "french": "fr", "german": "de", "korean": "ko",
                        "chinese": "zh", "vietnamese": "vi", "thai": "th", "indonesian": "id"
                    }
                    compat_key = compat_map.get(lang_key, 'en')
                    pu_text = fb.get(f'product_understanding_{compat_key}', fb.get(f'summary_{compat_key}', ''))
                st.write(pu_text)

                st.markdown(f"#### 🧑‍⚖️ {t('Judges Feedback', '審査員フィードバック')}")
                render_judge_feedback_tab(fb, avatar_map, lang=lang_name)

        st.markdown("---")
        st.subheader(t("🙋 Objection! / Q&A", "🙋 異議あり！ / 審査員への質問"))

        max_qa = get_max_qa_turns(current_h_id)

        # Get chat history for this evaluation
        chats = get_team_chats(selected_eval_id)

        # Calculate turns used (each user question is a turn)
        turns_used = sum(1 for c in chats if c['sender'] == 'team')

        if max_qa == 0:
            st.info(t("Q&A is disabled for this project.", "このプロジェクトではQ&Aは無効化されています。"))

        # Render Chat Thread UI if there is any history
        if chats:
            st.markdown(f"#### 💬 {t('Discussion Thread', 'ディスカッションスレッド')}")
            for chat in chats:
                is_user = (chat['sender'] == 'team')
                msg_data = chat['message_json']

                if is_user:
                    with st.chat_message("user"):
                        st.markdown(f"**{t('Your Question / Objection:', 'あなたからの質問・反論:')}**")
                        st.write(msg_data.get('user_objection', ''))
                else:
                    with st.chat_message("assistant", avatar="🧑‍⚖️"):
                        st.markdown(f"**⚖️ {t('Panel Response:', '審査員からの回答:')}**")

                        # Support multiple languages in tabs
                        qa_tabs = st.tabs(tab_titles)
                        for idx, lang_name in enumerate(languages):
                            lang_key = normalize_lang_to_key(lang_name)
                            with qa_tabs[idx]:
                                qa_summary = msg_data.get(f'qa_summary_{lang_key}')
                                if not qa_summary:
                                    compat_map = {
                                        "english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"
                                    }
                                    compat_key = compat_map.get(lang_key, 'en')
                                    qa_summary = msg_data.get(f'qa_summary_{compat_key}', '')
                                st.info(qa_summary)

                                for j in msg_data.get('judges_responses', []):
                                    j_name = j.get('judge_name', 'Judge')
                                    j_icon = avatar_map.get(j_name, '🧑‍⚖️')
                                    st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 10px;">{get_avatar_html(j_name, j_icon, size=24)}<strong style="margin-left: 8px;">{j_name}</strong></div>', unsafe_allow_html=True)

                                    j_resp = j.get(f'response_{lang_key}')
                                    if not j_resp:
                                        compat_map = {
                                            "english": "en", "japanese": "ja", "日本語": "ja", "英語": "en"
                                        }
                                        compat_key = compat_map.get(lang_key, 'en')
                                        j_resp = j.get(f'response_{compat_key}', '')
                                    st.write(j_resp)
                                    st.divider()

        # Handle form visibility based on Q&A turn limit
        has_reached_limit = (max_qa != -1 and turns_used >= max_qa)

        if max_qa > 0:
            if has_reached_limit:
                st.success(t(
                    f"You have completed the maximum allowed discussion turns ({turns_used} / {max_qa}).",
                    f"許容された最大ディスカッション回数に達しました ({turns_used} / {max_qa} 往復)。"
                ))
            else:
                if role == 'team':
                    if is_demo:
                        st.info(t(
                            "🔒 Demo Mode: Sending new questions is disabled.",
                            "🔒 デモモード: 審査員への新規質問送信は無効化されています。"
                        ))
                    else:
                        turns_left_str = f"{max_qa - turns_used} / {max_qa}" if max_qa != -1 else t("Unlimited", "無制限")
                        st.markdown(t(
                            f"You can ask questions or make objections ({turns_left_str} turns left). The AI Panel will read your message and respond.",
                            f"審査員パネルに対して質問や反論を送信できます (残りターン数: {turns_left_str})。"
                        ))
                        with st.form("objection_form"):
                            obj_text = st.text_area(t("Your message to the judges:", "審査員へのメッセージ:"), height=150)
                            submit_obj = st.form_submit_button(t("Send Message ✊", "メッセージを送信 ✊"), type="primary")

                            if submit_obj:
                                if not obj_text.strip():
                                    st.warning(t("Please enter your message.", "メッセージを入力してください。"))
                                else:
                                    with st.status(t("⚖️ Judges are discussing your point...", "⚖️ 審査員があなたの意見を議論中..."), expanded=True) as status:
                                        try:
                                            prev_eval_json_str = selected_eval['strengths_risks_json']

                                            submit_team_objection(
                                                hackathon_id=current_h_id,
                                                eval_id=selected_eval['id'],
                                                prev_eval_json=prev_eval_json_str,
                                                objection_text=obj_text
                                            )
                                            status.update(label=t("✅ Judges have responded!", "✅ 審査員からの回答が届きました！"), state="complete", expanded=False)
                                            st.rerun()
                                        except Exception as e:
                                            status.update(label=t("❌ Error", "❌ エラー"), state="error")
                                            st.error(f"Failed: {str(e)}")
                else:
                    if not chats:
                        st.info(t("No objections made by the team yet.", "チームからの質問・反論はまだありません。"))
