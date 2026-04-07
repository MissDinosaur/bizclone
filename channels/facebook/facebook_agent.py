"""
Facebook Channel Agent

Processes incoming Facebook Messenger messages and returns
standardized channel responses with AI-assisted intent detection
and simple entity extraction for booking requests.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI

from channels.schemas import (
    BookingResponseSchema,
    ChannelMessageResponseSchema,
    IntentType,
    MessageStatus,
)
from database.orm_models import ConversationState, KnowledgeBase
from scheduling.scheduler import check_availability, book_slot


logger = logging.getLogger(__name__)


class FacebookAgent:
    BOOKING_AWAITING_DAY = "appointment_awaiting_day"
    BOOKING_AWAITING_TIME = "appointment_awaiting_time"

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.ai_client = OpenAI(api_key=api_key) if api_key else None
        self.ai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def handle_incoming(self, normalized_message, db) -> ChannelMessageResponseSchema:
        text = (normalized_message.text or "").strip()
        sender_id = normalized_message.sender_id
        conversation_id = normalized_message.conversation_id

        logger.info("[FACEBOOK] Processing message from %s", sender_id)
        logger.info("[FACEBOOK] Conversation: %s", conversation_id)
        logger.info("[FACEBOOK] Text: %s", text)

        state = self._get_or_create_state(
            db=db,
            conversation_id=conversation_id,
            user_id=sender_id,
        )

        lowered = text.lower()

        intent = IntentType.FAQ
        booking_response: Optional[BookingResponseSchema] = None
        reply = self._reply_default()

        state_data = dict(state.state_data or {})
        extracted_day, extracted_period = self._extract_booking_entities(lowered)
        explicit_slot = self._extract_explicit_slot_selection(text)
        detected_service = self._extract_service_name(lowered)
        offered_slot_selection = self._extract_offered_slot_selection(text, state_data)

        if detected_service:
            normalized_service = self._normalize_service_key(detected_service)
            state_data = {
                **state_data,
                "last_service": normalized_service,
            }

        if explicit_slot:
            intent = IntentType.APPOINTMENT
            booking_response, reply = self._book_explicit_slot(
                user_id=sender_id,
                requested_day=explicit_slot["day"],
                requested_time=explicit_slot["time"],
                state_data=state_data,
            )
            state.awaiting_pricing_service = False
            state.awaiting_booking_details = False
            state.last_intent = IntentType.APPOINTMENT.value
            state.state_data = {
                **state_data,
                "requested_day": explicit_slot["day"],
                "requested_time": explicit_slot["time"],
                "last_offered_slots": [],
            }
            db.commit()
            db.refresh(state)

        elif offered_slot_selection:
            intent = IntentType.APPOINTMENT
            booking_response, reply = self._book_explicit_slot(
                user_id=sender_id,
                requested_day=offered_slot_selection["day"],
                requested_time=offered_slot_selection["time"],
                state_data=state_data,
            )
            state.awaiting_pricing_service = False
            state.awaiting_booking_details = False
            state.last_intent = IntentType.APPOINTMENT.value
            state.state_data = {
                **state_data,
                "requested_day": offered_slot_selection["day"],
                "requested_time": offered_slot_selection["time"],
                "last_offered_slots": [],
            }
            db.commit()
            db.refresh(state)

        elif self._is_booking_intent(lowered):
            intent = IntentType.APPOINTMENT

            if extracted_day and extracted_period:
                booking_response, reply, new_state_data = self._book_with_preferences(
                    user_id=sender_id,
                    requested_day=extracted_day,
                    requested_period=extracted_period,
                    state_data=state_data,
                )
                if booking_response is None and reply.startswith("No available"):
                    state.awaiting_booking_details = True
                    state.last_intent = self.BOOKING_AWAITING_TIME
                else:
                    state.awaiting_booking_details = False
                    state.last_intent = IntentType.APPOINTMENT.value
                state.awaiting_pricing_service = False
                state.state_data = {
                    **new_state_data,
                    "requested_day": extracted_day,
                    "requested_time_period": extracted_period,
                }
                db.commit()
                db.refresh(state)

            elif extracted_day and not extracted_period:
                reply = self._reply_ask_time_period(state_data)
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = True
                state.last_intent = self.BOOKING_AWAITING_TIME
                state.state_data = {
                    **state_data,
                    "requested_day": extracted_day,
                }
                db.commit()
                db.refresh(state)

            elif extracted_period and not extracted_day:
                reply = self._reply_ask_day(state_data)
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = True
                state.last_intent = self.BOOKING_AWAITING_DAY
                state.state_data = {
                    **state_data,
                    "requested_time_period": extracted_period,
                }
                db.commit()
                db.refresh(state)

            else:
                reply = self._reply_ask_day(state_data)
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = True
                state.last_intent = self.BOOKING_AWAITING_DAY
                state.state_data = state_data
                db.commit()
                db.refresh(state)

        elif state.awaiting_booking_details and state.last_intent == self.BOOKING_AWAITING_DAY:
            intent = IntentType.APPOINTMENT

            requested_period = extracted_period or (state.state_data or {}).get("requested_time_period")
            requested_day = extracted_day or text.strip().lower()

            if requested_period:
                booking_response, reply, new_state_data = self._book_with_preferences(
                    user_id=sender_id,
                    requested_day=requested_day,
                    requested_period=requested_period,
                    state_data=state_data,
                )
                state.awaiting_pricing_service = False
                if booking_response is None and reply.startswith("No available"):
                    state.awaiting_booking_details = True
                    state.last_intent = self.BOOKING_AWAITING_TIME
                else:
                    state.awaiting_booking_details = False
                    state.last_intent = IntentType.APPOINTMENT.value
                state.state_data = {
                    **new_state_data,
                    "requested_day": requested_day,
                    "requested_time_period": requested_period,
                }
            else:
                reply = self._reply_ask_time_period(state_data)
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = True
                state.last_intent = self.BOOKING_AWAITING_TIME
                state.state_data = {
                    **state_data,
                    "requested_day": requested_day,
                }

            db.commit()
            db.refresh(state)

        elif state.awaiting_booking_details and state.last_intent == self.BOOKING_AWAITING_TIME:
            intent = IntentType.APPOINTMENT

            requested_day = (state.state_data or {}).get("requested_day", "tomorrow")

            if explicit_slot:
                booking_response, reply = self._book_explicit_slot(
                    user_id=sender_id,
                    requested_day=explicit_slot["day"],
                    requested_time=explicit_slot["time"],
                    state_data=state_data,
                )
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = False
                state.last_intent = IntentType.APPOINTMENT.value
                state.state_data = {
                    **state_data,
                    "requested_day": explicit_slot["day"],
                    "requested_time": explicit_slot["time"],
                    "last_offered_slots": [],
                }
            elif offered_slot_selection:
                booking_response, reply = self._book_explicit_slot(
                    user_id=sender_id,
                    requested_day=offered_slot_selection["day"],
                    requested_time=offered_slot_selection["time"],
                    state_data=state_data,
                )
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = False
                state.last_intent = IntentType.APPOINTMENT.value
                state.state_data = {
                    **state_data,
                    "requested_day": offered_slot_selection["day"],
                    "requested_time": offered_slot_selection["time"],
                    "last_offered_slots": [],
                }
            else:
                requested_period = extracted_period or text.strip().lower()

                booking_response, reply, new_state_data = self._book_with_preferences(
                    user_id=sender_id,
                    requested_day=requested_day,
                    requested_period=requested_period,
                    state_data=state_data,
                )
                state.awaiting_pricing_service = False
                if booking_response is None and reply.startswith("No available"):
                    state.awaiting_booking_details = True
                    state.last_intent = self.BOOKING_AWAITING_TIME
                else:
                    state.awaiting_booking_details = False
                    state.last_intent = IntentType.APPOINTMENT.value
                state.state_data = {
                    **new_state_data,
                    "requested_day": requested_day,
                    "requested_time_period": requested_period,
                }
            db.commit()
            db.refresh(state)

        elif state.awaiting_pricing_service and (self._looks_like_service_name(lowered) or detected_service):
            intent = IntentType.PRICING_INQUIRY
            service_name = self._normalize_service_key(detected_service or text.strip())
            reply = self._build_service_pricing_reply(db, service_name)
            state.awaiting_pricing_service = False
            state.awaiting_booking_details = False
            state.state_data = {
                **state_data,
                "last_service": service_name,
            }
            state.last_intent = IntentType.PRICING_INQUIRY.value
            db.commit()
            db.refresh(state)

        elif self._is_greeting(lowered):
            intent = IntentType.OTHER
            reply = self._reply_greeting()
            state.awaiting_pricing_service = False
            state.awaiting_booking_details = False
            state.state_data = state_data
            state.last_intent = IntentType.OTHER.value
            db.commit()
            db.refresh(state)

        elif self._is_pricing_question(lowered):
            intent = IntentType.PRICING_INQUIRY
            remembered_service = state_data.get("last_service")

            if detected_service:
                normalized_service = self._normalize_service_key(detected_service)
                reply = self._build_service_pricing_reply(db, normalized_service)
                state.awaiting_pricing_service = False
                state.state_data = {
                    **state_data,
                    "last_service": normalized_service,
                }
            elif remembered_service:
                normalized_service = self._normalize_service_key(remembered_service)
                reply = self._build_service_pricing_reply(db, normalized_service)
                state.awaiting_pricing_service = False
                state.state_data = {
                    **state_data,
                    "last_service": normalized_service,
                }
            else:
                reply = self._reply_ask_service_for_pricing()
                state.awaiting_pricing_service = True
                state.state_data = state_data

            state.awaiting_booking_details = False
            state.last_intent = IntentType.PRICING_INQUIRY.value
            db.commit()
            db.refresh(state)

        elif self._is_hours_question(lowered):
            intent = IntentType.WORKING_HOURS
            reply = self._reply_ask_hours_detail()
            state.awaiting_pricing_service = False
            state.awaiting_booking_details = False
            state.state_data = state_data
            state.last_intent = IntentType.WORKING_HOURS.value
            db.commit()
            db.refresh(state)

        else:
            intent, reply = self._ai_classify_and_reply(text)

            if detected_service:
                normalized_service = self._normalize_service_key(detected_service)
                state_data = {
                    **state_data,
                    "last_service": normalized_service,
                }

            if intent == IntentType.PRICING_INQUIRY:
                remembered_service = detected_service or state_data.get("last_service")
                if remembered_service:
                    normalized_service = self._normalize_service_key(remembered_service)
                    reply = self._build_service_pricing_reply(db, normalized_service)
                    state.awaiting_pricing_service = False
                    state_data = {
                        **state_data,
                        "last_service": normalized_service,
                    }
                else:
                    reply = self._reply_ask_service_for_pricing()
                    state.awaiting_pricing_service = True
            elif intent == IntentType.APPOINTMENT:
                reply = self._reply_ask_day(state_data)
                state.awaiting_pricing_service = False
                state.awaiting_booking_details = True
                state.last_intent = self.BOOKING_AWAITING_DAY
                state.state_data = state_data
                db.commit()
                db.refresh(state)

                return ChannelMessageResponseSchema(
                    channel="facebook",
                    status=MessageStatus.AUTO_SEND,
                    intent=intent,
                    reply=reply,
                    booking=booking_response,
                    retrieved_docs=[],
                    error_code=None,
                    error_message=None,
                    metadata={
                        "sender_id": sender_id,
                        "conversation_id": conversation_id,
                        "channel_message_id": normalized_message.channel_message_id,
                    },
                )
            else:
                state.awaiting_pricing_service = False

            state.awaiting_booking_details = False
            state.state_data = state_data
            state.last_intent = intent.value
            db.commit()
            db.refresh(state)

        return ChannelMessageResponseSchema(
            channel="facebook",
            status=MessageStatus.AUTO_SEND,
            intent=intent,
            reply=reply,
            booking=booking_response,
            retrieved_docs=[],
            error_code=None,
            error_message=None,
            metadata={
                "sender_id": sender_id,
                "conversation_id": conversation_id,
                "channel_message_id": normalized_message.channel_message_id,
            },
        )

    def process_message(self, message: dict) -> ChannelMessageResponseSchema:
        sender = str(message.get("from", ""))
        text = (message.get("text") or "").strip()
        is_comment = message.get("is_comment", False)
        msg_type = "comment" if is_comment else "message"

        logger.info("[FACEBOOK] Processing %s from %s", msg_type, sender)

        intent, reply = self._ai_classify_and_reply(text)

        return ChannelMessageResponseSchema(
            channel="facebook",
            status=MessageStatus.AUTO_SEND,
            intent=intent,
            reply=reply,
            booking=None,
            retrieved_docs=[],
            error_code=None,
            error_message=None,
            metadata={
                "sender_id": sender,
                "message_type": msg_type,
            },
        )

    def _get_or_create_state(self, db, conversation_id: str, user_id: str) -> ConversationState:
        state = (
            db.query(ConversationState)
            .filter(ConversationState.conversation_id == conversation_id)
            .first()
        )

        if state:
            return state

        state = ConversationState(
            conversation_id=conversation_id,
            channel="facebook",
            user_id=user_id,
            last_intent=None,
            awaiting_pricing_service=False,
            awaiting_booking_details=False,
            state_data={},
        )
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def _book_with_preferences(
        self,
        user_id: str,
        requested_day: str,
        requested_period: str,
        state_data: dict,
    ):
        available_slots = check_availability(days_ahead=7)

        if not available_slots:
            return None, "No available slots at the moment. Please try again later.", state_data

        filtered_slots = self._filter_slots(
            slots=available_slots,
            requested_day=requested_day,
            time_period=requested_period,
        )

        selected_slot = filtered_slots[0] if filtered_slots else None

        if not selected_slot:
            same_day_alternatives = self._find_alternative_slots_for_day(
                slots=available_slots,
                requested_day=requested_day,
            )

            if same_day_alternatives:
                formatted_same_day = ", ".join(same_day_alternatives[:3])
                new_state_data = {
                    **state_data,
                    "last_offered_slots": [
                        f"{requested_day.title()} {slot}" for slot in same_day_alternatives[:3]
                    ],
                }
                return (
                    None,
                    self._reply_no_same_day_slot(
                        requested_period=requested_period,
                        requested_day=requested_day,
                        formatted_same_day=formatted_same_day,
                        example_slot=f"{requested_day.title()} {same_day_alternatives[0]}",
                    ),
                    new_state_data,
                )

            nearby_alternatives = self._find_next_available_slots(slots=available_slots)

            if nearby_alternatives:
                formatted_nearby = ", ".join(nearby_alternatives[:3])
                new_state_data = {
                    **state_data,
                    "last_offered_slots": nearby_alternatives[:3],
                }
                return (
                    None,
                    self._reply_no_nearby_slot(
                        requested_period=requested_period,
                        requested_day=requested_day,
                        formatted_nearby=formatted_nearby,
                    ),
                    new_state_data,
                )

            return None, "No available slots for that request right now. Please try another option.", state_data

        service_name = state_data.get("last_service")
        booking = book_slot(
            customer_email=user_id,
            slot=selected_slot,
            channel="facebook",
            notes=self._build_booking_notes(
                service_name=service_name,
                requested_day=requested_day,
                requested_time=requested_period,
            ),
        )

        booking_response = self._to_booking_schema(booking)
        reply = self._build_booking_reply(booking, service_name=service_name)
        new_state_data = {
            **state_data,
            "last_offered_slots": [],
        }
        return booking_response, reply, new_state_data

    def _extract_booking_entities(self, text: str):
        day = None
        period = None

        if "today" in text:
            day = "today"
        elif "tomorrow" in text:
            day = "tomorrow"
        else:
            weekdays = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            for weekday in weekdays:
                if weekday in text:
                    day = weekday
                    break

        if "morning" in text:
            period = "morning"
        elif "afternoon" in text:
            period = "afternoon"

        return day, period

    def _extract_explicit_slot_selection(self, text: str):
        lowered = text.strip().lower()
        match = re.search(
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b\s+(\d{1,2}:\d{2})\b",
            lowered,
        )
        if not match:
            return None

        return {
            "day": match.group(1),
            "time": match.group(2),
        }

    def _extract_offered_slot_selection(self, text: str, state_data: dict):
        offered_slots = state_data.get("last_offered_slots") or []
        if not offered_slots:
            return None

        lowered = text.strip().lower()

        ordered_patterns = [
            (r"\bsecond one\b", 1),
            (r"\b2nd one\b", 1),
            (r"\bsecond\b", 1),
            (r"\b2\b", 1),
            (r"\btwo\b", 1),
            (r"\bthird one\b", 2),
            (r"\b3rd one\b", 2),
            (r"\bthird\b", 2),
            (r"\b3\b", 2),
            (r"\bthree\b", 2),
            (r"\bfirst one\b", 0),
            (r"\b1st one\b", 0),
            (r"\bfirst\b", 0),
            (r"\b1\b", 0),
            (r"\bone\b", 0),
        ]

        for pattern, index in ordered_patterns:
            if re.search(pattern, lowered):
                if index < len(offered_slots):
                    return self._slot_string_to_selection(offered_slots[index])

        if any(
            phrase in lowered
            for phrase in [
                "book that one",
                "take that one",
                "that one",
                "book it",
                "take it",
                "yes book it",
                "yes take it",
                "book that one please",
                "that works",
                "this works",
                "lets do that",
                "let's do that",
                "okay book that",
                "ok book that",
            ]
        ):
            return self._slot_string_to_selection(offered_slots[0])

        time_only_match = re.search(r"\b(\d{1,2}:\d{2})\b", lowered)
        if time_only_match:
            requested_time = time_only_match.group(1)
            for offered_slot in offered_slots:
                if requested_time in offered_slot.lower():
                    return self._slot_string_to_selection(offered_slot)

        works_match = re.search(r"\b(\d{1,2}:\d{2})\s+(works|is fine|sounds good|is good)\b", lowered)
        if works_match:
            requested_time = works_match.group(1)
            for offered_slot in offered_slots:
                if requested_time in offered_slot.lower():
                    return self._slot_string_to_selection(offered_slot)

        for offered_slot in offered_slots:
            if lowered == offered_slot.lower():
                return self._slot_string_to_selection(offered_slot)

        return None

    def _slot_string_to_selection(self, slot_string: str):
        match = re.search(
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b\s+(\d{1,2}:\d{2})\b",
            slot_string.strip().lower(),
        )
        if not match:
            return None

        return {
            "day": match.group(1),
            "time": match.group(2),
        }

    def _book_explicit_slot(self, user_id: str, requested_day: str, requested_time: str, state_data: dict):
        available_slots = check_availability(days_ahead=7)
        target_date = self._resolve_requested_date(requested_day.strip().lower())

        if not available_slots or not target_date:
            return None, "No available slots at the moment. Please try again later."

        selected_slot = None
        for slot in available_slots:
            slot_dt = self._coerce_to_datetime(slot)
            if not slot_dt:
                continue

            if slot_dt.date() != target_date.date():
                continue

            if slot_dt.strftime("%H:%M") == requested_time:
                selected_slot = slot
                break

        if not selected_slot:
            same_day_alternatives = self._find_alternative_slots_for_day(
                slots=available_slots,
                requested_day=requested_day,
            )
            if same_day_alternatives:
                formatted_same_day = ", ".join(same_day_alternatives[:3])
                return (
                    None,
                    f"{requested_day.title()} {requested_time} is not available. Available options on {requested_day}: {formatted_same_day}.",
                )
            return None, f"{requested_day.title()} {requested_time} is not available. Please try another option."

        service_name = state_data.get("last_service")
        booking = book_slot(
            customer_email=user_id,
            slot=selected_slot,
            channel="facebook",
            notes=self._build_booking_notes(
                service_name=service_name,
                requested_day=requested_day,
                requested_time=requested_time,
            ),
        )

        booking_response = self._to_booking_schema(booking)
        reply = self._build_booking_reply(booking, service_name=service_name)
        return booking_response, reply

    def _build_booking_notes(self, service_name: Optional[str], requested_day: str, requested_time: str) -> str:
        if service_name:
            return f"FB booking: {service_name}, {requested_day}, {requested_time}"
        return f"FB booking: {requested_day}, {requested_time}"

    def _reply_default(self) -> str:
        return "Thanks for reaching out. How can I help you today?"

    def _reply_greeting(self) -> str:
        return "Hello. How can I help you today?"

    def _reply_ask_day(self, state_data: dict) -> str:
        service_name = state_data.get("last_service")
        if service_name:
            return f"Sure — for your {service_name}, what day works best for you?"
        return "Sure — what day works best for you?"

    def _reply_ask_time_period(self, state_data: dict) -> str:
        service_name = state_data.get("last_service")
        if service_name:
            return f"Got it — for your {service_name}, do you prefer morning or afternoon?"
        return "Got it — do you prefer morning or afternoon?"

    def _reply_ask_service_for_pricing(self) -> str:
        return "Please tell me which service you are interested in, and I will check the pricing details for you."

    def _reply_ask_hours_detail(self) -> str:
        return "Please let me know which day or time you are asking about, and I will help with the hours."

    def _reply_no_same_day_slot(
        self,
        requested_period: str,
        requested_day: str,
        formatted_same_day: str,
        example_slot: str,
    ) -> str:
        return (
            f"No available {requested_period} slots for {requested_day}. "
            f"Available options on {requested_day}: {formatted_same_day}. "
            f"Reply with one option using the day and time, for example: {example_slot}."
        )

    def _reply_no_nearby_slot(
        self,
        requested_period: str,
        requested_day: str,
        formatted_nearby: str,
    ) -> str:
        return (
            f"No available {requested_period} slots for {requested_day}. "
            f"Nearest available options: {formatted_nearby}. "
            f"Reply with one option exactly as written."
        )

    def _filter_slots(self, slots, requested_day: str, time_period: str):
        requested_day_normalized = requested_day.strip().lower()
        period_normalized = time_period.strip().lower()

        target_date = self._resolve_requested_date(requested_day_normalized)
        filtered = []

        for slot in slots:
            slot_dt = self._coerce_to_datetime(slot)
            if not slot_dt:
                continue

            if target_date and slot_dt.date() != target_date.date():
                continue

            if period_normalized == "morning" and slot_dt.hour >= 12:
                continue
            if period_normalized == "afternoon" and slot_dt.hour < 12:
                continue

            filtered.append(slot)

        return filtered

    def _find_alternative_slots_for_day(self, slots, requested_day: str):
        requested_day_normalized = requested_day.strip().lower()
        target_date = self._resolve_requested_date(requested_day_normalized)
        alternatives = []

        for slot in slots:
            slot_dt = self._coerce_to_datetime(slot)
            if not slot_dt:
                continue

            if target_date and slot_dt.date() != target_date.date():
                continue

            alternatives.append(self._format_slot_for_user(slot_dt))

        return alternatives

    def _find_next_available_slots(self, slots):
        collected = []

        for slot in slots:
            slot_dt = self._coerce_to_datetime(slot)
            if not slot_dt:
                continue

            collected.append(self._format_slot_with_day_for_user(slot_dt))

        return collected

    def _format_slot_for_user(self, slot_dt: datetime) -> str:
        return slot_dt.strftime("%H:%M")

    def _format_slot_with_day_for_user(self, slot_dt: datetime) -> str:
        return slot_dt.strftime("%A %H:%M")

    def _resolve_requested_date(self, requested_day: str):
        now = datetime.utcnow()

        if requested_day == "today":
            return now
        if requested_day == "tomorrow":
            return now + timedelta(days=1)

        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        if requested_day not in weekdays:
            return None

        target_weekday = weekdays[requested_day]
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return now + timedelta(days=days_ahead)

    def _coerce_to_datetime(self, slot):
        if isinstance(slot, datetime):
            return slot

        if isinstance(slot, str):
            try:
                return datetime.fromisoformat(slot)
            except ValueError:
                return None

        return None

    def _looks_like_service_name(self, text: str) -> bool:
        known_services = {
            "plumbing",
            "drain cleaning",
            "pipe repair",
            "leak repair",
            "water heater",
            "installation",
            "maintenance",
            "leak",
        }
        return text in known_services or len(text.split()) <= 3

    def _extract_service_name(self, text: str):
        known_services = [
            "leak repair",
            "drain cleaning",
            "pipe repair",
            "water heater service",
            "water heater",
            "installation",
            "maintenance",
            "plumbing",
            "leak",
            "drain",
            "pipe",
            "heater",
            "toilet repair",
            "emergency plumbing",
            "kitchen drain unclogging",
            "pipe installation",
            "bathroom plumbing",
            "water leak detection",
            "sewer line repair",
            "radiator installation",
            "pipe insulation",
            "gas line inspection",
        ]

        for service in known_services:
            if service in text:
                return service

        return None

    def _build_service_pricing_reply(self, db, service_name: str) -> str:
        service = self._normalize_service_key(service_name)
        kb_entry = self._find_service_kb_entry(db, service)

        if kb_entry:
            return self._format_service_pricing_reply(service, kb_entry)

        return (
            f"For {service} services, pricing depends on the issue type, required materials, "
            f"and visit scope. Please describe the problem in a bit more detail so we can provide an estimate."
        )

    def _find_service_kb_entry(self, db, service_name: str):
        normalized_service = self._normalize_service_key(service_name)

        service_rows = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.kb_field == "service",
                KnowledgeBase.is_active.is_(True),
            )
            .all()
        )

        exact_match = None
        partial_match = None

        for row in service_rows:
            item_key = (row.item_key or "").strip().lower()
            normalized_item_key = self._normalize_service_key(item_key)

            if normalized_item_key == normalized_service:
                exact_match = row
                break

            if normalized_service in normalized_item_key or normalized_item_key in normalized_service:
                partial_match = partial_match or row

        return exact_match or partial_match

    def _normalize_service_key(self, value: str) -> str:
        normalized = value.strip().lower().replace("_", " ")
        synonym_map = {
            "leak": "leak repair",
            "repair leak": "leak repair",
            "fix leak": "leak repair",
            "water leak": "leak repair",
            "pipe": "pipe repair",
            "drain": "drain cleaning",
            "heater": "water heater service",
            "water heater": "water heater service",
            "pipe installation": "pipe installation",
            "toilet repair": "toilet repair",
            "emergency plumbing": "emergency plumbing",
            "kitchen drain unclogging": "kitchen drain unclogging",
            "bathroom plumbing": "bathroom plumbing",
            "water leak detection": "water leak detection",
            "sewer line repair": "sewer line repair",
            "radiator installation": "radiator installation",
            "pipe insulation": "pipe insulation",
            "gas line inspection": "gas line inspection",
        }
        return synonym_map.get(normalized, normalized)

    def _format_service_pricing_reply(self, requested_service: str, kb_entry) -> str:
        detail = kb_entry.detail or {}

        if isinstance(detail, str):
            return detail

        service_name = (
            detail.get("name")
            or detail.get("service_name")
            or requested_service.strip().title()
        )

        price = (
            detail.get("price")
            or detail.get("service_price")
            or detail.get("starting_price")
            or detail.get("base_price")
        )

        description = (
            detail.get("description")
            or detail.get("service_description")
            or detail.get("details")
            or detail.get("summary")
        )

        duration = detail.get("duration") or detail.get("estimated_duration")

        if price and description and duration:
            return (
                f"{service_name} pricing starts at {price}. "
                f"{description} Estimated duration: {duration}."
            )

        if price and description:
            return f"{service_name} pricing starts at {price}. {description}"

        if price:
            return f"{service_name} pricing starts at {price}. Let me know if you want a more exact estimate."

        if description:
            return (
                f"{service_name}: {description} "
                f"Pricing depends on the exact issue and materials required."
            )

        return (
            f"For {requested_service.strip()} services, pricing depends on the issue type, "
            f"required materials, and visit scope."
        )

    def _is_booking_intent(self, text: str) -> bool:
        booking_keywords = [
            "book",
            "booking",
            "appointment",
            "schedule",
            "reserve",
            "visit",
        ]
        return any(keyword in text for keyword in booking_keywords)

    def _is_greeting(self, text: str) -> bool:
        greeting_keywords = [
            "hello",
            "hi",
            "hey",
        ]
        return any(keyword in text for keyword in greeting_keywords)

    def _is_pricing_question(self, text: str) -> bool:
        pricing_keywords = [
            "price",
            "pricing",
            "cost",
            "how much",
            "estimate",
            "quote",
        ]
        return any(keyword in text for keyword in pricing_keywords)

    def _is_hours_question(self, text: str) -> bool:
        hours_keywords = [
            "hours",
            "open",
            "close",
            "when",
        ]
        return any(keyword in text for keyword in hours_keywords)

    def _ai_classify_and_reply(self, text: str):
        if not self.ai_client:
            return IntentType.FAQ, "Thanks for your message. Could you please provide a bit more detail?"

        try:
            prompt = f"""
