RuntimeErroreview_context = None


def save_review_context(data: dict):
    global review_context
    review_context = data


def get_review_context():
    return review_context


def clear_review_context():
    global review_context
    review_context = None
