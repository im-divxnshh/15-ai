"""Document store — Firestore when configured, local JSON files otherwise.

Used for: conversations, tasks, audit log, agent state, approvals.
One simple interface so the rest of the code never cares which backend is live.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.settings import settings

log = logging.getLogger("memory.store")

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


class LocalStore:
    def __init__(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)

    def _path(self, collection: str) -> Path:
        p = DATA_DIR / f"{collection}.json"
        p.touch(exist_ok=True)
        return p

    def _load(self, collection: str) -> dict[str, Any]:
        try:
            return json.loads(self._path(collection).read_text() or "{}")
        except json.JSONDecodeError:
            return {}

    def _save(self, collection: str, data: dict[str, Any]) -> None:
        self._path(collection).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        docs = self._load(collection)
        docs[doc_id] = data
        self._save(collection, docs)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        return self._load(collection).get(doc_id)

    def list(self, collection: str, where: dict[str, Any] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        docs = self._load(collection)
        out = []
        for doc_id, doc in docs.items():
            if where and any(doc.get(k) != v for k, v in where.items()):
                continue
            out.append({"id": doc_id, **doc})
        out.sort(key=lambda d: str(d.get("created_at", "")), reverse=True)
        return out[:limit]

    def delete(self, collection: str, doc_id: str) -> bool:
        docs = self._load(collection)
        if doc_id in docs:
            del docs[doc_id]
            self._save(collection, docs)
            return True
        return False


class FirestoreStore:
    def __init__(self) -> None:
        import firebase_admin
        from firebase_admin import credentials, firestore

        creds_dict = settings.firebase_credentials_dict()
        if creds_dict:
            cred = credentials.Certificate(creds_dict)
            self.db = firestore.Client(project=settings.firebase_project_id or None, credentials=cred)
        elif settings.firebase_project_id:
            cred = credentials.ApplicationDefault()
            self.db = firestore.Client(project=settings.firebase_project_id)
        else:
            raise RuntimeError("Firebase not configured")
        log.info("Firestore store ready")

    def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        self.db.collection(collection).document(doc_id).set(data, merge=True)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        snap = self.db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def list(self, collection: str, where: dict[str, Any] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        q = self.db.collection(collection)
        if where:
            for k, v in where.items():
                q = q.where(k, "==", v)
        snaps = q.limit(limit).stream()
        out = []
        for s in snaps:
            out.append({"id": s.id, **(s.to_dict() or {})})
        out.sort(key=lambda d: str(d.get("created_at", "")), reverse=True)
        return out

    def delete(self, collection: str, doc_id: str) -> bool:
        self.db.collection(collection).document(doc_id).delete()
        return True


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_store():
    if settings.firebase_ready:
        try:
            return FirestoreStore()
        except Exception:  # noqa: BLE001
            log.exception("Firestore init failed, falling back to local JSON store")
    return LocalStore()


store = get_store()
