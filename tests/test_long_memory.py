from __future__ import annotations

from types import SimpleNamespace

import lang_agent.memory.long_memory as long_memory_module
from lang_agent.memory.long_memory import LongMemory


class _FakeCollection:
    def __init__(self) -> None:
        self.records: list[dict] = []

    @staticmethod
    def _match(row: dict, where: dict) -> bool:
        clauses = where.get("$and", [])
        if not clauses:
            return False
        metadata = row["metadata"]
        return all(metadata.get(next(iter(clause))) == next(iter(clause.values())) for clause in clauses)

    def add(self, *, ids, documents, metadatas, embeddings=None) -> None:
        for index, doc in enumerate(documents):
            self.records.append(
                {
                    "id": ids[index],
                    "document": doc,
                    "metadata": metadatas[index],
                    "embedding": embeddings[index] if embeddings else None,
                }
            )

    def query(self, *, query_embeddings, n_results, where):
        docs = [
            row["document"]
            for row in self.records
            if self._match(row, where)
        ][:n_results]
        return {"documents": [docs]}

    def get(self, *, where, include):
        rows = [
            row
            for row in self.records
            if self._match(row, where)
        ]
        return {
            "documents": [row["document"] for row in rows],
            "metadatas": [row["metadata"] for row in rows],
        }


class _FakeClient:
    def __init__(self, collection: _FakeCollection) -> None:
        self.collection = collection

    def get_or_create_collection(self, *, name):
        return self.collection


def test_long_memory_fallback_persists_and_retrieves_without_embeddings(monkeypatch):
    collection = _FakeCollection()
    fake_chromadb = SimpleNamespace(PersistentClient=lambda path: _FakeClient(collection))
    monkeypatch.setattr(long_memory_module, "chromadb", fake_chromadb)
    monkeypatch.setattr(long_memory_module, "build_embeddings", lambda: None)

    memory = LongMemory(chroma_dir=".tmp-chroma-tests")
    memory.add_validated_fix(
        error_type="NameError",
        error_signature="NameError: name 'response' is not defined",
        error_log="traceback",
        fixed_code="assert r.status_code < 500",
        test_file="generated_tests/test_demo.py",
        repair_round=1,
    )

    result = memory.retrieve_few_shots(
        error_type="NameError",
        error_signature="NameError: name 'response' is not defined",
        k=1,
    )

    assert result == ["assert r.status_code < 500"]
    assert collection.records[0]["embedding"] is None
