"""IMEI toolkit: generation, parsing, TAC identification, display formatting,
auto-detection of storage format, backup/restore, and CSV import/export.

Pure logic — no USB or protocol dependencies, so it is fully unit-testable.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from typing import Iterable

from .protocol import (
    luhn_valid,
    luhn_checksum,
    imei_to_raw,
    raw_to_imei,
)

#: Storage formats we can encode/decode.
FORMATS = ("le84", "ascii", "rev", "u32")

#: Best-effort TAC-prefix -> manufacturer. Only the first two digits of the TAC
#: are used, so this is coarse (and intentionally conservative). NOT exhaustive.
TAC_PREFIX_MAKERS: dict[str, str] = {
    "35": "Samsung", "36": "Samsung", "93": "Samsung",
    "33": "Nokia", "34": "Nokia",
    "30": "Huawei", "31": "Huawei", "32": "Huawei",
    "01": "Apple", "02": "Apple", "03": "Apple", "04": "Apple",
    "05": "Apple", "06": "Apple", "07": "Apple", "08": "Apple",
    "09": "Apple", "10": "Apple", "11": "Apple",
    "16": "LG", "17": "LG", "18": "LG",
    "20": "Motorola", "21": "Motorola",
    "72": "ZTE", "73": "ZTE",
    "12": "Xiaomi", "13": "Xiaomi", "14": "Xiaomi",
    "22": "Google", "23": "Google", "24": "Google", "25": "Google",
}

_DIGITS = re.compile(r"\D+")


def only_digits(s: str) -> str:
    """Strip every non-digit character from ``s``."""
    return _DIGITS.sub("", s or "")


def normalize_imei(s: str) -> str:
    """Clean an IMEI string: strip junk, and if it is a 14-digit body, append
    the Luhn check digit. Returns a 15-digit string, or the cleaned input if it
    is not 14/15 digits."""
    d = only_digits(s)
    if len(d) == 14 and d.isdigit():
        d = d + str(luhn_checksum(d))
    return d


def make_valid_imei(body14: str) -> str:
    """body14 must be exactly 14 digits; returns the 15-digit IMEI."""
    body14 = only_digits(body14)
    if len(body14) != 14 or not body14.isdigit():
        raise ValueError(f"body must be 14 digits, got {body14!r}")
    return body14 + str(luhn_checksum(body14))


def generate_imei(tac: str, serial: str = "", fill: int = 0) -> str:
    """Build a full 15-digit IMEI from a 6-digit TAC and a (<=8) serial number.

    ``fill`` is a single digit (0-9) used to pad the serial to 8 digits if it is
    shorter. The Luhn check digit is appended automatically.
    """
    tac = only_digits(tac)
    if len(tac) != 6 or not tac.isdigit():
        raise ValueError(f"TAC must be 6 digits, got {tac!r}")
    serial = only_digits(serial)
    if not (0 <= fill <= 9):
        raise ValueError("fill must be 0-9")
    if len(serial) > 8:
        serial = serial[-8:]
    serial = (str(fill) * (8 - len(serial)) + serial)[-8:]
    body = tac + serial
    return make_valid_imei(body)


@dataclass
class ParsedImei:
    imei: str
    tac: str
    serial: str
    check: str
    maker: str = "unknown"
    luhn_ok: bool = False


def parse_imei(imei: str) -> ParsedImei:
    """Split an IMEI into TAC / serial / check and (best-effort) identify maker."""
    d = only_digits(imei)
    maker = TAC_PREFIX_MAKERS.get(d[:2], "unknown")
    return ParsedImei(
        imei=d,
        tac=d[0:6] if len(d) >= 6 else d,
        serial=d[6:14] if len(d) >= 14 else d[6:],
        check=d[14] if len(d) >= 15 else "",
        maker=maker,
        luhn_ok=luhn_valid(d),
    )


def format_display(imei: str, style: str = "3x3") -> str:
    """Human display forms of an IMEI.

    styles:
      "3x3"   -> 3-3-3-3-3   (353-555-001-400-008)
      "tac"   -> TAC-SNR-check (353555-00140000-8)
      "plain" -> no separators
    """
    d = only_digits(imei)
    if len(d) != 15:
        return d
    if style == "plain":
        return d
    if style == "tac":
        return f"{d[0:6]}-{d[6:14]}-{d[14]}"
    # default 3x3
    return "-".join(d[i:i + 3] for i in range(0, 15, 3))


def auto_detect(raw: bytes) -> tuple[str, str]:
    """Try each storage format until one decodes to a Luhn-valid IMEI.

    Returns (imei, fmt). Raises if none works.
    """
    for fmt in FORMATS:
        try:
            imei = raw_to_imei(raw, fmt)
        except Exception:
            continue
        if luhn_valid(imei):
            return imei, fmt
    raise ValueError("no IMEI storage format produced a Luhn-valid IMEI")


# ---------------------------------------------------------------------------
# Backup / restore
# ---------------------------------------------------------------------------
def backup_imeis(backend, items: Iterable[int], fmt: str) -> dict[int, bytes]:
    """Read every IMEI item from a backend; returns {item: raw_bytes}."""
    out: dict[int, bytes] = {}
    for it in items:
        try:
            out[it] = backend.read_raw(it, fmt)
        except Exception:
            continue
    return out


def restore_imeis(backend, backup: dict[int, bytes], fmt: str) -> list[int]:
    """Write a backup dict back to the backend. Returns items written."""
    done: list[int] = []
    for it, raw in backup.items():
        try:
            backend.write_raw(it, raw, fmt)
            done.append(it)
        except Exception:
            continue
    return done


# ---------------------------------------------------------------------------
# CSV import / export
# ---------------------------------------------------------------------------
def export_csv(rows: list[dict], path: str) -> None:
    """rows: list of dicts with keys: slot, imei, maker, luhn_ok, item, fmt."""
    if not rows:
        return
    keys = ["slot", "imei", "maker", "luhn_ok", "item", "fmt"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def import_csv(path: str) -> list[dict]:
    out: list[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["slot"] = int(row.get("slot", 0) or 0)
            row["item"] = int(row.get("item", 0) or 0)
            row["fmt"] = row.get("fmt") or "le84"
            row["luhn_ok"] = str(row.get("luhn_ok", "")).lower() in ("1", "true", "yes")
            out.append(row)
    return out
