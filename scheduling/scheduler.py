def check_availability():
    return ["2026-02-10 10:00", "2026-02-10 14:00"]


def book_slot(customer_email: str, slot: str):
    return {
        "status": "confirmed",
        "slot": slot,
        "customer": customer_email,
    }
