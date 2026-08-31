"""Protocol round-trip test using the fake device.

Run:  python test_protocol.py
"""
from __future__ import annotations

import sys
import tempfile
import os

sys.path.insert(0, os.path.dirname(__file__))

from protocol import (
    Sahara,
    luhn_valid,
    luhn_checksum,
    make_valid_imei,
    imei_to_raw,
    raw_to_imei,
    make_fake_transport,
    Mct,
    MctUSB,
    make_fake_mct_transport,
    generate_imei,
    parse_imei,
    format_display,
    auto_detect,
    normalize_imei,
    only_digits,
    FirehoseBackend,
    MctBackend,
    AppleBackend,
    AppleWriteError,
    make_apple_reader,
    make_apple_writer,
)


def test_luhn() -> None:
    # A known-valid IMEI (Luhn): 353555001400000 -> check digit 8?
    # Compute one and verify round-trip.
    imei = make_valid_imei("35355500140000")
    assert len(imei) == 15, imei
    assert luhn_valid(imei), imei
    print("  luhn OK ->", imei)
    # A tampered IMEI should be invalid.
    assert not luhn_valid(imei[:14] + str((int(imei[14]) + 1) % 10))
    print("  luhn-invalid detection OK")


def test_raw_roundtrip(fmt: str) -> None:
    body = "99000011223344" if fmt != "u32" else "00000011223344"  # u32 must fit 32-bit
    imei = make_valid_imei(body)
    raw = imei_to_raw(imei, fmt)
    back = raw_to_imei(raw, fmt)
    assert back == imei, f"{fmt}: {back} != {imei}"
    print(f"  raw round-trip {fmt} OK  ({raw!r} -> {back})")


def test_sahara_firehose() -> None:
    # Fake device starts with a known IMEI stored in NVRAM item 136541.
    seed_imei = make_valid_imei("35355500140000")
    seed_raw = imei_to_raw(seed_imei, "le84")
    transport, dev = make_fake_transport({136541: seed_raw, 136542: imei_to_raw(make_valid_imei("35355500140099"), "le84")})

    # 1) Sahara: load a dummy programmer.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mbn") as f:
        f.write(b"PROGRAMMER-DATA-1234567890")
        prog_path = f.name
    sahara = Sahara(transport)
    firehose = sahara.load_programmer(prog_path)
    os.unlink(prog_path)
    print("  sahara load OK, state =", dev._state)

    # 2) Firehose GO / NOOP.
    firehose.noop()
    firehose.go()
    print("  noop/go OK")

    # 3) Properties.
    props = firehose.get_properties()
    assert "MaxPayloadSizeToTargetInBytes" in props, props
    print("  get_properties OK:", props)

    # 4) Read IMEI from NVRAM item 136541.
    imei1 = firehose.read_imei(136541, fmt="le84")
    assert imei1 == seed_imei, (imei1, seed_imei)
    print("  read IMEI1 OK ->", imei1)

    imei2 = firehose.read_imei(136542, fmt="le84")
    assert luhn_valid(imei2)
    print("  read IMEI2 OK ->", imei2)

    # 5) Write a NEW IMEI to item 136541 and read it back.
    new_imei = make_valid_imei("49000012345678")
    firehose.write_imei(new_imei, 136541, fmt="le84")
    read_back = firehose.read_imei(136541, fmt="le84")
    assert read_back == new_imei, (read_back, new_imei)
    print("  write/read IMEI OK ->", read_back)

    # 6) The fake device's nvram store reflects the write.
    assert dev.nvram[136541] == imei_to_raw(new_imei, "le84")
    print("  nvram store updated OK")

    # 7) Writing an invalid (non-Luhn) IMEI must raise.
    try:
        firehose.write_imei("123456789012341", 136541, fmt="le84")
        raise AssertionError("expected ValueError for invalid IMEI")
    except ValueError:
        print("  invalid-IMEI rejection OK")


