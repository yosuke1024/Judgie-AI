import streamlit as st
import pandas as pd
import altair as alt

def render_score_history_chart(eval_rows: list, criteria: list, total_weight: float):
    """
    Renders an Altair line chart showing the history of scores for a team over time.
    """
    if len(eval_rows) <= 1:
        return
        
    history_data = []
    for idx, r in enumerate(eval_rows):
        r_scores = r['scores_json']
        if isinstance(r_scores, str):
            import json
            r_scores = json.loads(r_scores)
            
        step_name = f"Consult {idx+1}" if not r['is_final'] else "Final"
        
        # Calculate weighted Total Score
        total_s = sum(r_scores.get(c['name'], 0) * 20.0 * (c['weight'] / total_weight) for c in criteria)
        history_data.append({"Step": step_name, "Criteria": "⭐ Total Score", "Score": total_s, "Order": idx})
        
        for c in criteria:
            history_data.append({"Step": step_name, "Criteria": c['name'], "Score": r_scores.get(c['name'], 0) * 20.0, "Order": idx})
            
    df_hist = pd.DataFrame(history_data)
    line_chart = alt.Chart(df_hist).mark_line(point=True).encode(
        x=alt.X('Step:N', sort=alt.EncodingSortField(field='Order', order='ascending'), title='Evaluation Phase', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Score:Q', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color('Criteria:N', legend=alt.Legend(title="Metrics")),
        tooltip=['Step', 'Criteria', 'Score']
    ).properties(height=300)
    
    st.altair_chart(line_chart, use_container_width=True)

def render_criteria_radar_chart(chart_data: list):
    """
    Renders an Altair horizontal bar chart showing the balance of current evaluation metrics.
    """
    df_chart = pd.DataFrame(chart_data)
    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X('Score:Q', scale=alt.Scale(domain=[0, 5])),
        y=alt.Y('Criteria:N', sort=None),
        color=alt.Color('Score:Q', scale=alt.Scale(scheme='tealblues'), legend=None),
        tooltip=['Criteria', 'Score']
    ).properties(height=250)
    
    st.altair_chart(chart, use_container_width=True)
