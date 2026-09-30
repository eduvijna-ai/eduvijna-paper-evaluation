#!/usr/bin/env python3
"""Create a minimal ACTIVE assessment on a disposable API for load uploads."""

from __future__ import annotations

import os
import sys
import uuid

import httpx

BASE = os.environ.get("LOAD_TEST_BASE_URL", "http://127.0.0.1:28000").rstrip("/")
EMAIL = os.environ.get("LOAD_TEST_EMAIL", "admin@demo.eduvijna.local")
PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "DemoAdmin!2026")
TENANT = os.environ.get("LOAD_TEST_TENANT", "demo")


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    with httpx.Client(base_url=BASE, timeout=60.0) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD, "tenant_slug": TENANT},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        curriculum = client.post(
            "/api/v1/curricula",
            headers=headers,
            json={
                "code": f"CUR-{suffix}",
                "name": "Mathematics",
                "version_label": "2026",
                "status": "active",
            },
        )
        curriculum.raise_for_status()
        node = client.post(
            f"/api/v1/curricula/{curriculum.json()['id']}/nodes",
            headers=headers,
            json={
                "node_type": "SUBJECT",
                "code": f"MATH-{suffix}",
                "name": "Mathematics",
                "sequence": 1,
                "metadata": {},
                "status": "active",
            },
        )
        node.raise_for_status()
        assessment = client.post(
            "/api/v1/assessments",
            headers=headers,
            json={
                "curriculum_id": curriculum.json()["id"],
                "subject_node_id": node.json()["id"],
                "code": f"ASM-{suffix}",
                "title": "Disposable load assessment",
                "assessment_type": "EXAM",
                "max_marks": "10.00",
                "duration_minutes": 60,
            },
        )
        assessment.raise_for_status()
        assessment_id = assessment.json()["id"]
        versions = client.get(
            f"/api/v1/assessments/{assessment_id}/versions", headers=headers
        )
        versions.raise_for_status()
        version_id = versions.json()[0]["id"]

        leaf = client.post(
            f"/api/v1/assessment-versions/{version_id}/questions",
            headers=headers,
            json={
                "stable_code": f"Q-{suffix[:6]}",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "leaf",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        leaf.raise_for_status()
        qid = leaf.json()["id"]

        key = client.post(
            f"/api/v1/assessments/{assessment_id}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": version_id,
                "question_version_id": qid,
                "answer_text": "ok",
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        key.raise_for_status()
        client.post(
            f"/api/v1/answer-key-versions/{key.json()['id']}/approve", headers=headers
        ).raise_for_status()

        rubric = client.post(
            f"/api/v1/assessments/{assessment_id}/rubrics",
            headers=headers,
            json={
                "question_version_id": qid,
                "title": "R",
                "provenance": "TEACHER",
            },
        )
        rubric.raise_for_status()
        rv = client.post(
            f"/api/v1/rubrics/{rubric.json()['id']}/versions",
            headers=headers,
            json={
                "question_version_id": qid,
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        rv.raise_for_status()
        client.post(
            f"/api/v1/rubric-versions/{rv.json()['id']}/criteria",
            headers=headers,
            json={
                "criterion_code": "C1",
                "description": "d",
                "max_marks": "10.00",
                "sequence": 1,
                "scoring_mode": "ADDITIVE",
                "partial_credit_allowed": True,
                "ecf_policy": "NONE",
            },
        ).raise_for_status()
        client.post(
            f"/api/v1/rubric-versions/{rv.json()['id']}/approve", headers=headers
        ).raise_for_status()

        ready = client.post(
            f"/api/v1/assessments/{assessment_id}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        if ready.status_code >= 400:
            print(f"READY_FAILED {ready.status_code} {ready.text}", file=sys.stderr)
            return 2
        active = client.post(
            f"/api/v1/assessments/{assessment_id}/transition",
            headers=headers,
            json={"to_status": "ACTIVE"},
        )
        active.raise_for_status()
        # stdout: assessment_id\ntoken
        print(assessment_id)
        print(token)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
