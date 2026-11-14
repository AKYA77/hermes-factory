"""Bounded free web downloads and exact HistData ASCII tick parsing.

Source timestamps are fixed EST (UTC-05:00), explicitly without DST per FAQ.
Raw source archives and notices are retained. No redistribution right is inferred.
"""

import calendar
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, InvalidOperation
import hashlib
import fcntl
import time
import urllib.error
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

from factory.contracts import SYMBOLS
from factory.data import Quote, atomic_bytes, sha256

PARSER_VERSION = "histdata-ascii-ticks/v2"
SCALE = 1000000
EST = timezone(timedelta(hours=-5))
MAX_ARCHIVE_BYTES = 128 * 1024**2
MAX_CSV_BYTES = 512 * 1024**2


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.active = attrs.get("id") == "file_down"
        if self.active and tag == "input" and attrs.get("type") == "hidden":
            self.fields[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = False


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlparse(newurl)
        if url.scheme != "https" or url.hostname not in ("histdata.com", "www.histdata.com"):
            raise ValueError("unapproved provider redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def preserve_interrupted(path, reason):
    """Keep unreceipted bytes, explicitly without inventing retrieval provenance."""
    if not path.exists():
        return
    failed = path.parent / "failed-captures"
    failed.mkdir(exist_ok=True)
    dest = failed / (path.name + f".{time.time_ns()}")
    os.replace(path, dest)
    atomic_bytes(
        dest.with_name(dest.name + ".json"),
        json.dumps(
            {
                "state": "UNVERIFIED_FAILED_CAPTURE",
                "reason": reason,
                "bytes_sha256": sha256(dest),
                "capture_provenance_verified": False,
                "recovered_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ).encode(),
    )


def download(root, instrument, year, month, *, refresh=False):
    if instrument not in SYMBOLS or year not in (2025, 2026) or not 1 <= month <= 12:
        raise ValueError("unsupported requested instrument/period")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"{instrument}-{year}{month:02}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        capture_root = root
        if refresh:
            import uuid

            # A recapture never replaces the original successful source receipt.
            capture_root = root / "captures" / f"{instrument}-{year}{month:02}" / uuid.uuid4().hex
            capture_root.mkdir(parents=True)
        for attempt in range(3):
            try:
                return _download(capture_root, instrument, year, month)
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("download retry accounting failed")


def _download(root, instrument, year, month):
    if instrument not in SYMBOLS or year not in (2025, 2026) or not 1 <= month <= 12:
        raise ValueError("unsupported requested instrument/period")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{instrument}-{year}{month:02}-ticks.zip"
    manifest_path = path.with_suffix(".manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (
            any(
                manifest.get(k) != v
                for k, v in {"instrument": instrument, "year": year, "month": month}.items()
            )
            or Path(manifest.get("archive", "")).resolve() != path.resolve()
        ):
            raise ValueError("cached source identity/path mismatch")
        inspect_archive(path, instrument, year, month)
        if sha256(path) != manifest["sha256"]:
            raise ValueError("source archive checksum mismatch")
        return manifest
    if path.exists():
        preserve_interrupted(
            path,
            "source bytes present without a success receipt; reacquire rather than forge provenance",
        )
    preserve_interrupted(
        path.with_suffix(".pending"), "interrupted download; no verified retrieval receipt"
    )
    page_url = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/{instrument.lower()}/{year}/{month}"
    opener = urllib.request.build_opener(
        HTTPSOnly(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    with opener.open(page_url, timeout=30) as response:
        page = response.read(500001)
    if len(page) > 500000:
        raise ValueError("provider page exceeds cap")
    form = DownloadForm()
    form.feed(page.decode("utf-8"))
    expected = {
        "fxpair": instrument,
        "date": str(year),
        "datemonth": f"{year}{month:02}",
        "platform": "ASCII",
        "timeframe": "T",
    }
    if not form.fields.get("tk") or any(form.fields.get(k) != v for k, v in expected.items()):
        raise ValueError("provider form does not match requested tick file")
    request = urllib.request.Request(
        "https://www.histdata.com/get.php",
        data=urllib.parse.urlencode(form.fields).encode(),
        headers={
            "Referer": page_url,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "HermesFactory historical research pilot",
        },
    )
    temporary = path.with_suffix(".pending")
    try:
        with opener.open(request, timeout=60) as response, temporary.open("xb") as out:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARCHIVE_BYTES:
                raise ValueError("archive exceeds bounded pilot download cap")
            size = 0
            digest = hashlib.sha256()
            while chunk := response.read(65536):
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise ValueError("archive exceeds download cap")
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        # Reject HTML/error responses, zip bombs and unexpected instrument files.
        inspect_archive(temporary, instrument, year, month)
        manifest = {
            "provider": "HistData.com",
            "instrument": instrument,
            "year": year,
            "month": month,
            "sha256": digest.hexdigest(),
            "bytes": size,
            "page_url": page_url,
            "download_url": "https://www.histdata.com/get.php",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider_page_sha256": hashlib.sha256(page).hexdigest(),
            "source_timezone": "UTC-05:00 fixed; no DST",
            "source_precision": "millisecond",
            "source_price_scale": SCALE,
            "parser_version": PARSER_VERSION,
            "cost": "free web download",
            "synthetic": False,
            "usage": "owner-authorized local research; redistribution not asserted",
            "archive": str(path.resolve()),
        }
        os.replace(temporary, path)
        atomic_bytes(manifest_path, json.dumps(manifest, indent=2).encode())
        # Preserve source page/offer without persisting the temporary form token.
        atomic_bytes(
            path.with_suffix(".page-sha256"), (manifest["provider_page_sha256"] + "\n").encode()
        )
        return manifest
    except BaseException:
        preserve_interrupted(temporary, "failed download; no success receipt")
        raise


def inspect_archive(path, instrument, year, month):
    name = f"DAT_ASCII_{instrument}_T_{year}{month:02}.csv"
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 10 or sum(i.file_size for i in infos) > MAX_CSV_BYTES:
            raise ValueError("archive expansion cap exceeded")
        if len([i for i in infos if i.filename == name]) != 1:
            raise ValueError("archive instrument/period filename mismatch")
        if any("/" in i.filename or "\\" in i.filename or i.flag_bits & 1 for i in infos):
            raise ValueError("unsupported archive path/encryption")
    return name


def parse_line(line, instrument, order, batch_id, expected_period=None):
    if instrument not in SYMBOLS or len(line) > 4096:
        raise ValueError("invalid instrument or row size")
    values = next(csv.reader([line]))
    if len(values) != 4:
        raise ValueError("tick row must have timestamp,bid,ask,placeholder-volume")
    stamp, bid, ask, _volume = values
    if len(stamp) != 18 or stamp[8] != " " or not (stamp[:8] + stamp[9:]).isdigit():
        raise ValueError("ambiguous timestamp precision")
    local = datetime.strptime(stamp[:15], "%Y%m%d %H%M%S").replace(tzinfo=EST)
    if expected_period and (local.year, local.month) != expected_period:
        raise ValueError("row outside declared source period")
    utc = local.astimezone(timezone.utc)
    ns = calendar.timegm(utc.timetuple()) * 10**9 + int(stamp[15:]) * 10**6
    prices = []
    for text in (bid, ask):
        try:
            value = D(text)
        except InvalidOperation as exc:
            raise ValueError("invalid source price") from exc
        # Multiplication under Decimal's arithmetic context can round an off-grid
        # value to a legal integer. Reject huge exponents before constructing an
        # exact ratio, then use integer arithmetic independent of that context.
        if not value.is_finite() or value <= 0 or not -6 <= value.adjusted() <= 12:
            raise ValueError("nonreversible price precision or invalid price")
        numerator, denominator = value.as_integer_ratio()
        integer, remainder = divmod(numerator * SCALE, denominator)
        if remainder or integer >= 2**63:
            raise ValueError("nonreversible price precision or invalid price")
        prices.append(integer)
    return Quote(
        instrument,
        ns,
        int(prices[0]),
        int(prices[1]),
        SCALE,
        "HistData.com",
        batch_id,
        order,
        source_precision="millisecond",
    )


def quotes_from_archive(manifest):
    path = Path(manifest["archive"])
    if sha256(path) != manifest["sha256"]:
        raise ValueError("source checksum mismatch")
    name = inspect_archive(path, manifest["instrument"], manifest["year"], manifest["month"])
    with zipfile.ZipFile(path) as archive, archive.open(name) as source:
        order = 0
        while line := source.readline(4097):
            if len(line) > 4096:
                raise ValueError("source row exceeds cap")
            if not line.strip():
                raise ValueError("unexpected empty source row")
            yield parse_line(
                line.decode("ascii"),
                manifest["instrument"],
                order,
                manifest["sha256"],
                (manifest["year"], manifest["month"]),
            )
            order += 1
