"""Transport layer: abstracts the USB / fake-device I/O used by Sahara+Firehose."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Transport(ABC):
    """A byte-stream channel to the target (9008/EDL mode)."""

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Write data to the target. Blocking."""

    @abstractmethod
    def recv(self, n: int) -> bytes:
        """Read exactly n bytes from the target (may issue multiple reads)."""

    def close(self) -> None:  # optional
        pass


class FakeTransport(Transport):
    """In-memory transport that runs a tiny state machine on the host side.

    Used for unit-testing the Sahara/Firehose client without a real phone.
    The device model lives in ``fake_device.py``.
    """

    def __init__(self, device):
        self.device = device

    def send(self, data: bytes) -> None:
        self.device.on_send(data)

    def recv(self, n: int) -> bytes:
        return self.device.recv(n)

    def close(self) -> None:
        self.device.close()


class USBTransport(Transport):
    """pyusb-backed transport for a Qualcomm 9008/EDL device (VID 0x05c6)."""

    VID = 0x05C6

    def __init__(self, timeout_ms: int = 15000):
        self.timeout = timeout_ms
        import usb.core
        import usb.util

        self._usb = usb
        self._dev = None
        self._ep_out = None
        self._ep_in = None
        self._claimed = False

    def connect(self) -> None:
        """Find and claim the 9008 device. Raises if not found."""
        dev = self._usb.core.find(
            id_vendor=self.VID,
            id_product=0x9008,
            find_all=True,
        )
        if not dev:
            raise RuntimeError(
                "No Qualcomm 9008/EDL device (05c6:9008) found. "
                "Put the phone into 9008/EDL mode and reconnect USB."
            )
        self._dev = dev
        # Pick the first interface; claim it.
        cfg = dev.get_configuration()
        intf = cfg[0]
        self._usb.util.claim_interface(dev, intf.bInterfaceNumber)
        self._claimed = True

        # OUT endpoint = 0x01, IN endpoint = 0x81 (standard QDLP layout).
        self._ep_out = dev.write_endpoint(intf[0].bEndpointAddress)
        self._ep_in = dev.read_endpoint(
            0x81 if intf[0].bmAttributes & 0x80 else intf[0].bEndpointAddress | 0x80
        )

    def send(self, data: bytes) -> None:
        if self._ep_out is None:
            raise RuntimeError("Transport not connected; call connect() first.")
        self._ep_out.write(data, self.timeout)

    def recv(self, n: int) -> bytes:
        if self._ep_in is None:
            raise RuntimeError("Transport not connected; call connect() first.")
        buf = b""
        while len(buf) < n:
            chunk = self._ep_in.read(min(n - len(buf), 4096), self.timeout)
            if not chunk:
                break
            buf += chunk
        if len(buf) < n:
            raise TimeoutError(f"Expected {n} bytes, got {len(buf)}")
        return buf

    def close(self) -> None:
        if self._dev is not None and self._claimed:
            try:
                self._usb.util.release_interface(
                    self._dev, self._dev.get_configuration()[0].bInterfaceNumber
                )
            except Exception:
                pass
            self._usb.util.detach_kernel_driver(self._dev, 0, detach_only_if_attached=True)
