"""Unified backend interface over the three phone families:

  * Firehose (Qualcomm 9008/EDL)  -> FirehoseBackend
  * MCT (MediaTek/Unisoc)         -> MctBackend
  * Apple (iPhone/iPad)           -> AppleBackend

Each backend exposes the same small API so the GUI and toolkit can read/write
IMEIs, do backup/restore, and auto-detect format without caring about family:

    read_imei(item, fmt) -> str
    write_imei(imei, item, fmt) -> None
    read_raw(item, fmt) -> bytes
    write_raw(item, raw, fmt) -> None
    items() -> list[int]            # the IMEI item slots this backend knows
    family -> str                   # "firehose" | "mct" | "apple"
    supports_write -> bool          # Apple write is best-effort

``item`` is an opaque slot identifier. For Qualcomm/MCT it is the NVRAM/AGDB
item id; for Apple it is the slot index (1, 2, ...).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .protocol import imei_to_raw, raw_to_imei, luhn_valid
from .imei_toolkit import auto_detect, normalize_imei
from . import mct as _mct


class BackendError(Exception):
    pass


class Backend(ABC):
    family: str = "base"
    supports_write: bool = True

    @abstractmethod
    def read_raw(self, item: int, fmt: str) -> bytes: ...

    @abstractmethod
    def write_raw(self, item: int, raw: bytes, fmt: str) -> None: ...

    @abstractmethod
    def items(self) -> list[int]: ...

    # -- high level --------------------------------------------------------
    def read_imei(self, item: int, fmt: str = "le84") -> str:
        raw = self.read_raw(item, fmt)
        try:
            return raw_to_imei(raw, fmt)
        except Exception:
            return auto_detect(raw)[0]  # fallback to any valid format

    def write_imei(self, imei: str, item: int, fmt: str = "le84") -> None:
        imei = normalize_imei(imei)
        if len(imei) == 14 and imei.isdigit():
            from .protocol import luhn_checksum
            imei = imei + str(luhn_checksum(imei))
        if not luhn_valid(imei):
            raise BackendError(f"{imei!r} is not a valid Luhn IMEI")
        self.write_raw(item, imei_to_raw(imei, fmt), fmt)


class FirehoseBackend(Backend):
    """Firehose (Qualcomm). ``items`` = NVRAM item ids for the IMEI slots."""

    family = "firehose"

    def __init__(self, firehose, items: list[int] | None = None):
        self.firehose = firehose
        self._items = items or [136541, 136542]

    def items(self) -> list[int]:
        return list(self._items)

    def read_raw(self, item: int, fmt: str) -> bytes:
        self.firehose.set_nvram_index(item)
        return self.firehose.read_nvram()

    def write_raw(self, item: int, raw: bytes, fmt: str) -> None:
        self.firehose.set_nvram_index(item)
        self.firehose.write_nvram(raw)
        self.firehose.flush()


class MctBackend(Backend):
    """MediaTek MCT. ``items`` = NVRAM/AGDB item ids for the IMEI slots."""

    family = "mct"

    def __init__(self, mct, items: list[int] | None = None, use_agdb: bool = False):
        self.mct = mct
        self._items = items or [MctBackend.default_imei_items()]
        self.use_agdb = use_agdb

    @staticmethod
    def default_imei_items() -> list[int]:
        return [_mct.Mct.IMEI1_ITEM, _mct.Mct.IMEI2_ITEM]

    def items(self) -> list[int]:
        return list(self._items)

    def read_raw(self, item: int, fmt: str) -> bytes:
        if self.use_agdb:
            return self.mct.read_agdb(item)
        return self.mct.read_nv_item(item)

    def write_raw(self, item: int, raw: bytes, fmt: str) -> None:
        if self.use_agdb:
            self.mct.write_agdb(item, raw)
        else:
            self.mct.write_nv_item(item, raw)


# ---------------------------------------------------------------------------
# Apple (iPhone)
# ---------------------------------------------------------------------------
class AppleReadError(BackendError):
    pass


class AppleWriteError(BackendError):
    """Raised when a write cannot be performed (Apple restricts this)."""


class AppleBackend(Backend):
    """iPhone/iPad IMEIs.

    Reading uses ``pyim`` (Apple's IMEI/ICCID reader) when available, else a
    pluggable ``reader`` callable. Writing is best-effort: ``writer`` is a
    callable(slot, imei) that the caller can back with iTunes'
    "restore with IMEI" or an Apple-specific tool; if absent, writes raise
    ``AppleWriteError``.

    ``items()`` returns slot indices [1, 2, ...].
    """

    family = "apple"
    supports_write = False

    def __init__(self, reader, writer=None, slots: list[int] | None = None):
        self.reader = reader
        self.writer = writer
        self._slots = slots or [1, 2]

    def items(self) -> list[int]:
        return list(self._slots)

    def read_raw(self, item: int, fmt: str) -> bytes:
        imei = self.reader(item)
        if not imei:
            raise AppleReadError(f"no IMEI for slot {item}")
        return imei_to_raw(imei, "ascii")

    def write_raw(self, item: int, raw: bytes, fmt: str) -> None:
        if self.writer is None:
            raise AppleWriteError(
                "iPhone write not available in this build. Use iTunes "
                "'Restore' with the new IMEI, or set AppleBackend.writer."
            )
        imei = raw_to_imei(raw, fmt)
        self.writer(item, imei)


def make_apple_reader(imeis: dict[int, str] | None = None):
    """A reader callable for AppleBackend, used in tests / fake mode.

    Pass an empty dict to model a phone with no readable IMEI slots.
    """
    if imeis is None:
        imeis = {1: "000000000000001", 2: "000000000000002"}
    return lambda slot: dict(imeis).get(slot)


def make_apple_writer(store: dict[int, str]):
    """A writer callable that just records the write (for tests)."""
    return lambda slot, imei: store.__setitem__(slot, imei)
