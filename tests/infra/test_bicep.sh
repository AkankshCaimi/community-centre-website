#!/usr/bin/env bash
# Checks on infra/main.bicep, compiled with `az bicep build`.
# Expected values come from docs/specs/deploy.md (Z1, Z4, Z6, Z9).
# Needs the Azure CLI; it creates nothing in Azure.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

if ! az bicep build --file "$REPO_ROOT/infra/main.bicep" --outfile "$OUT/main.json" > "$OUT/build.log" 2>&1; then
    echo "FAIL  infra/main.bicep compiles"
    grep -v "SyntaxWarning\|excludedActions" "$OUT/build.log"
    echo
    echo "0 passed, 1 failed"
    exit 1
fi

python3 - "$OUT/main.json" "$OUT/build.log" <<'PY'
import json
import sys

template = json.load(open(sys.argv[1]))
build_log = open(sys.argv[2]).read()
resources = template["resources"]
resources = list(resources.values()) if isinstance(resources, dict) else resources

passed = failed = 0


def check(description, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {description}")
    else:
        failed += 1
        print(f"FAIL  {description}{' (' + str(detail) + ')' if detail else ''}")


def of_type(kind):
    return [r for r in resources if r["type"].split("@")[0] == kind]


def inner(resource):
    """The resource itself, or the one inside a copy loop or condition."""
    return resource


check("the file compiles without a warning", "Warning" not in build_log, build_log.strip()[:200])

environments = of_type("Microsoft.App/managedEnvironments")
check("Z9 there is exactly one Container Apps environment", len(environments) == 1, len(environments))
environment = environments[0]
properties = environment["properties"]
check(
    "Z9 its mode is WorkloadProfiles, set explicitly, not Express",
    properties.get("environmentMode") == "WorkloadProfiles",
    properties.get("environmentMode"),
)
check(
    "Z9 its one workload profile is Consumption",
    properties.get("workloadProfiles") == [{"name": "Consumption", "workloadProfileType": "Consumption"}],
    properties.get("workloadProfiles"),
)
check(
    "Z6 Z9 its logs go to Log Analytics",
    properties.get("appLogsConfiguration", {}).get("destination") == "log-analytics",
)
check(
    "Z6 Z9 the workspace is log-community-centre",
    "log-community-centre" in json.dumps(properties.get("appLogsConfiguration"))
    or "log-community-centre" in json.dumps(of_type("Microsoft.OperationalInsights/workspaces")[0]["name"]),
)
check("Z9 the environment is named cae-community-centre", environment["name"] == "cae-community-centre")

websites = of_type("Microsoft.App/containerApps")
jobs = of_type("Microsoft.App/jobs")
check("Z1 there is one website", len(websites) == 1, len(websites))
check("Z4 the jobs are declared", len(jobs) == 1 and "copy" in jobs[0], len(jobs))
job_list = template["variables"].get("jobs", [])
check(
    "Z4 three jobs: auto-decline at minute 0, purge at minute 30, init-db by hand",
    [(j["name"], j["schedule"]) for j in job_list]
    == [("job-auto-decline", "0 * * * *"), ("job-purge", "30 * * * *"), ("job-init-db", "")],
    job_list,
)
for resource in websites + jobs:
    kind = resource["type"].split("/")[-1].split("@")[0]
    props = resource["properties"]
    check(
        f"Z9 {kind} use the one environment",
        "Microsoft.App/managedEnvironments" in props["environmentId"]
        and "cae-community-centre" in props["environmentId"],
        props["environmentId"],
    )
    check(
        f"Z9 {kind} name the Consumption profile",
        props.get("workloadProfileName") == "Consumption",
        props.get("workloadProfileName"),
    )
for resource in environments + websites + jobs:
    kind = resource["type"].split("/")[-1].split("@")[0]
    check(
        f"Z9 {kind} are declared with API version 2026-07-01",
        resource.get("apiVersion") == "2026-07-01",
        resource.get("apiVersion"),
    )

print()
print(f"{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
PY
