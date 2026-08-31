"""Sahara + Firehose (Qualcomm 9008/EDL) client protocol.

Implements the classic binary Sahara handshake and the Firehose command set,
including the NVRAM operations used to read/write the modem's IMEI items.
A thin XML-based send path is included for newer XML-mode programmers.
"""
from __future__ import annotations

import re
import struct

from .transport import Transport

# ---------------------------------------------------------------------------
# Sahara (pre-programmer handshake)
# ---------------------------------------------------------------------------
SAHARA_MAGIC = 0x46324357  # "WCF"
CMD_LOAD_PROGRAMMER = 0x06

# ---------------------------------------------------------------------------
# Firehose command IDs
# ---------------------------------------------------------------------------
CMD_NOOP = 0
CMD_RESET = 1
CMD_LOAD_FILE = 2
CMD_READ_FILE = 3
CMD_WRITE_FILE = 4
CMD_READ = 5
CMD_WRITE = 6
CMD_ERASE = 7
CMD_MEM_READ = 8
CMD_MEM_WRITE = 9
CMD_FLUSH = 10
CMD_SET_NVRAM_INDEX = 11
CMD_READ_NVRAM = 12
CMD_WRITE_NVRAM = 13
CMD_ERASE_NVRAM = 14
CMD_GET_PROPERTY = 15
CMD_GET_PARTITIONS = 16
CMD_GET_MEM_SIZE = 17
CMD_GO = 18

RESP_SUCCESS = 0
RESP_ERROR = 1

#: Firehose protocol version (used by most Firehose programmers; v1 is the
#: classic binary mode. v2+ adds XML, which we also support via xmlsend).
FIREHOSE_PROTOCOL_VERSION = 1


# ---------------------------------------------------------------------------
# IMEI helpers
# ---------------------------------------------------------------------------
def luhn_checksum(digit_string: str) -> int:
    """Return the Luhn check digit for the given 14-digit IMEI body."""
    total = 0
    # Luhn: count positions from the rightmost of the 15-digit IMEI.
    # Position 1 (rightmost) is the check digit; positions 2,4,6,8,10,12,14
    # are doubled; positions 1,3,5,7,9,11,13 are not.
    # For a 14-digit body (positions 1-14, rightmost being position 14),
    # positions 14,12,10,8,6,4,2 are NOT doubled, positions 13,11,9,7,5,3,1 are doubled.
    for i, c in enumerate(reversed(digit_string)):
        d = int(c)
        # i=0 is position 14 (rightmost of body = position 14 of the 15-digit IMEI).
        # Position 14 is NOT doubled (even position from the right).
        if i % 2 == 0:
            total += d
        else:
            d *= 2
            if d > 9:
                d -= 9
            total += d
    return (10 - (total % 10)) % 10


def luhn_valid(imei: str) -> bool:
    if len(imei) != 15 or not imei.isdigit():
        return False
    return int(imei[14]) == luhn_checksum(imei[:14])


def make_valid_imei(body14: str, tac: str | None = None) -> str:
    """Build a valid 15-digit IMEI from a 14-digit body (+ optional TAC)."""
    if tac:
        body14 = tac + body14[8:]
    if len(body14) != 14 or not body14.isdigit():
        raise ValueError(f"body must be 14 digits, got {body14!r}")
    return body14 + str(luhn_checksum(body14))


def imei_to_raw(imei: str, fmt: str = "le84") -> bytes:
    """Encode a 15-digit IMEI into the raw NVRAM bytes for the given format.

    fmt:
      "le84"   - 8-byte LE uint64 (low 8 digits) + 4-byte LE uint32 (high 7 digits)
      "ascii"  - plain ASCII digits, 15 bytes
      "rev"    - ASCII digits reversed, 15 bytes
      "u32"    - 4-byte LE uint32 (only if IMEI fits, e.g. 000000000000xxx)
    """
    if len(imei) != 15 or not imei.isdigit():
        raise ValueError(f"imei must be 15 digits, got {imei!r}")
    if fmt == "le84":
        low = int(imei[7:15])     # last 8 digits
        high = int(imei[0:7])     # first 7 digits
        return struct.pack("<QI", low, high)
    if fmt == "ascii":
        return imei.encode("ascii")
    if fmt == "rev":
        return imei[::-1].encode("ascii")
    if fmt == "u32":
        return struct.pack("<I", int(imei))
    raise ValueError(f"unknown fmt {fmt!r}")


