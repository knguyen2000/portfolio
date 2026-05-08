"""
Admin Review Dashboard page.

Gated behind Admin login. Allows the AI/ML team to triage visitor concerns,
generate structured backlog candidates, track metrics, and review an audit log
of every action taken on captured concerns.
"""
import streamlit as st
import os
from google import genai
from utils.sidebar import render_sidebar
from utils.workflow_db import (
    get_unresolved_concerns, get_all_concerns,
    mark_concern_resolved, discard_concern, mark_concern_accepted,
    get_backlog_candidates, insert_backlog_candidate,
    get_activity_log
)
from engines.workflow_intelligence import generate_backlog_candidate
from state import init_session_state

st.set_page_config(layout="wide", page_title="Review Dashboard", page_icon="⚙️")
init_session_state()
render_sidebar()

if st.session_state.get("user_role") != "Admin":
    st.error("Access Denied. Please log in as Admin in the sidebar.")
    st.stop()

# --- Init selection state ---
if "selected_concerns" not in st.session_state:
    st.session_state.selected_concerns = {}
if "discard_reason" not in st.session_state:
    st.session_state.discard_reason = {}

def get_client():
    """Build and return a Gemini API client using the configured API key."""
    api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


st.title("⚙️ Review Dashboard")
st.markdown("Monitor workflow pain points, feature requests, and trust concerns.")

tab1, tab2, tab3, tab4 = st.tabs(["Unresolved Concerns", "Backlog Candidates", "Metrics", "Audit Log"])

