"""Private local SQLite storage, optimistic revisions, and independently retained audit metadata."""

import json
import os
import sqlite3
import time
from pathlib import Path


class ConflictError(ValueError):
    pass


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        self.path = directory / "reviews.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, created REAL NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, review_id TEXT NOT NULL, created REAL NOT NULL, record TEXT NOT NULL);
            """)
        os.chmod(self.path, 0o600)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA secure_delete=ON")
        return db

    def insert(self, state):
        with self.connect() as db:
            db.execute("INSERT INTO reviews VALUES (?, ?, ?, ?)",
                       (state["id"], state["revision"], time.time(), json.dumps(state)))
            self._audit(db, state, "created")

    def get(self, review_id):
        with self.connect() as db:
            row = db.execute("SELECT state FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            raise KeyError("Review not found or expired")
        return json.loads(row[0])

    def list(self, reviewer=None):
        with self.connect() as db:
            rows = db.execute("SELECT state FROM reviews ORDER BY created DESC").fetchall()
        return [{"id": s["id"], "created_at": s["created_at"], "finalized": s["final"] is not None}
                for s in map(lambda r: json.loads(r[0]), rows)
                if reviewer is None or s["reviewer"] == reviewer]

    def save(self, state, expected_revision, action):
        state["revision"] = expected_revision + 1
        with self.connect() as db:
            result = db.execute("UPDATE reviews SET state=?, revision=? WHERE id=? AND revision=?",
                                (json.dumps(state), state["revision"], state["id"], expected_revision))
            if result.rowcount != 1:
                raise ConflictError("Review changed in another tab; reload before saving")
            self._audit(db, state, action)

    def _audit(self, db, state, action):
        # Protected audit data includes override reasons, but never proposal excerpts.
        # It is distinct from operational logs (which are disabled).
        record = {"action": action, "revision": state["revision"], "reviewer": state["reviewer"],
                  "application_hash": state["document"]["document_id"],
                  "extractor_version": state["document"]["extractor_version"],
                  "registry_hash": state["registry_hash"], "policy_hash": state["policy_hash"],
                  "rule_version": state["policy"]["version"],
                  "decisions": {qid: {key: d.get(key) for key in ("model", "model_version", "question_version",
                                "model_answer", "probabilities", "confidence", "evidence_ids", "reviewer_answer",
                                "reviewer_evidence_ids", "reviewer_note", "confirmed", "confirmed_facts_hash", "latency_ms")}
                                for qid, d in state["decisions"].items()},
                  "fact_confirmations": {key: {"confirmed": fact["confirmed"],
                                               "note": fact.get("reviewer_note"),
                                               "evidence_ids": fact.get("reviewer_evidence_ids")}
                                         for key, fact in state["facts"].items()},
                  "final_classification": state["final"]["classification"] if state["final"] else None,
                  "final_rationale": state["final"]["rationale"] if state["final"] else None}
        if state["final"]:
            record["rejection_category"] = state["final"].get("rejection_category")
            record["exception_note"] = state["final"].get("exception_note")
            record["templates_hash"] = state["final"].get("templates_hash")
        db.execute("INSERT INTO audit(review_id, created, record) VALUES (?, ?, ?)",
                   (state["id"], time.time(), json.dumps(record)))

    def audit(self, review_id):
        with self.connect() as db:
            rows = db.execute("SELECT created, record FROM audit WHERE review_id=? ORDER BY id", (review_id,)).fetchall()
        return [{"timestamp": row[0], **json.loads(row[1])} for row in rows]

    def delete(self, review_id):
        with self.connect() as db:
            db.execute("DELETE FROM reviews WHERE id=?", (review_id,))
            db.execute("DELETE FROM audit WHERE review_id=?", (review_id,))

    def purge(self, review_days, audit_days, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            reviews = db.execute("DELETE FROM reviews WHERE created < ?", (now - review_days * 86400,)).rowcount
            audits = db.execute("DELETE FROM audit WHERE created < ?", (now - audit_days * 86400,)).rowcount
        return {"reviews": reviews, "audit_records": audits}
