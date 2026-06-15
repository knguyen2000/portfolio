import streamlit as st

from services.calendly import (
    CalendlyClient,
    fetch_available_slots,
    fetch_event_types,
    format_slot_time,
    get_booking_url,
)
from utils.sidebar import render_sidebar

PAGE_TITLE = "Availability"


def _render_page():
    st.set_page_config(layout="wide", page_title=PAGE_TITLE, page_icon="📅")

    render_sidebar()

    st.markdown("# 📅 Availability")
    st.markdown("Want to chat? See my open slots below.")

    token = st.secrets.get("CALENDLY_TOKEN")
    if not token:
        st.warning("Calendly is not configured. Add `CALENDLY_TOKEN` to `.streamlit/secrets.toml`.")
        st.stop()

    @st.cache_data(ttl=300)
    def _get_user_info(_client):
        user = _client.get_current_user()
        return user["name"], user.get("timezone", "UTC"), user.get("scheduling_url", "")

    @st.cache_data(ttl=300)
    def _get_event_types(_client):
        return fetch_event_types(_client)

    @st.cache_data(ttl=300)
    def _get_slots(_client, event_type_uri):
        return fetch_available_slots(_client, event_type_uri)

    client = CalendlyClient(token)

    try:
        _, timezone, _ = _get_user_info(client)
    except Exception as e:
        st.error(f"Could not connect to Calendly: {e}")
        st.stop()

    event_types = _get_event_types(client)

    if not event_types:
        st.info("No active event types found on your Calendly account.")
        st.stop()

    if len(event_types) == 1:
        selected = event_types[0]
    else:
        names = [et["name"] for et in event_types]
        choice = st.selectbox("Select a meeting type", names)
        selected = next(et for et in event_types if et["name"] == choice)

    st.markdown(f"**{selected['name']}** — {selected['duration']} min")
    if selected.get("description"):
        st.caption(selected["description"])

    st.markdown(f"*Times shown in {timezone}*")
    st.markdown("---")

    slots = _get_slots(client, selected["uri"])

    if not slots:
        st.info("No availability this week.")
    else:
        for date_key in sorted(slots.keys()):
            day_slots = slots[date_key]
            st.subheader(date_key)
            cols = st.columns(min(len(day_slots), 4))
            for i, slot in enumerate(day_slots):
                with cols[i % len(cols)]:
                    time_label = format_slot_time(slot["start_time"], timezone=timezone)
                    booking_url = slot.get("scheduling_url") or get_booking_url(selected)
                    st.link_button(time_label, booking_url)


try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    if get_script_run_ctx() is not None:
        _render_page()
except ImportError:
    pass
