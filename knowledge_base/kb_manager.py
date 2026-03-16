import json
import os
from datetime import datetime
import config.config as cfg


class KnowledgeBaseManager:
    """
    Manages structured KB storage + versioning.
    """

    def __init__(self, kb_path=cfg.INITIAL_KB_JSON_PATH):
        self.kb_path = kb_path

        os.makedirs(cfg.KB_VERSIONS_DIR, exist_ok=True)

    def load_kb(self):
        with open(self.kb_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def update_kb(self, updated_data: dict):
        """
        Update KB with version backup.
        """

        # Step 1: Backup old KB
        self._backup_current()

        # Step 2: Write new KB
        with open(self.kb_path, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, indent=2)

        print("Knowledge Base updated successfully.")

    def _backup_current(self):
        """
        Save timestamped version copy.
        """

        if not os.path.exists(self.kb_path):
            print(f"Couldn't find the path: {self.kb_path}")
            return

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{cfg.KB_VERSIONS_DIR}/email_kb_{timestamp}.json"

        with open(self.kb_path, "r", encoding="utf-8") as f:
            old_data = f.read()

        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(old_data)

        print(f"Backup saved: {backup_path}")
