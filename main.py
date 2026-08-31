"""IMEI Writer — full toolkit for Qualcomm / MediaTek / Apple phones.

Reads and writes IMEIs (any number of SIM slots) across:
  * Qualcomm 9008/EDL  (Sahara + Firehose)
  * MediaTek / Unisoc  (MCT)
  * Apple iPhone       (read + best-effort write)

Plus: Luhn validate/auto-fix, IMEI generation, TAC parse, display formats,
auto-detect storage format, backup/restore, CSV import/export, history log,
read-only lock. A "fake device" mode runs every protocol in-memory so the
whole app can be exercised with no phone connected.

Run:  python main.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import (
    Sahara,
    Firehose,
    USBTransport,
    Mct,
    MctUSB,
    make_fake_transport,
    make_fake_mct_transport,
    imei_to_raw,
    luhn_valid,
    luhn_checksum,
    only_digits,
    normalize_imei,
    generate_imei,
    parse_imei,
    format_display,
    auto_detect,
    backup_imeis,
    restore_imeis,
    export_csv,
    import_csv,
    FirehoseBackend,
    MctBackend,
    AppleBackend,
    make_apple_reader,
    make_apple_writer,
    FORMATS,
    raw_to_imei,
)

APP_TITLE = "IMEI Toolkit — Qualcomm / MediaTek / Apple"
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.jsonl")
DISPLAY_STYLES = ("3x3", "tac", "plain")


def _demo_imei(n: int = 2):
    """Return n valid demo IMEIs for fake seeding."""
    import random
    out = []
    for i in range(n):
        body = (f"{'35' if i % 2 == 0 else '99'}{random.randrange(10 ** 12):012d}")[:14]
        out.append(body + str(luhn_checksum(body)))
    return out


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("900x660")
        root.minsize(820, 580)

        self.backend = None
        self.firehose = None
        self.transport = None
        self.fake = None
        self.family: str = "firehose"
        self.history: list[dict] = []
        self.slot_rows: list[dict] = []

        # String/Boolean vars must exist before the UI is built (tabs reference them).
        self.family_var = tk.StringVar(value="firehose")
        self.mode_var = tk.StringVar(value="fake")
        self.ro_var = tk.BooleanVar(value=False)
        self.slots_var = tk.StringVar(value="2")

        self._build_ui()
        self._load_history()

    # --------------------------------------------------------------- UI ----
    def _build_ui(self) -> None:
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)

        self._tab_device()
        self._tab_tools()
        self._tab_backup()
        self._tab_log()

    def _tab_device(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Device")
        tab.columnconfigure(0, weight=1)

        # --- connection ---
        con = ttk.LabelFrame(tab, text="Connection")
        con.grid(row=0, column=0, sticky="we", padx=6, pady=6)
        con.columnconfigure(1, weight=1)

        ttk.Label(con, text="Family:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Radiobutton(con, text="Qualcomm 9008/Firehose (Samsung, Pixel, most Android)",
                        variable=self.family_var, value="firehose",
                        command=self._on_family_change).grid(row=0, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(con, text="MediaTek / Unisoc (MCT)",
                        variable=self.family_var, value="mct",
                        command=self._on_family_change).grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(con, text="Apple iPhone (read + best-effort write)",
                        variable=self.family_var, value="apple",
                        command=self._on_family_change).grid(row=2, column=1, columnspan=2, sticky="w")

        ttk.Label(con, text="Mode:").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        ttk.Radiobutton(con, text="USB (real phone)", variable=self.mode_var, value="usb").grid(row=3, column=1, sticky="w")
        ttk.Radiobutton(con, text="Fake device (test, no phone)", variable=self.mode_var, value="fake").grid(row=3, column=2, sticky="w", padx=12)

        self.prog_var = tk.StringVar()
        ttk.Label(con, text="Programmer (.mbn/.elf):").grid(row=4, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(con, textvariable=self.prog_var).grid(row=4, column=1, sticky="we", padx=4)
        ttk.Button(con, text="Browse...", command=self._browse_programmer).grid(row=4, column=2, sticky="w")
        self.prog_row = 4

        ttk.Checkbutton(con, text="Read-only / lock (disable writes)", variable=self.ro_var,
                        command=self._apply_lock).grid(row=5, column=1, columnspan=2, sticky="w", pady=(4, 0))

        btns = ttk.Frame(con)
        btns.grid(row=6, column=0, columnspan=3, sticky="w", padx=4, pady=(4, 6))
        ttk.Button(btns, text="Connect & Load", command=self._connect).grid(row=0, column=0, sticky="w")
        ttk.Button(btns, text="Disconnect", command=self._disconnect).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(btns, text="Test Protocol (fake)", command=self._test_protocol).grid(row=0, column=2, sticky="w", padx=6)

        # --- slots ---
        sl = ttk.LabelFrame(tab, text="IMEI slots (multi-SIM)")
        sl.grid(row=1, column=0, sticky="we", padx=6, pady=(0, 6))

        hdr = ttk.Frame(sl)
        hdr.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Label(hdr, text="Number of SIM slots:").pack(side="left")
        scb = ttk.Combobox(hdr, textvariable=self.slots_var, values=["2", "3", "4"],
                           state="readonly", width=3)
        scb.pack(side="left", padx=6)
        scb.bind("<<ComboboxSelected>>", lambda e: self._rebuild_slots())
        ttk.Button(hdr, text="Read All", command=self._read_all).pack(side="left", padx=6)
        ttk.Button(hdr, text="Write All", command=self._write_all).pack(side="left")
        ttk.Button(hdr, text="Auto-detect fmt", command=self._auto_detect).pack(side="left", padx=6)
        ttk.Button(hdr, text="Parse TAC/maker", command=self._parse_all).pack(side="left")

        self.slots_content = ttk.Frame(sl)
        self.slots_content.pack(fill="x", padx=4, pady=2)
        self._rebuild_slots()

    def _tab_tools(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="IMEI Tools")
        tab.columnconfigure(0, weight=1)

        def lab_frame(parent, title, row):
            lf = ttk.LabelFrame(parent, text=title)
            lf.grid(row=row, column=0, sticky="we", padx=6, pady=4)
            lf.columnconfigure(1, weight=1)
            return lf

        # validate / fix
        vf = lab_frame(tab, "Validate / auto-fix Luhn", 0)
        self.valid_var = tk.StringVar()
        ttk.Label(vf, text="IMEI:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(vf, textvariable=self.valid_var).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(vf, text="Validate & fix", command=self._validate_fix).grid(row=0, column=2, sticky="w")
        self.valid_res = tk.StringVar()
        ttk.Label(vf, textvariable=self.valid_res).grid(row=1, column=0, columnspan=3, sticky="w", padx=4)

        # generate
        gf = lab_frame(tab, "Generate a valid IMEI (TAC + serial)", 1)
        self.gen_tac = tk.StringVar()
        self.gen_serial = tk.StringVar()
        self.gen_fill = tk.StringVar(value="0")
        ttk.Label(gf, text="TAC (6):").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(gf, textvariable=self.gen_tac, width=6).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(gf, text="serial (<=8):").grid(row=0, column=2, sticky="w", padx=4)
        ttk.Entry(gf, textvariable=self.gen_serial, width=8).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(gf, text="fill:").grid(row=0, column=4, sticky="w", padx=4)
        ttk.Entry(gf, textvariable=self.gen_fill, width=2).grid(row=0, column=5, sticky="w")
        self.gen_res = tk.StringVar()
        ttk.Label(gf, textvariable=self.gen_res).grid(row=1, column=0, columnspan=6, sticky="w", padx=4)
        ttk.Button(gf, text="Generate", command=self._generate).grid(row=1, column=6, sticky="w")
        ttk.Button(gf, text="Apply to SIM 1", command=self._apply_generate).grid(row=1, column=7, sticky="w", padx=4)

        # parse
        pf = lab_frame(tab, "Parse TAC / maker / display", 2)
        self.parse_var = tk.StringVar()
        ttk.Label(pf, text="IMEI:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(pf, textvariable=self.parse_var).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(pf, text="Parse", command=self._parse_one).grid(row=0, column=2, sticky="w")
        self.parse_res = tk.StringVar()
        ttk.Label(pf, textvariable=self.parse_res, wraplength=600, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=4, pady=(2, 4))

        # display format
        df = lab_frame(tab, "Display formatting", 3)
        self.disp_var = tk.StringVar()
        ttk.Label(df, text="IMEI:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(df, textvariable=self.disp_var).grid(row=0, column=1, sticky="we", padx=4)
        self.disp_style = tk.StringVar(value="3x3")
        ttk.Combobox(df, textvariable=self.disp_style, values=DISPLAY_STYLES,
                     state="readonly", width=6).grid(row=0, column=2, sticky="w", padx=4)
        ttk.Button(df, text="Format", command=self._format_preview).grid(row=0, column=3, sticky="w")
        self.disp_res = tk.StringVar()
        ttk.Label(df, textvariable=self.disp_res).grid(row=1, column=0, columnspan=4, sticky="w", padx=4)

    def _tab_backup(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Backup / CSV / History")
        tab.columnconfigure(0, weight=1)

        bf = ttk.LabelFrame(tab, text="Backup / Restore (JSON)")
        bf.grid(row=0, column=0, sticky="we", padx=6, pady=6)
        bf.columnconfigure(0, weight=1)
        self.backup_var = tk.StringVar()
        ttk.Entry(bf, textvariable=self.backup_var).grid(row=0, column=0, sticky="we", padx=4, pady=2)
        ttk.Button(bf, text="Browse...", command=lambda: self._browse(self.backup_var)).grid(row=0, column=1, sticky="w")
        ttk.Button(bf, text="Backup all IMEIs", command=self._backup).grid(row=1, column=0, sticky="w", padx=4, pady=(2, 6))
        ttk.Button(bf, text="Restore from backup", command=self._restore).grid(row=1, column=1, sticky="w")

        cf = ttk.LabelFrame(tab, text="CSV import / export")
        cf.grid(row=1, column=0, sticky="we", padx=6, pady=4)
        cf.columnconfigure(0, weight=1)
        self.csv_var = tk.StringVar()
        ttk.Entry(cf, textvariable=self.csv_var).grid(row=0, column=0, sticky="we", padx=4, pady=2)
        ttk.Button(cf, text="Browse...", command=lambda: self._browse(self.csv_var)).grid(row=0, column=1, sticky="w")
        ttk.Button(cf, text="Export slots to CSV", command=self._export_csv).grid(row=1, column=0, sticky="w", padx=4)
        ttk.Button(cf, text="Import CSV to slots", command=self._import_csv).grid(row=1, column=1, sticky="w")

        hf = ttk.LabelFrame(tab, text="History (this session + saved)")
        hf.grid(row=2, column=0, sticky="we", padx=6, pady=4)
        self.hist_text = tk.Text(hf, height=8, wrap="word", font=("Consolas", 9))
        self.hist_text.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Button(hf, text="Clear saved history", command=self._clear_history).pack(anchor="e", padx=4, pady=(0, 4))

    def _tab_log(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Log")
        lf = ttk.LabelFrame(tab, text="Operation log")
        lf.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_text = tk.Text(lf, wrap="word", font=("Consolas", 9))
        sb = ttk.Scrollbar(lf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0, 4))

    # ----------------------------------------------------------- helpers ----
    def _log(self, msg: str) -> None:
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')}  {msg}\n")
        self.log_text.see("end")

    def _browse(self, var: tk.StringVar) -> None:
        p = filedialog.askopenfilename(title="Choose file",
                                       filetypes=[("Any", "*.*"), ("JSON", "*.json"), ("CSV", "*.csv")])
        if p:
            var.set(p)

    def _browse_programmer(self) -> None:
        p = filedialog.askopenfilename(
            title="Choose Firehose programmer",
            filetypes=[("Programmer", "*.mbn *.elf *.raw *.xml"), ("All", "*.*")],
        )
        if p:
            self.prog_var.set(p)

    def _on_family_change(self) -> None:
        self.family = self.family_var.get()
        self._rebuild_slots()

    def _apply_lock(self) -> None:
        state = "disabled" if (self.ro_var.get() and self.backend is not None) else "normal"
        # (visual only; writes are also guarded in code)
        self._log(f"Read-only/lock = {self.ro_var.get()}")

    def _default_items(self, n: int) -> list[str]:
        fam = self.family
        if fam == "firehose":
            return ["136541", "136542"] + ["136543"] * max(0, n - 2)
        if fam == "mct":
            base = [Mct.IMEI1_ITEM, Mct.IMEI2_ITEM]
            return [str(x) for x in base[:n]] + [str(Mct.IMEI2_ITEM)] * max(0, n - 2)
        return [str(i) for i in range(1, n + 1)]  # apple slot indices

    def _rebuild_slots(self) -> None:
        try:
            n = int(self.slots_var.get() or 2)
        except ValueError:
            n = 2
        n = min(max(n, 2), 4)
        self.slots_var.set(str(n))
        for w in self.slots_content.winfo_children():
            w.destroy()
        self.slot_rows = []
        apple = self.family == "apple"
        for i in range(n):
            row = ttk.Frame(self.slots_content)
            row.grid(row=i, column=0, columnspan=10, sticky="we", pady=3, padx=4)
            row.columnconfigure(1, weight=1)
            ttk.Label(row, text=f"SIM {i+1}").grid(row=0, column=0, sticky="w")
            imei_var = tk.StringVar()
            ttk.Entry(row, textvariable=imei_var, width=18).grid(row=0, column=1, sticky="w", padx=4)
            fmt_var = tk.StringVar(value="le84")
            item_var = tk.StringVar(value=self._default_items(n)[i])
            col = 2
            if not apple:
                ttk.Label(row, text="item:").grid(row=0, column=col, sticky="e", padx=(8, 0))
                col += 1
                ttk.Entry(row, textvariable=item_var, width=12).grid(row=0, column=col, sticky="w", padx=4)
                col += 1
                ttk.Label(row, text="fmt:").grid(row=0, column=col, sticky="e", padx=(8, 0))
                col += 1
                ttk.Combobox(row, textvariable=fmt_var, values=list(FORMATS),
                             state="readonly", width=6).grid(row=0, column=col, sticky="w", padx=4)
                col += 1
            ttk.Button(row, text="Read",
                       command=lambda idx=i: self._read_imei(self.slot_rows[idx])).grid(row=0, column=col, padx=(8, 2))
            col += 1
            ttk.Button(row, text="Write",
                       command=lambda idx=i: self._write_imei(self.slot_rows[idx])).grid(row=0, column=col)
            col += 1
            info_var = tk.StringVar(value="—")
            ttk.Label(row, textvariable=info_var).grid(row=0, column=col, sticky="w", padx=8)
            self.slot_rows.append({
                "index": i + 1,
                "imei_var": imei_var,
                "item_var": item_var,
                "fmt_var": fmt_var,
                "info_var": info_var,
            })

    def _slot_item(self, slot: dict) -> int:
        if self.family == "apple":
            return slot["index"]
        try:
            return int(slot["item_var"].get())
        except ValueError:
            return 136541

    def _slot_fmt(self, slot: dict) -> str:
        if self.family == "apple":
            return "ascii"
        return slot["fmt_var"].get() or "le84"

    def _fill_info(self, slot: dict, imei: str) -> None:
        p = parse_imei(imei)
        slot["info_var"].set(
            f"Luhn:{'OK' if p.luhn_ok else 'BAD'}  TAC:{p.tac} {p.maker}  {format_display(imei, '3x3')}"
        )

    # --------------------------------------------------------- connections ---
    def _require(self):
        if self.backend is None:
            raise RuntimeError("Not connected. Click 'Connect & Load' first.")
        return self.backend

    def _new_fake_firehose(self, items):
        seed_imei = _demo_imei(len(items))
        seed = {it: imei_to_raw(seed_imei[i], "le84") for i, it in enumerate(items)}
        transport, dev = make_fake_transport(seed)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mbn") as f:
            f.write(b"FAKE-PROGRAMMER")
            prog = f.name
        firehose = Sahara(transport).load_programmer(prog)
        os.unlink(prog)
        return firehose, dev, transport

    def _connect(self) -> None:
        fam = self.family
        mode = self.mode_var.get()
        items = [self._slot_item(s) for s in self.slot_rows]
        self._log(f"--- Connect family={fam} mode={mode} ---")
        try:
            if fam == "firehose":
                prog = self.prog_var.get().strip()
                if mode == "usb":
                    if not prog or not os.path.isfile(prog):
                        raise RuntimeError("Choose an existing programmer file (.mbn/.elf) for USB mode.")
                    transport = USBTransport()
                    transport.connect()
                    self.transport = transport
                    firehose = Sahara(transport).load_programmer(prog)
                    self._log(f"Programmer loaded. properties={self._props(firehose)}")
                else:
                    firehose, dev, transport = self._new_fake_firehose(items)
                    self.transport = transport
                    self.fake = dev
                    self._log("Fake 9008 device ready. Click 'Read All'.")
                self.firehose = firehose
                self.backend = FirehoseBackend(firehose, items)
            elif fam == "mct":
                if mode == "usb":
                    usb = MctUSB()
                    mct = usb.connect()
                    self.transport = usb
                    self.backend = MctBackend(mct, items, use_agdb=True)
                else:
                    seed_imei = _demo_imei(len(items))
                    seed = {it: imei_to_raw(seed_imei[i], "le84") for i, it in enumerate(items)}
                    transport, dev = make_fake_mct_transport(seed)
                    mct = Mct(transport)
                    self.transport = transport
                    self.backend = MctBackend(mct, items, use_agdb=True)
                    self.fake = dev
                self._log("MCT ready.")
            else:  # apple
                if mode == "fake":
                    seed_imei = _demo_imei(len(items))
                    reader = make_apple_reader({i: seed_imei[i - 1] for i in items})
                    store = {i: seed_imei[i - 1] for i in items}
                    self.backend = AppleBackend(reader, make_apple_writer(store))
                    self.fake = store
                else:
                    self.backend = AppleBackend(self._real_apple_reader(), None)
                self._log("Apple backend ready (read + best-effort write).")
            self._log("Connected OK.")
        except Exception as e:  # noqa: BLE001
            self._log(f"CONNECT FAILED: {e!r}")
            messagebox.showerror(APP_TITLE, f"Connect failed:\n{e}")

    def _props(self, firehose) -> dict:
        try:
            return firehose.get_properties()
        except Exception:
            return {}

    def _real_apple_reader(self):
        def reader(slot: int) -> str:
            # Best-effort: try pyim (unix), else return "" (GUI explains to use iTunes).
            try:
                import pyim  # type: ignore
                return pyim.get_imei(slot)
            except Exception:
                return ""
        return reader

    def _disconnect(self) -> None:
        try:
            if self.transport is not None:
                self.transport.close()
        except Exception:  # noqa: BLE001
            pass
        self.backend = None
        self.firehose = None
        self.transport = None
        self._log("Disconnected.")

    # -------------------------------------------------------------- actions --
    def _read_imei(self, slot: dict) -> None:
        try:
            be = self._require()
            imei = be.read_imei(self._slot_item(slot), self._slot_fmt(slot))
            slot["imei_var"].set(imei)
            self._fill_info(slot, imei)
            self._log(f"READ  SIM{slot['index']} = {imei}")
            self._history(f"read SIM{slot['index']} {imei}")
        except Exception as e:  # noqa: BLE001
            self._log(f"READ SIM{slot['index']} FAILED: {e!r}")

    def _read_all(self) -> None:
        be = self._require()
        for s in self.slot_rows:
            self._read_imei(s)

    def _write_imei(self, slot: dict) -> None:
        if self.ro_var.get():
            self._log(f"WRITE SIM{slot['index']} blocked: read-only/lock is on.")
            return
        try:
            be = self._require()
            imei = normalize_imei(slot["imei_var"].get())
            if len(imei) == 14 and imei.isdigit():
                imei = imei + str(luhn_checksum(imei))
            if not luhn_valid(imei):
                raise ValueError(f"{slot['imei_var'].get()!r} is not a valid Luhn IMEI")
            item = self._slot_item(slot)
            fmt = self._slot_fmt(slot)
            be.write_imei(imei, item, fmt)
            slot["imei_var"].set(imei)
            back = be.read_imei(item, fmt)
            self._fill_info(slot, back)
            self._log(f"WROTE SIM{slot['index']} (item {item}, {fmt}) = {imei}   verify={'OK' if back == imei else back!r}")
            self._history(f"write SIM{slot['index']} {imei} item={item} fmt={fmt}")
        except Exception as e:  # noqa: BLE001
            self._log(f"WRITE SIM{slot['index']} FAILED: {e!r}")
            messagebox.showerror(APP_TITLE, f"Write failed:\n{e}")

    def _write_all(self) -> None:
        for s in self.slot_rows:
            self._write_imei(s)

    def _auto_detect(self) -> None:
        be = self._require()
        for s in self.slot_rows:
            try:
                raw = be.read_raw(self._slot_item(s), self._slot_fmt(s))
                imei, fmt = auto_detect(raw)
                s["fmt_var"].set(fmt)
                s["imei_var"].set(imei)
                self._fill_info(s, imei)
                self._log(f"SIM{s['index']} auto-detect -> fmt={fmt} imei={imei}")
            except Exception as e:  # noqa: BLE001
                self._log(f"SIM{s['index']} auto-detect failed: {e!r}")

    def _parse_all(self) -> None:
        for s in self.slot_rows:
            if only_digits(s["imei_var"].get()):
                self._fill_info(s, s["imei_var"].get())
                self._log(f"parsed SIM{s['index']} TAC/maker")

    # --------------------------------------------------- IMEI tools actions --
    def _validate_fix(self) -> None:
        raw = self.valid_var.get().strip()
        d = normalize_imei(raw)
        if len(d) != 15:
            self.valid_res.set(f"Input {raw!r} is not 14/15 digits. Normalized: {d!r}")
            return
        if luhn_valid(d):
            self.valid_res.set(f"{d}  -> Luhn VALID")
        else:
            fixed = d[:14] + str(luhn_checksum(d[:14]))
            self.valid_res.set(f"{d}  -> Luhn INVALID. Fixed: {fixed}")

    def _generate(self) -> None:
        try:
            imei = generate_imei(self.gen_tac.get(), self.gen_serial.get(),
                                 int(self.gen_fill.get() or 0))
            self.gen_res.set(f"Generated: {imei}  ({parse_imei(imei).maker})")
        except Exception as e:  # noqa: BLE001
            self.gen_res.set(f"generate error: {e}")

    def _apply_generate(self) -> None:
        try:
            imei = generate_imei(self.gen_tac.get(), self.gen_serial.get(),
                                 int(self.gen_fill.get() or 0))
            if self.slot_rows:
                self.slot_rows[0]["imei_var"].set(imei)
            self.nb.select(0)
            self._log(f"generated IMEI applied to SIM1: {imei}")
        except Exception as e:  # noqa: BLE001
            self.gen_res.set(f"generate error: {e}")

    def _parse_one(self) -> None:
        p = parse_imei(self.parse_var.get())
        self.parse_res.set(
            f"TAC: {p.tac}   maker: {p.maker}   serial: {p.serial}   check: {p.check}\n"
            f"3x3: {format_display(p.imei, '3x3')}   tac: {format_display(p.imei, 'tac')}"
        )

    def _format_preview(self) -> None:
        self.disp_res.set(format_display(self.disp_var.get(), self.disp_style.get()))

    # ------------------------------------------------------ backup / csv ----
    def _backup(self) -> None:
        be = self._require()
        path = self.backup_var.get().strip()
        if not path:
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        data: dict = {"family": self.family, "items": {}}
        for s in self.slot_rows:
            item = self._slot_item(s)
            fmt = self._slot_fmt(s)
            try:
                raw = be.read_raw(item, fmt)
                try:
                    imei = raw_to_imei(raw, fmt)
                except Exception:
                    imei = ""
                data["items"][str(item)] = {"raw_hex": raw.hex(), "fmt": fmt, "imei": imei}
            except Exception as e:  # noqa: BLE001
                data["items"][str(item)] = {"error": repr(e)}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._log(f"BACKUP written to {path}")
        self._history(f"backup -> {os.path.basename(path)}")

    def _restore(self) -> None:
        be = self._require()
        path = self.backup_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror(APP_TITLE, "Choose an existing backup .json file.")
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # map item -> slot
        item_to_slot = {self._slot_item(s): s for s in self.slot_rows}
        ok = 0
        for item_str, meta in data.get("items", {}).items():
            if "raw_hex" not in meta:
                continue
            item = int(item_str)
            slot = item_to_slot.get(item)
            if slot is None:
                continue
            slot["fmt_var"].set(meta.get("fmt", "le84"))
            be.write_raw(item, bytes.fromhex(meta["raw_hex"]), meta.get("fmt", "le84"))
            ok += 1
        self._log(f"RESTORED {ok} IMEI item(s) from {os.path.basename(path)}")
        self._history(f"restore <- {os.path.basename(path)} ({ok} items)")

    def _export_csv(self) -> None:
        path = self.csv_var.get().strip()
        if not path:
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        rows = []
        for s in self.slot_rows:
            imei = only_digits(s["imei_var"].get())
            p = parse_imei(imei) if imei else None
            rows.append({
                "slot": s["index"],
                "imei": imei,
                "maker": p.maker if p else "",
                "luhn_ok": p.luhn_ok if p else False,
                "item": self._slot_item(s),
                "fmt": self._slot_fmt(s),
            })
        export_csv(rows, path)
        self._log(f"EXPORTED {len(rows)} slot(s) to {os.path.basename(path)}")
        self._history(f"export csv -> {os.path.basename(path)}")

    def _import_csv(self) -> None:
        path = self.csv_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror(APP_TITLE, "Choose an existing CSV file.")
            return
        rows = import_csv(path)
        by_slot = {r["slot"]: r for r in rows}
        for s in self.slot_rows:
            r = by_slot.get(s["index"])
            if not r:
                continue
            s["imei_var"].set(r.get("imei", ""))
            if r.get("item"):
                s["item_var"].set(str(r["item"]))
            if r.get("fmt"):
                s["fmt_var"].set(r["fmt"])
            if r.get("imei"):
                self._fill_info(s, r["imei"])
        self._log(f"IMPORTED {len(rows)} slot(s) from {os.path.basename(path)}")
        self._history(f"import csv <- {os.path.basename(path)}")

    def _history(self, op: str) -> None:
        entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "op": op}
        self.history.append(entry)
        self._log_history(entry)
        try:
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:  # noqa: BLE001
            pass

    def _load_history(self) -> None:
        if not os.path.isfile(HISTORY_FILE):
            return
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:  # noqa: BLE001
                        continue
                    self.history.append(e)
                    self._log_history(e, redraw=False)
        except Exception:  # noqa: BLE001
            pass

    def _log_history(self, entry: dict, redraw: bool = True) -> None:
        self.hist_text.insert("end", f"{entry.get('ts','')}  {entry.get('op','')}\n")
        if redraw:
            self.hist_text.see("end")

    def _clear_history(self) -> None:
        self.history.clear()
        self.hist_text.delete("1.0", "end")
        if os.path.isfile(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        self._log("History cleared.")

    # ------------------------------------------------------------- testing ---
    def _test_protocol(self) -> None:
        self._log("--- Test Protocol (in-memory fake device) ---")
        try:
            import test_protocol
            test_protocol.main()
            self._log("ALL PROTOCOL TESTS PASSED")
            messagebox.showinfo(APP_TITLE, "Protocol self-test passed.\n"
                                          "Firehose + MCT + IMEI toolkit + Apple all OK.")
        except Exception as e:  # noqa: BLE001
            self._log(f"TEST FAILED: {e!r}")
            messagebox.showerror(APP_TITLE, f"Self-test failed:\n{e}")


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:  # noqa: BLE001
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
