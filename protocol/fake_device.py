"""A fake 9008/EDL device that runs the Sahara + Firehose state machine on the
host side. Used to unit-test the protocol client without a real phone.

The fake device exposes a ``FakeTransport`` (from ``transport.py``) that the
client talks to. The device tracks:
  - Sahara: LOAD_PROGRAMMER, then ACK, then expect the programmer bytes.
  - Firehose: NOOP, GET_PROPERTIES, SET_NVRAM_INDEX, READ_NVRAM, WRITE_NVRAM,
              FLUSH, GO, RESET.
"""
from __future__ import annotations

import struct
from typing import Callable

from .transport import FakeTransport
from .protocol import (
    SAHARA_MAGIC,
    CMD_LOAD_PROGRAMMER,
    CMD_NOOP,
    CMD_RESET,
    CMD_GO,
    CMD_GET_PROPERTY,
    CMD_SET_NVRAM_INDEX,
    CMD_READ_NVRAM,
    CMD_WRITE_NVRAM,
    CMD_FLUSH,
    RESP_SUCCESS,
)


class FakeDevice:
    """Simulated 9008/EDL device with a configurable NVRAM store."""

    def __init__(self, nvram: dict[int, bytes] | None = None):
        self.nvram = dict(nvram or {})
        self._rx = b""          # bytes the device has "received" from host
        self._tx = b""          # bytes the device wants to send to host
        self._state = "sahara"  # "sahara" | "firehose"
        self._sahara_sub = "expect_header"  # "expect_header" | "expect_body" | "done"
        self._pending_len = 0
        self._pending_cmd = 0
        self._current_nvram_index = 0
        self.sent_log: list[bytes] = []
        self.received_log: list[bytes] = []
        self.on_send_cb: Callable[[bytes], None] | None = None
        self.nvram_writes: list[tuple[int, bytes]] = []

    # -- transport side ---------------------------------------------------
    def on_send(self, data: bytes) -> None:
        """The host called transport.send(data). The device consumes it."""
        self.received_log.append(data)
        self._rx += data
        if self._state == "sahara":
            self._step_sahara()
        else:
            self._step_firehose()

    def recv(self, n: int) -> bytes:
        if len(self._tx) < n:
            raise TimeoutError(
                f"device has {len(self._tx)} pending bytes, recv({n}) needs {n}"
            )
        out, self._tx = self._tx[:n], self._tx[n:]
        self.sent_log.append(out)
        return out

    def close(self) -> None:
        pass

    # -- device state machine ---------------------------------------------
    def _step_sahara(self) -> None:
        """Classic binary Sahara: header -> ACK -> body.

        The host sends the 12-byte header, then reads a 4-byte ACK, then sends
        the programmer body. So the device must ACK the header immediately.
        """
        if self._sahara_sub == "expect_header":
            if len(self._rx) < 12:
                return
            header = self._rx[:12]
            self._rx = self._rx[12:]
            magic, cmd, length = struct.unpack("<I2I", header)
            if magic != SAHARA_MAGIC or cmd != CMD_LOAD_PROGRAMMER:
                return  # would NAK in a real device
            self._pending_cmd = CMD_LOAD_PROGRAMMER
            self._pending_len = length
            # ACK the header immediately.
            self._tx += struct.pack("<2I", SAHARA_MAGIC, CMD_LOAD_PROGRAMMER)
            self._sahara_sub = "expect_body"
        elif self._sahara_sub == "expect_body":
            if len(self._rx) < self._pending_len:
                return
            self._rx = self._rx[self._pending_len:]
            self._state = "firehose"
            self._sahara_sub = "done"

    def _step_firehose(self) -> None:
        """Consume Firehose commands and produce responses."""
        while len(self._rx) >= 8:
            cmd, plen = struct.unpack("<2I", self._rx[:8])
            if len(self._rx) < 8 + plen:
                return
            header = self._rx[:8]
            payload = self._rx[8:8 + plen]
            self._rx = self._rx[8 + plen:]
            self._handle_firehose(cmd, payload)

    def _handle_firehose(self, cmd: int, payload: bytes) -> None:
        if cmd == CMD_NOOP:
            self._tx += struct.pack("<2I", CMD_NOOP, RESP_SUCCESS)
        elif cmd == CMD_RESET:
            self._tx += struct.pack("<2I", CMD_RESET, RESP_SUCCESS)
        elif cmd == CMD_GO:
            self._tx += struct.pack("<2I", CMD_GO, RESP_SUCCESS)
        elif cmd == CMD_FLUSH:
            self._tx += struct.pack("<2I", CMD_FLUSH, RESP_SUCCESS)
        elif cmd == CMD_SET_NVRAM_INDEX:
            index = struct.unpack("<I", payload)[0]
            self._current_nvram_index = index
            self._tx += struct.pack("<2I", cmd, RESP_SUCCESS)
        elif cmd == CMD_READ_NVRAM:
            data = self.nvram.get(getattr(self, "_current_nvram_index", 0), b"\x00" * 16)
            # Response: 8-byte (cmd,status) header, then <I> length, then data.
            self._tx += struct.pack("<2I", cmd, RESP_SUCCESS)
            self._tx += struct.pack("<I", len(data)) + data
        elif cmd == CMD_WRITE_NVRAM:
            length = struct.unpack("<I", payload[:4])[0]
            data = payload[4:4 + length]
            self.nvram[getattr(self, "_current_nvram_index", 0)] = data
            self.nvram_writes.append((getattr(self, "_current_nvram_index", 0), data))
            self._tx += struct.pack("<2I", cmd, RESP_SUCCESS)
        elif cmd == CMD_GET_PROPERTY:
            # Return: 8-byte (cmd,status) header, then <I> length, then XML.
            xml = (
                '<?xml version="1.0" ?>'
                '<properties>'
                '<property name="MaxPayloadSizeToTargetInBytes">1048576</property>'
                '<property name="MaxPayloadSizeFromTargetInBytes">8192</property>'
                '<property name="MaxXMLSizeInBytes">4096</property>'
                "</properties>"
            ).encode()
            self._tx += struct.pack("<2I", cmd, RESP_SUCCESS)
            self._tx += struct.pack("<I", len(xml)) + xml
        else:
            # Unknown command: respond with error.
            self._tx += struct.pack("<2I", cmd, 1)


def make_fake_transport(nvram: dict[int, bytes] | None = None) -> tuple[FakeTransport, FakeDevice]:
    """Build a (FakeTransport, FakeDevice) pair for testing."""
    dev = FakeDevice(nvram)
    return FakeTransport(dev), dev
