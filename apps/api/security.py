"""Keep static Svelte bootstrap hashes and restrictive API headers consistent."""

import base64
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re


class Bootstrap(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hashes = set()
        self.inline = []
        self.script = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("http-equiv", "").lower() == "content-security-policy":
            for directive in values.get("content", "").split(";"):
                tokens = directive.split()
                if tokens and tokens[0] == "script-src":
                    self.hashes.update(
                        t for t in tokens[1:] if re.fullmatch(r"'sha256-[A-Za-z0-9+/]{43}='", t)
                    )
        if (
            tag == "script"
            and not values.get("src")
            and values.get("type", "")
            in ("", "module", "text/javascript", "application/javascript")
        ):
            self.script = []

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.inline.append("".join(self.script))
            self.script = None


def dashboard_csp(dashboard=None):
    hashes = set()
    if dashboard is not None:
        path = Path(dashboard) / "index.html"
        if path.exists():
            if path.stat().st_size > 1024**2:
                raise ValueError("dashboard index exceeds bootstrap verification budget")
            parsed = Bootstrap()
            parsed.feed(path.read_text())
            calculated = {
                "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
                for s in parsed.inline
            }
            if not calculated.issubset(parsed.hashes):
                raise ValueError(
                    "dashboard bootstrap CSP mismatch; rebuild dashboard before starting API"
                )
            hashes = calculated
    script = "'self'" + ((" " + " ".join(sorted(hashes))) if hashes else "")
    return (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src "
        + script
        + "; connect-src 'self'; frame-ancestors 'none'"
    )
