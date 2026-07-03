"""Dispatch safe STWI Symphony work items to Linear.

The script reads LINEAR_API_KEY from the global Symphony env file outside this
repository and never prints the token. It creates a small set of low-risk,
Todo-state Linear issues that match WORKFLOW.md safety filters.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ENV_PATH = Path(r"C:\Users\PC\.codex\symphony\.env")
PROJECT_SLUG = "traffic-agent-assistant-811a1da43eac"
API_URL = "https://api.linear.app/graphql"

DRY_RUN = "--dry-run" in sys.argv
SEED_FILTER = next(
    (
        {
            seed.strip()
            for seed in arg.split("=", 1)[1].split(",")
            if seed.strip()
        }
        for arg in sys.argv[1:]
        if arg.startswith("--seeds=")
    ),
    None,
)

ISSUES = [
    {
        "seed": "STWI-SYM-013",
        "title": (
            "Complete vision artifact metadata for latency, thresholds, "
            "ROI policy, and license/source"
        ),
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:vision",
            "phase:1",
            "task:validate",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "code/docs/tests only; do not read private weights, raw frames, "
            "or data/derived/private"
        ),
        "criteria": [
            "Detector metadata records latency, thresholds, ROI policy, class mapping, model/data version, and source/license notes.",
            "Promotion criteria remain consistent with scripts/training/promote_vision_model.py or the current promotion script location if renamed.",
            "No private weights, raw images, base64 images, or secret files are read or logged.",
            "Run focused validators/tests and report skipped private-artifact checks explicitly.",
        ],
    },
    {
        "seed": "STWI-SYM-005",
        "title": "Prove surrogate P99 under contract benchmark profile",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:simulation",
            "phase:2",
            "task:qa",
        ],
        "owner": "MLSimulationAgent",
        "scope": (
            "src/stwi/t2_forecast, scripts/validation, scripts/training, "
            "tests/t2_forecast, docs references"
        ),
        "criteria": [
            "Find or add a local/offline benchmark or report path for surrogate latency without requiring external services.",
            "Compare measured or recorded P99 against the contract target of surrogate P99 < 500 ms.",
            "If hardware benchmark cannot be run in the Symphony workspace, stop with Human Review and list exact missing evidence.",
            "Do not alter SLA thresholds or mark provisional results as production-ready.",
        ],
    },
    {
        "seed": "STWI-SYM-009",
        "title": "Replace provisional fake adapters in production runtime",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:api",
            "phase:4",
            "task:validate",
        ],
        "owner": "OrchestratorAgent",
        "scope": (
            "src/stwi/t4_orchestrator, src/stwi/config, "
            "tests/t4_orchestrator, DOC-04 references"
        ),
        "criteria": [
            "Inventory fake/provisional adapters reachable from production runtime paths.",
            "Replace only with fail-closed local implementations or add guards that prevent accidental production execution.",
            "Preserve statuses queued, running, succeeded, needs_review, failed, expired and recommended_action/candidate_action semantics.",
            "Run focused orchestrator/API tests and contract checks relevant to the touched files.",
        ],
    },
    {
        "seed": "STWI-SYM-011",
        "title": "Run full release QA after current refactor changes are settled",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:qa",
            "task:qa",
        ],
        "owner": "ReleaseQaAgent",
        "scope": (
            "validators/tests/docs/slides only; no staging, commit, push, "
            "PR, or release publication"
        ),
        "criteria": [
            "Run python scripts/validation/validate_docs.py and report pass/fail.",
            "Run python -m unittest tests.contracts.test_project_contract and report pass/fail.",
            "Run node --check slides/js/presentation.js and node --check slides/js/presentation-tools.js.",
            "Run git diff --check and confirm no cache/build artifact is staged.",
            "List skipped tests, unverified service paths, and any Human Review blockers.",
        ],
    },
    {
        "seed": "STWI-SYM-016",
        "title": "Reconcile readiness scoring and progress evidence",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:qa",
            "task:review",
        ],
        "owner": "LeadCoordinator",
        "scope": (
            "docs/project_management/symphony only; no contract, runtime, "
            "release, commit, or push actions"
        ),
        "criteria": [
            "Progress estimates are derived from board state, gate criteria, and verified checks instead of raw agent-report percentages.",
            "Stale test counts are replaced or explicitly marked stale.",
            "A single readiness summary is available for Symphony/Linear handoff.",
            "No project_contract.json invariants, API semantics, safety rules, or SLA thresholds are changed.",
        ],
    },
    {
        "seed": "STWI-SYM-017",
        "title": "Draft auth, RBAC, and tenant-boundary design",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:api",
            "phase:4",
            "task:review",
            "needs-human-review",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "docs/design proposal only; no dependency, IdP, API schema, "
            "credential, or runtime implementation"
        ),
        "criteria": [
            "Design derives operator identity and tenant context server-side instead of trusting request body fields.",
            "Role boundaries for operator, analyst, admin, and readonly are specified without choosing a new identity provider.",
            "No auth dependency, external IdP, or API schema change is implemented before Human Review approval.",
            "The proposal preserves decision-support-only behavior and human approval requirements.",
        ],
    },
    {
        "seed": "STWI-SYM-018",
        "title": "Specify observability minimum for trace, logs, and metrics",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:api",
            "phase:4",
            "task:review",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "docs and validation planning only; do not add Prometheus, "
            "OpenTelemetry, Grafana, or external services"
        ),
        "criteria": [
            "Required trace_id, job timing, model/data/policy version, status transition, and safety reason fields are listed.",
            "Metric names are specified for job counts, job latency, safety loop outcomes, retrieval latency, and surrogate latency.",
            "Prometheus, OpenTelemetry, or other observability services remain optional future deployment choices until explicitly approved.",
            "Any missing runtime fields are recorded as follow-up implementation issues rather than implemented in this issue.",
        ],
    },
    {
        "seed": "STWI-SYM-019",
        "title": "Define project-native model registry evidence format",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:ml",
            "phase:2",
            "task:review",
        ],
        "owner": "MLSimulationAgent",
        "scope": (
            "docs, schema proposal, and focused validators only; do not add "
            "MLflow or external model registry services"
        ),
        "criteria": [
            "Evidence schema covers model version, dataset version, checksum, metrics, calibration, benchmark profile, thresholds, and promotion decision.",
            "The format works for vision, baseline forecast, and surrogate artifacts without requiring MLflow.",
            "Existing promotion and validation paths either produce or validate the required fields.",
            "No current model claim is upgraded from provisional to production-ready without matching evidence.",
        ],
    },
    {
        "seed": "STWI-SYM-020",
        "title": "Document fail-closed resilience policy for dependency failures",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:api",
            "phase:4",
            "task:review",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "docs/tests planning first; runtime edits only if small and "
            "fail-closed, no pybreaker dependency or fail-open fallback"
        ),
        "criteria": [
            "Retries, timeout, circuit-breaker-style behavior, and dependency failure classes map to needs_review, failed, or expired.",
            "No runtime path returns an executable action after tool, RAG, TimescaleDB, Qdrant, Celery, Redis, or model failure.",
            "The rejected fail-open wording is replaced with an explicit fail-closed policy and focused tests are identified.",
            "recommended_action remains available only for succeeded jobs; needs_review exposes only non-executable candidate_action.",
        ],
    },
    {
        "seed": "STWI-SYM-021",
        "title": "Review production deployment options without changing the approved stack",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:release",
            "phase:4",
            "task:review",
            "needs-human-review",
            "contract-risk",
        ],
        "owner": "ReleaseQaAgent",
        "scope": (
            "options review only; do not add Kubernetes, secrets manager, "
            "tracing stack, model server, workflow, or CI deployment changes"
        ),
        "criteria": [
            "Docker Compose production, Kubernetes, and managed-service options are compared as deployment options only.",
            "No Kubernetes, secrets manager, tracing, or model-serving framework is added to active architecture.",
            "The recommendation lists cost, complexity, safety, rollback, and Human Review requirements for a later decision.",
            "The active MVP stack remains TimescaleDB, Qdrant, BGE-m3, LangGraph, Celery, Redis, FastAPI, and SSE.",
        ],
    },
    {
        "seed": "STWI-RTSP-001",
        "title": (
            "Prepare RTSP source alias and capture guardrails for edge_camera_1"
        ),
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:data",
            "phase:1",
            "task:validate",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "scripts/data_prep/capture_rtsp_frames.py, "
            "tests/t1_pipeline/test_capture_rtsp_frames.py, "
            "docs/guides/vision_local_training_runbook.md"
        ),
        "criteria": [
            "Accept edge_camera_1 as a safe source id while continuing to reject unsafe source ids.",
            "Keep the RTSP endpoint read only from STWI_RTSP_URL; do not put the endpoint in repo files, Linear, logs, or manifests.",
            "Ensure command output and manifests exclude endpoint values, credentials, image base64, and raw video references.",
            "Add or update focused tests for URL validation, missing env handling, safe source id, and fail-closed behavior without opening a live stream.",
        ],
    },
    {
        "seed": "STWI-RTSP-002",
        "title": "Document supervised RTSP-to-quarantine smoke test procedure",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:vision",
            "phase:1",
            "task:review",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "docs/guides/vision_local_training_runbook.md, "
            "docs/01_System_Architecture_Data_Pipeline.md, README.md if needed"
        ),
        "criteria": [
            "Document how an operator sets STWI_RTSP_URL locally without writing the endpoint to repo, Linear, logs, or manifests.",
            "Document sparse-frame quarantine capture under data/quarantine/rtsp_frames with no raw video container retention.",
            "List privacy review, retention, cleanup, and aggregate-only next steps before any frame leaves quarantine.",
            "Include exact offline verification commands that can run after supervised capture.",
        ],
    },
    {
        "seed": "STWI-RTSP-003",
        "title": "Run supervised live RTSP smoke test for edge_camera_1",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:data",
            "phase:1",
            "task:review",
            "needs-human-review",
            "external-service",
        ],
        "owner": "DataVisionAgent with human supervision",
        "scope": (
            "Human-supervised local run only; no unattended Symphony execution, "
            "no raw video retention, and no endpoint disclosure."
        ),
        "criteria": [
            "Human operator confirms the RTSP endpoint is approved for STWI testing and sets it only in STWI_RTSP_URL.",
            "Live capture is bounded to a small sample, stores sparse frames only in quarantine, and retains no raw video.",
            "Review the manifest to confirm no endpoint, credentials, image base64, or raw video reference is present.",
            "Delete evidence, keep it in quarantine for privacy review, or create a follow-up issue for approved aggregate-only conversion.",
        ],
    },
]


def read_key() -> str:
    if not ENV_PATH.exists():
        raise SystemExit(f"Missing env file: {ENV_PATH}")

    for raw_line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "LINEAR_API_KEY":
            return value.strip().strip('"').strip("'")

    raise SystemExit("LINEAR_API_KEY not found in Symphony env file")


TOKEN = read_key()


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode(
        "utf-8"
    )
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": TOKEN},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Linear HTTP {error.code}: {body}") from error

    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]


def find_project() -> tuple[dict[str, Any], dict[str, Any]]:
    data = gql(
        """
        query ProjectBySlug($slug: String!) {
          projects(filter: { slugId: { eq: $slug } }, first: 1) {
            nodes {
              id
              name
              slugId
              teams(first: 5) {
                nodes {
                  id
                  key
                  name
                  states(first: 50) { nodes { id name type } }
                  labels(first: 250) { nodes { id name } }
                }
              }
            }
          }
        }
        """,
        {"slug": PROJECT_SLUG},
    )
    projects = data["projects"]["nodes"]
    if not projects:
        raise SystemExit(f"No Linear project found for slug {PROJECT_SLUG}")

    project = projects[0]
    teams = project.get("teams", {}).get("nodes", [])
    if not teams:
        raise SystemExit(f"Project {PROJECT_SLUG} has no teams")
    return project, teams[0]


def build_description(item: dict[str, Any]) -> str:
    lines = [
        f"Seed: {item['seed']}",
        "",
        f"Owner role: {item['owner']}",
        f"Allowed scope: {item['scope']}",
        "",
        "Acceptance criteria:",
    ]
    lines.extend(f"- {criterion}" for criterion in item["criteria"])
    lines.extend(
        [
            "",
            "Symphony safety filters:",
            "- Use the project-local STWI skills and read AGENTS.md, README.md, project_contract.json before edits.",
            "- Keep network disabled inside the Symphony agent run.",
            "- Do not read or write .env*, secrets, raw video, private datasets, private model weights, .git, .codex, or data/derived/private.",
            "- Do not stage, commit, push, create PRs, deploy, publish releases, or run destructive commands.",
            "- Stop for Human Review instead of weakening contract, tests, safety, legal citation, SLA, tensor, feature, or API semantics.",
        ]
    )
    return "\n".join(lines)


def issue_exists(
    team_id: str, project_id: str, seed: str, title: str
) -> str | None:
    data = gql(
        """
        query ExistingIssues($teamId: ID!, $projectId: ID!, $term: String!) {
          issues(
            first: 10,
            filter: {
              team: { id: { eq: $teamId } },
              project: { id: { eq: $projectId } },
              or: [
                { title: { containsIgnoreCase: $term } },
                { description: { containsIgnoreCase: $term } }
              ]
            }
          ) { nodes { id identifier title url state { name } } }
        }
        """,
        {"teamId": team_id, "projectId": project_id, "term": seed},
    )
    for issue in data["issues"]["nodes"]:
        return issue["url"]

    data = gql(
        """
        query ExistingByTitle($teamId: ID!, $projectId: ID!, $title: String!) {
          issues(
            first: 10,
            filter: {
              team: { id: { eq: $teamId } },
              project: { id: { eq: $projectId } },
              title: { eqIgnoreCase: $title }
            }
          ) { nodes { id identifier title url state { name } } }
        }
        """,
        {"teamId": team_id, "projectId": project_id, "title": title},
    )
    for issue in data["issues"]["nodes"]:
        return issue["url"]
    return None


def main() -> None:
    project, team = find_project()
    states = {state["name"].lower(): state for state in team["states"]["nodes"]}
    labels = {label["name"].lower(): label for label in team["labels"]["nodes"]}

    def ensure_label(name: str) -> str:
        found = labels.get(name.lower())
        if found:
            return found["id"]
        if DRY_RUN:
            return f"dry-label:{name}"

        created = gql(
            """
            mutation CreateLabel($input: IssueLabelCreateInput!) {
              issueLabelCreate(input: $input) {
                success
                issueLabel { id name }
              }
            }
            """,
            {"input": {"teamId": team["id"], "name": name}},
        )["issueLabelCreate"]
        if not created.get("success"):
            raise RuntimeError(f"Failed to create label {name}")
        label = created["issueLabel"]
        labels[label["name"].lower()] = label
        return label["id"]

    results = []
    for item in ISSUES:
        if SEED_FILTER is not None and item["seed"] not in SEED_FILTER:
            continue
        state = states.get(item["state"].lower())
        if not state:
            names = ", ".join(state["name"] for state in states.values())
            raise SystemExit(
                f"State {item['state']} not found in Linear team {team['key']}; "
                f"states: {names}"
            )

        existing_url = issue_exists(
            team["id"], project["id"], item["seed"], item["title"]
        )
        if existing_url:
            results.append(
                {"seed": item["seed"], "status": "existing", "url": existing_url}
            )
            continue

        label_ids = [ensure_label(label) for label in item["labels"]]
        if DRY_RUN:
            results.append({"seed": item["seed"], "status": "dry-run", "url": None})
            continue

        created = gql(
            """
            mutation CreateIssue($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                success
                issue {
                  id
                  identifier
                  title
                  url
                  state { name }
                  labels { nodes { name } }
                }
              }
            }
            """,
            {
                "input": {
                    "teamId": team["id"],
                    "projectId": project["id"],
                    "stateId": state["id"],
                    "title": item["title"],
                    "description": build_description(item),
                    "labelIds": label_ids,
                }
            },
        )["issueCreate"]
        if not created.get("success"):
            raise RuntimeError(f"Failed to create issue {item['seed']}")

        issue = created["issue"]
        results.append(
            {
                "seed": item["seed"],
                "status": "created",
                "identifier": issue["identifier"],
                "url": issue["url"],
            }
        )

    print(
        json.dumps(
            {
                "project": {
                    "id": project["id"],
                    "name": project["name"],
                    "slug": project["slugId"],
                },
                "team": {"id": team["id"], "key": team["key"], "name": team["name"]},
                "issues": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
