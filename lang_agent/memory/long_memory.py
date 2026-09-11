from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

try:
    import chromadb
except Exception:  # type: ignore[no-redef]
    chromadb = None  # type: ignore[assignment]

from ..llm.factory import build_embeddings


@dataclass
class LongMemory:
    chroma_dir: str
    collection_name: str = "api_test_agent_fixes"

    @staticmethod
    def _where_clause(error_type: str) -> dict[str, Any]:
        return {
            "$and": [
                {"error_type": error_type},
                {"validated": True},
            ]
        }

    @staticmethod
    def _extract_docs(raw_docs: Any) -> list[str]:
        if not raw_docs:
            return []
        if isinstance(raw_docs, list) and raw_docs and isinstance(raw_docs[0], list):
            raw_docs = raw_docs[0]
        docs: list[str] = []
        for item in raw_docs:
            if isinstance(item, str) and item.strip():
                docs.append(item.strip())
        return docs

    @staticmethod
    def _signature_score(expected: str, actual: str) -> float:
        expected = (expected or "").strip()
        actual = (actual or "").strip()
        if not expected or not actual:
            return 0.0
        return SequenceMatcher(a=expected, b=actual).ratio()

    def _collection(self):
        if chromadb is None:
            raise RuntimeError("chromadb 未安装")
        client = chromadb.PersistentClient(path=self.chroma_dir)
        return client.get_or_create_collection(name=self.collection_name)

    def add_validated_fix(
        self,
        *,
        error_type: str,
        error_signature: str,
        error_log: str,
        fixed_code: str,
        test_file: str,
        repair_round: int,
    ) -> None:
        if chromadb is None:
            return
        embeddings = build_embeddings()

        doc = fixed_code
        meta: dict[str, Any] = {
            "error_type": error_type,
            "error_signature": error_signature,
            "error_log": error_log[-1000:],
            "validated": True,
            "test_file": test_file,
            "repair_round": int(repair_round),
            "ts": int(time.time()),
        }
        _id = str(uuid.uuid4())
        col = self._collection()
        if embeddings is None:
            col.add(ids=[_id], documents=[doc], metadatas=[meta])
            return
        vec = embeddings.embed_documents([doc])[0]
        col.add(ids=[_id], documents=[doc], metadatas=[meta], embeddings=[vec])

    def retrieve_few_shots(self, *, error_type: str, error_signature: str = "", k: int = 3) -> list[str]:
        if chromadb is None:
            return []
        col = self._collection()
        where = self._where_clause(error_type)
        embeddings = build_embeddings()
        if embeddings is not None:
            query_text = "\n".join(x for x in [error_type, error_signature] if x)
            q = embeddings.embed_query(query_text or error_type)
            res = col.query(query_embeddings=[q], n_results=int(k), where=where)
            return self._extract_docs(res.get("documents") or [])

        res = col.get(where=where, include=["documents", "metadatas"])
        docs = self._extract_docs(res.get("documents") or [])
        metas = res.get("metadatas") or []
        ranked: list[tuple[float, int, str]] = []
        for index, doc in enumerate(docs):
            meta = metas[index] if index < len(metas) and isinstance(metas[index], dict) else {}
            score = self._signature_score(error_signature, str(meta.get("error_signature") or ""))
            ranked.append((score, int(meta.get("ts") or 0), doc))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [doc for _, _, doc in ranked[: int(k)]]
