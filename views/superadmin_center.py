import pandas as pd
import streamlit as st
from sqlalchemy import func

from core.auth import require_login
from core.db import (
    Hackathon,
    SessionLocal,
    User,
    change_my_passcode,
    create_hackathon,
    delete_hackathon,
    update_admin_passcode,
)
from core.i18n import t
from core.security import is_safe_url

# Only superadmin can access this
require_login('superadmin')

st.title(t("🌍 Super Admin Console", "🌍 スーパー管理者コンソール"))

col_title, col_btn = st.columns([3, 1])
with col_title:
    st.markdown(t("Manage isolated Hackathon tenants and tenant admins.", "ハッカソン（テナント）の作成と管理者アカウントの発行を行います。"))
with col_btn:
    with st.popover(t("⚙️ Change Password", "⚙️ パスワード変更")):
        with st.form("change_my_pass_form"):
            curr_pass = st.text_input(t("Current Password", "現在のパスワード"), type="password")
            new_pass = st.text_input(t("New Password", "新しいパスワード"), type="password")
            if st.form_submit_button(t("Update", "更新"), type="primary"):
                if not curr_pass or not new_pass:
                    st.error(t("All fields required.", "すべて入力してください。"))
                else:
                    success = change_my_passcode(None, st.session_state.team_id, curr_pass, new_pass)
                    if success:
                        st.session_state.passcode = new_pass
                        st.success(t("Password updated!", "パスワードを更新しました！"))
                    else:
                        st.error(t("Incorrect current password.", "現在のパスワードが間違っています。"))

st.divider()

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader(t("➕ Create New Project", "➕ 新規プロジェクトの作成"))
    with st.form("superadmin_create_form"):
        h_name = st.text_input(t("Project Name", "プロジェクト名"), placeholder="e.g. Summer AI Hackathon 2026")
        a_id = st.text_input(t("Tenant Admin ID", "テナント管理者 ID"), placeholder="e.g. admin_summer26")
        a_pass = st.text_input(t("Tenant Admin Password", "テナント管理者パスワード"), type="password")

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

        if st.form_submit_button(t("Create Project", "プロジェクトを作成"), type="primary"):
            if not h_name or not a_id or not a_pass:
                st.error(t("All fields are required.", "すべての項目を入力してください。"))
            elif selected_tpl_key == "custom" and not custom_url.strip():
                st.error(t("Please enter a custom template URL.", "カスタムテンプレートのURLを入力してください。"))
            else:
                try:
                    custom_template_data = None
                    if selected_tpl_key == "custom" and custom_url.strip():
                        url_to_fetch = custom_url.strip()

                        # SSRF対策のインラインバリデーション
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

                        # 検証済みのパーツから安全なURLを再構築し、汚染追跡（Taint Tracking）を断ち切る
                        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            safe_url += f"?{parsed.query}"

                        import requests
                        res = requests.get(safe_url)
                        if res.status_code != 200:
                            raise ValueError(f"Failed to fetch template from URL. HTTP {res.status_code}")
                        custom_template_data = res.json()



                    new_id = create_hackathon(h_name, a_id, a_pass, template_id=selected_tpl_key, custom_template_data=custom_template_data)
                    st.success(f"Successfully created Project '{h_name}' (ID: {new_id}) with Admin '{a_id}'!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create project: {str(e)}")

with col2:
    st.subheader(t("🏢 Existing Hackathons", "🏢 既存のハッカソン一覧"))

    db = SessionLocal()
    try:
        results = db.query(
            Hackathon.id, Hackathon.name, Hackathon.created_at, User.team_id.label('admin_id')
        ).outerjoin(
            User, (Hackathon.id == User.hackathon_id) & (User.role == 'admin')
        ).order_by(Hackathon.id.desc()).all()

        rows = [{'id': r.id, 'name': r.name, 'created_at': r.created_at, 'admin_id': r.admin_id} for r in results]

        counts = db.query(User.hackathon_id, func.count(User.id).label('team_count')).filter(User.role == 'team').group_by(User.hackathon_id).all()
        team_counts = {c.hackathon_id: c.team_count for c in counts}
    finally:
        db.close()

    if not rows:
        st.info(t("No hackathons exist yet.", "まだハッカソンは作成されていません。"))
    else:
        data = []
        for r in rows:
            data.append({
                "ID": r['id'],
                t("Name", "名前"): r['name'],
                t("Admin ID", "管理者ID"): r['admin_id'],
                t("Teams", "参加チーム数"): team_counts.get(r['id'], 0),
                t("Created At", "作成日時"): r['created_at']
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader(t("🔑 Reset Admin Password", "🔑 管理者パスワードのリセット"))

        hackathon_options = {r['id']: f"[{r['id']}] {r['name']} (Admin: {r['admin_id']})" for r in rows if r['admin_id']}

        if hackathon_options:
            with st.form("reset_pass_form"):
                selected_h_id = st.selectbox(t("Select Tenant", "テナントを選択"), options=list(hackathon_options.keys()), format_func=lambda x: hackathon_options[x])
                new_pass = st.text_input(t("New Password", "新しいパスワード"), type="password")
                if st.form_submit_button(t("Reset Password", "パスワードをリセット"), type="primary"):
                    if not new_pass:
                        st.error(t("Password cannot be empty.", "パスワードを入力してください。"))
                    else:
                        update_admin_passcode(selected_h_id, new_pass)
                        st.success(t(f"Password reset successfully for tenant ID {selected_h_id}.", f"テナントID {selected_h_id} のパスワードをリセットしました。"))
        else:
            st.info(t("No tenants with admin accounts found.", "管理者アカウントを持つテナントが見つかりません。"))

        st.divider()
        st.subheader(t("⚠️ Delete Tenant", "⚠️ テナントの削除"))

        # Use all IDs from rows so that any hackathon can be deleted
        delete_options = {r['id']: f"[{r['id']}] {r['name']}" for r in rows}
        if delete_options:
            with st.form("delete_tenant_form"):
                st.markdown(t("Select a tenant to delete. This will permanently delete **all associated data** (users, submissions, settings, evaluations, etc.).", "削除するテナントを選択してください。この操作により、**関連するすべてのデータ**（ユーザー、提出物、設定、評価など）が完全に削除され、元に戻せなくなります。"))
                selected_del_h_id = st.selectbox(t("Select Tenant to Delete", "削除するテナントを選択"), options=list(delete_options.keys()), format_func=lambda x: delete_options[x])

                confirm_check = st.checkbox(t("I understand that all data for this tenant will be permanently deleted and cannot be recovered.", "このテナントのすべてのデータが永久に削除され、復元できないことを理解しました。"))

                if st.form_submit_button(t("🔥 Delete Tenant", "🔥 テナントを削除"), type="primary"):
                    if not confirm_check:
                        st.error(t("Please check the confirmation box to delete the tenant.", "削除するには確認のチェックボックスをオンにしてください。"))
                    else:
                        try:
                            delete_hackathon(selected_del_h_id)
                            st.success(t(f"Successfully deleted tenant ID {selected_del_h_id}.", f"テナントID {selected_del_h_id} を正常に削除しました。"))
                            st.rerun()
                        except Exception as e:
                            st.error(t(f"Failed to delete tenant: {str(e)}", f"テナントの削除に失敗しました: {str(e)}"))
        else:
            st.info(t("No tenants found.", "テナントが見つかりません。"))
