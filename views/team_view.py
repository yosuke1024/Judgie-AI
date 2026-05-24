import streamlit as st
import tempfile
import os
import json
import pandas as pd
from config import MAX_CONSULTATIONS
from core.db import get_consultation_count, save_evaluation, get_criteria, get_team_profile, update_team_profile, SessionLocal, User, Hackathon, Evaluation
from core.file_handler import extract_text_from_zip
from core.gemini import upload_to_gemini, wait_for_files_active, analyze_submission
from core.ui_utils import get_avatar_html

lang = st.session_state.get('language', 'English')
def t(en, ja): return en if lang == "English" else ja
role = st.session_state.role

st.set_page_config(layout="wide")

# Determine which team we are viewing
current_h_id = st.session_state.get('active_hackathon_id')

if role == 'admin':
    db = SessionLocal()
    try:
        if current_h_id:
            users = db.query(User.team_id).filter(User.role == 'team', User.hackathon_id == current_h_id).order_by(User.team_id).all()
        else:
            users = db.query(User.team_id).filter(User.role == 'team').order_by(User.team_id).all()
        all_teams = [u.team_id for u in users]
    finally:
        db.close()
    
    st.info(t("Admin Mode: Read-Only View", "管理者モード: 閲覧専用"))
    view_team_id = st.selectbox(t("Select Team to View", "閲覧するチームを選択"), all_teams) if all_teams else None
else:
    view_team_id = st.session_state.team_id

if not view_team_id:
    st.warning("No teams available in this hackathon.")
    st.stop()


# Fetch all evaluations for this team
db = SessionLocal()
try:
    evaluations = db.query(Evaluation).filter(Evaluation.team_id == view_team_id).order_by(Evaluation.id.asc()).all()
    eval_rows = []
    for e in evaluations:
        eval_rows.append({
            'id': e.id,
            'team_id': e.team_id,
            'scores_json': e.scores_json,
            'impact_score': e.impact_score,
            'strengths_risks_json': e.strengths_risks_json,
            'qa_json': e.qa_json,
            'is_final': e.is_final,
            'source_text': e.source_text,
            'gemini_file_ids': e.gemini_file_ids,
            'evaluated_at': e.evaluated_at
        })
finally:
    db.close()

consultations_used = sum(1 for r in eval_rows if not r['is_final'])
is_final_submitted = any(r['is_final'] for r in eval_rows)
consultations_left = MAX_CONSULTATIONS - consultations_used

col1, col2 = st.columns([1, 1.5])

