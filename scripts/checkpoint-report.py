"""Create NOT_READY checkpoint evidence from actual local reports, never a release."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata as md
import json
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
bench = read("reports/runtime/benchmark-report.json")
# The benchmark records the composite scientific identity
# "<git-sha>@source-sha256:<hash>"; git only understands the sha part.
benchmark_commit = bench["code_revision"].split("@", 1)[0]
subprocess.run(
    [
        "git",
        "diff",
        "--exit-code",
        benchmark_commit,
        "--",
        "factory",
        "apps",
        "config",
        "migrations",
        "tests",
        "pyproject.toml",
        "uv.lock",
    ],
    check=True,
    stdout=subprocess.DEVNULL,
)
suites = ET.parse("reports/runtime/test-results.xml").getroot().findall("testsuite")
counts = {
    k: sum(int(s.attrib.get(k, 0)) for s in suites)
    for k in ("tests", "failures", "errors", "skipped")
}
counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
counts["time_seconds"] = sum(float(s.attrib.get("time", 0)) for s in suites)
packages = []
for distribution in sorted(md.distributions(), key=lambda d: d.metadata["Name"].lower()):
    license_text = (
        distribution.metadata.get("License-Expression")
        or distribution.metadata.get("License")
        or "not declared in package metadata"
    )
    packages.append(
        {
            "name": distribution.metadata["Name"],
            "version": distribution.version,
            "license_metadata": " ".join(license_text.split())[:160],
        }
    )
write("reports/runtime/installed-packages.json", packages)
Path("THIRD_PARTY_LICENSES.md").write_text(
    "# Installed dependency license metadata\n\nGenerated using the project .venv interpreter. This is a development inventory,\nnot legal/security clearance. Libraries are installed, not vendored. Full license\ntexts remain in distributions. Source/client licensing does not license market\ndata. Nautilus is normally linked under LGPL-3.0-or-later.\n\n"
    "| Package | Version | License metadata (abbreviated) |\n|---|---|---|\n"
    + "".join(
        f"| {p['name']} | {p['version']} | {p['license_metadata'].replace('|', '/')} |\n"
        for p in packages
    )
)
commands = [
    {
        "command": "bash scripts/release-verify.sh",
        "exit_code": 1,
        "expected": "release gates not passed; refusal verified",
    },
    {"command": "uv lock && uv sync --frozen", "exit_code": 0},
    {"command": ".venv/bin/ruff check factory apps tests", "exit_code": 0},
    {"command": ".venv/bin/ruff format --check factory apps tests", "exit_code": 0},
    {
        "command": ".venv/bin/pytest -q --junitxml=reports/runtime/test-results.xml -o faulthandler_timeout=30",
        "exit_code": 0,
        "counts": counts,
    },
    {
        "command": "npm --prefix apps/dashboard run check",
        "exit_code": 0,
        "errors": 0,
        "warnings": 0,
    },
    {"command": "npm --prefix apps/dashboard run build", "exit_code": 0},
    {
        "command": ".venv/bin/python -m factory.operations.http_smoke",
        "exit_code": 0,
        "result": read("reports/runtime/http-smoke.json"),
    },
    {
        "command": "bash scripts/install.sh",
        "exit_code": 0,
        "repeat_execution": True,
        "scope": "development only",
    },
    {
        "command": "bash scripts/benchmark.sh reports/runtime/benchmark-report.json",
        "exit_code": 0,
        "source_commit": bench["code_revision"],
    },
    {
        "command": "FACTORY_STATE=.local/cli-smoke bash scripts/seed-fixtures.sh",
        "exit_code": 0,
        "repeated": True,
        "unique_jobs_after_two_calls": 1,
    },
    {
        "command": "FACTORY_STATE=.local/cli-smoke bash scripts/create-admin.sh",
        "exit_code": 0,
        "secrets_logged": False,
    },
    {
        "command": "FACTORY_STATE=.local/cli-smoke bash scripts/backup.sh .local/cli-backup-20261102",
        "exit_code": 0,
    },
    {
        "command": "bash scripts/restore-test.sh .local/cli-backup-20261102",
        "exit_code": 0,
        "result": read("reports/runtime/restore.json"),
    },
    {
        "command": "bash scripts/doctor.sh",
        "exit_code": 1,
        "expected": "NOT_READY; readiness is not passed",
    },
    {
        "command": "gh api repos/AKYA77/hermes-factory --jq '{full_name,private,permissions}'",
        "exit_code": 1,
        "error": "Forbidden",
    },
    {
        "command": "npm --prefix apps/dashboard audit --json",
        "exit_code": 1,
        "remaining_findings": 4,
        "severity": "low",
        "underlying_advisory": "GHSA-gcqx-w48m-w2h4",
    },
    {
        "command": "uvx --from pip-audit==2.9.0 pip-audit --path .venv/lib/python3.12/site-packages --format json --output reports/runtime/python-audit.json",
        "exit_code": 1,
        "remaining_findings": 1,
        "advisory": "PYSEC-2026-4217",
        "package": "fsspec==2026.2.0; exact Nautilus pin",
    },
]
report = {
    "status": "NOT_READY",
    "version": "0.1.0.dev0",
    "observation_scope": "initial checkpoint command observations only",
    "source_commit": bench["code_revision"],
    "report_base_commit": revision,
    "release_commit": None,
    "release_tag": None,
    "branch": "build/initial-factory",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "repository": {
        "existing_remote": "https://github.com/AKYA77/hermes-factory",
        "git_read_verified": True,
        "private_verified": False,
        "pushed": False,
        "pull_request": None,
        "creation_status": "EXISTING_REPO_REUSED; management access blocked",
    },
    "runtime": read("reports/runtime/doctor.json"),
    "python": platform.python_version(),
    "source_documents": {
        p: digest(p)
        for p in (
            "docs/source/Factory.pdf",
            "docs/source/Factory.extracted.txt",
            "CODEX_BUILD_PROMPT.md",
        )
    },
    "original_markdown_provided": False,
    "fixture_kind": "SYNTHETIC ONLY; no real historical data",
    "tests": counts,
    "commands": commands,
    "milestones_completed": [],
    "milestones": {
        f"C{i}": "BLOCKED_RELEASE" if i == 9 else "PARTIAL_IMPLEMENTATION" for i in range(10)
    },
    "acceptance": {
        f"T{i:02}": {
            "status": "PARTIAL_OR_PENDING",
            "details": "docs/acceptance-matrix.md; no full gate pass",
        }
        for i in range(1, 31)
    },
    "benchmark": bench,
    "packages": packages,
    "prior_failures": [
        "Arrow 21 pin incompatible with Nautilus >=25; corrected",
        "Initial lease test claimed before availability; corrected fixture clock",
        "HTTP TestClient socket access blocked in sandbox; rerun with socket capability",
        "npm initial pins had high advisories; updated compatible set",
        "SvelteKit 3 requires TypeScript 6 and new Vite configuration; migrated",
        "Initial HTTP smoke lacked static application identity; added metadata and reran",
        "First report generation used host Python without pyarrow; corrected to project .venv",
    ],
    "outstanding": "known-limitations.md",
    "ci": "NOT_RUN_ON_GITHUB",
    "vps": "NOT_TESTED",
    "handoff": "BLOCKED",
    "environment_draft": {
        "fields_saved": ["install_script", "start_skill", "network.allowed_domains"],
        "domains_added": ["api.github.com", "www.dukascopy.com", "datafeed.dukascopy.com"],
        "applied": False,
        "published": False,
    },
}
write("build-report.json", report)
write("benchmark-report.json", bench)
locks = {p: digest(p) for p in ("uv.lock", "apps/dashboard/package-lock.json")}
Path("dependency-lock-hashes.txt").write_text("".join(f"{h}  {p}\n" for p, h in locks.items()))
write(
    "release-manifest.json",
    {
        "status": "NOT_READY",
        "version": "0.1.0.dev0",
        "commit": report["source_commit"],
        "tag": None,
        "reason": "Mandatory C0-C9 and T01-T30 gates incomplete",
        "historical_data": False,
        "vps_verified": False,
        "ci_verified": False,
        "lock_hashes": locks,
        "files": {
            p: digest(p)
            for p in (
                "BLUEPRINT.md",
                "docs/source/Factory.pdf",
                "AGENTS.md",
                "CODEX_BUILD_PROMPT.md",
                "HERMES_AGENT_INSTRUCTIONS.md",
                "build-report.json",
                "known-limitations.md",
            )
        },
    },
)
print(
    json.dumps({"source_commit": report["source_commit"], "tests": counts, "status": "NOT_READY"})
)
