"""Dependency disposition gate: documented advisories pass, new ones fail."""

import json

import pytest

from scripts.dependency_disposition import main

PIP_KNOWN = {
    "dependencies": [
        {
            "name": "fsspec",
            "version": "2026.2.0",
            "vulns": [
                {
                    "id": "PYSEC-2026-4217",
                    "aliases": ["GHSA-27vj-qcqg-25rc", "CVE-2026-104851"],
                    "fix_versions": ["2026.6.0"],
                }
            ],
        }
    ]
}

PIP_UNKNOWN = {
    "dependencies": [
        {
            "name": "somepkg",
            "version": "1.0",
            "vulns": [{"id": "PYSEC-9999-9999", "aliases": [], "fix_versions": []}],
        }
    ]
}

NPM_CHAIN = {
    "vulnerabilities": {
        "deepmerge": {
            "severity": "low",
            "via": [
                {
                    "source": 1243505,
                    "name": "deepmerge",
                    "url": "https://github.com/advisories/GHSA-gcqx-w48m-w2h4",
                }
            ],
            "range": ">=4.2.0",
            "effects": ["@sveltejs/vite-plugin-svelte"],
            "nodes": [],
        },
        "@sveltejs/vite-plugin-svelte": {
            "severity": "low",
            "via": ["deepmerge"],
            "range": "*",
            "effects": ["@sveltejs/kit"],
            "nodes": [],
        },
    }
}

NPM_UNKNOWN = {
    "vulnerabilities": {
        "somepkg": {
            "severity": "high",
            "via": [
                {
                    "source": 1,
                    "name": "somepkg",
                    "url": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz",
                }
            ],
            "range": ">=1",
            "effects": [],
            "nodes": [],
        }
    }
}


def write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return path


def test_documented_python_advisory_passes(tmp_path, capsys):
    path = write(tmp_path, "pip.json", PIP_KNOWN)
    assert main(["--pip", str(path)]) == 0
    assert "DISPOSITIONED fsspec" in capsys.readouterr().out


def test_unknown_python_advisory_fails(tmp_path, capsys):
    path = write(tmp_path, "pip.json", PIP_UNKNOWN)
    assert main(["--pip", str(path)]) == 1
    assert "UNACCEPTED somepkg" in capsys.readouterr().out


def test_npm_derived_chain_passes_regardless_of_order(tmp_path, capsys):
    payload = {
        "vulnerabilities": {
            "@sveltejs/vite-plugin-svelte": NPM_CHAIN["vulnerabilities"][
                "@sveltejs/vite-plugin-svelte"
            ],
            "deepmerge": NPM_CHAIN["vulnerabilities"]["deepmerge"],
        }
    }
    path = write(tmp_path, "npm.json", payload)
    assert main(["--npm", str(path)]) == 0
    out = capsys.readouterr().out
    assert "DISPOSITIONED deepmerge" in out
    assert "DISPOSITIONED @sveltejs/vite-plugin-svelte" in out


def test_unknown_npm_advisory_fails(tmp_path, capsys):
    path = write(tmp_path, "npm.json", NPM_UNKNOWN)
    assert main(["--npm", str(path)]) == 1
    assert "UNACCEPTED somepkg" in capsys.readouterr().out


def test_gate_requires_exactly_one_input(tmp_path):
    with pytest.raises(SystemExit):
        main([])