def raw_to_imei(raw: bytes, fmt: str = "le84") -> str:
    if fmt == "le84":
        if len(raw) < 12:
            raise ValueError("raw too short for le84")
        low, high = struct.unpack_from("<QI", raw)
        return f"{high:07d}{low:08d}"
    if fmt == "ascii":
        return raw.rstrip(b"\x00").decode("ascii").strip()
    if fmt == "rev":
        return raw.rstrip(b"\x00")[::-1].decode("ascii").strip()
    if fmt == "u32":
        v = struct.unpack("<I", raw[:4])[0]
        return f"{v:015d}"
    raise ValueError(f"unknown fmt {fmt!r}")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class SaharaError(Exception):
    pass


class FirehoseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Sahara
# ---------------------------------------------------------------------------
class Sahara:
    """Sahara handshake: load a Firehose programmer onto a 9008/EDL device."""

    def __init__(self, transport: Transport):
        self.transport = transport

    def load_programmer(self, programmer_path: str) -> "Firehose":
        with open(programmer_path, "rb") as f:
            data = f.read()

        header = struct.pack("<I2I", SAHARA_MAGIC, CMD_LOAD_PROGRAMMER, len(data))
        self.transport.send(header)
        ack = self.transport.recv(8)
        magic, cmd = struct.unpack("<2I", ack)
        if magic != SAHARA_MAGIC or cmd != CMD_LOAD_PROGRAMMER:
            raise SaharaError(
                f"Sahara handshake failed: got magic=0x{magic:08x} cmd=0x{cmd:02x}"
            )
        self.transport.send(data)
        # Programmer is now loaded; return a Firehose client.
        return Firehose(self.transport)