def test_mct_roundtrip() -> None:
    seed_imei = make_valid_imei("99000011223344")
    seed_raw = imei_to_raw(seed_imei, "ascii")
    items = [Mct.IMEI1_ITEM, Mct.IMEI2_ITEM]
    transport, dev = make_fake_mct_transport({
        Mct.IMEI1_ITEM: seed_raw,
        Mct.IMEI2_ITEM: imei_to_raw(make_valid_imei("99000011223355"), "ascii"),
    })
    mct = Mct(transport)

    # 1) READ_AGDB returns stored bytes.
    raw1 = mct.read_agdb(Mct.IMEI1_ITEM)
    assert raw1 == seed_raw, (raw1, seed_raw)
    print("  mct read_agdb OK ->", raw1)

    # 2) WRITE_AGDB then read back.
    new_imei = make_valid_imei("99000011223366")
    new_raw = imei_to_raw(new_imei, "ascii")
    mct.write_agdb(Mct.IMEI1_ITEM, new_raw)
    back = mct.read_agdb(Mct.IMEI1_ITEM)
    assert back == new_raw, (back, new_raw)
    print("  mct write/read_agdb OK ->", back)

    # 3) NVRAM path (READ/WRITE_NV_ITEM) round-trip.
    mct.write_nv_item(0x1337, b"hello")
    assert mct.read_nv_item(0x1337) == b"hello"
    print("  mct nv_item round-trip OK")

    # 4) MctBackend over MCT, using AGDB, with the toolkit's auto_detect.
    be = MctBackend(mct, [Mct.IMEI1_ITEM], use_agdb=True)
    imei = be.read_imei(Mct.IMEI1_ITEM, "ascii")
    assert imei == new_imei, (imei, new_imei)
    print("  MctBackend read_imei OK ->", imei)


def test_imei_toolkit() -> None:
    # generate_imei
    imei = generate_imei("353555", "140000", 0)
    assert len(imei) == 15 and luhn_valid(imei), imei
    assert imei.startswith("353555"), imei
    print("  generate_imei OK ->", imei)

    # parse_imei + format_display (use a known-Luhn-valid IMEI)
    valid = make_valid_imei("35355500140000")  # ...06
    p = parse_imei(valid)
    assert p.tac == "353555", p
    assert p.luhn_ok, p
    assert p.maker == "Samsung", p.maker
    assert format_display(p.imei, "3x3") == valid[0:3] + "-" + valid[3:6] + "-" + valid[6:9] + "-" + valid[9:12] + "-" + valid[12:15]
    assert format_display(p.imei, "tac") == f"{p.tac}-{p.serial}-{p.check}"
    assert format_display(p.imei, "plain") == valid
    print("  parse_imei / format_display OK  maker =", p.maker)

    # auto_detect: an IMEI stored in 'rev' must be recovered
    raw = imei_to_raw(valid, "rev")
    got_imei, got_fmt = auto_detect(raw)
    assert got_imei == valid and luhn_valid(got_imei), (got_imei, got_fmt)
    print("  auto_detect OK  fmt =", got_fmt)

    # normalize_imei: 14-digit body gains its check digit
    n = normalize_imei("353-555-001-400-00")
    assert luhn_valid(n) and n[-1] == str(luhn_checksum(n[:14])), n
    print("  normalize_imei OK ->", n)


def test_apple_backend() -> None:
    imei1 = make_valid_imei("35355500140011")
    imei2 = make_valid_imei("35355500140022")
    new1 = make_valid_imei("35355500140033")
    reader = make_apple_reader({1: imei1, 2: imei2})
    store: dict[int, str] = {1: imei1, 2: imei2}
    be = AppleBackend(reader, make_apple_writer(store), [1, 2])
    assert be.family == "apple" and be.supports_write is False

    # read_imei works
    got = be.read_imei(1, "ascii")
    assert got == imei1, (got, imei1)
    print("  apple read_imei OK ->", got)

    # write goes through the writer callable
    be.write_imei(new1, 1, "ascii")
    assert store[1] == new1, store
    print("  apple write_imei (via writer) OK")

    # read_raw raises AppleReadError on a missing slot
    from protocol import AppleReadError
    be2 = AppleBackend(make_apple_reader({}), None)
    try:
        be2.read_raw(1, "ascii")
        raise AssertionError("expected AppleReadError")
    except AppleReadError:
        print("  apple missing-slot AppleReadError OK")

    # write raises AppleWriteError when no writer is configured
    try:
        be2.write_imei(imei1, 1, "ascii")
        raise AssertionError("expected AppleWriteError")
    except AppleWriteError:
        print("  apple write-without-writer AppleWriteError OK")


def main() -> int:
    print("test_luhn")
    test_luhn()
    print("test_raw_roundtrip")
    for fmt in ("le84", "ascii", "rev", "u32"):
        test_raw_roundtrip(fmt)
    print("test_sahara_firehose")
    test_sahara_firehose()
    print("test_mct_roundtrip")
    test_mct_roundtrip()
    print("test_imei_toolkit")
    test_imei_toolkit()
    print("test_apple_backend")
    test_apple_backend()
    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
