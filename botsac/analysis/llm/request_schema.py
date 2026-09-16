from pydantic import BaseModel
from typing import List

class RequestAnalysis(BaseModel):
    problem: str
    location: str
    institution: str
    requests: List[str]
    summary: str
