import json
import uuid

import pandas as pd
import streamlit as st

from core.db import (
    Evaluation,
    Hackathon,
    SessionLocal,
    User,
    get_admin_chats,
    get_ai_response_languages,
    get_criteria,
    get_max_consultations,
    get_max_qa_turns,
    get_personas,
    get_re_evaluation_context_mode,
    initialize_hackathon_template,
    normalize_lang_to_key,
    save_admin_chat,
    set_ai_response_languages,
    set_criteria,
    set_max_consultations,
    set_max_qa_turns,
    set_personas,
    set_re_evaluation_context_mode,
    update_team_passcode,
    update_user_role,
)
from core.i18n import t
from core.security import hash_passcode, is_safe_url
from core.ui_utils import encode_image_to_base64

st.title(t("👑 Admin Command Center", "👑 管理者コマンドセンター"))

current_h_id = st.session_state.get('active_hackathon_id')
is_demo = (current_h_id == 9999)

if not current_h_id:
    st.error(t("No active project selected. Please ensure you are logged in correctly as a Tenant Admin.", "アクティブなプロジェクトがありません。管理者の設定を確認してください。"))
    st.stop()

# Get hackathon details to check template_id
db = SessionLocal()
try:
    hackathon = db.query(Hackathon).filter(Hackathon.id == current_h_id).first()
finally:
    db.close()

if not hackathon:
    st.error(t("Project not found.", "プロジェクトが見つかりません。"))
    st.stop()

# Force template selection if not initialized yet (except in demo mode 9999)
if not hackathon.template_id and not is_demo:
    st.subheader(t("🚀 Project Setup: Select Evaluation Template", "🚀 プロジェクト初期セットアップ：評価テンプレートの選択"))
    st.markdown(t(
        "Please select a template to initialize this project. The template will automatically configure default evaluation criteria and AI judge personas.",
        "このプロジェクトを初期化するためのテンプレートを選択してください。テンプレートに応じて、デフォルトの評価軸や審査員ペルソナが自動設定されます。"
    ))

    with st.form("admin_setup_form"):
        # Template Selection
        template_options = {
            "hackathon": t("Hackathon Evaluation", "ハッカソン審査"),
            "startup_pitch": t("Startup Pitch Review", "スタートアップピッチ審査"),
            "hiring": t("Hiring & Technical Interview", "採用・技術面接評価"),
            "architecture": t("Software Architecture Review", "ソフトウェアアーキテクチャレビュー"),
            "custom": t("Custom (Import from URL)", "カスタム (URLからインポート)")
        }
        selected_tpl_key = st.selectbox(
            t("Evaluation Template", "評価テンプレート"),
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x]
        )

        custom_url = st.text_input(
            t("Custom Template URL (JSON)", "カスタムテンプレートURL (JSON)"),
            placeholder="https://raw.githubusercontent.com/.../template.json",
            help=t("Required only if Custom template is selected.", "カスタムテンプレート選択時のみ必須です。")
        )

        if st.form_submit_button(t("Initialize Project", "プロジェクトを初期化する"), type="primary"):
            if selected_tpl_key == "custom" and not custom_url.strip():
                st.error(t("Please enter a custom template URL.", "カスタムテンプレートのURLを入力してください。"))
            else:
                try:
                    custom_template_data = None
                    if selected_tpl_key == "custom" and custom_url.strip():
                        url_to_fetch = custom_url.strip()

                        # SSRF validation
                        from urllib.parse import urlparse
                        parsed = urlparse(url_to_fetch)
                        if parsed.scheme not in ('http', 'https'):
                            raise ValueError("Invalid URL scheme. Only HTTP/HTTPS is allowed.")

                        allowed_domains = {
                            'github.com',
                            'raw.githubusercontent.com',
                            'gist.githubusercontent.com',
                            'githubusercontent.com'
                        }
                        if parsed.hostname not in allowed_domains:
                            raise ValueError("Access to this domain is not allowed for custom templates.")

                        if not is_safe_url(url_to_fetch):
                            raise ValueError("Invalid or unsafe URL. Only public HTTP/HTTPS URLs are allowed.")

                        # Rebuild safe URL
                        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            safe_url += f"?{parsed.query}"

                        import requests
                        res = requests.get(safe_url)
                        if res.status_code != 200:
                            raise ValueError(f"Failed to fetch template from URL. HTTP {res.status_code}")
                        custom_template_data = res.json()

                    initialize_hackathon_template(current_h_id, selected_tpl_key, custom_template_data)
                    st.success(t("Project successfully initialized!", "プロジェクトの初期化が完了しました！"))
                    st.rerun()
                except Exception as e:
                    st.error(t(f"Failed to initialize project: {str(e)}", f"プロジェクトの初期化に失敗しました: {str(e)}"))
    st.stop()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    t("📊 Live Scoreboard", "📊 スコアボード"),
    t("🏢 Team Management", "🏢 チーム管理"),
    t("⚖️ Evaluation Criteria", "⚖️ 評価軸"),
    t("🧑‍🏫 Judges (Personas)", "🧑‍🏫 審査員ペルソナ"),
    t("💬 Submissions & AI Chat", "💬 提出物とAIチャット"),
    t("🤖 AI Response Settings", "🤖 AIレスポンス設定"),
    t("⚙️ Project Settings", "⚙️ プロジェクト詳細設定")
])

