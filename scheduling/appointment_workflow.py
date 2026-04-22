import logging
from datetime import datetime
from typing import Optional, Dict, Any

from channels.email.booking_email_sender import get_booking_email_sender
from scheduling.llm_booking_assistant import get_booking_assistant
from scheduling.scheduler import check_availability, book_slot


logger = logging.getLogger(__name__)


class EmailAppointmentWorkflow:
    """
    Encapsulates appointment lifecycle operations for the email channel.

    This component centralizes slot selection, booking confirmation, cancellation handling, and rescheduling updates 
    so EmailAgent can remain focused on orchestration (intent/urgency routing and response assembly).

    The class is state-light and depends on two collaborators:
    - scheduling_config: provides booking horizon and scheduling constraints.
    - booking_manager: executes appointment mutations in persistent storage.
    """

    def __init__(self, scheduling_config, booking_manager):
        """
        Initialize workflow dependencies.
        """
        self.scheduling_config = scheduling_config
        self.booking_manager = booking_manager

    def select_appointment_slot(
        self,
        customer_email: str,
        email_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best appropriate appointment slot for a new booking request.

        Flow:
        1. Query open slots within configured booking horizon.
        2. Delegate ranking/selection to the LLM booking assistant.
        3. Return one chosen slot plus model reasoning.

        Args:
            customer_email: Customer identifier used by the selector context.
            email_text: Raw customer message used to infer preferences.

        Returns:
            A dictionary with keys:
            - slot: selected datetime string.
            - reasoning: textual rationale from the selection model.
            Returns None when no slots exist or selection fails.
        """
        try:
            available_slots = check_availability(
                days_ahead=self.scheduling_config.advance_booking_days
            )

            if not available_slots:
                logger.warning(f"email - no available slots for {customer_email}")
                return None

            booking_assistant = get_booking_assistant()
            selected_slot, llm_reasoning = booking_assistant.select_best_appointment_slot(
                customer_email=customer_email,
                email_content=email_text,
                available_slots=available_slots
            )

            if not selected_slot:
                logger.warning(f"email - LLM failed to select slot for {customer_email}")
                return None

            logger.info(f"email - selected slot: {selected_slot} - Reasoning: {llm_reasoning}")

            return {
                "slot": selected_slot,
                "reasoning": llm_reasoning
            }

        except Exception as e:
            logger.error(f"Error in select_best_appointment_slot: {e}", exc_info=True)
            return None

    def handle_booking_request(
        self,
        customer_email: str,
        message_text: str,
        thread_id: str,
        message_id: str,
        subject: str,
        selected_slot: str,
        reply_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Finalize booking and send confirmation email with calendar invite.

        This method assumes the slot has already been selected earlier in the
        pipeline so the same slot can be reused consistently across response
        text, database state, and ICS content.

        Flow:
        1. Persist booking using scheduler/book_slot.
        2. Compose booking details into final email body.
        3. Send reply email with ICS attachment in the original thread.
        4. Attach delivery status metadata to the returned booking payload.

        Args:
            customer_email: Recipient email address.
            message_text: Original inbound email content (used in booking notes).
            thread_id: Gmail thread id for reply threading.
            message_id: Parent message id for in-reply-to linkage.
            subject: Original subject line (used to build Re: subject).
            selected_slot: Previously selected appointment slot.
            reply_text: LLM-generated response body before details suffix.

        Returns:
            Booking dictionary enriched with:
            - message_id (sent message id on success)
            - confirmation_sent (bool)
            Returns None if booking creation fails or an exception occurs.
        """
        try:
            booking = book_slot(
                customer_email=customer_email,
                slot=selected_slot,
                channel="email",
                notes=f"AI-selected booking from email: {message_text[:100]}",
                days_ahead=self.scheduling_config.advance_booking_days
            )

            if booking.get("status") != "confirmed":
                logger.warning(
                    f"email - booking creation failed for {customer_email}: {booking.get('reason')}"
                )
                return None

            logger.info(
                f"email - booking confirmed: {booking.get('id')} for {customer_email} at {selected_slot}"
            )

            email_sender = get_booking_email_sender()
            customer_name = customer_email.split('@')[0]

            email_body = f"""{reply_text}

---
Appointment Details:
Time: {selected_slot}
Status: Confirmed

To reschedule, please reply directly to this email."""

            success, sent_message_id = email_sender.send_email_reply_with_ics(
                customer_email=customer_email,
                customer_name=customer_name,
                appointment_slot=selected_slot,
                thread_id=thread_id,
                message_id=message_id,
                service_description="Consultation Booking",
                service_duration_minutes=60,
                email_body=email_body,
                subject=f"Re: {subject}"
            )

            if success:
                logger.info(f"email - booking confirmation sent to {customer_email}")
                booking["message_id"] = sent_message_id
                booking["confirmation_sent"] = True
            else:
                logger.warning(f"email - failed to send booking confirmation: {sent_message_id}")
                booking["confirmation_sent"] = False

            return booking

        except Exception as e:
            logger.error(f"Error in handle_booking_request: {e}", exc_info=True)
            return None

    def handle_cancellation_request(
        self,
        customer_email: str,
        email_text: str,
        reply_text: str,
        thread_id: str,
        message_id: str,
        references: str,
        subject: str
    ) -> Dict[str, Any]:
        """
        Process cancellation request and send cancellation confirmation.

        Flow:
        1. Validate booking manager availability.
        2. Cancel current active appointment for the customer.
        3. Build customer-facing cancellation summary.
        4. Send threaded cancellation email (with cancellation ICS behavior delegated to sender implementation).

        Args:
            customer_email: Requesting customer email.
            email_text: Original cancellation request text.
            reply_text: LLM-generated cancellation response text.
            thread_id: Gmail thread id for reply threading.
            message_id: Parent message id for in-reply-to linkage.
            references: Full References chain from inbound message.
            subject: Original subject used for reply continuity.

        Returns:
            Result dictionary from booking/cancellation flow with additional confirmation metadata:
            Returns structured error payload when cancellation cannot be completed.
        """
        try:
            if not self.booking_manager:
                logger.warning("BookingManager not initialized - cannot process cancellation")
                return {
                    "status": "error",
                    "message": "Booking system not available",
                    "details": {}
                }

            cancellation_result = self.booking_manager.cancel_appointment(
                customer_email=customer_email,
                reason=f"Customer requested cancellation via email: {email_text[:100]}",
                channel="email"
            )

            if cancellation_result.get("status") != "success":
                logger.warning(
                    f"email - cancellation request failed for {customer_email}: {cancellation_result.get('message')}"
                )
                return cancellation_result

            logger.info(
                f"email - appointment cancelled for {customer_email}: {cancellation_result.get('message')}"
            )

            email_sender = get_booking_email_sender()
            customer_name = customer_email.split('@')[0]

            email_body = f"""{reply_text}

---
Cancellation Details:
Original Appointment: {cancellation_result['details'].get('original_slot', 'N/A')}
Status: Cancelled
Cancellation Time: {cancellation_result.get('cancelled_at', 'Now').isoformat() if isinstance(cancellation_result.get('cancelled_at'), str) else cancellation_result.get('cancelled_at')}

If you would like to reschedule, please send us a new appointment request."""

            success, new_message_id = email_sender.send_cancellation_confirmation(
                customer_email=customer_email,
                customer_name=customer_name,
                original_slot=cancellation_result['details'].get('original_slot'),
                thread_id=thread_id,
                message_id=message_id,
                original_subject=subject,
                original_references=references,
                email_body=email_body,
                subject=f"Re: {subject}"
            )

            if success:
                logger.info(f"email - cancellation confirmation sent to {customer_email}")
                cancellation_result["confirmation_sent"] = True
                cancellation_result["confirmation_message_id"] = new_message_id
            else:
                logger.warning(f"email - failed to send cancellation confirmation: {new_message_id}")
                cancellation_result["confirmation_sent"] = False

            return cancellation_result

        except Exception as e:
            logger.error(f"Error in handle_cancellation_request: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing cancellation: {str(e)}",
                "details": {}
            }

    def handle_rescheduling_request(
        self,
        customer_email: str,
        email_text: str,
        reply_text: str,
        thread_id: str,
        message_id: str,
        subject: str,
        selected_slot: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reschedule an existing appointment and send updated confirmation.

        Flow:
        1. Validate booking manager availability.
        2. Load current active booking.
        3. Reuse caller-provided selected_slot, or select one if absent.
        4. Apply database reschedule operation (deactivate old, create new).
        5. Send confirmation email with ICS for the new slot.

        Args:
            customer_email: Requesting customer email.
            email_text: Original rescheduling request text.
            reply_text: LLM-generated response text.
            thread_id: Gmail thread id for reply threading.
            message_id: Parent message id for in-reply-to linkage.
            subject: Original subject line for reply continuity.
            selected_slot: Optional preselected slot; when provided, this value
                is used directly to maintain cross-step consistency.

        Returns:
            Structured result payload containing status/message, booking ids,
            old/new slot values, confirmation flag, and details metadata.
            Returns structured error payload if no active booking exists,
            no suitable slot can be selected, or update/send fails.
        """
        try:
            if not self.booking_manager:
                logger.warning("BookingManager not initialized - cannot process rescheduling")
                return {
                    "status": "error",
                    "message": "Booking system not available",
                    "details": {}
                }

            current_booking = self.booking_manager._get_customer_current_booking(
                customer_email=customer_email,
                exclude_inactive=True
            )

            if not current_booking:
                logger.warning(
                    f"email - no active booking found for rescheduling from {customer_email}"
                )
                return {
                    "status": "error",
                    "message": "No active appointment found to reschedule",
                    "details": {}
                }

            logger.info(f"email - found existing booking for {customer_email}: {current_booking.id}")

            if not selected_slot:
                slot_selection_result = self.select_best_reschedule_slot(
                    customer_email=customer_email,
                    email_text=email_text
                )

                if not slot_selection_result:
                    logger.warning(f"email - no available slots for rescheduling {customer_email}")
                    return {
                        "status": "error",
                        "message": "No available slots for rescheduling at this time",
                        "details": {}
                    }

                selected_slot = slot_selection_result["slot"]

            logger.info(f"email - selected new slot for reschedule: {selected_slot}")

            reschedule_result = self.booking_manager.reschedule_appointment(
                customer_email=customer_email,
                new_slot=selected_slot,
                reason="Customer requested reschedule via email",
                channel="email"
            )

            if reschedule_result["status"] != "success":
                logger.error(f"email - reschedule_appointment failed: {reschedule_result}")
                return {
                    "status": "error",
                    "message": reschedule_result.get("message", "Failed to reschedule appointment"),
                    "details": reschedule_result.get("details", {})
                }

            old_booking_id = reschedule_result.get("old_booking_id")
            new_booking_id = reschedule_result.get("new_booking_id")

            logger.info(f"email - reschedule completed: {old_booking_id} -> {new_booking_id}")
            logger.info(
                "email - database now has 2 records: old (is_active=False) and new (is_active=True)"
            )

            email_sender = get_booking_email_sender()
            customer_name = customer_email.split('@')[0]

            new_slot_dt = datetime.fromisoformat(selected_slot)
            readable_time = new_slot_dt.strftime("%A, %B %d, %Y at %I:%M %p")

            confirmation_body = f"""{reply_text}

Your appointment has been rescheduled!

Previous Appointment: {current_booking.slot.strftime('%Y-%m-%d %H:%M')}
New Appointment: {selected_slot}

---
Appointment Details:
Date: {readable_time}
Status: Confirmed (Rescheduled)

A calendar invitation is attached. Please add it to your calendar.

To reschedule again, please reply directly to this email."""

            success, sent_message_id = email_sender.send_email_reply_with_ics(
                customer_email=customer_email,
                customer_name=customer_name,
                appointment_slot=selected_slot,
                thread_id=thread_id,
                message_id=message_id,
                original_subject=subject,
                service_description="Rescheduled Appointment",
                service_duration_minutes=60,
                email_body=confirmation_body,
                subject=f"Re: {subject}"
            )

            if success:
                logger.info(
                    f"email - reschedule confirmation sent to {customer_email} with .ics for {selected_slot}"
                )
            else:
                logger.warning(f"email - failed to send reschedule confirmation: {sent_message_id}")

            return {
                "status": "success",
                "message": f"Appointment successfully rescheduled to {readable_time}",
                "old_booking_id": old_booking_id,
                "new_booking_id": new_booking_id,
                "old_slot": current_booking.slot.isoformat(),
                "new_slot": selected_slot,
                "confirmation_sent": success,
                "details": {
                    "old_booking_id": old_booking_id,
                    "new_booking_id": new_booking_id,
                    "old_slot": current_booking.slot.isoformat(),
                    "new_slot": selected_slot,
                    "customer_email": customer_email,
                    "database_updated": True,
                    "database_status": "Old booking marked inactive, new booking created and linked",
                    "confirmation_email_sent": success
                }
            }

        except Exception as e:
            logger.error(f"Error in handle_rescheduling_request: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing rescheduling: {str(e)}",
                "details": {"error": str(e)}
            }

    def select_best_reschedule_slot(
        self,
        customer_email: str,
        email_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best new slot for rescheduling based on extracted preferences.

        Flow:
        1. Query available slots within configured horizon.
        2. Extract date/time preferences from customer email.
        3. Filter slots according to extracted preferences.
        4. Let booking assistant pick the best candidate from filtered list.
        5. Fallback to first filtered slot if model does not return one.

        Args:
            customer_email: Customer identity for selection context.
            email_text: Customer rescheduling request text.

        Returns:
            A dictionary with keys:
            - slot: chosen replacement slot.
            - reasoning: model or fallback reasoning text.
            Returns None if no availability exists or an unrecoverable error
            occurs during selection.
        """
        try:
            available_slots = check_availability(
                days_ahead=self.scheduling_config.advance_booking_days
            )

            if not available_slots:
                return None

            booking_assistant = get_booking_assistant()
            date_preferences = booking_assistant._extract_date_preferences_from_email(email_text)

            logger.info(
                f"email - extracted date preferences for reschedule: {date_preferences}"
            )

            filtered_slots = booking_assistant._filter_slots_by_preferences(
                available_slots,
                date_preferences
            )

            if not filtered_slots:
                if booking_assistant._has_strict_date_constraints(date_preferences):
                    logger.warning(
                        f"No slots match explicit reschedule preferences: {date_preferences}"
                    )
                    return None

                logger.warning(
                    f"No slots match reschedule preferences: {date_preferences}, using all available slots"
                )
                filtered_slots = available_slots
            else:
                logger.info(
                    f"Filtered {len(available_slots)} slots to {len(filtered_slots)} matching reschedule preferences"
                )

            selected_slot, llm_reasoning = booking_assistant.select_best_appointment_slot(
                customer_email=customer_email,
                email_content=email_text,
                available_slots=filtered_slots
            )

            if not selected_slot:
                logger.warning(
                    "Failed to select best slot for reschedule, using first available"
                )
                selected_slot = filtered_slots[0]
                llm_reasoning = "Using first available matching slot"

            return {
                "slot": selected_slot,
                "reasoning": llm_reasoning
            }

        except Exception as e:
            logger.error(f"Error in select_best_reschedule_slot: {e}", exc_info=True)
            return None
