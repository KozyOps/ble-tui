#!/usr/bin/env python3
import asyncio
import curses
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Dict

from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic


@dataclass
class DeviceEntry:
    address: str
    name: str


@dataclass
class CharacteristicEntry:
    service_uuid: str
    char_uuid: str
    properties: List[str]


class BleTuiApp:
    """
    Simple curses + asyncio TUI for BLE:

    - Scan for devices
    - Select device
    - Connect and list services/characteristics
    - Choose a characteristic
    - Serial console style view with notifications + writes
    """

    def __init__(self, stdscr):
        self.stdscr = stdscr

        # global state
        self.devices: List[DeviceEntry] = []
        self.selected_device_idx: int = 0
        self.client: Optional[BleakClient] = None
        self.connected_device: Optional[DeviceEntry] = None

        self.characteristics: List[CharacteristicEntry] = []
        self.selected_char_idx: int = 0

        # console state
        self.console_log: deque[str] = deque(maxlen=500)
        self.console_input: str = ""
        self.console_char: Optional[CharacteristicEntry] = None
        self.notifications_enabled: bool = False

        # screen state
        self.current_screen: str = "devices"  # "devices" | "chars" | "console"
        self.status_message: str = ""

        # curses config
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.nodelay(True)
        curses.curs_set(0)

    # ------------- Utility / status -------------

    def set_status(self, msg: str):
        self.status_message = msg

    def clear_status(self):
        self.status_message = ""

    # ------------- Scanning & connecting -------------

    async def scan_devices(self):
        self.set_status("Scanning for BLE devices (5s)...")
        self.devices = []
        self.selected_device_idx = 0
        try:
            found = await BleakScanner.discover(timeout=5.0)
            for d in found:
                name = d.name or "Unknown"
                self.devices.append(DeviceEntry(address=d.address, name=name))
            if not self.devices:
                self.set_status("No BLE devices found. Try again.")
            else:
                self.set_status(f"Found {len(self.devices)} devices.")
        except Exception as e:
            self.set_status(f"Scan error: {e}")

    async def connect_selected_device(self):
        if not self.devices:
            self.set_status("No devices to connect to. Press 's' to scan.")
            return

        dev = self.devices[self.selected_device_idx]
        self.set_status(f"Connecting to {dev.name} ({dev.address})...")
        await self.disconnect()  # clean up any existing connection first

        self.client = BleakClient(dev.address)
        try:
            await self.client.connect()
            if not self.client.is_connected:
                self.set_status("Failed to connect.")
                self.client = None
                return

            self.connected_device = dev
            self.set_status(f"Connected to {dev.name}. Fetching services...")
            await self.load_characteristics()
            self.current_screen = "chars"
        except Exception as e:
            self.set_status(f"Connect error: {e}")
            self.client = None
            self.connected_device = None

    async def disconnect(self):
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.connected_device = None
        self.characteristics.clear()
        self.selected_char_idx = 0
        self.console_char = None
        self.notifications_enabled = False

    async def load_characteristics(self):
        self.characteristics = []
        self.selected_char_idx = 0
        if self.client is None:
            self.set_status("Not connected.")
            return
        try:
            services = self.client.services
            if services is None:
                self.set_status("Services not available yet.")
                return
            for svc in services:
                for ch in svc.characteristics:
                    props = [str(p) for p in ch.properties]
                    self.characteristics.append(
                        CharacteristicEntry(
                            service_uuid=str(svc.uuid),
                            char_uuid=str(ch.uuid),
                            properties=props,
                        )
                    )
            if not self.characteristics:
                self.set_status("No characteristics found.")
            else:
                self.set_status(f"Loaded {len(self.characteristics)} characteristics.")
        except Exception as e:
            self.set_status(f"Error loading characteristics: {e}")

    # ------------- Notification handler -------------

    def notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        # Called by Bleak when notifications arrive
        hex_str = data.hex(" ")
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        line = f"[RX] {sender.uuid}: {hex_str}  | {ascii_str}"
        self.console_log.append(line)

    async def toggle_notifications(self):
        if self.client is None or self.console_char is None:
            self.set_status("No characteristic selected.")
            return

        uuid = self.console_char.char_uuid
        try:
            if not self.notifications_enabled:
                await self.client.start_notify(uuid, self.notification_handler)
                self.notifications_enabled = True
                self.set_status("Notifications ON.")
            else:
                await self.client.stop_notify(uuid)
                self.notifications_enabled = False
                self.set_status("Notifications OFF.")
        except Exception as e:
            self.set_status(f"Notify error: {e}")

    async def send_console_line(self):
        if self.client is None or self.console_char is None:
            self.set_status("No characteristic selected.")
            return

        text = self.console_input
        if not text:
            return

        data = text.encode("utf-8")  # simple ASCII/UTF-8 line
        uuid = self.console_char.char_uuid

        try:
            await self.client.write_gatt_char(uuid, data)
            hex_str = data.hex(" ")
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
            self.console_log.append(f"[TX] {hex_str}  | {ascii_str}")
            self.console_input = ""
        except Exception as e:
            self.set_status(f"Write error: {e}")

    # ------------- Drawing -------------

    def draw_status_bar(self):
        status_line = self.status_message[: self.width - 1]
        self.stdscr.attron(curses.A_REVERSE)
        self.stdscr.addstr(self.height - 1, 0, status_line.ljust(self.width - 1))
        self.stdscr.attroff(curses.A_REVERSE)

    def draw_devices_screen(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()
        title = "BLE TUI – Device List (press 's' to scan, Enter to connect, 'q' to quit)"
        self.stdscr.addstr(0, 0, title[: self.width - 1], curses.A_BOLD)

        if not self.devices:
            self.stdscr.addstr(2, 0, "No devices. Press 's' to scan.")
        else:
            max_lines = self.height - 3  # leave space for title and status bar
            start = 0
            if self.selected_device_idx >= max_lines:
                start = self.selected_device_idx - max_lines + 1

            for visual_row, idx in enumerate(range(start, min(len(self.devices), start + max_lines))):
                if 2 + visual_row >= self.height - 1:  # don't overwrite status bar
                    break
                prefix = "-> " if idx == self.selected_device_idx else "   "
                name = self.devices[idx].name
                addr = self.devices[idx].address
                line = f"{prefix}{idx:02d}: {name} [{addr}]"
                attr = curses.A_REVERSE if idx == self.selected_device_idx else curses.A_NORMAL
                self.stdscr.addstr(2 + visual_row, 0, line[: self.width - 1], attr)

        self.draw_status_bar()
        self.stdscr.refresh()

    def draw_chars_screen(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()
        dev_str = (
            f"{self.connected_device.name} [{self.connected_device.address}]"
            if self.connected_device
            else "Not connected"
        )
        title = f"BLE TUI – Characteristics for {dev_str}  (Enter=console, 'd'=devices, 'q'=quit)"
        self.stdscr.addstr(0, 0, title[: self.width - 1], curses.A_BOLD)

        if not self.characteristics:
            self.stdscr.addstr(2, 0, "No characteristics found. Try reconnecting.")
        else:
            max_lines = self.height - 3
            start = 0
            if self.selected_char_idx >= max_lines:
                start = self.selected_char_idx - max_lines + 1

            for visual_row, idx in enumerate(range(start, min(len(self.characteristics), start + max_lines))):
                if 2 + visual_row >= self.height - 1:  # don't overwrite status bar
                    break
                ch = self.characteristics[idx]
                props = ",".join(ch.properties)
                s_uuid_short = ch.service_uuid[:8]
                c_uuid_short = ch.char_uuid[:8]
                prefix = "-> " if idx == self.selected_char_idx else "   "
                line = f"{prefix}{idx:03d}: svc={s_uuid_short} char={c_uuid_short} [{props}]"
                attr = curses.A_REVERSE if idx == self.selected_char_idx else curses.A_NORMAL
                self.stdscr.addstr(2 + visual_row, 0, line[: self.width - 1], attr)

        self.draw_status_bar()
        self.stdscr.refresh()

    def draw_console_screen(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()
        dev_str = (
            f"{self.connected_device.name} [{self.connected_device.address}]"
            if self.connected_device
            else "Not connected"
        )
        char_str = self.console_char.char_uuid if self.console_char else "None"
        notif_str = "ON" if self.notifications_enabled else "OFF"
        title = (
            f"BLE TUI – Console  dev={dev_str}  char={char_str}  notif={notif_str}  "
            "(Enter=send, 'n'=toggle notify, 'b'=back, 'q'=quit)"
        )
        self.stdscr.addstr(0, 0, title[: self.width - 1], curses.A_BOLD)

        # log area
        log_height = max(1, self.height - 4)  # leave space for input + status
        visible_log = list(self.console_log)[-log_height:]

        start_row = 1
        for i, line in enumerate(visible_log):
            if start_row + i >= self.height - 2:  # don't overwrite input or status
                break
            self.stdscr.addstr(start_row + i, 0, line[: self.width - 1])

        # input line
        if self.height >= 3:
            self.stdscr.attron(curses.A_REVERSE)
            input_prompt = "> " + self.console_input
            # Use width - 2 to avoid writing to the last character of the line
            self.stdscr.addstr(self.height - 2, 0, input_prompt[: self.width - 2].ljust(self.width - 2))
            self.stdscr.attroff(curses.A_REVERSE)

        self.draw_status_bar()
        self.stdscr.refresh()

    # ------------- Key handling -------------

    async def handle_devices_keys(self, ch: int):
        if ch == ord("q"):
            raise SystemExit
        elif ch == ord("s"):
            await self.scan_devices()
        elif ch in (curses.KEY_UP, ord("k")):
            if self.devices:
                self.selected_device_idx = max(0, self.selected_device_idx - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            if self.devices:
                self.selected_device_idx = min(len(self.devices) - 1, self.selected_device_idx + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            await self.connect_selected_device()

    async def handle_chars_keys(self, ch: int):
        if ch == ord("q"):
            raise SystemExit
        elif ch == ord("d"):
            # disconnect and go back
            await self.disconnect()
            self.current_screen = "devices"
            self.set_status("Disconnected.")
        elif ch in (curses.KEY_UP, ord("k")):
            if self.characteristics:
                self.selected_char_idx = max(0, self.selected_char_idx - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            if self.characteristics:
                self.selected_char_idx = min(len(self.characteristics) - 1, self.selected_char_idx + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            if self.characteristics:
                self.console_char = self.characteristics[self.selected_char_idx]
                self.console_log.clear()
                self.console_input = ""
                self.notifications_enabled = False
                self.current_screen = "console"
                self.set_status("Console opened. Press 'n' to enable notifications.")

    async def handle_console_keys(self, ch: int):
        if ch == ord("q"):
            raise SystemExit
        elif ch == ord("b"):
            # back to characteristics
            self.current_screen = "chars"
            self.clear_status()
        elif ch == ord("n"):
            await self.toggle_notifications()
        elif ch in (curses.KEY_ENTER, 10, 13):
            await self.send_console_line()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.console_input:
                self.console_input = self.console_input[:-1]
        elif ch >= 32 and ch <= 126:  # printable ASCII
            self.console_input += chr(ch)

    # ------------- Main loop -------------

    async def run(self):
        # initial scan to populate list quickly (optional)
        await self.scan_devices()

        while True:
            # draw
            if self.current_screen == "devices":
                self.draw_devices_screen()
            elif self.current_screen == "chars":
                self.draw_chars_screen()
            elif self.current_screen == "console":
                self.draw_console_screen()

            # get key (non-blocking)
            try:
                ch = self.stdscr.getch()
            except curses.error:
                ch = -1

            if ch != -1:
                try:
                    if self.current_screen == "devices":
                        await self.handle_devices_keys(ch)
                    elif self.current_screen == "chars":
                        await self.handle_chars_keys(ch)
                    elif self.current_screen == "console":
                        await self.handle_console_keys(ch)
                except SystemExit:
                    break
                except Exception as e:
                    self.set_status(f"Error: {e}")

            await asyncio.sleep(0.05)  # give event loop time for BLE events


def main(stdscr):
    app = BleTuiApp(stdscr)
    asyncio.run(app.run())


if __name__ == "__main__":
    curses.wrapper(main)

