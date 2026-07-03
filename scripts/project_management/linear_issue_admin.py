"""Small Linear admin helper for Symphony queue hygiene.

This script reads LINEAR_API_KEY from the global Symphony env file outside the
repository and never prints the token. It intentionally supports only narrow
state updates by issue identifier so the lead/coordinator can keep unattended
Symphony focused on the next approved issue.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ENV_PATH = Path(r"C:\Users\PC\.codex\symphony\.env")
API_URL = "https://api.linear.app/graphql"


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


def get_issue(identifier: str) -> dict[str, Any]:
    data = gql(
        """
        query IssueByIdentifier($identifier: String!) {
          issue(id: $identifier) {
            id
            identifier
            title
            url
            state { id name }
            labels { nodes { id name } }
            team {
              id
              key
              states(first: 50) { nodes { id name type } }
              labels(first: 250) { nodes { id name } }
            }
          }
        }
        """,
        {"identifier": identifier},
    )
    issue = data.get("issue")
    if not issue:
        raise SystemExit(f"Issue not found: {identifier}")
    return issue


def state_id_for(issue: dict[str, Any], state_name: str) -> str:
    for state in issue["team"]["states"]["nodes"]:
        if state["name"].lower() == state_name.lower():
            return state["id"]
    names = ", ".join(state["name"] for state in issue["team"]["states"]["nodes"])
    raise SystemExit(
        f"State {state_name!r} not found for team {issue['team']['key']}; "
        f"available states: {names}"
    )


def set_state(identifier: str, state_name: str) -> dict[str, Any]:
    issue = get_issue(identifier)
    target_state_id = state_id_for(issue, state_name)
    if issue["state"]["id"] == target_state_id:
        return {
            "identifier": issue["identifier"],
            "title": issue["title"],
            "state": issue["state"]["name"],
            "status": "unchanged",
            "url": issue["url"],
        }

    result = gql(
        """
        mutation UpdateIssueState($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue {
              identifier
              title
              url
              state { name }
            }
          }
        }
        """,
        {"id": identifier, "input": {"stateId": target_state_id}},
    )["issueUpdate"]
    if not result.get("success"):
        raise RuntimeError(f"Failed to update {identifier}")
    updated = result["issue"]
    return {
        "identifier": updated["identifier"],
        "title": updated["title"],
        "state": updated["state"]["name"],
        "status": "updated",
        "url": updated["url"],
    }


def label_ids_for(issue: dict[str, Any], label_names: list[str]) -> list[str]:
    by_name = {
        label["name"].lower(): label
        for label in issue["team"]["labels"]["nodes"]
    }
    missing = [
        label_name
        for label_name in label_names
        if label_name.lower() not in by_name
    ]
    if missing:
        raise SystemExit(
            f"Labels not found for team {issue['team']['key']}: "
            f"{', '.join(missing)}"
        )
    return [by_name[label_name.lower()]["id"] for label_name in label_names]


def set_labels(identifier: str, label_names: list[str]) -> dict[str, Any]:
    issue = get_issue(identifier)
    target_label_ids = label_ids_for(issue, label_names)
    current_labels = sorted(label["name"] for label in issue["labels"]["nodes"])
    target_labels = sorted(label_names)
    if current_labels == target_labels:
        return {
            "identifier": issue["identifier"],
            "title": issue["title"],
            "labels": current_labels,
            "status": "unchanged",
            "url": issue["url"],
        }

    result = gql(
        """
        mutation UpdateIssueLabels($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue {
              identifier
              title
              url
              labels { nodes { name } }
            }
          }
        }
        """,
        {"id": identifier, "input": {"labelIds": target_label_ids}},
    )["issueUpdate"]
    if not result.get("success"):
        raise RuntimeError(f"Failed to update labels for {identifier}")
    updated = result["issue"]
    return {
        "identifier": updated["identifier"],
        "title": updated["title"],
        "labels": sorted(label["name"] for label in updated["labels"]["nodes"]),
        "status": "updated",
        "url": updated["url"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Narrow Linear issue admin.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_state_parser = subparsers.add_parser("set-state")
    set_state_parser.add_argument("identifier")
    set_state_parser.add_argument("state")

    set_labels_parser = subparsers.add_parser("set-labels")
    set_labels_parser.add_argument("identifier")
    set_labels_parser.add_argument("labels", nargs="+")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "set-state":
        print(json.dumps(set_state(args.identifier, args.state), indent=2))
    elif args.command == "set-labels":
        print(json.dumps(set_labels(args.identifier, args.labels), indent=2))


if __name__ == "__main__":
    main()
