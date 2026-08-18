"""
FORGE Deploy Agent — Stage 6 (Deploy, staging only).

Deploys the built application to the `forge-staging` Azure Container Apps
environment: detects deployable units, generates any missing Dockerfiles,
builds and pushes container images to ACR, and creates/updates one Container
App per unit. Posts one summary PR comment listing each unit's staging URL.

No Claude/invoke_agent call anywhere in this stage — unlike every prior
stage agent, there is no human-facing write-up here that benefits from an
LLM pass. Everything this agent produces (unit detection, Dockerfile
generation, the PR comment) is deterministic string/template work, in the
same spirit as QA's TRX/Jest parsing and Security's severity mapping: no
judgment call exists here that would justify a model call. This is a
deliberate scope decision, not an oversight.

Scope: staging auto-deploy only (Document 3 §9 / FORGE-context v36, chat 33).
Production (GitHub Environment-gated, second service principal) is explicitly
out of scope for this stage — see the module-level TODO markers below for
exactly what's deferred.

Unit detection (deterministic, not an LLM decision — Document 3's "FORGE
automatic, not AI judgment" discipline, same as QA/Security):
  - Walk services/<request-id>/backend/ for *.csproj files, skipping any
    path with a case-insensitive "test" substring in any path segment (same
    convention as team/gitleaks-allowlist.toml's test-path exclusion).
  - Classify each remaining project as "web" (references
    Microsoft.NET.Sdk.Web or Microsoft.AspNetCore.App) or "worker"
    (references Microsoft.Extensions.Hosting, no ASP.NET reference). A
    project matching neither is treated as "worker" (no public ingress) as
    the safer default, logged as a warning — see _classify_backend_unit().
  - Treat services/<request-id>/frontend/package.json as one additional
    "frontend" unit if present.
  - Each unit gets a Container App / image name of
    "<request-id>-<slug>" (all lowercase — both Docker repository names and
    Azure Container App names reject uppercase), its own Dockerfile
    (generated from template ONLY if the project directory doesn't already
    have one of its own — see _generate_dockerfile_if_missing()), its own
    ACR image tag, and its own Container App.

KNOWN, PRE-EXISTING GAP THIS AGENT SURFACES BUT DOES NOT FIX: neither
design.md nor any prior stage ever assigned the EmailWorker unit a
design.md entry (it appears in tasks.md but not design.md — flagged back in
the Stage 3 build, chat 28, and never resolved). Rather than silently deploy
a unit nobody signed off on in the design document, _detect_design_gaps()
flags (does not block) any detected unit whose project label doesn't appear
in docs/<request-id>/design.md, surfaced in the PR comment.

TARGET PORTS (fixed, not configurable per-run): web units listen on 8080
(matching the ASP.NET Core 8+ container default and this project's existing
hand-written Dockerfiles for DocumentApi/EmailWorker), frontend units on
3000 (Next.js default `next start` port). Worker units get no ingress at
all — Document 3 doesn't call for background workers to be reachable over
HTTP.

Like QA and Security, this script needs the actual repository contents on
disk (passed via --repo-path) — it does not clone anything itself.

Required environment variables (see .env.example):
    ACR_LOGIN_SERVER, ACR_USERNAME, ACR_PASSWORD — existing ACR admin-user
        credentials (Phase 2.2), unchanged, no new secrets introduced here.
    AZURE_STAGING_CREDENTIALS — one JSON blob with clientId/clientSecret/
        subscriptionId/tenantId for the `forge-deploy-staging` service
        principal (Document 3 §9, finalized chat 33). Parsed here, not by
        the caller — arrives as a single secret in both local .env and the
        eventual GitHub Actions secret.

Reads container_apps.staging (environment, resource_group, max_replicas,
min_replicas, cpu, memory) from team/config.yaml via file_io.read_yaml() —
same config file ado_helper.py already reads at import time, different
top-level key.

Usage:
    python -m core.agents.deploy_agent --issue-number 2 --request-id REQ-2026-01 \\
        --repo-path /path/to/forge-demo-apps-checkout --commit-sha <sha> --pr-number 5
    python -m core.agents.deploy_agent --issue-number 2 --request-id REQ-2026-01 \\
        --repo-path /path/to/forge-demo-apps-checkout --commit-sha <sha> --pr-number 5 --dry-run

CLI arguments:
    --issue-number   FORGE tracking issue number in forge-template, used to
                     post a failure comment (best-effort) on error (required).
    --request-id     FORGE request ID. Used to locate services/<request-id>/
                     within --repo-path and docs/<request-id>/design.md
                     (required).
    --repo-path      Local path to an existing checkout of forge-demo-apps at
                     the feature branch (required — this script does not
                     clone anything itself).
    --commit-sha     The commit SHA being deployed — used as the image tag
                     and included in the PR comment (required).
    --pr-number      The feature PR number in forge-demo-apps, used to post
                     the summary comment (required).
    --dry-run        Run real `docker build`/`docker push` (same "exercise
                     the real tool, skip only the posting" pattern as QA/
                     Security dry-runs) and real read-only `az` queries
                     (login, containerapp show, FQDN lookup), but print the
                     planned `az containerapp create`/`update` command
                     instead of executing it, and post nothing to the PR.

Per ADR-0011 / Document 6: the deploy body is wrapped in try/except at the
call site. On failure, a failure comment is posted to the tracking issue
(best-effort, real run only) before the exception is re-raised.

No label is applied on success — Document 6's Label Reference table has no
deploy-stage label; staging is a verification step, not a release gate
(Build Plan 4.7 / Document 2 §4.8).

EXPLICITLY OUT OF SCOPE for this stage (not built, not stubbed):
  - Production path (second service principal, GitHub Environment approval
    gate, `az containerapp update` against forge-production).
  - Rollback (redeploy prior image tag).
  - Phase 4 GitHub Actions wiring for either environment.
  - Actually resolving the EmailWorker design.md gap (flagged, not fixed).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from core.agents.utils import file_io
from core.agents.utils.github_helper import get_file_contents, post_comment, post_pr_comment

load_dotenv()

logger = logging.getLogger(__name__)

_STAGE_NAME = "deploy"
_SHELL_TIMEOUT_SECONDS = 1800  # 30 min ceiling per docker/az invocation

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "core" / "agents" / "templates" / "dockerfiles"
_CONFIG_PATH = _REPO_ROOT / "team" / "config.yaml"

_TARGET_PORTS = {"web": 8080, "frontend": 3000}  # worker units get no ingress at all
_SENSITIVE_FLAGS = {"--registry-password", "-p"}  # redacted before logging/printing

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")
_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")
_VALID_CONTAINER_APP_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# Azure CLI's own stated constraint (`az containerapp create --help`, confirmed
# live 2026-08-17): "must be less than 32 characters" -- i.e. len < 32, not <=.
_MAX_CONTAINER_APP_NAME_LEN = 32


@dataclass
class DeployUnit:
    slug: str                # e.g. "document-api", "email-worker", "frontend"
    unit_type: str            # "web" | "worker" | "frontend"
    name: str                 # Container App / image name: "<request-id>-<slug>" (lowercase)
    project_label: str        # human label for the design.md gap check, e.g. "DocumentApi"
    dockerfile_path: Path
    build_context: Path
    csproj_name: str | None = None
    dockerfile_generated: bool = False


@dataclass
class DeployResult:
    unit: DeployUnit
    image: str
    action: str = ""           # "create" | "update" -- "" if it failed before a command was built
    command: list[str] = field(default_factory=list)
    executed: bool = False
    fqdn: str | None = None
    error: str | None = None   # set if this unit's build/push/deploy failed; other units still proceed


def _run_shell(
    command: list[str],
    cwd: str,
    input_text: str | None = None,
    timeout: int = _SHELL_TIMEOUT_SECONDS,
    log_override: str | None = None,
) -> subprocess.CompletedProcess:
    logger.info("Running: %s (cwd=%s)", log_override or " ".join(command), cwd)
    resolved = shutil.which(command[0]) or command[0]
    return subprocess.run(
        [resolved, *command[1:]],
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _redact_command(command: list[str]) -> list[str]:
    redacted = list(command)
    for i, token in enumerate(redacted):
        if token in _SENSITIVE_FLAGS and i + 1 < len(redacted):
            redacted[i + 1] = "***"
    return redacted


def _slugify(name: str) -> str:
    """
    'DocumentApi' -> 'document-api', 'EmailWorker' -> 'email-worker',
    'OnCallRosterTracker.Api' -> 'on-call-roster-tracker-api', 'frontend' -> 'frontend'.

    Splits on PascalCase word boundaries AND any literal non-alphanumeric
    character (e.g. '.') as equivalent word separators -- both collapse to a
    single '-', then any leading/trailing '-' is stripped. Previously only
    PascalCase boundaries were converted; a literal '.' passed straight
    through untouched, so a project shaped like Foo.Bar produced a stray '.'
    immediately adjacent to the '-' inserted before the next boundary (e.g.
    'Tracker.-Api') -- an invalid Docker tag ('invalid reference format').
    Confirmed live on REQ-2026-03's OnCallRosterTracker.Api.
    """
    camel_split = _CAMEL_BOUNDARY.sub("-", name)
    return _NON_ALNUM_RUN.sub("-", camel_split.lower()).strip("-")


def _validate_unit_name(name: str, project_label: str) -> None:
    """
    Raises ValueError, naming the offending project, if `name` (the full
    "<request-id>-<slug>" Container App / image name) would be rejected by
    Docker's tag grammar or Azure Container Apps' naming rules. A loud,
    early, diagnosable failure here is strictly better than letting an
    invalid name reach `docker build`/`az containerapp create` and fail
    there instead (the original REQ-2026-03 failure mode this closes).

    `_VALID_CONTAINER_APP_NAME` alone covers both rule sets' character
    constraints (lowercase alphanumeric segments joined by single hyphens,
    starting with a letter -- Azure's stricter of the two on start
    character; Docker also permits a leading digit or '.'/'_'/'__'
    separators, but `_slugify()` above never emits those, so this simplified
    pattern is sufficient). Length is Azure-specific and checked separately,
    since Docker has no such limit.
    """
    if not _VALID_CONTAINER_APP_NAME.match(name):
        raise ValueError(
            f"Computed Container App / image name '{name}' (from project "
            f"'{project_label}') is not a valid Docker tag / Azure Container App "
            "name -- must be lowercase alphanumeric segments separated by single "
            "hyphens, starting with a letter."
        )
    if len(name) >= _MAX_CONTAINER_APP_NAME_LEN:
        raise ValueError(
            f"Computed Container App name '{name}' (from project '{project_label}') "
            f"is {len(name)} characters -- Azure Container Apps requires names "
            f"under {_MAX_CONTAINER_APP_NAME_LEN} characters. This project's name "
            "does not fit the '<request-id>-<slug>' naming convention as-is; this "
            "needs an explicit naming decision (e.g. a shorter project directory "
            "name), not a Deploy Agent truncation workaround -- flagged, not "
            "silently shortened."
        )


# ---------------------------------------------------------------------------
# Unit detection
# ---------------------------------------------------------------------------

def _classify_backend_unit(csproj_path: Path) -> str:
    """Fixed, deterministic mapping (module docstring) — not an LLM judgment call."""
    content = csproj_path.read_text(encoding="utf-8")
    if "Microsoft.NET.Sdk.Web" in content or "Microsoft.AspNetCore.App" in content:
        return "web"
    if "Microsoft.Extensions.Hosting" in content:
        return "worker"
    logger.warning(
        "%s matched neither the 'web' nor 'worker' classification markers -- "
        "defaulting to 'worker' (no public ingress) as the safer default.",
        csproj_path,
    )
    return "worker"


def _detect_backend_units(backend_dir: Path, request_id: str) -> list[DeployUnit]:
    units: list[DeployUnit] = []
    if not backend_dir.is_dir():
        return units

    for csproj_path in sorted(backend_dir.rglob("*.csproj")):
        rel_parts = csproj_path.relative_to(backend_dir).parts
        if any("test" in part.lower() for part in rel_parts):
            continue

        project_label = csproj_path.parent.name
        unit_type = _classify_backend_unit(csproj_path)
        slug = _slugify(project_label)
        units.append(DeployUnit(
            slug=slug,
            unit_type=unit_type,
            name=f"{request_id.lower()}-{slug}",
            project_label=project_label,
            dockerfile_path=csproj_path.parent / "Dockerfile",
            build_context=backend_dir,
            csproj_name=csproj_path.name,
        ))
    return units


def _detect_frontend_unit(frontend_dir: Path, request_id: str) -> DeployUnit | None:
    if not (frontend_dir / "package.json").is_file():
        return None
    slug = "frontend"
    return DeployUnit(
        slug=slug,
        unit_type="frontend",
        name=f"{request_id.lower()}-{slug}",
        project_label="frontend",
        dockerfile_path=frontend_dir / "Dockerfile",
        build_context=frontend_dir,
    )


def _detect_units(repo_path: str, request_id: str) -> list[DeployUnit]:
    service_root = Path(repo_path) / "services" / request_id
    units = _detect_backend_units(service_root / "backend", request_id)
    frontend_unit = _detect_frontend_unit(service_root / "frontend", request_id)
    if frontend_unit:
        units.append(frontend_unit)
    return units


# ---------------------------------------------------------------------------
# Dockerfile + .dockerignore generation
# ---------------------------------------------------------------------------

def _assembly_name(csproj_path: Path) -> str:
    try:
        tree = ET.parse(csproj_path)
        elem = tree.find(".//AssemblyName")
        if elem is not None and elem.text:
            return elem.text.strip()
    except ET.ParseError:
        logger.warning("Could not parse %s as XML -- falling back to filename for AssemblyName.", csproj_path)
    return csproj_path.stem


def _generate_dockerfile_if_missing(unit: DeployUnit) -> bool:
    """Returns True if a Dockerfile was generated, False if one already existed (not overwritten)."""
    if unit.dockerfile_path.exists():
        logger.info("Dockerfile already exists for %s at %s -- not overwriting.", unit.name, unit.dockerfile_path)
        return False

    if unit.unit_type == "frontend":
        content = (_TEMPLATES_DIR / "nextjs.Dockerfile.template").read_text(encoding="utf-8")
    else:
        template_name = "dotnet-web.Dockerfile.template" if unit.unit_type == "web" else "dotnet-worker.Dockerfile.template"
        content = (_TEMPLATES_DIR / template_name).read_text(encoding="utf-8")

        build_props_path = unit.build_context / "Directory.Build.props"
        build_props_copy_line = (
            'COPY ["Directory.Build.props", "."]\n' if build_props_path.exists() else ""
        )
        assembly_name = _assembly_name(unit.dockerfile_path.parent / unit.csproj_name)
        content = (
            content.replace("{{BUILD_PROPS_COPY_LINE}}", build_props_copy_line)
            .replace("{{PROJECT_DIR}}", unit.project_label)
            .replace("{{CSPROJ_NAME}}", unit.csproj_name)
            .replace("{{ASSEMBLY_NAME}}", assembly_name)
        )

    unit.dockerfile_path.write_text(content, encoding="utf-8")
    logger.info("Generated Dockerfile for %s at %s.", unit.name, unit.dockerfile_path)
    return True


_DOCKERIGNORE_BACKEND = "**/bin/\n**/obj/\n**/*.user\n.vs/\n"
_DOCKERIGNORE_FRONTEND = "node_modules\n.next\nnpm-debug.log*\n.env*.local\n.git\n"


def _ensure_dockerignore(build_context: Path, unit_type: str) -> None:
    """
    Not part of the original brief, but required for a *correct* build:
    without excluding node_modules/bin/obj, `COPY . .` in the generated
    templates would overwrite the fresh, correct-platform artifacts copied
    from the earlier build stage with host-platform ones (Windows dotnet
    obj/ caches absolute host paths; frontend node_modules would carry
    Windows-native binaries into a linux/alpine image), and would balloon
    the build context with gigabytes of irrelevant files on every build.
    Only written if the build context doesn't already have one.
    """
    dockerignore_path = build_context / ".dockerignore"
    if dockerignore_path.exists():
        return
    content = _DOCKERIGNORE_FRONTEND if unit_type == "frontend" else _DOCKERIGNORE_BACKEND
    dockerignore_path.write_text(content, encoding="utf-8")
    logger.info("Generated .dockerignore at %s.", dockerignore_path)


def _ensure_frontend_public_dir(build_context: Path) -> bool:
    """
    Next.js apps with no static assets never get a public/ directory from
    create-next-app-style scaffolding, and Git doesn't track empty
    directories -- so a checkout of such an app has no public/ directory on
    disk at all. Every frontend Dockerfile seen so far -- both
    Deploy-Agent-generated (nextjs.Dockerfile.template) and
    Frontend-subagent-authored during Implementation (confirmed
    independently on REQ-2026-02 and REQ-2026-03's own committed
    Dockerfiles) -- includes `COPY --from=builder /app/public ./public`,
    which fails the entire build ("not found") when that directory is
    missing.

    Deploy Agent never overwrites an existing Dockerfile (see
    _generate_dockerfile_if_missing()), so patching the COPY line itself
    only ever helps a project that has no Dockerfile yet -- it would not
    have fixed either of the two real occurrences of this bug, both of
    which already had a committed Dockerfile. Fixed instead at the
    filesystem level, identically regardless of which Dockerfile is in
    play: create an empty public/ directory in the local checkout right
    before the build, so the Dockerfile's own `COPY . .` build-context step
    picks it up like any other real directory and the later
    `COPY --from=builder /app/public ./public` has something to copy.
    Returns True if it had to be created.
    """
    public_dir = build_context / "public"
    if public_dir.is_dir():
        return False
    public_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Created empty %s (no public/ dir in the checkout) so the frontend "
        "Dockerfile's public/ COPY step doesn't fail.", public_dir,
    )
    return True


# ---------------------------------------------------------------------------
# Docker build / push
# ---------------------------------------------------------------------------

def _docker_build(unit: DeployUnit, full_image: str, build_args: dict[str, str] | None = None) -> None:
    command = ["docker", "build", "-f", str(unit.dockerfile_path)]
    for key, value in (build_args or {}).items():
        command += ["--build-arg", f"{key}={value}"]
    command += ["-t", full_image, str(unit.build_context)]
    result = _run_shell(command, cwd=str(_REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"docker build failed for unit {unit.name} (image {full_image}):\n"
            f"{(result.stdout or '')[-3000:]}\n{(result.stderr or '')[-2000:]}"
        )


def _docker_login(acr_login_server: str, acr_username: str, acr_password: str) -> None:
    command = ["docker", "login", acr_login_server, "-u", acr_username, "--password-stdin"]
    result = _run_shell(
        command, cwd=str(_REPO_ROOT), input_text=acr_password, timeout=120,
        log_override=f"docker login {acr_login_server} -u {acr_username} --password-stdin",
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker login to {acr_login_server} failed:\n{(result.stderr or '')[-2000:]}")


def _docker_push(full_image: str) -> None:
    result = _run_shell(["docker", "push", full_image], cwd=str(_REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"docker push failed for {full_image}:\n{(result.stdout or '')[-3000:]}\n{(result.stderr or '')[-2000:]}"
        )


# ---------------------------------------------------------------------------
# Azure CLI: login, existence check, create/update, FQDN
# ---------------------------------------------------------------------------

def _az_login(credentials: dict) -> None:
    client_id = credentials["clientId"]
    tenant_id = credentials["tenantId"]
    subscription_id = credentials["subscriptionId"]

    command = ["az", "login", "--service-principal", "-u", client_id, "-p", credentials["clientSecret"], "--tenant", tenant_id]
    result = _run_shell(
        command, cwd=str(_REPO_ROOT), timeout=120,
        log_override=f"az login --service-principal -u {client_id} -p *** --tenant {tenant_id}",
    )
    if result.returncode != 0:
        raise RuntimeError(f"az login --service-principal failed:\n{(result.stderr or '')[-1500:]}")

    sub_result = _run_shell(["az", "account", "set", "--subscription", subscription_id], cwd=str(_REPO_ROOT), timeout=60)
    if sub_result.returncode != 0:
        raise RuntimeError(f"az account set --subscription failed:\n{(sub_result.stderr or '')[-1500:]}")


def _containerapp_exists(name: str, resource_group: str) -> bool:
    result = _run_shell(
        ["az", "containerapp", "show", "--name", name, "--resource-group", resource_group],
        cwd=str(_REPO_ROOT), timeout=120,
    )
    return result.returncode == 0


def _build_containerapp_command(
    unit: DeployUnit,
    exists: bool,
    full_image: str,
    acr_login_server: str,
    acr_username: str,
    acr_password: str,
    staging_cfg: dict,
    extra_env_vars: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    resource_group = staging_cfg["resource_group"]
    # `create` and `update` take env vars via two DIFFERENT flags --
    # `--env-vars` on create (the initial full set), `--set-env-vars` on
    # update (add/update against an existing set). Confirmed empirically:
    # `az containerapp create --set-env-vars ...` errors with "unrecognized
    # arguments" (caught live during REQ-2026-02 end-to-end verification --
    # `az containerapp create --help`/`update --help` confirm the split).
    # One merged flag either way, built from the same env_var_args, so a
    # future second caller of this function can't clobber this one with a
    # competing flag -- no other env vars are set here today, but this
    # keeps that true if that changes.
    env_var_args = [f"{k}={v}" for k, v in (extra_env_vars or {}).items()]

    if exists:
        command = [
            "az", "containerapp", "update",
            "--name", unit.name,
            "--resource-group", resource_group,
            "--image", full_image,
        ]
        if env_var_args:
            command += ["--set-env-vars", *env_var_args]
        return "update", command

    command = [
        "az", "containerapp", "create",
        "--name", unit.name,
        "--resource-group", resource_group,
        "--environment", staging_cfg["environment"],
        "--image", full_image,
        "--registry-server", acr_login_server,
        "--registry-username", acr_username,
        "--registry-password", acr_password,
        "--cpu", str(staging_cfg["cpu"]),
        "--memory", str(staging_cfg["memory"]),
        "--min-replicas", str(staging_cfg["min_replicas"]),
        "--max-replicas", str(staging_cfg["max_replicas"]),
    ]
    if unit.unit_type in _TARGET_PORTS:
        command += ["--target-port", str(_TARGET_PORTS[unit.unit_type]), "--ingress", "external"]
    if env_var_args:
        command += ["--env-vars", *env_var_args]
    return "create", command


def _get_env_default_domain(environment_name: str, resource_group: str) -> str:
    """
    A unit's FQDN is `f"{unit.name}.{env_default_domain}"` -- confirmed
    empirically against every real Container App deployed so far. This lets
    a unit's FQDN be predicted before that unit's Container App exists,
    which is what cross-service wiring (NEXT_PUBLIC_API_BASE_URL,
    FRONTEND_ORIGIN) needs. Raises rather than returning None/"" on failure
    -- the bug this fixes was a *silent* empty value; a quiet fallback here
    would just reintroduce the same failure mode one level up.
    """
    result = _run_shell(
        ["az", "containerapp", "env", "show", "--resource-group", resource_group, "--name", environment_name,
         "--query", "properties.defaultDomain", "-o", "tsv"],
        cwd=str(_REPO_ROOT), timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"az containerapp env show failed for environment '{environment_name}' in resource group "
            f"'{resource_group}' -- cannot compute a unit's FQDN for cross-service wiring:\n"
            f"{(result.stderr or '')[-1500:]}"
        )
    domain = (result.stdout or "").strip()
    if not domain:
        raise RuntimeError(
            f"az containerapp env show for environment '{environment_name}' returned an empty "
            "defaultDomain -- cannot compute a unit's FQDN for cross-service wiring."
        )
    return domain


def _get_fqdn(name: str, resource_group: str) -> str | None:
    result = _run_shell(
        ["az", "containerapp", "show", "--name", name, "--resource-group", resource_group,
         "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"],
        cwd=str(_REPO_ROOT), timeout=120,
    )
    if result.returncode != 0:
        return None
    fqdn = (result.stdout or "").strip()
    return fqdn or None


# ---------------------------------------------------------------------------
# design.md gap check
# ---------------------------------------------------------------------------

def _detect_design_gaps(request_id: str, units: list[DeployUnit]) -> list[str]:
    """
    Flags (never blocks) any detected unit with no corresponding design.md
    entry, so a unit deployed without design sign-off doesn't go unnoticed.

    Checks both the literal project directory name (e.g. "EmailWorker") and
    a de-camelCased, spaced variant ("Email Worker") case-insensitively --
    design.md is human-authored prose and consistently refers to components
    with a space ("Document API", "Email Worker"), never the bare
    identifier, so a literal-only match produces false-positive gaps for
    units that ARE documented.
    """
    try:
        design_md = get_file_contents(f"docs/{request_id}/design.md")
    except Exception:
        logger.warning(
            "Could not fetch docs/%s/design.md -- skipping the design-doc gap check for this run.",
            request_id,
        )
        return []

    lowered = design_md.lower()
    gaps = []
    for unit in units:
        spaced = _CAMEL_BOUNDARY.sub(" ", unit.project_label)
        variants = {unit.project_label.lower(), spaced.lower()}
        if not any(variant in lowered for variant in variants):
            gaps.append(unit.project_label)
    return gaps


# ---------------------------------------------------------------------------
# PR comment (deterministic — no Claude call, see module docstring)
# ---------------------------------------------------------------------------

def _build_pr_comment(request_id: str, commit_sha: str, results: list[DeployResult], design_gaps: list[str]) -> str:
    marker = f"<!-- forge:agent-comment stage=deploy request_id={request_id} -->"
    lines = [
        marker,
        "## FORGE Deploy Agent — Staging Deployment",
        "",
        f"**Request:** {request_id}  ",
        f"**Commit:** `{commit_sha[:12]}`",
        "",
        "| Unit | Type | Image | Staging URL |",
        "|---|---|---|---|",
    ]
    for r in results:
        if r.error:
            # First line alone is often just "...failed for unit X:" with the
            # actual CLI error on the next line(s) -- confirmed live on the
            # real create/update failure this was written against. Take the
            # first few non-empty lines instead of just line one.
            snippet_lines = [line.strip() for line in r.error.splitlines() if line.strip()][:3]
            snippet = " / ".join(snippet_lines)[:400]
            status = f"❌ **failed** — {snippet}"
        else:
            status = f"https://{r.fqdn}" if r.fqdn else "_(internal — no public ingress)_"
        lines.append(f"| `{r.unit.name}` | {r.unit.unit_type} | `{r.image}` | {status} |")
    lines.append("")

    failed = [r for r in results if r.error]
    if failed:
        lines.append(
            f"**{len(failed)} of {len(results)} unit(s) failed to deploy** -- a failure on one unit "
            "does not block the others; see the table above for which unit(s) and why."
        )
        lines.append("")

    if design_gaps:
        lines.append(
            "**design.md gap:** the following deployed unit(s) have no corresponding entry "
            f"in `docs/{request_id}/design.md` — deployed anyway, but nobody has signed off on "
            "them in the design document:"
        )
        for g in design_gaps:
            lines.append(f"- {g}")
        lines.append("")

    lines.append(
        "_Staging deploy only — not gated; Document 6 has no deploy-stage label, so none is "
        "applied here._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _load_staging_config() -> dict:
    config = file_io.read_yaml(_CONFIG_PATH)
    staging = (config or {}).get("container_apps", {}).get("staging")
    if not staging:
        raise ValueError(f"No container_apps.staging block found in {_CONFIG_PATH}")
    required = ("environment", "resource_group", "max_replicas", "min_replicas", "cpu", "memory")
    missing = [k for k in required if k not in staging]
    if missing:
        raise ValueError(f"container_apps.staging in {_CONFIG_PATH} is missing key(s): {missing}")
    return staging


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Required environment variable {name} is not set.")
    return value


def run_deploy_agent(
    issue_number: int,
    request_id: str,
    repo_path: str,
    commit_sha: str,
    pr_number: int,
    dry_run: bool = False,
) -> dict:
    """Core entry point. Returns a dict summarizing the run."""
    try:
        acr_login_server = _require_env("ACR_LOGIN_SERVER")
        acr_username = _require_env("ACR_USERNAME")
        acr_password = _require_env("ACR_PASSWORD")
        azure_credentials = json.loads(_require_env("AZURE_STAGING_CREDENTIALS"))
        for key in ("clientId", "clientSecret", "subscriptionId", "tenantId"):
            if key not in azure_credentials:
                raise ValueError(f"AZURE_STAGING_CREDENTIALS is missing required key '{key}'.")

        staging_cfg = _load_staging_config()

        units = _detect_units(repo_path, request_id)
        if not units:
            raise ValueError(
                f"No deployable units detected under services/{request_id}/ in {repo_path} — "
                "nothing to deploy. Check --repo-path and --request-id."
            )
        logger.info(
            "Detected %d unit(s) for %s: %s",
            len(units), request_id, ", ".join(f"{u.name} ({u.unit_type})" for u in units),
        )

        for unit in units:
            unit.dockerfile_generated = _generate_dockerfile_if_missing(unit)
            _ensure_dockerignore(unit.build_context, unit.unit_type)
            if unit.unit_type == "frontend":
                _ensure_frontend_public_dir(unit.build_context)

        # Real docker build + push for every unit, dry-run or not — same
        # "exercise the real tool, skip only the posting" pattern as
        # QA/Security's --dry-run.
        _docker_login(acr_login_server, acr_username, acr_password)

        # Cross-service wiring: a frontend unit needs the backend's FQDN baked
        # in at build time (Next.js NEXT_PUBLIC_* vars are build-time-only),
        # and the backend needs the frontend's FQDN for CORS. Both derived
        # from one shared env_default_domain lookup, computed once per run,
        # not per unit -- see _get_env_default_domain().
        frontend_unit = next((u for u in units if u.unit_type == "frontend"), None)
        backend_web_unit = next((u for u in units if u.unit_type == "web"), None)
        # A backend unit whose own name is invalid (bad characters, or too
        # long for Azure) will never actually build/deploy -- see the
        # per-unit try/except below, which will record its own error. Don't
        # let that same broken name reach the frontend's build-arg / this
        # unit's own FRONTEND_ORIGIN wiring first: validate here, before
        # either FQDN is derived, and fall back to the same "no web backend
        # unit" no-wiring behavior rather than baking in an unreachable URL.
        if backend_web_unit is not None:
            try:
                _validate_unit_name(backend_web_unit.name, backend_web_unit.project_label)
            except ValueError as name_exc:
                logger.warning(
                    "Backend web unit %s has an invalid name and will fail to build -- "
                    "treating as if no 'web' backend unit exists for cross-service wiring "
                    "purposes (NEXT_PUBLIC_API_BASE_URL/FRONTEND_ORIGIN will not be set): %s",
                    backend_web_unit.name, name_exc,
                )
                backend_web_unit = None
        backend_fqdn: str | None = None
        frontend_fqdn: str | None = None
        if frontend_unit is not None:
            if backend_web_unit is not None:
                env_default_domain = _get_env_default_domain(
                    staging_cfg["environment"], staging_cfg["resource_group"],
                )
                backend_fqdn = f"{backend_web_unit.name}.{env_default_domain}"
                frontend_fqdn = f"{frontend_unit.name}.{env_default_domain}"
            else:
                logger.warning(
                    "Frontend unit %s detected with no 'web' backend unit in this request -- "
                    "NEXT_PUBLIC_API_BASE_URL and FRONTEND_ORIGIN will not be set.", frontend_unit.name,
                )

        # Real az login + real read-only existence checks, dry-run or not —
        # only the create/update mutation itself is print-only in dry-run.
        _az_login(azure_credentials)

        # Build+push+deploy interleaved per unit (not two batched passes) --
        # one unit's failure must not block a different unit that would
        # otherwise succeed. Each unit's own try/except records its outcome
        # (success or error) into `results` and moves on; nothing here
        # re-raises mid-loop. FQDNs needed for cross-service wiring were
        # already computed above from unit *names*, not from any unit's
        # create/update having actually run yet, so processing order here
        # doesn't matter for backend_fqdn/frontend_fqdn's correctness.
        results: list[DeployResult] = []
        for unit in units:
            full_image = f"{acr_login_server}/{unit.name}:{commit_sha}"
            result = DeployResult(unit=unit, image=full_image)
            try:
                _validate_unit_name(unit.name, unit.project_label)
                build_args = {"NEXT_PUBLIC_API_BASE_URL": f"https://{backend_fqdn}"} if (
                    unit.unit_type == "frontend" and backend_fqdn
                ) else None
                _docker_build(unit, full_image, build_args=build_args)
                _docker_push(full_image)

                exists = _containerapp_exists(unit.name, staging_cfg["resource_group"])
                extra_env_vars = {"FRONTEND_ORIGIN": f"https://{frontend_fqdn}"} if (
                    unit is backend_web_unit and frontend_fqdn
                ) else None
                action, command = _build_containerapp_command(
                    unit, exists, full_image, acr_login_server, acr_username, acr_password, staging_cfg,
                    extra_env_vars=extra_env_vars,
                )
                result.action = action
                result.command = command

                if dry_run:
                    logger.info(
                        "[dry-run] Would run: %s", " ".join(_redact_command(command)),
                    )
                else:
                    exec_result = _run_shell(
                        command, cwd=str(_REPO_ROOT), timeout=_SHELL_TIMEOUT_SECONDS,
                        log_override=" ".join(_redact_command(command)),
                    )
                    if exec_result.returncode != 0:
                        raise RuntimeError(
                            f"az containerapp {action} failed for unit {unit.name}:\n"
                            f"{(exec_result.stdout or '')[-3000:]}\n{(exec_result.stderr or '')[-2000:]}"
                        )
                    result.executed = True
                    if unit.unit_type in _TARGET_PORTS:
                        result.fqdn = _get_fqdn(unit.name, staging_cfg["resource_group"])
            except Exception as unit_exc:
                logger.exception(
                    "Deploy failed for unit %s -- continuing with remaining unit(s).", unit.name,
                )
                result.error = str(unit_exc)
            results.append(result)

        design_gaps = _detect_design_gaps(request_id, units)
        pr_comment = _build_pr_comment(request_id, commit_sha, results, design_gaps)
        failed_results = [r for r in results if r.error]

    except Exception as exc:
        logger.exception("Deploy Agent failed for request %s", request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE Deploy Agent failed to complete.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before staging can be "
                "considered deployed for this request."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    run_summary = {
        "units": [
            {
                "name": r.unit.name,
                "type": r.unit.unit_type,
                "image": r.image,
                "action": r.action,
                "command": _redact_command(r.command),
                "executed": r.executed,
                "fqdn": r.fqdn,
                "error": r.error,
                "dockerfile_generated": r.unit.dockerfile_generated,
            }
            for r in results
        ],
        "design_gaps": design_gaps,
        "pr_comment_markdown": pr_comment,
    }

    if dry_run:
        print("=" * 20, "units detected", "=" * 20)
        print(json.dumps(run_summary["units"], indent=2))
        print("=" * 20, "design.md gaps", "=" * 20)
        print(json.dumps(design_gaps, indent=2))
        print("=" * 20, "PR comment (not posted)", "=" * 20)
        print(pr_comment)
        logger.info(
            "Dry run complete for request %s -- images built and pushed for real, "
            "containerapp create/update NOT executed, nothing posted. %d of %d unit(s) succeeded.",
            request_id, len(results) - len(failed_results), len(results),
        )
        if failed_results:
            failed_names = ", ".join(r.unit.name for r in failed_results)
            raise RuntimeError(
                f"Deploy Agent dry-run: {len(failed_results)} of {len(results)} unit(s) failed: {failed_names}"
            )
        return run_summary

    post_pr_comment(pr_number, pr_comment)

    logger.info(
        "Deploy Agent complete for request %s -- %d of %d unit(s) deployed to staging, "
        "PR #%s comment posted.",
        request_id, len(results) - len(failed_results), len(results), pr_number,
    )

    if failed_results:
        failed_names = ", ".join(r.unit.name for r in failed_results)
        failure_body = (
            f"⚠️ **FORGE Deploy Agent: {len(failed_results)} of {len(results)} unit(s) failed to "
            f"deploy** (`{failed_names}`) -- the rest were deployed successfully; see the PR "
            "comment above for per-unit detail.\n\n"
            "An Orchestration Manager needs to investigate before staging can be considered "
            "fully deployed for this request."
        )
        try:
            post_comment(issue_number, failure_body)
        except Exception:
            logger.exception("Also failed to post partial-failure comment to issue #%s", issue_number)
        raise RuntimeError(
            f"Deploy Agent: {len(failed_results)} of {len(results)} unit(s) failed: {failed_names}"
        )

    return run_summary


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Deploy Agent (staging)")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", required=True, help="FORGE request ID")
    parser.add_argument("--repo-path", required=True, help="Local path to an existing checkout of forge-demo-apps at the feature branch")
    parser.add_argument("--commit-sha", required=True, help="Commit SHA being deployed (used as the image tag)")
    parser.add_argument("--pr-number", required=True, type=int, help="Feature PR number in forge-demo-apps")
    parser.add_argument("--dry-run", action="store_true", help="Real docker build/push, but print (don't execute) az containerapp commands and post nothing")
    args = parser.parse_args()

    try:
        run_deploy_agent(
            issue_number=args.issue_number,
            request_id=args.request_id,
            repo_path=args.repo_path,
            commit_sha=args.commit_sha,
            pr_number=args.pr_number,
            dry_run=args.dry_run,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
