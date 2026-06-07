import streamlit as st
import pandas as pd
import json
import uuid
from core.db import (
    get_criteria, set_criteria, SessionLocal, User, Hackathon, Evaluation,
    get_setting, set_setting, get_personas, set_personas,
    save_admin_chat, get_admin_chats, update_team_passcode
)
from core.security import hash_passcode
from core.ui_utils import encode_image_to_base64
from core.i18n import t

st.title(t("👑 Admin Command Center", "👑 管理者コマンドセンター"))

current_h_id = st.session_state.get('active_hackathon_id')

if not current_h_id:
    st.error(t("No active hackathon selected. Please ensure you are logged in correctly as a Tenant Admin.", "アクティブなハッカソンがありません。管理者の設定を確認してください。"))
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    t("📊 Live Scoreboard", "📊 スコアボード"), 
    t("🏢 Team Management", "🏢 チーム管理"),
    t("⚖️ Evaluation Criteria", "⚖️ 評価軸"), 
    t("🧑‍🏫 Judges (Personas)", "🧑‍🏫 審査員ペルソナ"),
    t("💬 Submissions & AI Chat", "💬 提出物とAIチャット")
])

# --- TAB 1: Live Scoreboard ---
with tab1:
    st.markdown(f"### 📊 {t('Live Scoreboard', 'リアルタイムスコアボード')}")
    
    db = SessionLocal()
    try:
        hackathon = db.query(Hackathon).filter(Hackathon.id == current_h_id).first()
        h_name = hackathon.name if hackathon else "Unknown"
        st.info(f"**{t('Viewing Hackathon:', '表示中のハッカソン:')}** {h_name}")
        
        users = db.query(User).filter(User.hackathon_id == current_h_id, User.role == 'team').all()
        team_ids = [u.team_id for u in users]
        
        evaluations = db.query(Evaluation).filter(Evaluation.team_id.in_(team_ids)).all() if team_ids else []
        
        rows = []
        for tid in team_ids:
            team_evals = [e for e in evaluations if e.team_id == tid]
            if team_evals:
                latest = max(team_evals, key=lambda x: x.id)
                rows.append({
                    'team_id': latest.team_id,
                    'scores_json': latest.scores_json,
                    'impact_score': latest.impact_score,
                    'consults': len(team_evals)
                })
    finally:
        db.close()

    criteria = get_criteria(current_h_id)
    total_weight = sum(c['weight'] for c in criteria) if criteria else 1

    if not rows:
        st.warning(t("No submissions yet for this hackathon.", "このハッカソンにはまだ提出物がありません。"))
    else:
        data = []
        for r in rows:
            team_id = r['team_id']
            scores = json.loads(r['scores_json'])
            
            total_score = sum(
                scores.get(crit["name"], 0) * 20.0 * (crit["weight"] / total_weight) for crit in criteria
            )
            
            data.append({
                t("Team", "チーム"): team_id,
                t("Total Score", "総合スコア"): round(total_score, 1),
                t("Impact (Tie-breaker)", "インパクト (Tie-breaker)"): r['impact_score'],
                t("Consults", "相談回数"): r['consults']
            })

        df = pd.DataFrame(data).sort_values(
            by=[t("Total Score", "総合スコア"), t("Impact (Tie-breaker)", "インパクト (Tie-breaker)")], 
            ascending=[False, False]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- TAB 2: Team Management ---
with tab2:
    db = SessionLocal()
    try:
        results = db.query(User.team_id, User.product_name, User.team_name).filter(User.hackathon_id == current_h_id, User.role == 'team').order_by(User.id.desc()).all()
        teams = [{'team_id': r.team_id, 'product_name': r.product_name, 'team_name': r.team_name} for r in results]
    finally:
        db.close()

    col_csv, col_manual = st.columns(2)
    
    with col_csv:
        st.markdown(f"### {t('Import Teams (CSV)', 'チーム一括登録 (CSV)')}")
        st.caption(t("CSV Format: team_id, passcode", "CSV形式: 1列目にteam_id、2列目にpasscode"))
        
        uploaded_csv = st.file_uploader(t("Upload CSV", "CSVをアップロード"), type=['csv'])
        if uploaded_csv is not None:
            if st.button(t("Import Teams", "チームをインポート")):
                try:
                    df_csv = pd.read_csv(uploaded_csv, header=None)
                    db = SessionLocal()
                    count = 0
                    try:
                        for _, row in df_csv.iterrows():
                            tid = str(row[0]).strip()
                            pwd = str(row[1]).strip()
                            if tid and pwd:
                                existing = db.query(User).filter_by(team_id=tid).first()
                                if not existing:
                                    db.add(User(hackathon_id=current_h_id, team_id=tid, passcode=hash_passcode(pwd), role='team'))
                                    count += 1
                        db.commit()
                        st.success(f"Successfully imported {count} teams!")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Failed to read CSV: {str(e)}")
                    finally:
                        db.close()
                except Exception as e:
                    st.error(f"Failed to read CSV: {str(e)}")

    with col_manual:
        st.markdown(f"### {t('Add Single Team', 'チームの個別追加')}")
        st.caption(t("Manually register a team.", "1チームずつ手動で登録します。"))
        
        with st.form("manual_add_team_form"):
            new_tid = st.text_input(t("Team ID", "チームID"))
            new_pwd = st.text_input(t("Passcode", "パスコード"))
            if st.form_submit_button(t("Add Team", "チームを追加"), type="primary"):
                if new_tid and new_pwd:
                    db = SessionLocal()
                    try:
                        existing = db.query(User).filter_by(team_id=new_tid.strip()).first()
                        if existing:
                            st.error(t("Failed to add team. The Team ID might already exist.", "追加に失敗しました。チームIDが既に存在する可能性があります。"))
                        else:
                            db.add(User(hackathon_id=current_h_id, team_id=new_tid.strip(), passcode=hash_passcode(new_pwd.strip()), role='team'))
                            db.commit()
                            st.success(f"Team '{new_tid}' added successfully!")
                            st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(t("Failed to add team.", "追加に失敗しました。"))
                    finally:
                        db.close()
                else:
                    st.warning(t("Both Team ID and Passcode are required.", "チームIDとパスコードの両方を入力してください。"))

        st.markdown("---")
        st.markdown(f"### {t('Change Team Passcode', 'チームのパスコード変更')}")
        st.caption(t("Update the passcode for an existing team.", "登録済みのチームのパスコードを変更します。"))
        
        with st.form("change_team_passcode_form"):
            team_options = [t_row['team_id'] for t_row in teams]
            if team_options:
                target_tid = st.selectbox(t("Select Team ID", "変更対象のチームID"), team_options)
            else:
                target_tid = st.text_input(t("Team ID", "変更対象のチームID"), disabled=True, placeholder=t("No teams registered", "登録済みのチームがありません"))
            
            change_pwd = st.text_input(t("New Passcode", "新しいパスコード"), type="password")
            
            if st.form_submit_button(t("Update Passcode", "パスコードを変更"), type="primary"):
                if not team_options:
                    st.warning(t("No teams registered to change passcode.", "変更対象のチームが登録されていません。"))
                elif not change_pwd:
                    st.warning(t("Please enter a new passcode.", "新しいパスコードを入力してください。"))
                else:
                    if update_team_passcode(current_h_id, target_tid, change_pwd.strip()):
                        st.success(t(f"Successfully updated passcode for team '{target_tid}'!", f"チーム '{target_tid}' のパスコードを更新しました！"))
                        st.rerun()
                    else:
                        st.error(t("Failed to update passcode.", "パスコードの更新に失敗しました。"))

    st.divider()
    st.markdown(f"### {t('Registered Teams', '登録済みチーム一覧')}")
    
    if not teams:
        st.info(t("No teams registered yet.", "まだチームは登録されていません。"))
    else:
        team_data = []
        for t_row in teams:
            team_data.append({
                t("Team ID", "チームID"): t_row['team_id'],
                t("Product Name", "プロダクト名"): t_row['product_name'] or "",
                t("Team Name", "チーム名"): t_row['team_name'] or ""
            })
        st.dataframe(pd.DataFrame(team_data), use_container_width=True, hide_index=True)

# --- TAB 3: Evaluation Criteria ---
with tab3:
    st.markdown(f"### {t('Evaluation Criteria', '評価軸の設定')}")
    st.info(t("Select a criteria from the list to edit its details, or add a new one.", "リストから評価軸を選択して詳細を編集するか、新しく追加してください。"))
    
    criteria = get_criteria(current_h_id)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Current Criteria**")
        for i, c in enumerate(criteria):
            st.write(f"- {c['name']} ({c['weight']}%)")
        
        st.markdown("---")
        action_c = st.radio("Action", ["Edit Existing", "Add New"], horizontal=True, label_visibility="collapsed", key="admin_criteria_action")
        
        if action_c == "Edit Existing" and criteria:
            crit_names = [c['name'] for c in criteria]
            selected_c_name = st.selectbox("Select Criteria to Edit", crit_names, key="admin_criteria_select")
            selected_c = next((c for c in criteria if c['name'] == selected_c_name), None)
            idx = criteria.index(selected_c)
        else:
            selected_c = {"name": "", "weight": 10, "description": ""}
            idx = -1
    
    with col2:
        with st.form("criteria_form"):
            c_name = st.text_input("Criteria Name", value=selected_c['name'])
            c_weight = st.number_input("Weight (%)", min_value=1, max_value=100, value=selected_c.get('weight', 10))
            c_desc = st.text_area("Detailed Description (Prompt for AI)", value=selected_c.get('description', ''), height=200, help="Write multiple lines here to deeply define how AI should score this.")
            
            submitted_c = st.form_submit_button(t("Save Criteria", "この評価軸を保存"), type="primary")
            if submitted_c:
                if c_name:
                    new_c = {"name": c_name, "weight": c_weight, "description": c_desc}
                    if idx >= 0:
                        criteria[idx] = new_c
                    else:
                        criteria.append(new_c)
                    set_criteria(current_h_id, criteria)
                    st.success("Saved!")
                    st.rerun()

        if idx >= 0:
            if st.button("Delete this Criteria", type="secondary", key="admin_criteria_delete"):
                criteria.pop(idx)
                set_criteria(current_h_id, criteria)
                st.success("Deleted!")
                st.rerun()

# --- TAB 4: Judges (Personas) ---
with tab4:
    st.markdown(f"### {t('Judges (Personas)', '審査員ペルソナの設定')}")
    st.info(t("Define rich personas for the AI judges.", "AI審査員の詳細なペルソナ定義を入力します。"))
    
    personas = get_personas(current_h_id)
    active_count = sum(1 for p in personas if p.get('active', False))
    st.write(f"**Active Judges:** {active_count} / 5")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Current Personas**")
        for i, p in enumerate(personas):
            role_str = f"({p.get('role', '')})" if p.get('role') else ""
            label = f"{p['name']} {role_str}"
            is_active = st.checkbox(label, value=p.get('active', False), key=f"admin_persona_active_toggle_{i}")
            
            if is_active != p.get('active', False):
                if is_active and sum(1 for cp in personas if cp.get('active', False)) >= 5:
                    st.error(t("Cannot exceed 5 active judges.", "アクティブな審査員は5名までです。"))
                else:
                    personas[i]['active'] = is_active
                    set_personas(current_h_id, personas)
                    st.rerun()
            
        st.markdown("---")
        action_p = st.radio("Persona Action", ["Edit Existing", "Add New"], horizontal=True, label_visibility="collapsed", key="admin_action_p")
        
        if action_p == "Edit Existing" and personas:
            per_names = [p['name'] for p in personas]
            selected_p_name = st.selectbox("Select Persona to Edit", per_names, key="admin_persona_select")
            selected_p = next((p for p in personas if p['name'] == selected_p_name), None)
            idx_p = personas.index(selected_p)
        else:
            selected_p = {"name": "", "role": "", "avatar": "🧑‍⚖️", "prompt": "", "active": False}
            idx_p = -1
            
    with col2:
        with st.form("persona_form"):
            p_name = st.text_input("Judge Name (e.g. Yoh)", value=selected_p['name'])
            p_role = st.text_input("Judge Role/Title (e.g. Chief Architect)", value=selected_p.get('role', ''))
            p_avatar = st.text_input("Avatar (Emoji)", value=selected_p.get('avatar', '🧑‍⚖️'))
            
            # Custom avatar image preview and uploader
            avatar_image_val = selected_p.get('avatar_image')
            remove_avatar = False
            if avatar_image_val:
                st.markdown(t("Current Custom Avatar:", "現在のカスタムアバター:"))
                st.markdown(f'<img src="{avatar_image_val}" style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; box-shadow: 0 2px 4px rgba(0,0,0,0.2); margin-bottom: 10px;">', unsafe_allow_html=True)
                remove_avatar = st.checkbox(t("Remove custom avatar image (fallback to emoji)", "カスタムアバター画像を削除する (絵文字表示に戻す)"))
            
            uploaded_avatar_file = st.file_uploader(
                t("Upload New Avatar Image (PNG/JPG, Max 500KB)", "新しいアバター画像をアップロード (PNG/JPG, 最大500KB)"), 
                type=["png", "jpg", "jpeg"]
            )
            
            p_active = st.checkbox("Active (Participates in evaluation)", value=selected_p.get('active', False))
            p_prompt = st.text_area("Detailed Persona Prompt", value=selected_p.get('prompt', ''), height=300, help="Write dozens of lines detailing their background, tone of voice, and what they care about.")
            
            submitted_p = st.form_submit_button(t("Save Persona", "このペルソナを保存"), type="primary")
            if submitted_p:
                if p_name:
                    if p_active and not selected_p.get('active') and active_count >= 5:
                        st.error("Cannot exceed 5 active judges.")
                    else:
                        p_avatar_image = selected_p.get('avatar_image')
                        if remove_avatar:
                            p_avatar_image = None
                        elif uploaded_avatar_file is not None:
                            file_bytes = uploaded_avatar_file.getvalue()
                            if len(file_bytes) > 500 * 1024:
                                st.error(t("Image size exceeds 500KB limit. Please optimize the image before uploading.", "画像サイズが500KBを超えています。アップロード前に画像を最適化してください。"))
                                st.stop()
                            else:
                                mime = "image/png"
                                if uploaded_avatar_file.name.lower().endswith((".jpg", ".jpeg")):
                                    mime = "image/jpeg"
                                p_avatar_image = encode_image_to_base64(file_bytes, mime)
                                
                        new_p = {
                            "id": selected_p.get('id', str(uuid.uuid4())), 
                            "name": p_name, 
                            "role": p_role, 
                            "avatar": p_avatar, 
                            "avatar_image": p_avatar_image,
                            "prompt": p_prompt, 
                            "active": p_active
                        }
                        if idx_p >= 0:
                            personas[idx_p] = new_p
                        else:
                            if len(personas) >= 10:
                                st.error("Cannot exceed 10 registered personas.")
                            else:
                                personas.append(new_p)
                        set_personas(current_h_id, personas)
                        st.success("Saved!")
                        st.rerun()
                        
        if idx_p >= 0:
            if st.button("Delete this Persona", type="secondary", key="admin_persona_delete"):
                personas.pop(idx_p)
                set_personas(current_h_id, personas)
                st.success("Deleted!")
                st.rerun()

# --- TAB 5: Submissions & AI Chat ---
with tab5:
    st.markdown(f"### {t('💬 Submissions & AI Chat', '💬 提出物とAIチャット')}")
    st.caption(t("Ask the AI Expert Panel specific questions about a team's submission based on their actual source code.", "チームの実際のソースコードに基づいて、AI審査員に具体的な質問をすることができます。"))
    
    evals = None
    db = SessionLocal()
    try:
        users = db.query(User.team_id).filter(User.hackathon_id == current_h_id, User.role == 'team').order_by(User.team_id).all()
        chat_teams = [u.team_id for u in users]
        
        if not chat_teams:
            st.info(t("No teams available.", "チームがいません。"))
        else:
            selected_team = st.selectbox(t("Select a Team", "チームを選択"), chat_teams, key="chat_team_select")
            
            eval_results = db.query(Evaluation).filter(Evaluation.team_id == selected_team).order_by(Evaluation.id.desc()).all()
            evals = []
            for e in eval_results:
                evals.append({
                    'id': e.id,
                    'is_final': e.is_final,
                    'evaluated_at': e.evaluated_at,
                    'source_text': e.source_text,
                    'gemini_file_ids': e.gemini_file_ids,
                    'strengths_risks_json': e.strengths_risks_json
                })
    finally:
        db.close()
        
    if evals is not None:
        if not evals:
            st.info(t("No submissions from this team yet.", "このチームからの提出物はまだありません。"))
        else:
            eval_dict_map = {}
            eval_options = []
            for r in evals:
                r_dict = dict(r)
                e_id = r_dict['id']
                eval_dict_map[e_id] = r_dict
                label = f"{'⭐ Final' if r_dict['is_final'] else '🔄 Consultation'} (ID: {e_id}) - {r_dict['evaluated_at']}"
                eval_options.append((e_id, label))
                
            selected_eval_id = st.selectbox(
                t("Select Submission", "提出履歴を選択"), 
                [opt[0] for opt in eval_options], 
                format_func=lambda x: next(opt[1] for opt in eval_options if opt[0] == x),
                key="admin_center_submission_select"
            )
            selected_eval = eval_dict_map[selected_eval_id]
            
            source_text = selected_eval.get('source_text')
            gemini_file_ids = selected_eval.get('gemini_file_ids')
            prev_json_str = selected_eval.get('strengths_risks_json')
            
            if not source_text and not gemini_file_ids:
                st.warning(t(
                    "This is a legacy submission. The raw source code and files were not saved. AI Chat is disabled for this submission to prevent hallucinations.", 
                    "これは過去の提出物です。元のソースコードやファイルが保存されていないため、ハルシネーション（AIの嘘）を防ぐ目的でAIチャット機能は無効化されています。"
                ))
            else:
                st.success(t("✅ Source code and files are available. You can ask the AI panel detailed questions.", "✅ ソースコードとファイルが利用可能です。この提出物についてAIに詳細な質問ができます。"))
                
                # Retrieve existing chat history
                chats = get_admin_chats(selected_eval_id)
                
                if chats:
                    st.markdown(f"#### 💬 {t('Chat History', 'チャット履歴')}")
                    tab_chat_en, tab_chat_ja = st.tabs(["🇺🇸 English", "🇯🇵 日本語"])
                    
                    with tab_chat_en:
                        for chat in chats:
                            with st.container(border=True):
                                st.markdown(f"**Question:** {chat['question_en']}")
                                st.markdown(f"**AI Response:**")
                                st.info(chat['answer_en'])
                                
                    with tab_chat_ja:
                        for chat in chats:
                            with st.container(border=True):
                                st.markdown(f"**質問:** {chat['question_ja']}")
                                st.markdown(f"**AIからの回答:**")
                                st.info(chat['answer_ja'])
                
                with st.form("admin_chat_form"):
                    admin_q = st.text_area(t("Your Question to the AI Panel:", "AIへの質問（例：バックエンドで何のライブラリを使っている？ セキュリティの懸念はある？等）:"), height=100)
                    submit_q = st.form_submit_button(t("Ask AI", "AIに質問する"), type="primary")
                    
                    if submit_q:
                        if not admin_q.strip():
                            st.error(t("Please enter a question.", "質問を入力してください。"))
                        else:
                            with st.status(t("🤖 AI is reading the source code and files...", "🤖 AIがソースコードとファイルを参照中..."), expanded=True) as status:
                                try:
                                    from core.gemini import admin_chat_about_submission
                                    res_json = admin_chat_about_submission(current_h_id, source_text, gemini_file_ids, prev_json_str, admin_q)
                                    
                                    # Save to database
                                    save_admin_chat(
                                        evaluation_id=selected_eval_id,
                                        question_en=res_json.get('question_en', admin_q),
                                        question_ja=res_json.get('question_ja', admin_q),
                                        answer_en=res_json.get('answer_en', ''),
                                        answer_ja=res_json.get('answer_ja', '')
                                    )
                                    
                                    status.update(label=t("✅ AI Responded", "✅ AIの回答が完了しました"), state="complete")
                                    st.rerun()
                                except Exception as e:
                                    status.update(label="Error", state="error")
                                    st.error(str(e))
