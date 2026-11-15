"""Fresh generated state seeded from REAL acquired HistData.com archives.

The source-registry panel reports provider provenance, fidelity and parser version,
so its smoke cannot be satisfied by synthetic rows -- it needs actual archived
partitions. This fixture imports one month per instrument from the retained
production archive directory into an isolated catalog, then creates an operator
token.

Read-only with respect to the source archives: they are opened, hashed and parsed,
never modified. The imported catalog lives entirely inside the isolated state.

    env -u PYTHONPATH .venv/bin/python scripts/source-registry-browser-fixture.py \
        --state <fresh-dir> [--archives /var/lib/hermes-factory/archives]
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument(
    "--archives",
    type=Path,
    default=Path("/var/lib/hermes-factory/archives"),
    help="directory holding retained <INSTRUMENT>-<YYYYMM>-ticks.zip archives",
)
args = parser.parse_args()
state = args.state
if state.exists() and any(state.iterdir()):
    raise SystemExit("Use a new isolated state; never overwrite earlier browser evidence")

from factory.data.resume import import_archive  # noqa: E402

# import_archive takes the catalog root path and wraps it itself.
imported = []
# One recent month per instrument: eight genuine provider partitions.
for path in sorted(args.archives.glob("*-202601-ticks.manifest.json")):
    manifest = json.loads(path.read_text())
    archive = path.with_name(path.name[: -len(".manifest.json")] + ".zip")
    if not archive.exists():
        continue
    stored, _metrics = import_archive(
        state / "catalog",
        {**manifest, "archive": str(archive)},
        {
            "provider": manifest["provider"],
            "source": f"{manifest['provider']} ASCII tick data, {manifest['instrument']} "
            f"{manifest['year']}-{manifest['month']:02d}",
            "license": "provider terms; historical research only, not broker metadata",
        },
    )
    imported.append(stored["dataset_hash"])

if len(imported) < 8:
    raise SystemExit(f"expected eight provider partitions, imported {len(imported)}")

# One unattributed rehearsal dataset: the panel must label datasets that carry no
# provider rather than silently counting them as provider-sourced.
from factory.data import Quote

rehearsal = [
    Quote(
        "EURUSD",
        1735689600 * 10**9 + i * 60 * 10**9,
        110000 + ((i * 37) % 113),
        110002 + ((i * 37) % 113),
        100000,
        "undeclared-rehearsal-extract",
        "rehearsal",
        i,
    )
    for i in range(24)
]
Catalog(state / "catalog").commit(
    rehearsal,
    repr(rehearsal).encode(),
    {
        "source": "Undeclared rehearsal extract; provider unknown",
        "license": "unknown provenance; not market evidence",
    },
)

subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
    check=True,
)
print(
    f"GENERATED source-registry fixture: {len(imported)} real provider partitions "
    f"imported, research paused, operator token created"
)
