from pydantic import BaseModel
from typing import List


class KnowledgeItem(BaseModel):
    id: str
    category: str
    title: str
    content: str
    tags: List[str] = []
    version: int = 1
