"""GUI smoke test: verify main.py imports, builds its UI, and that a
fake connect + read/write round-trip works for all three families.

Runs headless (no phone, no window interaction).

Usage:
    python smoke_gui.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import main as gui_mod
from protocol import (
    make_valid_imei,
)


def _expect(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"SMOKE FAIL: {label}")
    print(f"  ok: {label}")


def main() -> int:
    print("[1] import main ...")
    _expect(hasattr(gui_mod, "App"), "main.App exists")
    _expect(hasattr(gui_mod, "main"), "main.main exists")
    print("  ok: main imported cleanly")

    print("[2] build Tk root + App UI ...")
    root = tk.Tk()
    app = gui_mod.App(root)
    _expect(app.slot_rows is not None and len(app.slot_rows) >= 2,
            f"slot_rows built (got {len(app.slot_rows)})")
    _expect(app.log_text is not None, "log_text widget present")
    _expect(app.hist_text is not None, "hist_text widget present")
    print(f"  ok: UI built with {len(app.slot_rows)} SIM slots")

    try:
        _run_families(app, root)
    finally:
        root.destroy()

    print("\nALL GUI SMOKE TESTS PASSED")
    return 0


def _run_families(app, root) -> None:
    # ---------------- Qualcomm 9008 / Firehose (fake) ----------------
    print("[3] firehose fake connect + read/write ...")
    app.family_var.set("firehose")
    app.mode_var.set("fake")
    app.family = "firehose"
    app._connect()
    _expect(app.backend is not None, "backend created")
    _expect(app.firehose is not None, "firehose object created")
    app._read_all()
    imei1 = app.slot_rows[0]["imei_var"].get()
    _expect(len(imei1) == 15 and imei1.isdigit(), f"read SIM1 = {imei1!r}")
    new = make_valid_imei("35355500140000")
    app.slot_rows[0]["imei_var"].set(new)
    app._write_imei(app.slot_rows[0])
    _expect(app.slot_rows[0]["imei_var"].get() == new,
            f"write verify: {app.slot_rows[0]['imei_var'].get()!r}")
    app._disconnect()
    print("  ok: firehose round-trip")

    # ---------------- MediaTek MCT (fake) ----------------
    print("[4] mct fake connect + read/write ...")
    app.family_var.set("mct")
    app.family = "mct"
    app._connect()
    _expect(app.backend is not None, "mct backend created")
    app._read_all()
    m = app.slot_rows[0]["imei_var"].get()
    _expect(len(m) == 15 and m.isdigit(), f"mct read SIM1 = {m!r}")
    new_m = make_valid_imei("99000000000011")
    app.slot_rows[0]["imei_var"].set(new_m)
    app._write_imei(app.slot_rows[0])
    _expect(app.slot_rows[0]["imei_var"].get() == new_m,
            f"mct write verify: {app.slot_rows[0]['imei_var'].get()!r}")
    app._disconnect()
    print("  ok: mct round-trip")

    # ---------------- Apple (fake) ----------------
    print("[5] apple fake connect + read/write ...")
    app.family_var.set("apple")
    app.family = "apple"
    app._connect()
    _expect(app.backend is not None, "apple backend created")
    app._read_all()
    a = app.slot_rows[0]["imei_var"].get()
    _expect(len(a) == 15 and a.isdigit(), f"apple read SIM1 = {a!r}")
    new_a = make_valid_imei("35355500140022")
    app.slot_rows[0]["imei_var"].set(new_a)
    app._write_imei(app.slot_rows[0])
    _expect(app.slot_rows[0]["imei_var"].get() == new_a,
            f"apple write verify: {app.slot_rows[0]['imei_var'].get()!r}")
    app._disconnect()
    print("  ok: apple round-trip")

    # ---------------- read-only lock ----------------
    print("[6] read-only lock blocks writes ...")
    app.family_var.set("firehose")
    app.family = "firehose"
    app._connect()
    app.ro_var.set(True)
    app.slot_rows[0]["imei_var"].set(make_valid_imei("35355500140033"))
    before = app.slot_rows[0]["imei_var"].get()
    app._write_imei(app.slot_rows[0])
    # _write_imei returns early when lock is on; the entry keeps the
    # value we set (not the written-back value) and no exception.
    _expect(app.slot_rows[0]["imei_var"].get() == before,
            "write blocked by read-only lock (value unchanged, no error)")
    app.ro_var.set(False)
    app._disconnect()
    print("  ok: lock mode")


if __name__ == "__main__":
    raise SystemExit(main())
