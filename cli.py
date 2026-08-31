"""Headless CLI for the IMEI Toolkit — no GUI needed (batch / scripting).

Examples:
  python cli.py parse 353555001400008
  python cli.py validate 35355500140000
  python cli.py generate --tac 353555 --serial 140000
  python cli.py format 353555001400008 --style 3x3
  python cli.py read --family firehose --programmer prog.mbn --item 136541 --fmt le84
  python cli.py write --family firehose --programmer prog.mbn --item 136541 \
      --fmt le84 --imei 353555001400008
  python cli.py read --family mct --item 0x10001137
  python cli.py backup --family firehose --programmer prog.mbn --out backup.json
  python cli.py restore --family firehose --programmer prog.mbn --in backup.json
  python cli.py csv-export --family firehose --mode fake --out imeis.csv
  python cli.py csv-import --family firehose --mode fake --in imeis.csv --items 136541,136542
  python cli.py test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import (
    Sahara,
    USBTransport,
    Mct,
    MctUSB,
    make_fake_transport,
    make_fake_mct_transport,
    imei_to_raw,
    luhn_checksum,
    luhn_valid,
    make_valid_imei,
    normalize_imei,
    generate_imei,
    parse_imei,
    format_display,
    auto_detect,
    export_csv,
    import_csv,
    FirehoseBackend,
    MctBackend,
    AppleBackend,
    make_apple_reader,
    make_apple_writer,
)
from main import _demo_imei


# ---------------------------------------------------------------- helpers --
def _build_backend(args) -> "Backend":
    family = args.family
    mode = getattr(args, "mode", "usb")
    if family == "firehose":
        if mode == "fake":
            items = _items_from_args(args)
            seed = _demo_imei(len(items))
            store = {it: imei_to_raw(seed[i], args.fmt) for i, it in enumerate(items)}
            transport, dev = make_fake_transport(store)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mbn") as f:
                f.write(b"FAKE-PROGRAMMER")
                prog = f.name
            firehose = Sahara(transport).load_programmer(prog)
            os.unlink(prog)
            return FirehoseBackend(firehose, items)
        if not args.programmer or not os.path.isfile(args.programmer):
            raise SystemExit("firehose/usb requires --programmer <file>")
        transport = USBTransport()
        transport.connect()
        return FirehoseBackend(Sahara(transport).load_programmer(args.programmer),
                              _items_from_args(args))
    if family == "mct":
        if mode == "fake":
            items = _items_from_args(args)
            seed = _demo_imei(len(items))
            store = {it: imei_to_raw(seed[i], args.fmt) for i, it in enumerate(items)}
            transport, dev = make_fake_mct_transport(store)
            return MctBackend(Mct(transport), items, use_agdb=True)
        usb = MctUSB()
        return MctBackend(usb.connect(), _items_from_args(args), use_agdb=True)
    # apple
    if mode == "fake":
        items = _items_from_args(args)
        seed = _demo_imei(len(items))
        reader = make_apple_reader({i: seed[i - 1] for i in items})
        store = {i: seed[i - 1] for i in items}
        return AppleBackend(reader, make_apple_writer(store), list(range(1, len(items) + 1)))
    def _reader(slot: int) -> str:
        try:
            import pyim  # type: ignore
            return pyim.get_imei(slot)
        except Exception:
            return ""
    return AppleBackend(_reader, None)


def _items_from_args(args) -> list[int]:
    if getattr(args, "items", None):
        return [int(x, 0) for x in args.items.split(",")]
    if getattr(args, "item", None):
        return [int(args.item, 0)]
    if args.family == "mct":
        return [Mct.IMEI1_ITEM, Mct.IMEI2_ITEM]
    if args.family == "apple":
        return [1, 2]
    return [136541, 136542]


# ---------------------------------------------------------------- commands --
def cmd_parse(args) -> int:
    p = parse_imei(args.imei)
    print(json.dumps({
        "imei": p.imei, "tac": p.tac, "serial": p.serial, "check": p.check,
        "maker": p.maker, "luhn_ok": p.luhn_ok,
        "display_3x3": format_display(p.imei, "3x3"),
        "display_tac": format_display(p.imei, "tac"),
    }, indent=2))
    return 0


def cmd_validate(args) -> int:
    d = normalize_imei(args.imei)
    if len(d) == 15 and d.isdigit():
        ok = luhn_valid(d)
        print(f"{'VALID' if ok else 'INVALID (fixed: ' + d[:14] + str(luhn_checksum(d[:14])) + ')'}  {d}")
        return 0 if ok else 1
    print(f"not 14/15 digits: {d!r}")
    return 2


def cmd_generate(args) -> int:
    imei = generate_imei(args.tac, args.serial, int(args.fill or 0))
    print(imei)
    return 0


def cmd_format(args) -> int:
    print(format_display(args.imei, args.style))
    return 0


def cmd_read(args) -> int:
    be = _build_backend(args)
    for item in _items_from_args(args):
        imei = be.read_imei(item, args.fmt)
        print(f"{item}\t{args.fmt}\t{imei}")
    return 0


def cmd_write(args) -> int:
    be = _build_backend(args)
    if not luhn_valid(args.imei):
        print(f"ERROR: {args.imei} is not Luhn-valid", file=sys.stderr)
        return 1
    for item in _items_from_args(args):
        be.write_imei(args.imei, item, args.fmt)
        back = be.read_imei(item, args.fmt)
        print(f"{item}\t{args.fmt}\t{args.imei}\tverify={'OK' if back == args.imei else back}")
    return 0


def cmd_backup(args) -> int:
    be = _build_backend(args)
    items = _items_from_args(args)
    data = {"family": args.family, "items": {}}
    for it in items:
        raw = be.read_raw(it, args.fmt)
        data["items"][str(it)] = {"raw_hex": raw.hex(), "fmt": args.fmt}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"backup wrote {len(items)} item(s) -> {args.out}")
    return 0


def cmd_restore(args) -> int:
    be = _build_backend(args)
    with open(args.infile, encoding="utf-8") as f:
        data = json.load(f)
    ok = 0
    for item_str, meta in data.get("items", {}).items():
        it = int(item_str)
        if it not in _items_from_args(args):
            continue
        be.write_raw(it, bytes.fromhex(meta["raw_hex"]), meta.get("fmt", args.fmt))
        ok += 1
    print(f"restored {ok} item(s) from {args.infile}")
    return 0


def cmd_csv_export(args) -> int:
    be = _build_backend(args)
    rows = []
    for i, item in enumerate(_items_from_args(args)):
        try:
            imei = be.read_imei(item, args.fmt)
        except Exception:
            continue
        p = parse_imei(imei)
        rows.append({"slot": i + 1, "imei": imei, "maker": p.maker,
                     "luhn_ok": p.luhn_ok, "item": item, "fmt": args.fmt})
    export_csv(rows, args.out)
    print(f"csv-export wrote {len(rows)} row(s) -> {args.out}")
    return 0


def cmd_csv_import(args) -> int:
    be = _build_backend(args)
    ok = 0
    for r in import_csv(args.infile):
        if be.family == "apple" and be.writer is None:
            print(f"apple: no writer configured, skipping {r['imei']}", file=sys.stderr)
            continue
        be.write_imei(r["imei"], int(r["item"]), r.get("fmt") or "ascii")
        ok += 1
    print(f"csv-import wrote {ok} row(s) from {args.infile}")
    return 0


def cmd_test(args) -> int:
    import test_protocol
    return test_protocol.main()


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--family", choices=["firehose", "mct", "apple", "fake"], default="firehose")
    p.add_argument("--mode", choices=["usb", "fake"], default="fake")
    p.add_argument("--programmer", default="")
    p.add_argument("--item", default="", help="NVRAM/AGDB item (or slot for apple)")
    p.add_argument("--items", default="", help="comma-separated item list")
    p.add_argument("--fmt", default="le84", choices=["le84", "ascii", "rev", "u32"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="IMEI Toolkit CLI (headless)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("parse", help="parse an IMEI (TAC/maker/format)")
    sp.add_argument("imei")
    sp.set_defaults(fn=cmd_parse)

    sp = sub.add_parser("validate", help="validate/auto-fix Luhn")
    sp.add_argument("imei")
    sp.set_defaults(fn=cmd_validate)

    sp = sub.add_parser("generate", help="generate a valid IMEI from TAC+serial")
    sp.add_argument("--tac", required=True)
    sp.add_argument("--serial", default="")
    sp.add_argument("--fill", default="0")
    sp.set_defaults(fn=cmd_generate)

    sp = sub.add_parser("format", help="display-format an IMEI")
    sp.add_argument("imei")
    sp.add_argument("--style", default="3x3", choices=["3x3", "tac", "plain"])
    sp.set_defaults(fn=cmd_format)

    sp = sub.add_parser("read", help="read IMEIs from a device/family")
    _add_common(sp)
    sp.set_defaults(fn=cmd_read)

    sp = sub.add_parser("write", help="write an IMEI to a device/family")
    _add_common(sp)
    sp.add_argument("--imei", required=True)
    sp.set_defaults(fn=cmd_write)

    sp = sub.add_parser("backup", help="backup all IMEIs to JSON")
    _add_common(sp)
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=cmd_backup)

    sp = sub.add_parser("restore", help="restore IMEIs from a JSON backup")
    _add_common(sp)
    sp.add_argument("--in", dest="infile", required=True)
    sp.set_defaults(fn=cmd_restore)

    sp = sub.add_parser("csv-export", help="export all IMEIs to CSV")
    _add_common(sp)
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=cmd_csv_export)

    sp = sub.add_parser("csv-import", help="import IMEIs from CSV and write them")
    _add_common(sp)
    sp.add_argument("--in", dest="infile", required=True)
    sp.set_defaults(fn=cmd_csv_import)

    sp = sub.add_parser("test", help="run the protocol self-test")
    sp.set_defaults(fn=cmd_test)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
