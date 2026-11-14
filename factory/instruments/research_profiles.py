"""Explicit generic FX research units; never universal broker specifications.

Published pip/currency conventions and declared model constraints have different
provenance. Choosing this model does not certify historical broker feasibility.
Gold deliberately requires its own reviewed cost-equivalent/units definition.
"""

from decimal import Decimal as D
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from factory.contracts import InstrumentSpec, SYMBOLS

MODEL_VERSION = "generic-fx-base-unit-unlevered-cap1/v1"


class ReferenceText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def reference_text(data):
    parser = ReferenceText()
    parser.feed(data.decode("utf-8"))
    return re.sub(r"\s+", " ", " ".join(parser.parts))


def verified_fx_captures(directory):
    """Check captured retrieval identities and literal primary-source facts.

    Raw captures stay in operator state, not in redistributed project code.
    Initial verification is an authorized builder/operator action, not acceptance
    of an unverified runtime model proposal.
    """
    directory = Path(directory)
    receipts = {r["name"]: r for r in json.loads((directory / "retrievals.json").read_text())}
    expected = {
        "oanda-pip": "https://www.oanda.com/us-en/trading/learn/introduction-to-leverage-trading/what-is-a-pip/",
        "iso4217-list": "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml",
        "histdata-faq": "https://www.histdata.com/f-a-q/",
        "oanda-hours": "https://www.oanda.com/us-en/trading/hours-of-operation/",
    }
    captures = {}
    for name, url in expected.items():
        record = receipts[name]
        data = (directory / (name + ".capture")).read_bytes()
        if (
            record.get("status") != 200
            or record["url"] != url
            or not record["resolved_url"].startswith("https://")
            or not 1 <= len(data) <= 4 * 1024**2
            or hashlib.sha256(data).hexdigest() != record["sha256"]
        ):
            raise ValueError("PRIMARY_REFERENCE_CAPTURE_MISMATCH: " + name)
        captures[name] = data
    pip = reference_text(captures["oanda-pip"])
    if not all(
        term in pip
        for term in (
            "four decimal places",
            "1.1600 to 1.1605",
            "0.0005",
            "5-pip",
            "154.01 to 154.02",
            "EUR/USD currency pair with five decimal points",
            "yen pairs now extend to three decimal points",
        )
    ):
        raise ValueError("primary FX convention text changed; review required")
    faq = reference_text(captures["histdata-faq"])
    if not all(
        term in faq
        for term in (
            "WITHOUT Day Light Savings",
            "Eastern Standard Time",
            "Ask price is only included",
        )
    ):
        raise ValueError("provider timestamp/quote definition changed; review required")
    if b"<!DOCTYPE" in captures["iso4217-list"] or b"<!ENTITY" in captures["iso4217-list"]:
        raise ValueError("unsupported currency-reference XML declaration")
    currencies = {node.text for node in ET.fromstring(captures["iso4217-list"]).iter("Ccy")}
    if not {"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"} <= currencies:
        raise ValueError("required ISO currency references missing")
    return {
        "captures": captures,
        "receipts": {k: receipts[k] for k in expected},
        "pip_text": pip,
        "hours_text": reference_text(captures["oanda-hours"]),
    }


def generic_fx_profile(symbol, price_scale, empirical_grid):
    if symbol not in SYMBOLS or symbol == "XAUUSD":
        raise ValueError("UNKNOWN_SPEC: generic FX recipe does not define a Gold pip or contract")
    profile = InstrumentSpec(
        instrument=symbol,
        version=MODEL_VERSION,
        tick_size=D(empirical_grid),
        pip_size=D(".01") if symbol == "USDJPY" else D(".0001"),
        price_scale=price_scale,
        base_currency=symbol[:3],
        quote_currency=symbol[3:],
        contract_multiplier=D(1),
        volume_step=D(1),
        min_volume=D(1),
        max_volume=D(1),
        margin_rate=D(1),
        min_stop_ticks=1,
        synthetic=False,
        source=(
            "GENERIC_RESEARCH_NOT_BROKER: published FX pip/currency convention; "
            "empirical-grid research choice; base-unit quantity; unlevered 1-unit cap; "
            "no historical broker minimum/maximum/margin/session feasibility certified"
        ),
    )
    return profile