# --- LEFT COLUMN: UPLOAD ---
with col1:
    st.title(t("📤 Submission", "📤 成果物の提出"))
    
    # Show Hackathon Name
    db = SessionLocal()
    try:
        result = db.query(Hackathon.name).join(User, User.hackathon_id == Hackathon.id).filter(User.team_id == view_team_id).first()
        h_row = {'name': result.name} if result else None
    finally:
        db.close()
    if h_row:
        st.caption(f"🏆 {h_row['name']}")
        
    # Team Profile Section
    profile = get_team_profile(current_h_id, view_team_id)
    display_name = profile.get('product_name') or profile.get('team_name') or view_team_id
    
    st.markdown(f"**{t('Team / Product:', 'チーム / プロダクト:')}** `{display_name}`")
    if profile.get('one_liner'):
        st.caption(f"✨ {profile['one_liner']}")
        
    if role == 'team':
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
                        from core.db import change_my_passcode
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
            else: submit_type = None
                
        with sub_c2:
            st.metric(t("Final Submission", "最終提出"), t("Available", "未提出"))
            if st.button(t("Submit Final Pitch", "最終成果物として提出"), type="primary", disabled=not uploaded_files):
                submit_type = "final"
                
        if submit_type:
            is_final_flag = (submit_type == "final")
            
            # Prepare previous feedback as context
            prev_json_str = None
            if eval_rows:
                # pass the last one
                last_fb = json.loads(eval_rows[-1]['strengths_risks_json'])
                prev_json_str = json.dumps(last_fb.get('judges_feedback', []))
            
            with st.status(t("🤖 AI Expert Panel is reviewing...", "🤖 AI専門家パネルが審査中..."), expanded=True) as status:
                try:
                    st.write(t("📦 Extracting submitted files...", "📦 提出ファイルを展開中..."))
                    text_content = ""
                    gemini_media_files = []
                    for uf in uploaded_files:
                        if uf.name.endswith(".zip"):
                            text_content += extract_text_from_zip(uf)
                        elif uf.name.endswith((".mp4", ".mov", ".pdf")):
                            ext = os.path.splitext(uf.name)[1]
                            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                                tmp.write(uf.read())
                                tmp_path = tmp.name
                            mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".pdf": "application/pdf"}
                            mime_type = mime_map.get(ext.lower(), "application/octet-stream")
                            g_file = upload_to_gemini(tmp_path, mime_type=mime_type)
                            gemini_media_files.append(g_file)
                            os.unlink(tmp_path)
                    
                    if gemini_media_files:
                        st.write(t("📹 Processing media files...", "📹 メディアファイルを処理中..."))
                        wait_for_files_active(gemini_media_files)
                    
                    # Labor Illusion / Entertainment effect
                    import time
                    from core.db import get_personas
                    personas_list = get_personas(current_h_id)
                    active_judges = [p for p in personas_list if p.get('active', True)]
                    
                    for judge in active_judges:
                        st.write(f"{judge.get('avatar', '🧑‍⚖️')} **{judge['name']}** {t('is evaluating the submission...', 'が提出物を精査しています...')}")
                        time.sleep(1)
                    
                    st.write(t("🧠 Generating final scores and feedback...", "🧠 スコアとフィードバックを取りまとめています..."))
                    result_json = analyze_submission(current_h_id, text_content, gemini_media_files, previous_evaluations_json=prev_json_str, is_final=is_final_flag)
                    
                    g_file_names = [f.name for f in gemini_media_files] if gemini_media_files else []
                    save_evaluation(view_team_id, result_json, is_final=is_final_flag, source_text=text_content, gemini_file_ids=g_file_names)
                    
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
        eval_dict_map = {}
        history_options = []
        for i, r in enumerate(eval_rows):
            r_dict = dict(r)
            e_id = r_dict['id']
            eval_dict_map[e_id] = r_dict
            if r_dict['is_final']:
                history_options.append((e_id, f"⭐ Final Submission"))
            else:
                history_options.append((e_id, f"🔄 Consultation {i+1}"))
                
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
        
        # Identify previous evaluation for delta
        current_idx = next((i for i, r in enumerate(eval_rows) if r['id'] == selected_eval['id']), 0)
        prev_scores = None
        if current_idx > 0:
            prev_scores = json.loads(eval_rows[current_idx - 1]['scores_json'])
            
        # Top: Score Breakdown
        criteria = get_criteria(current_h_id)
        total_weight = sum(c['weight'] for c in criteria) if criteria else 1
        
        st.markdown(f"#### 📊 {t('Score Breakdown (Raw Score × Weight = Contribution)', 'スコア内訳 (素点 × ウェイト = 貢献スコア)')}")
        score_cols = st.columns(3)
        
        chart_data = []
        
        for i, crit in enumerate(criteria):
            col = score_cols[i % 3]
            s = scores.get(crit['name'], 0)
            weight_pct = crit['weight']
            contribution = s * (weight_pct / total_weight)
            
            delta_str = None
            if prev_scores is not None:
                prev_s = prev_scores.get(crit['name'], 0)
                diff = s - prev_s
                if diff != 0:
                    delta_str = f"{diff:+.1f} pts"
                else:
                    delta_str = "±0"
            
            col.metric(crit['name'], f"{s} / 5.0", delta_str, delta_color="normal")
            
            chart_data.append({
                "Criteria": crit['name'],
                "Score": s
            })
            
        st.markdown("---")
        
        import altair as alt
        
        # Visualize Score History (Line Chart) if multiple evaluations exist
        if len(eval_rows) > 1:
            st.markdown(f"#### 📈 {t('Score History (Evolution)', 'スコア推移（進化の軌跡）')}")
            history_data = []
            for idx, r in enumerate(eval_rows):
                r_scores = json.loads(r['scores_json'])
                step_name = f"Consult {idx+1}" if not r['is_final'] else "Final"
                
                # Total Score
                total_s = sum(r_scores.get(c['name'], 0) * (c['weight'] / total_weight) for c in criteria)
                history_data.append({"Step": step_name, "Criteria": "⭐ Total Score", "Score": total_s, "Order": idx})
                
                for c in criteria:
                    history_data.append({"Step": step_name, "Criteria": c['name'], "Score": r_scores.get(c['name'], 0), "Order": idx})
                    
            df_hist = pd.DataFrame(history_data)
            line_chart = alt.Chart(df_hist).mark_line(point=True).encode(
                x=alt.X('Step:N', sort=alt.EncodingSortField(field='Order', order='ascending'), title='Evaluation Phase', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Score:Q', scale=alt.Scale(domain=[0, 5])),
                color=alt.Color('Criteria:N', legend=alt.Legend(title="Metrics")),
                tooltip=['Step', 'Criteria', 'Score']
            ).properties(height=300)
            st.altair_chart(line_chart, use_container_width=True)
            st.markdown("---")

        # Visualize current strengths with Altair Bar Chart
        st.markdown(f"#### 📊 {t('Current Radar', '現在の評価バランス')}")
        df_chart = pd.DataFrame(chart_data)
        chart = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X('Score:Q', scale=alt.Scale(domain=[0, 5])),
            y=alt.Y('Criteria:N', sort=None),
            color=alt.Color('Score:Q', scale=alt.Scale(scheme='tealblues'), legend=None),
            tooltip=['Criteria', 'Score']
        ).properties(height=250)
        st.altair_chart(chart, use_container_width=True)
        
        st.markdown("---")
            
        # Tabs for Bilingual
        tab_en, tab_ja = st.tabs(["🇺🇸 English", "🇯🇵 日本語"])
        
        from core.db import get_personas
        personas = get_personas(current_h_id)
        avatar_map = {p['name']: p.get('avatar', '🧑‍⚖️') for p in personas}
        
        with tab_en:
            st.markdown("#### 🔥 Top Priorities (Next Steps)")
            action_items_en = fb.get('action_items_en', [])
            if action_items_en:
                for item in action_items_en:
                    st.info(f"👉 {item}")
            else:
                st.write("No specific action items provided.")
                
            st.markdown("#### 🧠 AI Product Understanding")
            st.write(fb.get('product_understanding_en', fb.get('summary_en', '')))
            st.markdown("#### 🧑‍⚖️ Judges Feedback")
            judges = fb.get('judges_feedback', [])
            for j in judges:
                j_name = j.get('judge_name', 'Judge')
                j_icon = avatar_map.get(j_name, '🧑‍⚖️')
                with st.expander(f"{j_name} - {j.get('judge_role', 'Expert')}", expanded=True):
                    avatar_html = get_avatar_html(j_name, j_icon, size=40)
                    st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 10px;">{avatar_html}<div><strong style="font-size: 1.1em;">{j_name}</strong><br><span style="font-size: 0.8em; color: gray;">{j.get("judge_persona", "")}</span></div></div>', unsafe_allow_html=True)
                    
                    # Display individual judge scores
                    j_scores = j.get('judge_scores', [])
                    if j_scores:
                        score_html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; padding: 10px; background-color: rgba(255,255,255,0.05); border-radius: 5px;">'
                        for s_item in j_scores:
                            c_name = s_item.get('criteria_name', '')
                            s_val = s_item.get('score', 0)
                            color = "#4CAF50" if s_val >= 4 else "#FF9800" if s_val >= 3 else "#F44336"
                            score_html += f'<div style="flex: 1; min-width: 120px;"><div style="font-size: 0.75em; color: gray;">{c_name}</div><div style="font-weight: bold; color: {color};">{s_val} / 5.0</div></div>'
                        score_html += '</div>'
                        st.markdown(score_html, unsafe_allow_html=True)
                        
                    st.write(j.get('feedback_en', ''))
            
        with tab_ja:
            st.markdown("#### 🔥 最優先アクション (Next Steps)")
            action_items_ja = fb.get('action_items_ja', [])
            if action_items_ja:
                for item in action_items_ja:
                    st.info(f"👉 {item}")
            else:
                st.write("具体的なアクションアイテムは提供されていません。")
                
            st.markdown("#### 🧠 プロダクト理解")
            st.write(fb.get('product_understanding_ja', fb.get('summary_ja', '')))
            st.markdown("#### 🧑‍⚖️ 審査員フィードバック")
            judges = fb.get('judges_feedback', [])
            for j in judges:
                j_name = j.get('judge_name', 'Judge')
                j_icon = avatar_map.get(j_name, '🧑‍⚖️')
                with st.expander(f"{j_name} - {j.get('judge_role', 'Expert')}", expanded=True):
                    avatar_html = get_avatar_html(j_name, j_icon, size=40)
                    st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 10px;">{avatar_html}<div><strong style="font-size: 1.1em;">{j_name}</strong><br><span style="font-size: 0.8em; color: gray;">{j.get("judge_persona", "")}</span></div></div>', unsafe_allow_html=True)
                    
                    # Display individual judge scores
                    j_scores = j.get('judge_scores', [])
                    if j_scores:
                        score_html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; padding: 10px; background-color: rgba(255,255,255,0.05); border-radius: 5px;">'
                        for s_item in j_scores:
                            c_name = s_item.get('criteria_name', '')
                            s_val = s_item.get('score', 0)
                            color = "#4CAF50" if s_val >= 4 else "#FF9800" if s_val >= 3 else "#F44336"
                            score_html += f'<div style="flex: 1; min-width: 120px;"><div style="font-size: 0.75em; color: gray;">{c_name}</div><div style="font-weight: bold; color: {color};">{s_val} / 5.0</div></div>'
                        score_html += '</div>'
                        st.markdown(score_html, unsafe_allow_html=True)
                        
                    st.write(j.get('feedback_ja', ''))

        st.markdown("---")
        st.subheader(t("🙋 Objection! / Q&A", "🙋 異議あり！ / 審査員への質問"))
        
        qa_data_str = selected_eval.get('qa_json')
        
        if qa_data_str:
            # Show QA history
            qa_data = json.loads(qa_data_str)
            st.info(t("You have already used your one-time objection for this evaluation.", "この評価に対する1回限りの「反論・質問」権は使用済みです。"))
            
            with st.container(border=True):
                st.markdown(t("**Your Question / Objection:**", "**あなたからの質問・反論:**"))
                st.write(qa_data.get('user_objection', ''))
                
            st.markdown("#### ⚖️ Panel Response")
            tab_qa_en, tab_qa_ja = st.tabs(["🇺🇸 English", "🇯🇵 日本語"])
            
            with tab_qa_en:
                st.info(qa_data.get('qa_summary_en', ''))
                for j in qa_data.get('judges_responses', []):
                    j_name = j.get('judge_name', 'Judge')
                    j_icon = avatar_map.get(j_name, '🧑‍⚖️')
                    st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 10px;">{get_avatar_html(j_name, j_icon, size=30)}<strong style="font-size: 1.1em;">{j_name}</strong></div>', unsafe_allow_html=True)
                    st.write(j.get('response_en', ''))
                    st.divider()
                    
            with tab_qa_ja:
                st.info(qa_data.get('qa_summary_ja', ''))
                for j in qa_data.get('judges_responses', []):
                    j_name = j.get('judge_name', 'Judge')
                    j_icon = avatar_map.get(j_name, '🧑‍⚖️')
                    st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 10px;">{get_avatar_html(j_name, j_icon, size=30)}<strong style="font-size: 1.1em;">{j_name}</strong></div>', unsafe_allow_html=True)
                    st.write(j.get('response_ja', ''))
                    st.divider()
                    
        else:
            if role == 'team':
                st.markdown(t(
                    "You can ask ONE question or make ONE objection per evaluation. The AI Panel will read your comment alongside their previous feedback and respond.", 
                    "1回の評価につき、1回だけ審査員パネルに対して質問や反論を投げることができます。"
                ))
                with st.form("objection_form"):
                    obj_text = st.text_area(t("Your message to the judges:", "審査員へのメッセージ:"), height=150)
                    submit_obj = st.form_submit_button(t("Objection! ✊", "異議あり！ ✊"), type="primary")
                    
                    if submit_obj:
                        if not obj_text.strip():
                            st.warning(t("Please enter your message.", "メッセージを入力してください。"))
                        else:
                            from core.gemini import object_to_judges
                            from core.db import save_objection_qa
                            
                            with st.status(t("⚖️ Judges are discussing your point...", "⚖️ 審査員があなたの意見を議論中..."), expanded=True) as status:
                                try:
                                    # Fetch original content to pass as context (not extracting media again for speed, just text)
                                    # Actually, since we don't have the media cached locally, we only pass the previous JSON.
                                    # This is usually enough for the AI to reason about the feedback it gave.
                                    prev_eval_json_str = selected_eval['strengths_risks_json']
                                    
                                    qa_result = object_to_judges(current_h_id, "", None, prev_eval_json_str, obj_text)
                                    
                                    # Append the user's text to the result so we can display it later
                                    qa_result['user_objection'] = obj_text
                                    
                                    save_objection_qa(selected_eval['id'], qa_result)
                                    
                                    status.update(label=t("✅ Judges have reached a conclusion!", "✅ 審査員からの回答が届きました！"), state="complete", expanded=False)
                                    st.rerun()
                                except Exception as e:
                                    status.update(label=t("❌ Error", "❌ エラー"), state="error")
                                    st.error(f"Failed: {str(e)}")
            else:
                st.info(t("No objections made by the team yet.", "チームからの質問・反論はまだありません。"))