# ---------------------------------------------------------------------------
# Firehose
# ---------------------------------------------------------------------------
class Firehose:
    """Client for the Firehose protocol (post-Sahara)."""

    def __init__(self, transport: Transport):
        self.transport = transport

    def _send(self, command: int, payload: bytes = b"") -> tuple[int, int]:
        """Send a Firehose command (binary mode), read the 8-byte ack.

        Returns (command, status). Raises on mismatch.
        """
        self.transport.send(struct.pack("<2I", command, len(payload)))
        if payload:
            self.transport.send(payload)
        resp = self.transport.recv(8)
        cmd, status = struct.unpack("<2I", resp)
        if cmd != command:
            raise FirehoseError(f"Firehose: expected cmd {command}, got {cmd}")
        if status != RESP_SUCCESS:
            raise FirehoseError(f"Firehose cmd {command} returned status {status}")
        return cmd, status

    def _send_xml(self, xml: str) -> bytes:
        """Send an XML command (used by newer Firehose programmers).

        Returns the raw response bytes after the XML header.
        """
        data = xml.encode("utf-8")
        self.transport.send(struct.pack("<I", len(data)))
        self.transport.send(data)
        # Response is <I> length then data, or just SUCCESS ack.
        # We'll read a 4-byte header first to see if it's length-prefixed.
        head = self.transport.recv(4)
        length = struct.unpack("<I", head)[0]
        if 0 < length < 1 << 20:
            return self.transport.recv(length)
        return bytes(struct.pack("<I", length))  # SUCCESS

    # -- basic -------------------------------------------------------------
    def noop(self) -> None:
        self._send(CMD_NOOP)

    def go(self) -> None:
        """Firehose GO — finalizes the loaded programmer."""
        self._send(CMD_GO)

    def reset(self) -> None:
        self._send(CMD_RESET)

    def get_properties(self) -> dict:
        """Ask the programmer for its properties and parse the XML."""
        self.transport.send(struct.pack("<2I", CMD_GET_PROPERTY, 0))
        head = struct.unpack("<2I", self.transport.recv(8))
        if head[1] != RESP_SUCCESS:
            raise FirehoseError(f"GET_PROPERTIES status={head[1]}")
        length = struct.unpack("<I", self.transport.recv(4))[0]
        xml = self.transport.recv(length).decode("utf-8", errors="replace")
        return dict(re.findall(r'<property name="([^"]+)">\s*([^<]+?)\s*</property>', xml))

    # -- file operations ---------------------------------------------------
    def load_file(self, data: bytes, memory: str = "gpt") -> None:
        """Load a file into the programmer, then GO."""
        self._send(CMD_LOAD_FILE, data)
        self.go()

    def read_file(self, offset: int, length: int) -> bytes:
        self._send(CMD_READ_FILE, struct.pack("<2I", offset, length))
        return self.transport.recv(length)

    def write_file(self, offset: int, data: bytes) -> None:
        self._send(CMD_WRITE_FILE, struct.pack("<I", offset) + data)

    # -- memory operations -------------------------------------------------
    def read(self, memory: str, address: int, length: int) -> bytes:
        """Read ``length`` bytes from ``memory`` at ``address``."""
        self._send(CMD_READ, struct.pack("<I16sI", length, memory, address))
        # Response: <I> data length, then the data.
        resp_len = struct.unpack("<I", self.transport.recv(4))[0]
        if resp_len != length:
            raise FirehoseError(f"READ: expected {length} bytes, got {resp_len}")
        return self.transport.recv(resp_len)

    def write(self, memory: str, address: int, data: bytes) -> None:
        self._send(CMD_WRITE, struct.pack("<I16sI", len(data), memory, address) + data)

    def erase(self, memory: str, address: int, length: int) -> None:
        self._send(CMD_ERASE, struct.pack("<16sII", memory, address, length))

    def mem_read(self, memory: str, address: int, length: int) -> bytes:
        self._send(CMD_MEM_READ, struct.pack("<16sII", memory, address, length))
        resp_len = struct.unpack("<I", self.transport.recv(4))[0]
        return self.transport.recv(resp_len)

    def mem_write(self, memory: str, address: int, data: bytes) -> None:
        self._send(CMD_MEM_WRITE, struct.pack("<16sI", memory, address) + data)

    def flush(self) -> None:
        self._send(CMD_FLUSH)

    # -- NVRAM (IMEIs live here) ------------------------------------------
    def set_nvram_index(self, index: int) -> None:
        self._send(CMD_SET_NVRAM_INDEX, struct.pack("<I", index))

    def read_nvram(self) -> bytes:
        """Send READ_NVRAM and return the item data (header + length + data)."""
        self.transport.send(struct.pack("<2I", CMD_READ_NVRAM, 0))
        # 8-byte ack: (cmd, status)
        cmd, status = struct.unpack("<2I", self.transport.recv(8))
        if status != RESP_SUCCESS:
            raise FirehoseError(f"READ_NVRAM status={status}")
        # 4-byte length, then data
        length = struct.unpack("<I", self.transport.recv(4))[0]
        return self.transport.recv(length)

    def write_nvram(self, data: bytes) -> None:
        self._send(CMD_WRITE_NVRAM, struct.pack("<I", len(data)) + data)

    def erase_nvram(self) -> None:
        self._send(CMD_ERASE_NVRAM)

    # -- high-level IMEI helpers ------------------------------------------
    #: Default NVRAM item index for IMEI1. Samsung Firehose programmers commonly
    #: use 136541 (IMEI1) and 136542 (IMEI2). Some use 0 / 1.
    IMEI1_ITEM = 136541
    IMEI2_ITEM = 136542

    def read_imei(self, item_index: int = IMEI1_ITEM, fmt: str = "le84") -> str:
        self.set_nvram_index(item_index)
        raw = self.read_nvram()
        try:
            return raw_to_imei(raw, fmt)
        except Exception:
            # Fallback: try other formats
            for f in ("ascii", "rev", "u32"):
                try:
                    return raw_to_imei(raw, f)
                except Exception:
                    continue
            raise

    def write_imei(self, imei: str, item_index: int = IMEI1_ITEM, fmt: str = "le84") -> None:
        if not luhn_valid(imei):
            raise ValueError(f"{imei!r} is not a valid Luhn IMEI")
        data = imei_to_raw(imei, fmt)
        self.set_nvram_index(item_index)
        self.write_nvram(data)
        self.flush()

    # -- XML-mode helpers (newer programmers) ------------------------------
    def xml_read(self, memory: str, address: int, length: int) -> bytes:
        xml = (
            f'<?xml version="1.0"?><data><read memory="{memory}"'
            f' address="{address}" length="{length}"/></data>'
        )
        return self._send_xml(xml)

    def xml_write(self, memory: str, address: int, data: bytes) -> bytes:
        xml = (
            f'<?xml version="1.0"?><data><write memory="{memory}"'
            f' address="{address}" length="{len(data)}">'
            f'{data.hex()}</write></data>'
        )
        return self._send_xml(xml)
