import streamlit as st
import pandas as pd
import json
from core.db import get_criteria, get_personas, SessionLocal, User, Evaluation
from core.auth import require_login
from core.ui_utils import get_avatar_html

# Require login, but accessible by both 'admin' and 'team'
require_login()

lang = st.session_state.get('language', 'English')
def t(en, ja): return en if lang == "English" else ja

st.title(t("🔥 The Hype Board", "🔥 The Hype Board"))
st.markdown(t("Overview of the hackathon heat and team rankings.", "ハッカソン全体の熱量と、全チームの暫定・最終スコアの俯瞰ビューです。"))

current_h_id = st.session_state.get('active_hackathon_id')

if not current_h_id:
    st.error(t("No active hackathon selected.", "アクティブなハッカソンがありません。"))
    st.stop()

# ------------------
# Meet the AI Judges
# ------------------
st.subheader(t("🤖 Meet the AI Jury Panel", "🤖 審査員パネルの紹介"))
st.markdown(t("This expert panel will evaluate your submissions.", "このハッカソンでは、以下の5名のAI審査員が容赦のない評価を行います。"))

personas = get_personas(current_h_id)
active_personas = [p for p in personas if p.get('active', True)]

if active_personas:
    cols = st.columns(len(active_personas))
    for i, p in enumerate(active_personas):
        with cols[i]:
            with st.container(border=True):
                avatar_html = get_avatar_html(p['name'], p.get('avatar', '🧑‍⚖️'), size=50)
                st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 10px;">{avatar_html}<h3 style="margin: 0;">{p["name"]}</h3></div>', unsafe_allow_html=True)
                st.caption(f"{p['role']}")
                with st.popover("🧠 View Persona"):
                    st.markdown(p.get('prompt', '').replace('\n', '\n\n'))

# ------------------
# The Rules of the Game
# ------------------
st.subheader(t("⚖️ The Rules of the Game", "⚖️ 評価基準とウェイト"))
criteria = get_criteria(current_h_id)
total_weight = sum(c['weight'] for c in criteria) if criteria else 1

if criteria:
    for i in range(0, len(criteria), 2):
        r_cols = st.columns(2)
        for j in range(2):
            if i + j < len(criteria):
                c = criteria[i + j]
                with r_cols[j]:
                    with st.container(border=True):
                        st.markdown(f"#### {c['name']} \n **Weight: {c['weight']}%**")
                        st.markdown(c['description'].replace('\n', '\n\n'))

st.divider()

st.subheader(t("🚀 Current Rankings", "🚀 最新ランキング"))

db = SessionLocal()
try:
    if current_h_id:
        users = db.query(User).filter(User.role == 'team', User.hackathon_id == current_h_id).order_by(User.team_id).all()
    else:
        users = db.query(User).filter(User.role == 'team').order_by(User.team_id).all()
        
    all_teams = {u.team_id: {'team_id': u.team_id, 'product_name': u.product_name, 'one_liner': u.one_liner} for u in users}
    team_ids = list(all_teams.keys())
    
    evaluations = db.query(Evaluation).filter(Evaluation.team_id.in_(team_ids)).all() if team_ids else []
    eval_rows = []
    for tid in team_ids:
        team_evals = [e for e in evaluations if e.team_id == tid]
        if team_evals:
            latest = max(team_evals, key=lambda x: x.id)
            eval_rows.append({
                'team_id': latest.team_id,
                'scores_json': latest.scores_json,
                'is_final': latest.is_final,
                'consults': len(team_evals)
            })
finally:
    db.close()

eval_dict = {r['team_id']: r for r in eval_rows}

data = []
for team_id, u_row in all_teams.items():
    product_disp = u_row['product_name'] if u_row['product_name'] else team_id
    one_liner_disp = u_row['one_liner'] if u_row['one_liner'] else ""
    
    row_data = {
        t("Product / Team", "プロダクト / チーム"): product_disp,
        t("One-liner", "一言アピール"): one_liner_disp
    }
    
    if team_id in eval_dict:
        r = eval_dict[team_id]
        scores = json.loads(r['scores_json'])
        total_score = sum(scores.get(crit["name"], 0) * (crit["weight"] / total_weight) for crit in criteria)
        
        if r['is_final']:
            status = t("✅ Final", "✅ 最終提出")
        else:
            status = t(f"⏳ Cons ({r['consults']}/3)", f"⏳ 構築中 ({r['consults']}/3)")
            
        row_data[t("Status", "状態")] = status
        row_data[t("Total Score", "総合スコア")] = round(total_score, 2)
        row_data[t("Consults", "相談回数")] = r['consults']
            
    else:
        row_data[t("Status", "状態")] = t("Not Submitted", "未提出")
        row_data[t("Total Score", "総合スコア")] = 0.0
        row_data[t("Consults", "相談回数")] = 0

    data.append(row_data)

if data:
    df = pd.DataFrame(data).sort_values(by=[t("Total Score", "総合スコア"), t("Product / Team", "プロダクト / チーム")], ascending=[False, True])
    
    col_config = {
        t("Total Score", "総合スコア"): st.column_config.ProgressColumn(
            t("Total Score", "総合スコア"),
            help="Max score is 5.0",
            format="%.2f",
            min_value=0,
            max_value=5.0,
        )
    }
        
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)
    
    # ------------------
    # Category Leaders
    # ------------------
    st.divider()
    st.subheader(t("🏅 Category Leaders", "🏅 カテゴリ別リーダー"))
    if criteria:
        tabs = st.tabs([c['name'] for c in criteria])
        for i, c in enumerate(criteria):
            with tabs[i]:
                cat_data = []
                for team_id, u_row in all_teams.items():
                    s = 0.0
                    if team_id in eval_dict:
                        scores = json.loads(eval_dict[team_id]['scores_json'])
                        s = float(scores.get(c['name'], 0.0))
                    
                    product_disp = u_row['product_name'] if u_row['product_name'] else team_id
                    cat_data.append({"Team": product_disp, "Score": s})
                
                df_cat = pd.DataFrame(cat_data).sort_values(by="Score", ascending=False).head(5)
                st.dataframe(df_cat, use_container_width=True, hide_index=True, column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", format="%.1f", min_value=0, max_value=5.0
                    )
                })

else:
    st.info("No teams yet.")
