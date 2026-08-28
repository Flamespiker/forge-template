"""
FORGE — shared Enhancement-target resolution (Item #25 §2.1).

QA (Stage 4) and Security (Stage 5) both need the same concept
implementation_coordinator.py already has (Item #24): for an Enhancement
request, the real scan/test target is the existing services/<existing_service>/
folder, not services/<request_id>/ (which doesn't exist for an Enhancement --
Stage 3 never creates one). Before this module, each stage that needed this
built its own copy inline (Ingestion Agent, then Stage 3) -- this is the third
copy, factored out once rather than duplicated a second time.

Deliberately NOT wired into implementation_coordinator.py itself (Item #25 §3.2):
that script's own inline resolution is already working and live-verified: this
module exists for QA/Security only, which never had this concept before.
"""

from __future__ import annotations


def resolve_service_root(request_id: str, existing_service: str | None) -> str:
    """
    Returns the repo-relative services/<n>/ path QA and Security should treat
    as the real target: services/<existing_service>/ when this is an
    Enhancement request with a resolved existing-service value, else
    services/<request_id>/ (Greenfield, or an Enhancement whose existing
    service name didn't resolve to anything -- same fallback
    implementation_coordinator.py's own inline logic uses).

    existing_service is treated as unset for both None and "" (the workflow
    layer always passes --existing-service, using "" for a Greenfield
    request -- see 03-implementation.yml's own "Determine Enhancement status"
    step, mirrored by 04-qa.yml/05-security.yml).
    """
    return f"services/{existing_service}" if existing_service else f"services/{request_id}"
