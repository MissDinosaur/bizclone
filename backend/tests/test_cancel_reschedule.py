"""
Tests for appointment cancellation and rescheduling services.
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.scheduling.cancel import CancellationService
from app.services.scheduling.reschedule import RescheduleService
from app.models.appointment import AppointmentStatus, UrgencyLevel
from app.db.crud import (
    create_customer,
    create_call,
    create_appointment,
    get_appointment_by_id,
)
from app.db.base import Base

TEST_DATABASE_URL = "sqlite:///:memory:"
TZ = ZoneInfo("Europe/Berlin")


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_appointment(db_session):
    """Create a single scheduled appointment for testing."""
    customer = create_customer(
        db=db_session,
        phone_number="+15551234567",
        name="John Doe",
    )
    call = create_call(
        db=db_session,
        call_sid="TEST_CANCEL_CALL_001",
        customer_id=customer.id,
        from_number="+15551234567",
        to_number="+15559876543",
        direction="inbound",
    )
    tomorrow = datetime.now(TZ).replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appt = create_appointment(
        db=db_session,
        call_id=call.id,
        customer_id=customer.id,
        scheduled_time_start=tomorrow,
        scheduled_time_end=tomorrow + timedelta(hours=1),
        status=AppointmentStatus.SCHEDULED,
        urgency=UrgencyLevel.MEDIUM,
        service_type="sink_repair",
        contact_name="John Doe",
    )
    return {"appointment": appt, "call": call, "customer": customer}


# ====================================================================
# Cancellation Tests
# ====================================================================

class TestCancellationService:
    """Tests for CancellationService."""

    def test_cancel_by_id_success(self, db_session, sample_appointment):
        svc = CancellationService()
        appt = sample_appointment["appointment"]

        with patch(
            "app.services.scheduling.cancel.delete_calendar_event",
            return_value=False,
        ):
            result = svc.cancel(
                db_session, appointment_id=appt.id
            )

        assert result.success is True
        assert result.appointment_id == appt.id
        assert "cancelled" in result.message.lower()

        # Verify DB status
        refreshed = get_appointment_by_id(db_session, appt.id)
        status_val = (
            refreshed.status.value
            if hasattr(refreshed.status, "value")
            else refreshed.status
        )
        assert status_val == "canceled"

    def test_cancel_not_found(self, db_session):
        svc = CancellationService()
        result = svc.cancel(
            db_session, appointment_id="nonexistent-id"
        )
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_cancel_by_name(self, db_session, sample_appointment):
        svc = CancellationService()

        with patch(
            "app.services.scheduling.cancel.delete_calendar_event",
            return_value=False,
        ):
            result = svc.cancel(
                db_session, customer_name="John Doe"
            )

        assert result.success is True

    def test_cancel_already_cancelled(
        self, db_session, sample_appointment
    ):
        svc = CancellationService()
        appt = sample_appointment["appointment"]

        # Cancel once
        with patch(
            "app.services.scheduling.cancel.delete_calendar_event",
            return_value=False,
        ):
            svc.cancel(db_session, appointment_id=appt.id)

        # Cancel again
        result = svc.cancel(db_session, appointment_id=appt.id)
        assert result.success is False
        assert "already" in result.message.lower()



# ====================================================================
# Reschedule Tests
# ====================================================================

class TestRescheduleService:
    """Tests for RescheduleService."""

    @patch(
        "app.services.scheduling.reschedule.has_conflict",
        return_value=False,
    )
    @patch(
        "app.services.scheduling.reschedule.update_calendar_event",
        return_value=False,
    )
    def test_reschedule_success(
        self, mock_update, mock_conflict,
        db_session, sample_appointment,
    ):
        svc = RescheduleService()
        appt = sample_appointment["appointment"]
        new_time = datetime.now(TZ).replace(
            hour=14, minute=0, second=0, microsecond=0
        ) + timedelta(days=2)

        result = svc.reschedule(
            db_session,
            new_start_time=new_time,
            appointment_id=appt.id,
        )

        assert result.success is True
        assert result.new_start == new_time

        refreshed = get_appointment_by_id(db_session, appt.id)
        # SQLite strips timezone info, so compare naive values
        assert (
            refreshed.scheduled_time_start.replace(tzinfo=None)
            == new_time.replace(tzinfo=None)
        )

    def test_reschedule_not_found(self, db_session):
        svc = RescheduleService()
        new_time = datetime.now(TZ) + timedelta(days=3)

        result = svc.reschedule(
            db_session,
            new_start_time=new_time,
            appointment_id="nonexistent-id",
        )
        assert result.success is False
        assert "not found" in result.message.lower()

    @patch(
        "app.services.scheduling.reschedule.has_conflict",
        return_value=True,
    )
    @patch(
        "app.services.scheduling.reschedule.find_next_available_slot",
        return_value=None,
    )
    @patch(
        "app.services.scheduling.reschedule.update_calendar_event",
        return_value=False,
    )
    def test_reschedule_conflict_no_alternative(
        self, mock_update, mock_find, mock_conflict,
        db_session, sample_appointment,
    ):
        svc = RescheduleService()
        appt = sample_appointment["appointment"]
        # Use a time within business hours so DB check passes
        new_time = datetime.now(TZ).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=2)

        result = svc.reschedule(
            db_session,
            new_start_time=new_time,
            appointment_id=appt.id,
        )
        assert result.success is False
        assert (
            "conflict" in result.message.lower()
            or "not available" in result.message.lower()
        )

    @patch(
        "app.services.scheduling.reschedule.has_conflict",
        return_value=True,
    )
    @patch(
        "app.services.scheduling.reschedule.update_calendar_event",
        return_value=True,
    )
    def test_reschedule_conflict_auto_resolve(
        self, mock_update, mock_conflict,
        db_session, sample_appointment,
    ):
        svc = RescheduleService()
        appt = sample_appointment["appointment"]
        alt_time = datetime.now(TZ).replace(
            hour=15, minute=0, second=0, microsecond=0
        ) + timedelta(days=3)

        with patch(
            "app.services.scheduling.reschedule.find_next_available_slot",
            return_value=alt_time,
        ):
            result = svc.reschedule(
                db_session,
                new_start_time=datetime.now(TZ) + timedelta(days=2),
                appointment_id=appt.id,
            )

        assert result.success is True
        assert result.new_start == alt_time