You are a business messaging assistant.

Classify the user's message into exactly one of these intents:
- price_inquiry
- working_hours_inquiry
- appointment_booking_request
- general_faq_question
- other

Return strict JSON with this schema:
{{
  "intent": "...",
  "reply": "..."
}}

User message:
{text}
"""
            response = self.ai_client.responses.create(
                model=self.ai_model,
                input=prompt,
            )

            raw_text = getattr(response, "output_text", "") or ""
            parsed = json.loads(raw_text)

            intent_str = parsed.get("intent", "general_faq_question")
            reply = parsed.get("reply", "Thanks for your message. Could you please clarify your request?")

            intent_map = {
                "price_inquiry": IntentType.PRICING_INQUIRY,
                "working_hours_inquiry": IntentType.WORKING_HOURS,
                "appointment_booking_request": IntentType.APPOINTMENT,
                "general_faq_question": IntentType.FAQ,
                "other": IntentType.OTHER,
            }

            return intent_map.get(intent_str, IntentType.FAQ), reply

        except Exception as exc:
            logger.exception("[FACEBOOK AI] Fallback used due to error: %s", exc)
            return IntentType.FAQ, "Thanks for your message. Could you please provide a bit more detail?"

    def _to_booking_schema(self, booking) -> BookingResponseSchema:
        return BookingResponseSchema(
            id=str(booking.get("booking_id") or booking.get("id") or "N/A"),
            slot=str(booking.get("slot") or booking.get("scheduled_time") or booking.get("time") or ""),
            customer_email=str(booking.get("customer_email") or booking.get("customer") or ""),
            channel=str(booking.get("channel") or "facebook"),
            status=str(booking.get("status") or "confirmed"),
            booked_at=str(booking.get("booked_at") or booking.get("created_at") or ""),
            notes=booking.get("notes"),
        )

    def _build_booking_reply(self, booking, service_name: Optional[str] = None) -> str:
        booking_id = booking.get("booking_id") or booking.get("id") or "N/A"
        slot = booking.get("slot") or booking.get("scheduled_time") or booking.get("time")

        if slot:
            try:
                slot_dt = datetime.fromisoformat(str(slot))
                readable_slot = slot_dt.strftime("%A at %H:%M")
            except ValueError:
                readable_slot = str(slot)
        else:
            readable_slot = None

        normalized_service = self._normalize_service_key(service_name) if service_name else None
        service_label = normalized_service if normalized_service else None

        if service_label and readable_slot:
            return f"Your {service_label} appointment is confirmed for {readable_slot}. Booking ID: {booking_id}."
        if readable_slot:
            return f"Your booking is confirmed for {readable_slot}. Booking ID: {booking_id}."
        return f"Your booking is confirmed. Booking ID: {booking_id}."


def process_facebook_message(message: dict) -> ChannelMessageResponseSchema:
    agent = FacebookAgent()
    return agent.process_message(message)