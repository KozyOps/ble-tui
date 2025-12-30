#!/usr/bin/env python3
import argparse
import binascii
import serial
import sys
from typing import Optional

SYNC = b"\x7e\x7e"
ESC  = 0x1B          # per LCP spec
MAX_DATA_LEN = 255   # per spec (data portion max)


class BufferedSerial:
    def __init__(self, ser: serial.Serial):
        self.ser = ser
        self.buf = bytearray()

    def _fill(self, n: int) -> bool:
        while len(self.buf) < n:
            chunk = self.ser.read(max(256, n - len(self.buf)))
            if not chunk:
                return False
            self.buf.extend(chunk)
        return True

    def read_raw(self, n: int) -> Optional[bytes]:
        if n <= 0:
            return b""
        if not self._fill(n):
            return None
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def find_and_consume_sync(self) -> bool:
        """Find next SYNC in the raw stream and consume through it."""
        while True:
            idx = bytes(self.buf).find(SYNC)
            if idx != -1:
                del self.buf[: idx + len(SYNC)]
                return True
            chunk = self.ser.read(256)
            if not chunk:
                return False
            self.buf.extend(chunk)


def read_decoded_byte(bs: BufferedSerial) -> Optional[int]:
    b = bs.read_raw(1)
    if b is None:
        return None
    x = b[0]
    if x == ESC:
        b2 = bs.read_raw(1)
        if b2 is None:
            return None
        return b2[0]
    return x


def decode_status(status: int) -> dict:
    is_response = bool(status & 0x80)

    d = {
        "raw": status,
        "message_type": "response" if is_response else "command",
        "message_identifier": status & 0x01,
        "synchronization": bool(status & 0x02),
    }

    if not is_response:
        d.update({
            "check_request": bool(status & 0x04),
            "abort_request": bool(status & 0x08),
            "reserved_bit4": bool(status & 0x10),
            "reserved_bit5": bool(status & 0x20),
            "reserved_bit6": bool(status & 0x40),
        })
    else:
        d.update({
            "busy": bool(status & 0x04),
            "request_aborted": bool(status & 0x08),
            "no_request_active": bool(status & 0x10),
            "buffer_overrun": bool(status & 0x20),
            "not_supported": bool(status & 0x40),
        })

    return d


def fmt_hex(b: bytes, sep: str = " ") -> str:
    return sep.join(f"{x:02X}" for x in b)


def fmt_ascii(b: bytes) -> str:
    # Printable ASCII 0x20..0x7E, else '.'
    return "".join(chr(x) if 0x20 <= x <= 0x7E else "." for x in b)


def main():
    ap = argparse.ArgumentParser(description="LCP RX frame dumper (~~ framed, ESC unescape, len-based)")
    ap.add_argument("--port", required=True, help="Serial device (e.g. /dev/ttyUSB0 or /dev/serial/by-id/...)")
    ap.add_argument("--baud", type=int, default=19200)
    ap.add_argument("--timeout", type=float, default=1.0, help="Read timeout seconds")
    ap.add_argument("--show-frame-hex", action="store_true", help="Also print full decoded frame hex")
    args = ap.parse_args()

    ser = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        timeout=args.timeout,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        rtscts=False,
        dsrdtr=False,
    )

    print(f"Listening on {args.port} @ {args.baud} baud", file=sys.stderr)

    bs = BufferedSerial(ser)

    try:
        while True:
            if not bs.find_and_consume_sync():
                continue

            # Read header (decoded)
            to_ = read_decoded_byte(bs)
            frm = read_decoded_byte(bs)
            status = read_decoded_byte(bs)
            length = read_decoded_byte(bs)
            if None in (to_, frm, status, length):
                continue

            # Sanity checks to avoid runaway on desync
            if length > MAX_DATA_LEN or to_ == 0x7E or frm == 0x7E:
                continue

            # Data (decoded/unescaped) exactly <len>
            data = bytearray()
            ok = True
            for _ in range(length):
                v = read_decoded_byte(bs)
                if v is None:
                    ok = False
                    break
                data.append(v)
            if not ok:
                continue

            # CRC bytes (decoded/unescaped)
            crc0 = read_decoded_byte(bs)
            crc1 = read_decoded_byte(bs)
            if None in (crc0, crc1):
                continue

            decoded_frame = SYNC + bytes([to_, frm, status, length]) + bytes(data) + bytes([crc0, crc1])

            s = decode_status(status)

            # Build a nice flags string
            if s["message_type"] == "command":
                flags = []
                if s["synchronization"]: flags.append("sync")
                flags.append(f"id={s['message_identifier']}")
                if s["check_request"]: flags.append("check_request")
                if s["abort_request"]: flags.append("abort_request")
                # Reserved bits only if present (helps spot bad frames)
                if s["reserved_bit4"] or s["reserved_bit5"] or s["reserved_bit6"]:
                    flags.append("reserved_bits_set")
            else:
                flags = []
                if s["synchronization"]: flags.append("sync")  # usually false in responses, but decode anyway
                flags.append(f"id={s['message_identifier']}")
                if s["busy"]: flags.append("busy")
                if s["request_aborted"]: flags.append("request_aborted")
                if s["no_request_active"]: flags.append("no_request_active")
                if s["buffer_overrun"]: flags.append("buffer_overrun")
                if s["not_supported"]: flags.append("not_supported")
                if len(flags) == 2:  # only sync/id
                    flags.append("ok")

            data_bytes = bytes(data)

            # Output (multi-line per message; easy to scan)
            print(f"to={to_:02X} from={frm:02X} type={s['message_type']} status={status:02X} ({', '.join(flags)}) len={length}")
            print(f"  data_hex: {fmt_hex(data_bytes)}")
            print(f"  data_txt: {fmt_ascii(data_bytes)}")
            print(f"  crc: {crc0:02X} {crc1:02X}")
            if args.show_frame_hex:
                print(f"  frame_hex: {binascii.hexlify(decoded_frame).decode()}")
            print()

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()


if __name__ == "__main__":
    main()