with tab1:
    st.subheader("Top Unresolved Concerns")
    concerns = get_unresolved_concerns()
    
    if not concerns:
        st.info("No unresolved concerns at the moment!")
    else:
        # Group by category
        categories = {}
        for c in concerns:
            cat = c.get("concern_category", "Unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(c)
            
        for cat, items in categories.items():
            with st.expander(f"{cat} ({len(items)} items)", expanded=True):
                
                for item in items:
                    col_check, col_content = st.columns([0.05, 0.95])
                    with col_check:
                        checked = st.checkbox(
                            "Select",
                            label_visibility="hidden",
                            key=f"chk_{item['id']}",
                            value=st.session_state.selected_concerns.get(item['id'], False),
                            help="Select to include in a backlog candidate"
                        )
                        st.session_state.selected_concerns[item['id']] = checked
                    with col_content:
                        st.markdown(f"**Quote:** _{item['original_quote']}_")
                        
                        ws = item.get('workflow_stage')
                        rc = item.get('likely_root_cause')
                        tm = item.get('existing_tool_match')
                        
                        if ws or rc:
                            st.markdown(f"**Workflow Stage:** {ws or 'N/A'}  |  **Root Cause:** {rc or 'N/A'}")
                        if tm:
                            st.markdown(f"**Tool Match:** {tm}")
                        
                        act_col1, act_col2 = st.columns([1, 1])
                        with act_col1:
                            if st.button("✅ Mark Solved", key=f"res_{item['id']}", use_container_width=True):
                                mark_concern_resolved(item['id'])
                                st.session_state.selected_concerns.pop(item['id'], None)
                                st.rerun()
                        with act_col2:
                            if st.button("🗑️ Discard", key=f"dis_{item['id']}", use_container_width=True, type="secondary"):
                                st.session_state.discard_reason[item['id']] = True
                        
                        # Inline discard reason input
                        if st.session_state.discard_reason.get(item['id']):
                            reason = st.text_input(
                                "Reason for discarding (optional):",
                                key=f"reason_{item['id']}",
                                placeholder="e.g., Not a real issue, duplicate, out of scope..."
                            )
                            dc1, dc2 = st.columns([1, 3])
                            with dc1:
                                if st.button("Confirm Discard", key=f"confirm_dis_{item['id']}", type="primary"):
                                    discard_concern(item['id'], reason)
                                    st.session_state.discard_reason.pop(item['id'], None)
                                    st.session_state.selected_concerns.pop(item['id'], None)
                                    st.rerun()
                    
                    st.markdown("---")
                
                # Backlog generation from selected items
                selected_items = [item for item in items if st.session_state.selected_concerns.get(item['id'])]
                n_selected = len(selected_items)
                btn_label = f"🧠 Generate Backlog Candidate ({n_selected} selected)" if n_selected > 0 else "🧠 Generate Backlog Candidate"
                
                if st.button(btn_label, key=f"gen_{cat}", disabled=(n_selected == 0), type="primary"):
                    client = get_client()
                    if not client:
                        st.error("GOOGLE_API_KEY required for generation.")
                    else:
                        with st.spinner(f"Analyzing {n_selected} concern(s) and drafting candidate..."):
                            try:
                                candidate = generate_backlog_candidate(client, selected_items)
                                if candidate:
                                    backlog_id = insert_backlog_candidate(candidate)
                                    # Mark selected concerns as accepted to backlog
                                    for item in selected_items:
                                        mark_concern_accepted(item['id'], backlog_id)
                                        st.session_state.selected_concerns[item['id']] = False
                                    st.success(f"✅ Backlog candidate created! See the **Backlog Candidates** tab.")
                                else:
                                    st.error("The AI returned an empty response. Please try again.")
                            except Exception as e:
                                st.error(f"Error generating candidate: {e}")

with tab2:
    st.subheader("Backlog Candidates")
    candidates = get_backlog_candidates()
    if not candidates:
        st.info("No backlog candidates yet. Select concerns in the 'Unresolved Concerns' tab and click 'Generate Backlog Candidate'.")
    for cand in candidates:
        with st.expander(f"📌 {cand['title']}"):
            col_imp, col_risk = st.columns(2)
            col_imp.metric("Impact", cand['impact'])
            col_risk.metric("Risk", cand['risk'])
            st.markdown(f"**Problem:** {cand['problem']}")
            st.markdown(f"**Workflow Stage:** {cand['workflow_stage']} | **User Group:** {cand['user_group']}")
            st.markdown(f"**Existing Tool Check:** {cand['existing_tool_check']}")
            st.markdown(f"**Root Causes:** {cand['hypothesized_root_causes']}")
            st.markdown("#### Suggested Validation")
            st.info(cand['suggested_validation'])
            st.markdown("#### Potential MVP")
            st.success(cand['potential_mvp'])
            st.markdown("#### Acceptance Criteria")
            st.markdown(cand['acceptance_criteria'])
            st.markdown("#### Original Evidence")
            st.text(cand['original_evidence'])
            
with tab3:
    st.subheader("Workflow Intelligence Metrics")
    all_concerns = get_all_concerns()
    unresolved = get_unresolved_concerns()
    all_candidates = get_backlog_candidates()
    
    # Count by status
    status_counts = {}
    for c in all_concerns:
        s = c.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Captured", len(all_concerns))
    col2.metric("🟡 Unresolved", len(unresolved))
    col3.metric("✅ Solved", status_counts.get("solved", 0))
    col4.metric("🗑️ Discarded", status_counts.get("discarded", 0))
    col5.metric("🟢 In Backlog", status_counts.get("accepted_to_backlog", 0))
    
    if all_concerns:
        st.markdown("---")
        st.markdown("#### Breakdown by Category")
        cat_counts = {}
        for c in all_concerns:
            cat = c.get("concern_category", "Unknown")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            st.markdown(f"- **{cat}**: {count} concern(s)")

with tab4:
    st.subheader("Audit Log")
    st.caption("Every action taken on a concern is logged here.")
    
    log = get_activity_log()
    if not log:
        st.info("No actions logged yet.")
    else:
        action_icons = {
            "solved": "✅ Solved",
            "discarded": "🗑️ Discarded",
            "accepted_to_backlog": "🟢 Accepted to Backlog",
            "submitted": "🟡 Submitted",
        }
        for entry in log:
            icon_label = action_icons.get(entry['action'], entry['action'])
            ts = entry['timestamp'][:16].replace("T", " ")
            category = entry.get('concern_category') or ''
            quote = entry.get('original_quote') or ''
            with st.container():
                c1, c2 = st.columns([0.15, 0.85])
                c1.markdown(f"**{icon_label}**")
                c2.markdown(
                    f"`{ts}` — _{quote[:80]}{'...' if len(quote) > 80 else ''}_"
                    + (f"  \n**Note:** {entry['note']}" if entry.get('note') else "")
                    + (f"  \n**Category:** {category}" if category else "")
                )
            st.markdown("---")
