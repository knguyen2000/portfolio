"""Failing tests for the Availability feature (SPEC.md Stories 1–5).

Each test class maps to one SPEC story. All tests fail until the story is implemented.
Tests drive creation of services/calendly.py as the testable service layer.
"""

import os
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Story 1: Availability page shell
# ---------------------------------------------------------------------------


class TestStory1PageShell:
    def test_availability_page_file_exists(self):
        assert os.path.isfile(os.path.join("pages", "availability.py"))

    def test_page_defines_title(self):
        from pages.availability import PAGE_TITLE

        assert PAGE_TITLE
        assert isinstance(PAGE_TITLE, str)


# ---------------------------------------------------------------------------
# Story 2: Fetch event types from Calendly
# ---------------------------------------------------------------------------


class TestStory2FetchEventTypes:
    def test_fetch_event_types_returns_list(self):
        from services.calendly import fetch_event_types

        mock_client = MagicMock()
        mock_client.list_event_types.return_value = [
            {"name": "30 Min Meeting", "duration": 30, "scheduling_url": "https://calendly.com/khuong/30min"}
        ]
        result = fetch_event_types(mock_client)
        assert isinstance(result, list)

    def test_event_type_contains_name_and_duration(self):
        from services.calendly import fetch_event_types

        mock_client = MagicMock()
        mock_client.list_event_types.return_value = [
            {"name": "30 Min Meeting", "duration": 30, "scheduling_url": "https://calendly.com/khuong/30min"}
        ]
        result = fetch_event_types(mock_client)
        assert len(result) > 0
        event = result[0]
        assert "name" in event
        assert "duration" in event

    def test_fetch_event_types_returns_empty_on_api_error(self):
        from services.calendly import fetch_event_types

        mock_client = MagicMock()
        mock_client.list_event_types.side_effect = Exception("API error")
        result = fetch_event_types(mock_client)
        assert result == []


# ---------------------------------------------------------------------------
# Story 3: Display available time slots
# ---------------------------------------------------------------------------


class TestStory3AvailableSlots:
    def test_fetch_slots_returns_dict_grouped_by_day(self):
        from services.calendly import fetch_available_slots

        mock_client = MagicMock()
        mock_client.list_available_times.return_value = [
            {"start_time": "2026-06-15T10:00:00-05:00"},
            {"start_time": "2026-06-15T14:00:00-05:00"},
            {"start_time": "2026-06-16T09:00:00-05:00"},
        ]
        result = fetch_available_slots(mock_client, event_type_uri="https://api.calendly.com/event_types/123")
        assert isinstance(result, dict)
        assert len(result) >= 1

    def test_slots_grouped_by_date_key(self):
        from services.calendly import fetch_available_slots

        mock_client = MagicMock()
        mock_client.list_available_times.return_value = [
            {"start_time": "2026-06-15T10:00:00-05:00"},
            {"start_time": "2026-06-16T09:00:00-05:00"},
        ]
        result = fetch_available_slots(mock_client, event_type_uri="https://api.calendly.com/event_types/123")
        assert "2026-06-15" in result or any("2026-06-15" in k for k in result)

    def test_fetch_slots_returns_empty_on_no_availability(self):
        from services.calendly import fetch_available_slots

        mock_client = MagicMock()
        mock_client.list_available_times.return_value = []
        result = fetch_available_slots(mock_client, event_type_uri="https://api.calendly.com/event_types/123")
        assert result == {}

    def test_times_include_timezone_label(self):
        from services.calendly import format_slot_time

        formatted = format_slot_time("2026-06-15T10:00:00-05:00", timezone="America/Chicago")
        assert any(tz in formatted for tz in ["CDT", "CST", "CT", "America/Chicago"])


# ---------------------------------------------------------------------------
# Story 4: Booking link
# ---------------------------------------------------------------------------


class TestStory4BookingLink:
    def test_booking_url_uses_scheduling_url(self):
        from services.calendly import get_booking_url

        event_type = {
            "scheduling_url": "https://calendly.com/khuong/30min",
            "uri": "https://api.calendly.com/event_types/123",
        }
        url = get_booking_url(event_type)
        assert url.startswith("https://calendly.com/")
        assert "api.calendly.com" not in url

    def test_booking_url_never_returns_api_uri(self):
        from services.calendly import get_booking_url

        event_type = {
            "scheduling_url": "https://calendly.com/khuong/30min",
            "uri": "https://api.calendly.com/event_types/123",
        }
        url = get_booking_url(event_type)
        assert "api.calendly.com" not in url


# ---------------------------------------------------------------------------
# Story 5: Book meetings through the chat agent
# ---------------------------------------------------------------------------


class TestStory5ChatBooking:
    def test_detect_scheduling_intent_positive(self):
        from services.calendly import detect_scheduling_intent

        assert detect_scheduling_intent("Can I schedule a call with Khuong?") is True
        assert detect_scheduling_intent("I'd like to book a meeting") is True
        assert detect_scheduling_intent("Are you available Thursday?") is True

    def test_detect_scheduling_intent_negative(self):
        from services.calendly import detect_scheduling_intent

        assert detect_scheduling_intent("What projects has Khuong worked on?") is False
        assert detect_scheduling_intent("Tell me about the RLM agent") is False

    def test_create_booking_returns_confirmation(self):
        from services.calendly import create_booking

        mock_client = MagicMock()
        mock_client.create_invitee.return_value = {
            "resource": {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "event": "https://api.calendly.com/scheduled_events/abc123",
            }
        }
        result = create_booking(
            mock_client,
            event_type_uri="https://api.calendly.com/event_types/123",
            name="Jane Doe",
            email="jane@example.com",
        )
        assert result["name"] == "Jane Doe"
        assert result["email"] == "jane@example.com"

    def test_create_booking_handles_api_error(self):
        from services.calendly import create_booking

        mock_client = MagicMock()
        mock_client.create_invitee.side_effect = Exception("Booking failed")
        result = create_booking(
            mock_client,
            event_type_uri="https://api.calendly.com/event_types/123",
            name="Jane Doe",
            email="jane@example.com",
        )
        assert result is None or "error" in result

    def test_nla_mode_excluded(self):
        from services.calendly import is_booking_supported

        assert is_booking_supported("File-Based Context") is True
        assert is_booking_supported("Standard RAG (Vector + Sliding Window)") is True
        assert is_booking_supported("Recursive Language Model (RLM)") is True
        assert is_booking_supported("NLA (Natural Language Autoencoder)") is False
