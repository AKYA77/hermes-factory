#!/usr/bin/env python3
"""Verify the frozen goldens with every NautilusTrader import blocked.

The migration gate requires that the golden evidence survive NautilusTrader's
removal. This script installs a meta-path finder that raises on any
``nautilus_trader`` import, then runs the golden verifier. If the frozen goldens
can still be reproduced without the dependency, the evidence base is
independent of the package being removed.

Usage:
    .venv/bin/python scripts/verify_goldens_without_nautilus.py
"""

import importlib.abc
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


class BlockNautilus(importlib.abc.MetaPathFinder):
    """Refuse to import nautilus_trader or any submodule."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "nautilus_trader" or fullname.startswith("nautilus_trader."):
            raise ImportError(f"blocked by verify_goldens_without_nautilus: {fullname}")
        return None


def main() -> int:
    sys.meta_path.insert(0, BlockNautilus())
    sys.path.insert(0, str(SCRIPTS))

    verifier = SCRIPTS / "verify_raptor_goldens.py"
    source = verifier.read_text()
    namespace = {"__name__": "__main__", "__file__": str(verifier)}
    try:
        exec(compile(source, str(verifier), "exec"), namespace)
    except ImportError as exc:
        print(f"FAILED: the golden verifier still needs NautilusTrader: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
