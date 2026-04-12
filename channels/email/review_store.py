# Store for pending review emails (emergency/escalated)
review_queue = []


def add_email_to_review(email_data: dict):
    """
    Add an email to the review queue.
    
    Args:
        email_data: dict with keys: customer_email, subject, agent_reply, customer_question, 
                   thread_id, message_id, urgency_level, escalation_reason
    """
    global review_queue
    email_data['id'] = len(review_queue)  # Simple ID based on queue position
    review_queue.append(email_data)


def get_review_queue():
    """Get list of all emails pending review."""
    return review_queue


def get_review_email_by_id(email_id: int):
    """Get a specific email from review queue by ID."""
    if 0 <= email_id < len(review_queue):
        return review_queue[email_id]
    return None


def remove_email_from_review(email_id: int):
    """Remove an email from review queue after it's been approved."""
    global review_queue
    if 0 <= email_id < len(review_queue):
        review_queue.pop(email_id)
        # Reindex remaining items
        for i, email in enumerate(review_queue):
            email['id'] = i


def clear_review_queue():
    """Clear all pending reviews."""
    global review_queue
    review_queue = []


# Backward compatibility functions
review_context = None


def save_review_context(data: dict):
    """Backward compatibility - saves single review context"""
    global review_context
    review_context = data


def get_review_context():
    """Backward compatibility - returns single review context"""
    return review_context


def clear_review_context():
    """Backward compatibility - clears single review context"""
    global review_context
    review_context = None
