import json
import os
from datetime import datetime
import config.config as cfg


class FeedbackStore:
    """
    Stores all owner corrections for supervised learning traceability.
    """

    def __init__(self, path=cfg.UPDATES_LOG_PATH):
        self.path = path
        os.makedirs(cfg.KB_UPDATES, exist_ok=True)

    def save(self, feedback_entry: dict):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            **feedback_entry
        }

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        print("Feedback saved into learning log.")
