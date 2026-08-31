"""MediaTek / Unisoc MCT (MediaTek Control Tool) client.

MediaTek phones do NOT use Qualcomm's 9008/Sahara/Firehose path. They use the
**MCT** protocol, which has a simple binary framing:

  request : <I> command   <I> payload length   payload
  response: <I> command   <I> data length      data

The MCT commands used here (mirroring the mtkclient command set):
  READ_NV_ITEM  = 0x1001   (index -> raw)
  WRITE_NV_ITEM = 0x1002   (index, raw)
  READ_AGDB_ITEM= 0x1021   (item id -> raw)   # AGDB stores modem NVRAM
  WRITE_AGDB_ITEM = 0x1022 (item id, raw)

IMEIs on MediaTek phones live in the modem NVRAM / AGDB, not in the Android
partition, so root is irrelevant — exactly like the Qualcomm path.
"""
from __future__ import annotations

import struct
from typing import Optional

from .transport import Transport


class MctError(Exception):
    pass


class Mct:
    """Client for the MediaTek MCT binary protocol."""

    READ_NV_ITEM = 0x1001
    WRITE_NV_ITEM = 0x1002
    READ_AGDB_ITEM = 0x1021
    WRITE_AGDB_ITEM = 0x1022

    #: Default AGDB item ids used to store IMEIs on many MediaTek boards. These
    #: vary per board; override via the backend's item parameter if needed.
    IMEI1_ITEM = 0x10001137
    IMEI2_ITEM = 0x10001139

    def __init__(self, transport: Transport):
        self.transport = transport

    # -- low level ---------------------------------------------------------
    def _tx(self, cmd: int, payload: bytes = b"") -> bytes:
        self.transport.send(struct.pack("<2I", cmd, len(payload)) + payload)
        rcmd, rlen = struct.unpack("<2I", self.transport.recv(8))
        if rcmd != cmd:
            raise MctError(f"MCT: expected cmd 0x{cmd:x}, got 0x{rcmd:x}")
        return self.transport.recv(rlen) if rlen else b""

    # -- NVRAM -------------------------------------------------------------
    def read_nv_item(self, index: int) -> bytes:
        return self._tx(self.READ_NV_ITEM, struct.pack("<I", index))

    def write_nv_item(self, index: int, data: bytes) -> None:
        self._tx(self.WRITE_NV_ITEM, struct.pack("<I", index) + data)

    def read_agdb(self, item_id: int) -> bytes:
        return self._tx(self.READ_AGDB_ITEM, struct.pack("<I", item_id))

    def write_agdb(self, item_id: int, data: bytes) -> None:
        self._tx(self.WRITE_AGDB_ITEM, struct.pack("<I", item_id) + data)


class MctUSB:
    """Find and claim a MediaTek MCT USB device.

    Supported VID/PID set (MediaTek / Unisoc / some Qualcomm-MCT boards). The
    caller can override if their board uses different endpoints.
    """

    DEVICES = [
        (0x0E8D, 0x00E0), (0x0E8D, 0x00E3), (0x0E8D, 0x00E5),
        (0x2B70, 0x055F), (0x2B70, 0x055E),
        (0x1004, 0x6000), (0x1004, 0x6001),
    ]

    def __init__(self, timeout_ms: int = 15000, vid: Optional[int] = None, pid: Optional[int] = None):
        import usb.core
        import usb.util

        self._usb = usb
        self.timeout = timeout_ms
        self._dev = None
        self._ep_out = None
        self._ep_in = None

    def find(self):
        for v, p in self.DEVICES:
            dev = self._usb.core.find(id_vendor=v, id_product=p)
            if dev:
                return dev
        return None

    def connect(self) -> Mct:
        dev = self.find()
        if dev is None:
            raise RuntimeError(
                "No MediaTek MCT device found. Put the phone into MCT/preloader "
                "mode (e.g. adb reboot preloader) and reconnect USB."
            )
        self._dev = dev
        cfg = dev.get_configuration()
        intf = cfg[0]
        self._usb.util.claim_interface(dev, intf.bInterfaceNumber)
        ep = intf[0]
        self._ep_out = dev.write_endpoint(ep.bEndpointAddress)
        self._ep_in = dev.read_endpoint(
            0x81 if ep.bmAttributes & 0x80 else ep.bEndpointAddress | 0x80
        )
        return Mct(_MctUsbTransport(self))


class _MctUsbTransport(Transport):
    def __init__(self, holder: MctUSB):
        self.h = holder

    def send(self, data: bytes) -> None:
        if self.h._ep_out is None:
            raise RuntimeError("MCT not connected")
        self.h._ep_out.write(data, self.h.timeout)

    def recv(self, n: int) -> bytes:
        if self.h._ep_in is None:
            raise RuntimeError("MCT not connected")
        buf = b""
        while len(buf) < n:
            chunk = self.h._ep_in.read(min(n - len(buf), 4096), self.h.timeout)
            if not chunk:
                break
            buf += chunk
        if len(buf) < n:
            raise TimeoutError(f"MCT expected {n} bytes, got {len(buf)}")
        return buf

    def close(self) -> None:
        if self.h._dev is not None:
            try:
                self.h._usb.util.release_interface(
                    self.h._dev, self.h._dev.get_configuration()[0].bInterfaceNumber
                )
            except Exception:
                pass


class FakeMct:
    """In-memory MCT device for tests. Stores NVRAM items in ``self.store``
    keyed by index (for READ/WRITE_NV_ITEM) and by AGDB item id."""

    def __init__(self, store: dict[int, bytes] | None = None):
        self.store = dict(store or {})
        self._tx = b""

    def on_send(self, data: bytes) -> None:
        cmd, plen = struct.unpack("<2I", data[:8])
        payload = data[8:]
        if cmd == Mct.READ_NV_ITEM:
            idx = struct.unpack("<I", payload[:4])[0]
            raw = self.store.get(idx, b"")
            self._tx += struct.pack("<2I", cmd, len(raw)) + raw
        elif cmd == Mct.WRITE_NV_ITEM:
            idx = struct.unpack("<I", payload[:4])[0]
            self.store[idx] = payload[4:]
            self._tx += struct.pack("<2I", cmd, 0)
        elif cmd == Mct.READ_AGDB_ITEM:
            item = struct.unpack("<I", payload[:4])[0]
            raw = self.store.get(item, b"")
            self._tx += struct.pack("<2I", cmd, len(raw)) + raw
        elif cmd == Mct.WRITE_AGDB_ITEM:
            item = struct.unpack("<I", payload[:4])[0]
            self.store[item] = payload[4:]
            self._tx += struct.pack("<2I", cmd, 0)
        else:
            self._tx += struct.pack("<2I", cmd, 0)

    def recv(self, n: int) -> bytes:
        if len(self._tx) < n:
            raise TimeoutError(f"fake MCT has {len(self._tx)} pending bytes")
        out, self._tx = self._tx[:n], self._tx[n:]
        return out

    def close(self) -> None:
        pass


def make_fake_mct_transport(store: dict[int, bytes] | None = None):
    """Return a (Transport, FakeMct) pair that implements the MCT framing."""
    dev = FakeMct(store)
    return _MctFakeTransport(dev), dev


class _MctFakeTransport(Transport):
    def __init__(self, device: FakeMct):
        self.device = device

    def send(self, data: bytes) -> None:
        self.device.on_send(data)

    def recv(self, n: int) -> bytes:
        return self.device.recv(n)

    def close(self) -> None:
        self.device.close()
