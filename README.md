# IMEI Writer — Qualcomm 9008 / Firehose

A small desktop tool to **read and write IMEIs on Qualcomm-based phones in
9008/EDL (Firehose) mode** — the same mode a phone-repair box uses. No root,
no Android shell: it talks to the modem directly over USB.

## What it does

- Finds a `05c6:9008` USB device (phone in 9008/EDL mode).
- Loads a **Firehose programmer** (`.mbn`/`.elf`) over the Sahara handshake.
- Reads/writes the **modem NVRAM** where the IMEIs are stored (default items
  `136541` = IMEI1, `136542` = IMEI2).
- Auto-computes the Luhn check digit and validates it.
- **Fake-device test mode** runs the whole protocol in-memory so you can verify
  the tool with no phone connected.

## Files

```
main.py               GUI entry point (tkinter)
protocol/
  protocol.py         Sahara + Firehose client, IMEI encode/decode, Luhn
  transport.py        USBTransport (pyusb) + FakeTransport
  fake_device.py      in-memory 9008 device for tests
test_protocol.py      protocol round-trip self-test
run.bat               launches the GUI
requirements.txt      pyusb
```

## Setup

```bat
pip install -r requirements.txt
```

## Use

1. Put the phone in **9008/EDL mode** (method varies by SoC/model — see below).
2. Run `run.bat` (or `python main.py`).
3. Pick your Firehose **programmer file** (the one for that exact SoC).
4. **USB** mode → click **Connect & Load Programmer**.
5. Click **Read IMEI(s)** to see the current IMEIs.
6. Type a 14-digit body (e.g. `99000011223344`), then **Write IMEI 1 / 2**.
   The check digit is added and verified automatically.

To verify without a phone: pick **Fake device**, **Connect**, then **Test
Protocol**.

## Entering 9008/EDL mode (common methods)

- **Qualcomm (most SoCs):** `adb reboot edl`, or a test-point short, or
  `fastboot oem edl` on some boards.
- **MediaTek phones:** use **MCT** (not 9008) — this tool targets the
  Qualcomm/Samsung/Exynos-Firehose path.
- The phone must present as USB device **05c6:9008**.

## Notes & limits

- The NVRAM **item index** and the **storage format** differ by Firehose
  programmer. Defaults here (`136541`/`136542`, format `le84`) work for many
  Samsung/Qualcomm programmers; adjust the item numbers / format in the UI if
  your programmer stores IMEIs differently.
- Always **read the existing IMEIs first** (or back up EFS) before writing —
  a bad write can knock the phone off the network.
- This implements the **classic binary** Sahara/Firehose protocol. Newer
  XML-mode programmers are partially supported (`xmlsend`), but the binary path
  is the one the self-test covers.

## Self-test

```bat
"C:\Program Files\Python312\python.exe" test_protocol.py
```

Sources:
- [bkerler/edl](https://github.com/bkerler/edl) — reference Sahara/Firehose
  implementation.
- [96Boards qdl](https://www.96boards.org/documentation/consumer/guides/qdl.md.html).
