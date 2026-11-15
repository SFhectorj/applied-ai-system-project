"""Retrieval half of PawPal+'s RAG pipeline: a small, dependency-free knowledge base.

Entries are scored with TF-IDF cosine similarity against a query, after
filtering by species and age so that irrelevant guidance is never retrieved.
"""

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("pawpal.rag")

DEFAULT_KB_PATH = Path(__file__).parent / "knowledge" / "pet_care.json"
_TOKEN = re.compile(r"[a-z]+")
_STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "for", "is", "are", "with", "on", "at", "as", "be", "can", "it", "their", "that", "this"}


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with stop words removed and trailing 's' stemmed."""
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t
            for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@dataclass(frozen=True)
class Passage:
    id: str
    title: str
    text: str
    species: tuple
    min_age: int
    max_age: int
    keywords: tuple
    recommendation: dict

    def searchable(self) -> str:
        return f"{self.title} {' '.join(self.keywords)} {self.text}"


class KnowledgeBase:
    def __init__(self, passages: list[Passage]) -> None:
        if not passages:
            raise ValueError("knowledge base is empty")
        self.passages = passages
        self._docs = [Counter(tokenize(p.searchable())) for p in passages]
        df = Counter(t for doc in self._docs for t in doc)
        n = len(passages)
        self._idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self._norms = [self._norm(doc) for doc in self._docs]

    @classmethod
    def load(cls, path: Path | str = DEFAULT_KB_PATH) -> "KnowledgeBase":
        """Load and validate a JSON knowledge base file."""
        try:
            raw = json.loads(Path(path).read_text())
            passages = [Passage(
                id=e["id"], title=e["title"], text=e["text"],
                species=tuple(e["species"]), min_age=int(e["min_age"]),
                max_age=int(e["max_age"]), keywords=tuple(e.get("keywords", [])),
                recommendation=dict(e["recommendation"])) for e in raw]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"could not load knowledge base {path}: {exc}") from exc
        log.info("loaded %d knowledge passages from %s", len(passages), path)
        return cls(passages)

    def _norm(self, doc: Counter) -> float:
        return math.sqrt(sum((c * self._idf.get(t, 1.0)) ** 2 for t, c in doc.items())) or 1.0

    def retrieve(self, query: str, species: str, age: int, k: int = 5,
                 min_score: float = 0.05) -> list[tuple[Passage, float]]:
        """Top-k passages for a pet, as (passage, score) best first.

        Passages are first filtered to the pet's species and age range, then
        ranked by TF-IDF cosine similarity to the query. Scores below
        min_score are dropped so weak matches never reach the model.
        """
        q = Counter(tokenize(query))
        q_norm = math.sqrt(sum((c * self._idf.get(t, 1.0)) ** 2 for t, c in q.items())) or 1.0
        scored = []
        for p, doc, norm in zip(self.passages, self._docs, self._norms):
            if species not in p.species and "all" not in p.species:
                continue
            if not p.min_age <= age <= p.max_age:
                continue
            dot = sum(c * self._idf.get(t, 1.0) * doc[t] * self._idf.get(t, 1.0)
                      for t, c in q.items() if t in doc)
            score = dot / (q_norm * norm)
            if score >= min_score:
                scored.append((p, score))
        scored.sort(key=lambda x: -x[1])
        log.debug("query=%r species=%s age=%s -> %s", query, species, age,
                  [(p.id, round(s, 3)) for p, s in scored[:k]])
        return scored[:k]