# --- TAB 1: Live Scoreboard ---
with tab1:
    st.markdown(f"### 📊 {t('Live Scoreboard', 'リアルタイムスコアボード')}")

    db = SessionLocal()
    try:
        hackathon = db.query(Hackathon).filter(Hackathon.id == current_h_id).first()
        h_name = hackathon.name if hackathon else "Unknown"
        st.info(f"**{t('Viewing Project:', '表示中のプロジェクト:')}** {h_name}")

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
        st.warning(t("No submissions yet for this project.", "このプロジェクトにはまだ提出物がありません。"))
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
        results = db.query(User.team_id, User.product_name, User.team_name, User.role).filter(
            User.hackathon_id == current_h_id,
            User.role.in_(['team', 'observer'])
        ).order_by(User.id.desc()).all()
        teams = [{'team_id': r.team_id, 'product_name': r.product_name, 'team_name': r.team_name, 'role': r.role} for r in results]
    finally:
        db.close()

    col_csv, col_manual = st.columns(2)

    with col_csv:
        st.markdown(f"### {t('Import Users (CSV)', 'ユーザー一括登録 (CSV)')}")
        st.caption(t(
            "CSV Format: team_id, passcode, role (optional: team / observer)",
            "CSV形式: 1列目にID、2列目にpasscode、3列目にrole（省略時はteam、その他はobserverを指定可能）"
        ))

        uploaded_csv = st.file_uploader(t("Upload CSV", "CSVをアップロード"), type=['csv'], disabled=is_demo)
        if uploaded_csv is not None:
            if st.button(t("Import Users", "ユーザーをインポート"), disabled=is_demo):
                try:
                    df_csv = pd.read_csv(uploaded_csv, header=None)
                    db = SessionLocal()
                    count = 0
                    try:
                        for _, row in df_csv.iterrows():
                            tid = str(row[0]).strip()
                            pwd = str(row[1]).strip()
                            role_val = 'team'
                            if len(row) > 2:
                                potential_role = str(row[2]).strip().lower()
                                if potential_role in ['team', 'observer']:
                                    role_val = potential_role

                            if tid and pwd:
                                existing = db.query(User).filter_by(team_id=tid).first()
                                if not existing:
                                    db.add(User(hackathon_id=current_h_id, team_id=tid, passcode=hash_passcode(pwd), role=role_val))
                                    count += 1
                        db.commit()
                        st.success(f"Successfully imported {count} users!")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Failed to read CSV: {str(e)}")
                    finally:
                        db.close()
                except Exception as e:
                    st.error(f"Failed to read CSV: {str(e)}")

    with col_manual:
        st.markdown(f"### {t('Add Single User', 'ユーザーの個別追加')}")
        st.caption(t("Manually register a user.", "1ユーザーずつ手動で登録します。"))

        if is_demo:
            st.caption(t("💡 Adding users and changing configurations are disabled in Demo Mode.", "💡 デモモードではユーザーの追加や設定変更は無効化されています。"))
        with st.form("manual_add_team_form"):
            new_tid = st.text_input(t("User ID / Team ID", "ユーザーID / チームID"), disabled=is_demo)
            new_pwd = st.text_input(t("Passcode", "パスコード"), disabled=is_demo)
            new_role = st.selectbox(
                t("Role", "ロール"),
                ["team", "observer"],
                format_func=lambda x: t("Participant (team)", "一般参加者 (team)") if x == "team" else t("Observer (observer)", "オブザーバー (observer)"),
                disabled=is_demo
            )
            if st.form_submit_button(t("Add User", "ユーザーを追加"), type="primary", disabled=is_demo):
                if new_tid and new_pwd:
                    db = SessionLocal()
                    try:
                        existing = db.query(User).filter_by(team_id=new_tid.strip()).first()
                        if existing:
                            st.error(t("Failed to add user. The User ID might already exist.", "追加に失敗しました。ユーザーIDが既に存在する可能性があります。"))
                        else:
                            db.add(User(hackathon_id=current_h_id, team_id=new_tid.strip(), passcode=hash_passcode(new_pwd.strip()), role=new_role))
                            db.commit()
                            st.success(f"User '{new_tid}' added successfully!")
                            st.rerun()
                    except Exception:
                        db.rollback()
                        st.error(t("Failed to add user.", "追加に失敗しました。"))
                    finally:
                        db.close()
                else:
                    st.warning(t("Both User ID and Passcode are required.", "ユーザーIDとパスコードの両方を入力してください。"))

        st.markdown("---")
        st.markdown(f"### {t('Change Passcode', 'パスコード変更')}")
        st.caption(t("Update the passcode for an existing user.", "登録済みのユーザーのパスコードを変更します。"))

        with st.form("change_team_passcode_form"):
            team_options = [t_row['team_id'] for t_row in teams]
            if team_options:
                target_tid = st.selectbox(t("Select User ID", "変更対象のユーザーID"), team_options, disabled=is_demo)
            else:
                target_tid = st.text_input(t("User ID", "変更対象のユーザーID"), disabled=True, placeholder=t("No users registered", "登録済みのユーザーがありません"))

            change_pwd = st.text_input(t("New Passcode", "新しいパスコード"), type="password", disabled=is_demo)
            confirm_pwd = st.text_input(t("Confirm New Passcode", "新しいパスコード（確認）"), type="password", disabled=is_demo)

            if st.form_submit_button(t("Update Passcode", "パスコードを変更"), type="primary", disabled=is_demo):
                if not team_options:
                    st.warning(t("No users registered to change passcode.", "変更対象のユーザーが登録されていません。"))
                elif not change_pwd or not confirm_pwd:
                    st.warning(t("All fields required.", "すべて入力してください。"))
                elif change_pwd != confirm_pwd:
                    st.error(t("Passcodes do not match.", "新しいパスコードが一致しません。"))
                else:
                    if update_team_passcode(current_h_id, target_tid, change_pwd.strip()):
                        st.success(t(f"Successfully updated passcode for user '{target_tid}'!", f"ユーザー '{target_tid}' のパスコードを更新しました！"))
                        st.rerun()
                    else:
                        st.error(t("Failed to update passcode.", "パスコードの更新に失敗しました。"))

        st.markdown("---")
        st.markdown(f"### {t('Change User Role', 'ユーザーのロール変更')}")
        st.caption(t("Update the role for an existing user.", "登録済みのユーザーのロールを変更します。"))

        with st.form("change_user_role_form"):
            if team_options:
                target_role_tid = st.selectbox(t("Select User ID", "変更対象のユーザーID"), team_options, disabled=is_demo, key="role_target_tid")
            else:
                target_role_tid = st.text_input(t("User ID", "変更対象のユーザーID"), disabled=True, placeholder=t("No users registered", "登録済みのユーザーがありません"), key="role_target_tid")

            new_user_role = st.selectbox(
                t("New Role", "新しいロール"),
                ["team", "observer"],
                format_func=lambda x: t("Participant (team)", "一般参加者 (team)") if x == "team" else t("Observer (observer)", "オブザーバー (observer)"),
                disabled=is_demo
            )

            if st.form_submit_button(t("Update Role", "ロールを変更"), type="primary", disabled=is_demo):
                if not team_options:
                    st.warning(t("No users registered to change role.", "変更対象のユーザーが登録されていません。"))
                else:
                    if update_user_role(current_h_id, target_role_tid, new_user_role):
                        st.success(t(f"Successfully updated role for user '{target_role_tid}' to '{new_user_role}'!", f"ユーザー '{target_role_tid}' のロールを '{new_user_role}' に更新しました！"))
                        st.rerun()
                    else:
                        st.error(t("Failed to update role.", "ロールの更新に失敗しました。"))

    st.divider()
    st.markdown(f"### {t('Registered Users', '登録済みユーザー一覧')}")

    if not teams:
        st.info(t("No users registered yet.", "まだユーザーは登録されていません。"))
    else:
        team_data = []
        for t_row in teams:
            team_data.append({
                t("User ID / Team ID", "ユーザーID / チームID"): t_row['team_id'],
                t("Product Name", "プロダクト名"): t_row['product_name'] or "",
                t("Team Name", "チーム名"): t_row['team_name'] or "",
                t("Role", "ロール"): t_row['role']
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
        if is_demo:
            st.caption(t("💡 Editing evaluation criteria is disabled in Demo Mode.", "💡 デモモードでは評価基準の編集は無効化されています。"))

        with st.form("criteria_form"):
            c_name = st.text_input("Criteria Name", value=selected_c['name'], disabled=is_demo)
            c_weight = st.number_input("Weight (%)", min_value=1, max_value=100, value=selected_c.get('weight', 10), disabled=is_demo)
            c_desc = st.text_area("Detailed Description (Prompt for AI)", value=selected_c.get('description', ''), height=200, help="Write multiple lines here to deeply define how AI should score this.", disabled=is_demo)

            submitted_c = st.form_submit_button(t("Save Criteria", "この評価軸を保存"), type="primary", disabled=is_demo)
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
            if st.button("Delete this Criteria", type="secondary", key="admin_criteria_delete", disabled=is_demo):
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
            is_active = st.checkbox(label, value=p.get('active', False), key=f"admin_persona_active_toggle_{i}", disabled=is_demo)

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
        if is_demo:
            st.caption(t("💡 Editing personas is disabled in Demo Mode.", "💡 デモモードではペルソナの編集は無効化されています。"))

        with st.form("persona_form"):
            p_name = st.text_input("Judge Name (e.g. Yoh)", value=selected_p['name'], disabled=is_demo)
            p_role = st.text_input("Judge Role/Title (e.g. Chief Architect)", value=selected_p.get('role', ''), disabled=is_demo)
            p_avatar = st.text_input("Avatar (Emoji)", value=selected_p.get('avatar', '🧑‍⚖️'), disabled=is_demo)

            # Custom avatar image preview and uploader
            avatar_image_val = selected_p.get('avatar_image')
            remove_avatar = False
            if avatar_image_val:
                st.markdown(t("Current Custom Avatar:", "現在のカスタムアバター:"))
                st.markdown(f'<img src="{avatar_image_val}" style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; box-shadow: 0 2px 4px rgba(0,0,0,0.2); margin-bottom: 10px;">', unsafe_allow_html=True)
                remove_avatar = st.checkbox(t("Remove custom avatar image (fallback to emoji)", "カスタムアバター画像を削除する (絵文字表示に戻す)"), disabled=is_demo)

            uploaded_avatar_file = st.file_uploader(
                t("Upload New Avatar Image (PNG/JPG, Max 500KB)", "新しいアバター画像をアップロード (PNG/JPG, 最大500KB)"),
                type=["png", "jpg", "jpeg"],
                disabled=is_demo
            )

            p_active = st.checkbox("Active (Participates in evaluation)", value=selected_p.get('active', False), disabled=is_demo)
            p_prompt = st.text_area("Detailed Persona Prompt", value=selected_p.get('prompt', ''), height=300, help="Write dozens of lines detailing their background, tone of voice, and what they care about.", disabled=is_demo)

            submitted_p = st.form_submit_button(t("Save Persona", "このペルソナを保存"), type="primary", disabled=is_demo)
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
            if st.button("Delete this Persona", type="secondary", key="admin_persona_delete", disabled=is_demo):
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
                    chat_tabs = st.tabs(tab_titles)

                    for idx, lang_name in enumerate(languages):
                        lang_key = normalize_lang_to_key(lang_name)
                        # Map language key to fallback for english/japanese
                        compat_map = {
                            "english": "english", "japanese": "japanese", "日本語": "japanese", "英語": "english",
                            "spanish": "spanish", "french": "french", "german": "german", "korean": "korean",
                            "chinese": "chinese", "vietnamese": "vietnamese", "thai": "thai", "indonesian": "indonesian"
                        }
                        mapped_key = compat_map.get(lang_key, lang_key)

                        with chat_tabs[idx]:
                            for chat in chats:
                                qa_data = chat.get('qa_json', {})
                                q_val = qa_data.get(f'question_{mapped_key}')

                                # Fallback logic for legacy values
                                if not q_val:
                                    if mapped_key == "english":
                                        q_val = qa_data.get("question_en", chat.get("question_en"))
                                    elif mapped_key == "japanese":
                                        q_val = qa_data.get("question_ja", chat.get("question_ja"))
                                    else:
                                        q_val = qa_data.get("question_english", qa_data.get("question_en", chat.get("question_en")))

                                a_val = qa_data.get(f'answer_{mapped_key}')
                                if not a_val:
                                    if mapped_key == "english":
                                        a_val = qa_data.get("answer_en", chat.get("answer_en"))
                                    elif mapped_key == "japanese":
                                        a_val = qa_data.get("answer_ja", chat.get("answer_ja"))
                                    else:
                                        a_val = qa_data.get("answer_english", qa_data.get("answer_en", chat.get("answer_en")))

                                with st.container(border=True):
                                    st.markdown(f"**{t('Question:', '質問:')}** {q_val}")
                                    st.markdown(f"**{t('AI Response:', 'AIからの回答:')}**")
                                    st.info(a_val)

                if is_demo:
                    st.info(t(
                        "🔒 Demo Mode: Sending new questions is disabled. Please view the pre-recorded QA history above.",
                        "🔒 デモモード: AIへの新規質問送信は無効化されています。上記のチャット履歴をご覧ください。"
                    ))
                with st.form("admin_chat_form"):
                    admin_q = st.text_area(t("Your Question to the AI Panel:", "AIへの質問（例：バックエンドで何のライブラリを使っている？ セキュリティの懸念はある？等）:"), height=100, disabled=is_demo)
                    submit_q = st.form_submit_button(t("Ask AI", "AIに質問する"), type="primary", disabled=is_demo)

                    if submit_q:
                        if not admin_q.strip():
                            st.error(t("Please enter a question.", "質問を入力してください。"))
                        else:
                            with st.status(t("🤖 AI is reading the source code and files...", "🤖 AIがソースコードとファイルを参照中..."), expanded=True) as status:
                                try:
                                    from core.gemini import admin_chat_about_submission
                                    res_json = admin_chat_about_submission(current_h_id, source_text, gemini_file_ids, prev_json_str, admin_q)

                                    # Save to database (map dynamic keys to static columns for backward compatibility)
                                    languages = get_ai_response_languages(current_h_id)
                                    q_en = admin_q
                                    q_ja = admin_q
                                    a_en = ''
                                    a_ja = ''

                                    for lang in languages:
                                        lang_key = normalize_lang_to_key(lang)
                                        if lang_key in ['english', 'en', '英語']:
                                            q_en = res_json.get(f'question_{lang_key}', admin_q)
                                            a_en = res_json.get(f'answer_{lang_key}', '')
                                        elif lang_key in ['japanese', 'ja', '日本語']:
                                            q_ja = res_json.get(f'question_{lang_key}', admin_q)
                                            a_ja = res_json.get(f'answer_{lang_key}', '')

                                    save_admin_chat(
                                        evaluation_id=selected_eval_id,
                                        question_en=q_en,
                                        question_ja=q_ja,
                                        answer_en=a_en,
                                        answer_ja=a_ja,
                                        qa_json=res_json
                                    )

                                    status.update(label=t("✅ AI Responded", "✅ AIの回答が完了しました"), state="complete")
                                    st.rerun()
                                except Exception as e:
                                    status.update(label="Error", state="error")
                                    st.error(str(e))

# --- TAB 6: AI Response Settings ---
with tab6:
    st.markdown(f"### {t('🤖 AI Response Settings', '🤖 AIレスポンス設定')}")

    st.warning(t(
        "⚠️ **Warning**: Setting multiple languages increases the amount of text generated by the AI. This will prolong the response time (latency). It is highly recommended to configure only 1 or 2 essential languages for optimal performance.",
        "⚠️ **警告 / 注意**: 複数の言語を設定すると、AIがそれぞれの言語表現でフィードバックやアクションアイテムを作成するため、レスポンスの生成時間（遅延）が長くなります。最適なパフォーマンスのために、必要な言語のみ（通常は1〜2つ）を設定することをお勧めします。"
    ))

    # Initialize editing session state if not set
    state_key = f"editing_langs_{current_h_id}"
    if state_key not in st.session_state:
        st.session_state[state_key] = get_ai_response_languages(current_h_id)

    st.write(t("Configure AI Response Languages", "AIレスポンス言語設定"))

    langs_list = st.session_state[state_key]

    st.markdown(f"**{t('Configured Languages (Max 5):', '設定済みの言語 (最大5つ):')}**")
    if not langs_list:
        st.info(t("No languages configured yet. Please add at least one.", "言語が設定されていません。少なくとも1つの言語を追加してください。"))
    else:
        # Render a list of languages with delete buttons
        for idx, lang in enumerate(langs_list):
            col_lang, col_btn = st.columns([6, 1])
            with col_lang:
                st.markdown(f'<div style="padding: 6px 12px; background-color: rgba(255,255,255,0.05); border-radius: 4px; margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.1);">{idx+1}. {lang}</div>', unsafe_allow_html=True)
            with col_btn:
                if st.button("❌", key=f"del_lang_btn_{current_h_id}_{idx}"):
                    st.session_state[state_key].pop(idx)
                    st.rerun()

    # Input to add a new language
    if len(langs_list) < 5:
        col_input, col_add = st.columns([5, 2])
        with col_input:
            new_lang_val = st.text_input(
                t("Language Name", "言語名"),
                placeholder=t("e.g. Spanish, French, Korean", "例: Spanish, French, Korean"),
                key=f"new_lang_text_{current_h_id}",
                label_visibility="collapsed"
            )
        with col_add:
            if st.button(t("➕ Add Language", "➕ 言語を追加"), key=f"add_lang_btn_{current_h_id}"):
                cleaned_new = new_lang_val.strip()
                if not cleaned_new:
                    st.error(t("Language name cannot be empty.", "言語名を入力してください。"))
                elif cleaned_new in langs_list:
                    st.warning(t("Language already added.", "この言語は既に追加されています。"))
                else:
                    st.session_state[state_key].append(cleaned_new)
                    st.rerun()

    st.markdown("---")
    # Save button to commit to database
    if st.button(t("💾 Save Language Settings", "💾 言語設定を保存"), type="primary", key=f"save_langs_btn_{current_h_id}"):
        if not langs_list:
            st.error(t("Please configure at least one language.", "少なくとも1つの言語を設定してください。"))
        else:
            set_ai_response_languages(current_h_id, langs_list)
            st.success(t("AI response languages updated successfully!", "AIレスポンスの言語設定を更新しました！"))
            st.rerun()

# --- TAB 7: Project Settings ---
with tab7:
    st.markdown(f"### ⚙️ {t('Project Details & Behavior Settings', 'プロジェクト詳細・挙動設定')}")
    st.info(t(
        "Fine-tune evaluation context behaviors and Q&A constraints for this specific project.",
        "このプロジェクトにおける評価コンテキストの挙動やQ&A対話の制限を設定します。"
    ))

    curr_mode = get_re_evaluation_context_mode(current_h_id)
    curr_max_qa = get_max_qa_turns(current_h_id)
    curr_max_consultations = get_max_consultations(current_h_id)

    with st.form("project_behavior_settings_form"):
        st.subheader(t("🔄 Re-evaluation Context Mode", "🔄 再評価（イテレーション）時のコンテキスト"))
        st.markdown(t(
            "Configure how the AI panel handles updates when teams resubmit their work.",
            "成果物が再アップロードされた際に、AIパネルが前回の評価結果をどのように扱うかを定義します。"
        ))
        re_eval_options = {
            "cumulative": t(
                "Cumulative (Include previous evaluation context. Recommended for iterative projects)",
                "累積（前回の評価内容や改善点をコンテキストに含め、改善度を評価に反映させます ※継続的なプロジェクト推奨）"
            ),
            "independent": t(
                "Independent (Evaluate freshly from scratch. Recommended for hiring/recruiting)",
                "独立（前回の評価は引き継がず、毎回純粋に提出物のみでフラットに採点します ※採用や単発評価推奨）"
            )
        }
        selected_mode = st.radio(
            "re_evaluation_context_mode",
            options=list(re_eval_options.keys()),
            format_func=lambda x: re_eval_options[x],
            index=0 if curr_mode == "cumulative" else 1,
            label_visibility="collapsed"
        )

        st.markdown("---")

        st.subheader(t("🙋 Max Q&A Dialogue Turns", "🙋 Q&A（異議申し立て）の最大ターン数"))
        st.markdown(t(
            "Define how many questions or objections a team/candidate can send to the AI judges.",
            "チームや候補者が、評価結果に対して最大何回AI審査員へ質問や反論を送信できるかを設定します。"
        ))

        qa_options = {
            0: t("Disable Q&A (0 Turns)", "Q&A無効 (0回)"),
            1: t("1 Turn (One-shot Q&A)", "1往復のみ (デフォルト)"),
            2: t("2 Turns", "2往復"),
            3: t("3 Turns", "3往復"),
            5: t("5 Turns", "5往復"),
            -1: t("Unlimited Turns", "無制限")
        }

        default_index = 1
        if curr_max_qa in qa_options:
            default_index = list(qa_options.keys()).index(curr_max_qa)
        else:
            default_index = 1

        selected_max_qa = st.selectbox(
            "max_qa_turns",
            options=list(qa_options.keys()),
            format_func=lambda x: qa_options[x],
            index=default_index,
            label_visibility="collapsed"
        )

        st.markdown("---")

        st.subheader(t("📤 Max Consultations / Submissions Limit", "📤 最大提出・相談回数の制限"))
        st.markdown(t(
            "Define how many draft submissions (AI consultations) a team is allowed to get.",
            "各チームが受けられるAIコーチング（相談提出）の最大回数を設定します。"
        ))

        cons_options = {
            1: t("1 Consultation", "1回のみ"),
            2: t("2 Consultations", "2回"),
            3: t("3 Consultations (Default)", "3回 (デフォルト)"),
            5: t("5 Consultations", "5回"),
            10: t("10 Consultations", "10回"),
            -1: t("Unlimited", "無制限")
        }

        default_cons_index = 2
        if curr_max_consultations in cons_options:
            default_cons_index = list(cons_options.keys()).index(curr_max_consultations)
        else:
            default_cons_index = 2

        selected_max_cons = st.selectbox(
            "max_consultations",
            options=list(cons_options.keys()),
            format_func=lambda x: cons_options[x],
            index=default_cons_index,
            label_visibility="collapsed"
        )

        submitted_settings = st.form_submit_button(t("Save Project Settings", "プロジェクト設定を保存"), type="primary", disabled=is_demo)
        if submitted_settings:
            set_re_evaluation_context_mode(current_h_id, selected_mode)
            set_max_qa_turns(current_h_id, selected_max_qa)
            set_max_consultations(current_h_id, selected_max_cons)
            st.success(t("Project settings saved successfully!", "プロジェクト設定を正常に保存しました！"))
            st.rerun()

    # --- Export Template ---
    st.markdown("---")
    st.subheader(t("📤 Export Template", "📤 テンプレートのエクスポート"))
    st.markdown(t(
        "Export your current project settings (criteria and personas) as a JSON file to share with others.",
        "現在のプロジェクト設定（評価基準と審査員ペルソナ）をJSONファイルとして書き出し、他の管理者と共有できます。"
    ))

    # Retrieve current configurations for export
    export_criteria = get_criteria(current_h_id)
    export_personas = get_personas(current_h_id)

    # Use template description if template_id exists, otherwise default to empty string
    from core.templates import TEMPLATES
    tpl_desc = ""
    tpl_tags = []
    if hackathon.template_id and hackathon.template_id in TEMPLATES:
        tpl_desc = TEMPLATES[hackathon.template_id].get("description", "")
        tpl_tags = TEMPLATES[hackathon.template_id].get("tags", [])

    export_data = {
        "name": hackathon.name,
        "description": tpl_desc,
        "re_evaluation_context_mode": curr_mode,
        "max_qa_turns": curr_max_qa,
        "max_consultations": curr_max_consultations,
        "criteria": export_criteria,
        "personas": export_personas,
        "tags": tpl_tags
    }
    try:
        export_json = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label=t("💾 Download Template JSON", "💾 テンプレートJSONをダウンロード"),
            data=export_json,
            file_name=f"judgie-template-{current_h_id}.json",
            mime="application/json",
            key=f"export_template_btn_{current_h_id}"
        )
    except Exception as e:
        st.error(t(f"Failed to generate export file: {str(e)}", f"エクスポートファイルの生成に失敗しました: {str(e)}"))

    # --- Import Template ---
    st.markdown("---")
    st.subheader(t("📥 Import External Template", "📥 外部テンプレートのインポート"))
    st.markdown(t(
        "Import evaluation criteria and AI judge personas from a GitHub Gist or public Raw JSON URL. **Warning: This will overwrite your current settings.**",
        "GitHub Gistや公開されたRaw JSONのURLから評価基準とAIペルソナをインポートします。**警告：現在の設定は上書きされます。**"
    ))

    st.info(t(
        "💡 **Looking for templates?** Visit the [PixApps Template Marketplace](https://pixapps.com/judgie-marketplace) (coming soon) to find and share templates!",
        "💡 **テンプレートをお探しですか？** [PixApps テンプレートマーケットプレイス](https://pixapps.com/judgie-marketplace) (開発中) でテンプレートを探したり、共有したりできます！"
    ))

    with st.form("import_template_form"):
        import_url = st.text_input(
            t("Template JSON URL", "テンプレートJSONのURL"),
            placeholder="https://gist.githubusercontent.com/.../raw/template.json",
            help=t("Supports raw GitHub/Gist JSON URLs. Standard Gist URLs will be automatically converted.", "GitHubまたはGistのRaw JSON URLに対応しています。通常のGist URLは自動変換されます。")
        )

        confirm_import = st.checkbox(
            t("I understand this will overwrite current criteria and personas.", "現在の評価基準と審査員設定が上書きされることを理解しています。")
        )

        submitted_import = st.form_submit_button(t("Run Import", "インポートを実行"), disabled=is_demo)

        if submitted_import:
            if not import_url.strip():
                st.error(t("Please enter a URL.", "URLを入力してください。"))
            elif not confirm_import:
                st.error(t("Please check the confirmation box to proceed.", "上書きの確認チェックボックスにチェックを入れてください。"))
            else:
                try:
                    url_to_fetch = import_url.strip()

                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(url_to_fetch)
                    if parsed.scheme not in ('http', 'https'):
                        raise ValueError(t("Invalid URL scheme. Only HTTP/HTTPS is allowed.", "無効なURLスキームです。HTTPまたはHTTPSのみ許可されます。"))

                    # Auto convert standard Gist URL to raw Gist URL
                    hostname = parsed.hostname
                    if hostname == "gist.github.com" and not parsed.path.endswith("/raw"):
                        path_parts = parsed.path.strip("/").split("/")
                        if len(path_parts) >= 2:
                            # Standard Gist URL: https://gist.github.com/username/gist_id
                            # Raw Gist URL: https://gist.githubusercontent.com/username/gist_id/raw
                            raw_url = f"https://gist.githubusercontent.com/{path_parts[0]}/{path_parts[1]}/raw"
                            parsed = urlparse(raw_url)
                            hostname = parsed.hostname

                    # SSRF validation using whitelisted domains
                    allowed_domains = {
                        'github.com',
                        'raw.githubusercontent.com',
                        'gist.githubusercontent.com',
                        'githubusercontent.com'
                    }
                    if hostname not in allowed_domains:
                        raise ValueError(t("Access to this domain is not allowed for security reasons.", "セキュリティ上の理由から、このドメインへのアクセスは許可されていません。"))

                    # Reconstruct URL to prevent SSRF detection and verify it
                    safe_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

                    if not is_safe_url(safe_url):
                        raise ValueError(t("URL fails security checks.", "URLがセキュリティチェックに合格しませんでした。"))

                    import requests
                    res = requests.get(safe_url)
                    if res.status_code != 200:
                        raise ValueError(f"Failed to fetch template. HTTP {res.status_code}")

                    imported_data = res.json()

                    # Basic schema validation
                    if not isinstance(imported_data, dict):
                        raise ValueError(t("Template must be a JSON object.", "テンプレートはJSONオブジェクトである必要があります。"))
                    if "criteria" not in imported_data or "personas" not in imported_data:
                        raise ValueError(t("JSON is missing 'criteria' or 'personas' keys.", "JSONに 'criteria' または 'personas' キーがありません。"))

                    # Import tags if present
                    if "tags" in imported_data:
                        imported_tags = imported_data["tags"]
                        if not isinstance(imported_tags, list) or not all(isinstance(t, str) for t in imported_tags):
                            raise ValueError(t("'tags' must be a list of strings.", "'tags' は文字列のリストである必要があります。"))

                    # Import criteria
                    imported_criteria = imported_data["criteria"]
                    if not isinstance(imported_criteria, list):
                        raise ValueError(t("'criteria' must be a list.", "'criteria' はリストである必要があります。"))
                    for idx, c in enumerate(imported_criteria):
                        if not all(k in c for k in ("name", "weight", "description")):
                            raise ValueError(t(f"Criteria at index {idx} is missing required fields.", f"インデックス {idx} の評価基準に必要なフィールドが不足しています。"))

                    # Import personas
                    imported_personas = imported_data["personas"]
                    if not isinstance(imported_personas, list):
                        raise ValueError(t("'personas' must be a list.", "'personas' はリストである必要があります。"))
                    for idx, p in enumerate(imported_personas):
                        if not all(k in p for k in ("id", "name", "role", "avatar", "prompt", "active")):
                            raise ValueError(t(f"Persona at index {idx} is missing required fields.", f"インデックス {idx} のペルソナに必要なフィールドが不足しています。"))

                    # Update database
                    set_criteria(current_h_id, imported_criteria)
                    set_personas(current_h_id, imported_personas)

                    # Update optional project settings if provided
                    if "re_evaluation_context_mode" in imported_data:
                        if imported_data["re_evaluation_context_mode"] in ("cumulative", "independent"):
                            set_re_evaluation_context_mode(current_h_id, imported_data["re_evaluation_context_mode"])
                    if "max_qa_turns" in imported_data:
                        if isinstance(imported_data["max_qa_turns"], int):
                            set_max_qa_turns(current_h_id, imported_data["max_qa_turns"])
                    if "max_consultations" in imported_data:
                        if isinstance(imported_data["max_consultations"], int):
                            set_max_consultations(current_h_id, imported_data["max_consultations"])

                    st.success(t("Template successfully imported!", "テンプレートのインポートに成功しました！"))
                    st.rerun()
                except Exception as e:
                    st.error(t(f"Import failed: {str(e)}", f"インポートに失敗しました: {str(e)}"))

