#!/usr/bin/env python3
"""
CP-26 BLE Adapter Configuration TUI

A specialized curses + asyncio TUI for managing DX-Smart CP-26 Bluetooth adapters.

Features:
- Scans only for CP-26 devices (MAC prefix 48:87:2D)
- Configure device name, mode, baud rate, passthrough settings
- Dual serial console: Module TX/RX and Host TX/RX
- Send data as ASCII or HEX
- Real-time notifications from both channels
"""

import asyncio
import curses
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Callable

from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic


# =============================================================================
# CP-26 GATT UUIDs (Common for serial BLE modules)
# =============================================================================

# Nordic UART Service (commonly used by CP-26 and similar modules)
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Write (to module)
UART_RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Notify (from module)

# Some CP-26 modules use a secondary service for host/passthrough communication
# These may vary - adjust based on your specific module's documentation
HOST_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
HOST_TX_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"  # Write to host
HOST_RX_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"  # Notify from host

# Configuration characteristic (for AT commands or config writes)
CONFIG_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CONFIG_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# CP-26 MAC prefix
CP26_MAC_PREFIX = "48:87:2D"


# =============================================================================
# Data Types
# =============================================================================

class InputMode(Enum):
    ASCII = "ASCII"
    HEX = "HEX"


class BaudRate(Enum):
    B9600 = "9600"
    B19200 = "19200"
    B38400 = "38400"
    B57600 = "57600"
    B115200 = "115200"


class DeviceMode(Enum):
    PERIPHERAL = "Peripheral"
    CENTRAL = "Central"
    BEACON = "Beacon"


@dataclass
class DeviceEntry:
    address: str
    name: str
    rssi: int = 0


@dataclass
class CP26Config:
    """Current configuration of the CP-26 module"""
    name: str = "CP-26"
    mode: DeviceMode = DeviceMode.PERIPHERAL
    baud_rate: BaudRate = BaudRate.B115200
    passthrough: bool = True
    pin: str = "000000"


@dataclass
class SerialChannel:
    """Represents a serial communication channel"""
    name: str
    tx_uuid: Optional[str] = None
    rx_uuid: Optional[str] = None
    log: deque = field(default_factory=lambda: deque(maxlen=500))
    notifications_enabled: bool = False
    available: bool = False


# =============================================================================
# Main Application
# =============================================================================

class CP26TuiApp:
    """
    Curses + asyncio TUI for CP-26 BLE adapter management.
    
    Screens:
    - devices: Scan and select CP-26 devices
    - config: View/modify device configuration
    - console: Dual-channel serial console with ASCII/HEX modes
    """

    def __init__(self, stdscr):
        self.stdscr = stdscr

        # Device state
        self.devices: List[DeviceEntry] = []
        self.selected_device_idx: int = 0
        self.client: Optional[BleakClient] = None
        self.connected_device: Optional[DeviceEntry] = None

        # Configuration state
        self.config = CP26Config()
        self.config_menu_idx: int = 0
        self.config_editing: bool = False
        self.config_edit_value: str = ""

        # Serial channels
        self.module_channel = SerialChannel(name="Module")
        self.host_channel = SerialChannel(name="Host")
        self.active_channel: SerialChannel = self.module_channel

        # Console state
        self.console_input: str = ""
        self.input_mode: InputMode = InputMode.ASCII
        self.show_timestamps: bool = True

        # Screen state
        self.current_screen: str = "devices"
        self.status_message: str = ""
        self.help_visible: bool = False

        # Curses config
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.nodelay(True)
        curses.curs_set(0)
        
        # Initialize colors if available
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)   # TX
            curses.init_pair(2, curses.COLOR_CYAN, -1)    # RX Module
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # RX Host
            curses.init_pair(4, curses.COLOR_RED, -1)     # Error
            curses.init_pair(5, curses.COLOR_MAGENTA, -1) # Info

    # -------------------------------------------------------------------------
    # Utility / Status
    # -------------------------------------------------------------------------

    def set_status(self, msg: str):
        self.status_message = msg

    def clear_status(self):
        self.status_message = ""

    def get_timestamp(self) -> str:
        if self.show_timestamps:
            import datetime
            return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3] + " "
        return ""

    # -------------------------------------------------------------------------
    # Scanning & Connecting
    # -------------------------------------------------------------------------

    async def scan_devices(self):
        self.set_status("Scanning for CP-26 devices (48:87:2D:*)...")
        self.devices = []
        self.selected_device_idx = 0
        
        try:
            found = await BleakScanner.discover(timeout=5.0, return_adv=True)
            for address, (device, adv_data) in found.items():
                # Filter for CP-26 MAC prefix
                if address.upper().startswith(CP26_MAC_PREFIX):
                    name = device.name or adv_data.local_name or "CP-26 Unknown"
                    rssi = adv_data.rssi if adv_data.rssi else -100
                    self.devices.append(DeviceEntry(address=address, name=name, rssi=rssi))
            
            # Sort by signal strength
            self.devices.sort(key=lambda d: d.rssi, reverse=True)
            
            if not self.devices:
                self.set_status("No CP-26 devices found (48:87:2D:*). Press 's' to rescan.")
            else:
                self.set_status(f"Found {len(self.devices)} CP-26 device(s).")
        except Exception as e:
            self.set_status(f"Scan error: {e}")

    async def connect_selected_device(self):
        if not self.devices:
            self.set_status("No devices to connect. Press 's' to scan.")
            return

        dev = self.devices[self.selected_device_idx]
        self.set_status(f"Connecting to {dev.name} ({dev.address})...")
        await self.disconnect()

        self.client = BleakClient(dev.address)
        try:
            await self.client.connect()
            if not self.client.is_connected:
                self.set_status("Failed to connect.")
                self.client = None
                return

            self.connected_device = dev
            self.set_status(f"Connected! Discovering services...")
            await self.discover_channels()
            await self.read_config()
            self.current_screen = "config"
            self.set_status(f"Connected to {dev.name}. Configure or press 'c' for console.")
        except Exception as e:
            self.set_status(f"Connect error: {e}")
            self.client = None
            self.connected_device = None

    async def disconnect(self):
        # Stop notifications first
        if self.client and self.client.is_connected:
            try:
                if self.module_channel.notifications_enabled and self.module_channel.rx_uuid:
                    await self.client.stop_notify(self.module_channel.rx_uuid)
                if self.host_channel.notifications_enabled and self.host_channel.rx_uuid:
                    await self.client.stop_notify(self.host_channel.rx_uuid)
            except Exception:
                pass
            try:
                await self.client.disconnect()
            except Exception:
                pass

        self.client = None
        self.connected_device = None
        self.module_channel = SerialChannel(name="Module")
        self.host_channel = SerialChannel(name="Host")
        self.active_channel = self.module_channel

    async def discover_channels(self):
        """Discover available GATT services and set up channels"""
        if not self.client or not self.client.services:
            return

        services = self.client.services

        # Look for UART service (module channel)
        for svc in services:
            svc_uuid = str(svc.uuid).lower()
            
            # Nordic UART Service
            if "6e400001" in svc_uuid or svc_uuid == UART_SERVICE_UUID.lower():
                for ch in svc.characteristics:
                    ch_uuid = str(ch.uuid).lower()
                    if "6e400002" in ch_uuid:  # TX (write)
                        self.module_channel.tx_uuid = str(ch.uuid)
                    elif "6e400003" in ch_uuid:  # RX (notify)
                        self.module_channel.rx_uuid = str(ch.uuid)
                if self.module_channel.tx_uuid or self.module_channel.rx_uuid:
                    self.module_channel.available = True

            # FFE0 service (often used for config/serial)
            elif "ffe0" in svc_uuid:
                for ch in svc.characteristics:
                    ch_uuid = str(ch.uuid).lower()
                    props = [str(p) for p in ch.properties]
                    if "ffe1" in ch_uuid:
                        if "write" in props or "write-without-response" in props:
                            if not self.module_channel.tx_uuid:
                                self.module_channel.tx_uuid = str(ch.uuid)
                                self.module_channel.available = True
                        if "notify" in props:
                            if not self.module_channel.rx_uuid:
                                self.module_channel.rx_uuid = str(ch.uuid)
                                self.module_channel.available = True

            # FFF0 service (host/passthrough channel)
            elif "fff0" in svc_uuid:
                for ch in svc.characteristics:
                    ch_uuid = str(ch.uuid).lower()
                    props = [str(p) for p in ch.properties]
                    if "fff1" in ch_uuid or "fff2" in ch_uuid:
                        if "write" in props or "write-without-response" in props:
                            self.host_channel.tx_uuid = str(ch.uuid)
                        if "notify" in props:
                            self.host_channel.rx_uuid = str(ch.uuid)
                if self.host_channel.tx_uuid or self.host_channel.rx_uuid:
                    self.host_channel.available = True

        # Log discovered channels
        if self.module_channel.available:
            self.module_channel.log.append(f"[INFO] Module channel ready (TX: {self.module_channel.tx_uuid}, RX: {self.module_channel.rx_uuid})")
        if self.host_channel.available:
            self.host_channel.log.append(f"[INFO] Host channel ready (TX: {self.host_channel.tx_uuid}, RX: {self.host_channel.rx_uuid})")

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    async def read_config(self):
        """Read current configuration from device"""
        if not self.client:
            return

        # Try to read device name from GAP service
        try:
            # Standard GAP Device Name characteristic
            name_data = await self.client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
            self.config.name = name_data.decode("utf-8").rstrip("\x00")
        except Exception:
            if self.connected_device:
                self.config.name = self.connected_device.name

        # Note: Actual config reading depends on CP-26's specific protocol
        # You may need to send AT commands or read specific characteristics

    async def write_config_command(self, command: str):
        """Send a configuration command to the device"""
        if not self.client:
            self.set_status("Not connected")
            return False

        tx_uuid = self.module_channel.tx_uuid
        if not tx_uuid:
            self.set_status("No TX characteristic available")
            return False

        try:
            data = (command + "\r\n").encode("utf-8")
            await self.client.write_gatt_char(tx_uuid, data)
            self.set_status(f"Sent: {command}")
            return True
        except Exception as e:
            self.set_status(f"Write error: {e}")
            return False

    async def set_device_name(self, name: str):
        """Set the device name (AT+NAME command)"""
        await self.write_config_command(f"AT+NAME{name}")
        self.config.name = name

    async def set_baud_rate(self, baud: BaudRate):
        """Set baud rate (AT+BAUD command)"""
        baud_codes = {
            BaudRate.B9600: "0",
            BaudRate.B19200: "1",
            BaudRate.B38400: "2",
            BaudRate.B57600: "3",
            BaudRate.B115200: "4",
        }
        code = baud_codes.get(baud, "4")
        await self.write_config_command(f"AT+BAUD{code}")
        self.config.baud_rate = baud

    async def set_mode(self, mode: DeviceMode):
        """Set device mode"""
        mode_codes = {
            DeviceMode.PERIPHERAL: "0",
            DeviceMode.CENTRAL: "1",
            DeviceMode.BEACON: "2",
        }
        code = mode_codes.get(mode, "0")
        await self.write_config_command(f"AT+MODE{code}")
        self.config.mode = mode

    async def set_passthrough(self, enabled: bool):
        """Enable/disable passthrough mode"""
        await self.write_config_command(f"AT+PASS{1 if enabled else 0}")
        self.config.passthrough = enabled

    async def set_pin(self, pin: str):
        """Set pairing PIN"""
        await self.write_config_command(f"AT+PIN{pin}")
        self.config.pin = pin

    async def reset_device(self):
        """Reset the device"""
        await self.write_config_command("AT+RESET")
        self.set_status("Device reset command sent. Reconnect may be needed.")

    async def factory_reset(self):
        """Factory reset the device"""
        await self.write_config_command("AT+DEFAULT")
        self.set_status("Factory reset command sent. Reconnect required.")

    # -------------------------------------------------------------------------
    # Serial Communication
    # -------------------------------------------------------------------------

    def module_notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Handle notifications from module channel"""
        ts = self.get_timestamp()
        hex_str = data.hex(" ")
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        line = f"{ts}[RX-MOD] {hex_str}  | {ascii_str}"
        self.module_channel.log.append(line)

    def host_notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Handle notifications from host channel"""
        ts = self.get_timestamp()
        hex_str = data.hex(" ")
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        line = f"{ts}[RX-HOST] {hex_str}  | {ascii_str}"
        self.host_channel.log.append(line)

    async def toggle_module_notifications(self):
        """Toggle notifications on module channel"""
        if not self.client or not self.module_channel.rx_uuid:
            self.set_status("Module RX not available")
            return

        try:
            if not self.module_channel.notifications_enabled:
                await self.client.start_notify(
                    self.module_channel.rx_uuid, 
                    self.module_notification_handler
                )
                self.module_channel.notifications_enabled = True
                self.set_status("Module notifications ON")
            else:
                await self.client.stop_notify(self.module_channel.rx_uuid)
                self.module_channel.notifications_enabled = False
                self.set_status("Module notifications OFF")
        except Exception as e:
            self.set_status(f"Notify error: {e}")

    async def toggle_host_notifications(self):
        """Toggle notifications on host channel"""
        if not self.client or not self.host_channel.rx_uuid:
            self.set_status("Host RX not available")
            return

        try:
            if not self.host_channel.notifications_enabled:
                await self.client.start_notify(
                    self.host_channel.rx_uuid,
                    self.host_notification_handler
                )
                self.host_channel.notifications_enabled = True
                self.set_status("Host notifications ON")
            else:
                await self.client.stop_notify(self.host_channel.rx_uuid)
                self.host_channel.notifications_enabled = False
                self.set_status("Host notifications OFF")
        except Exception as e:
            self.set_status(f"Notify error: {e}")

    async def send_data(self):
        """Send data on active channel"""
        if not self.client:
            self.set_status("Not connected")
            return

        text = self.console_input.strip()
        if not text:
            return

        tx_uuid = self.active_channel.tx_uuid
        if not tx_uuid:
            self.set_status(f"{self.active_channel.name} TX not available")
            return

        try:
            if self.input_mode == InputMode.HEX:
                # Parse hex input
                text_clean = text.replace(" ", "").replace(":", "").replace("-", "")
                if not re.match(r'^[0-9a-fA-F]*$', text_clean):
                    self.set_status("Invalid hex format")
                    return
                if len(text_clean) % 2 != 0:
                    self.set_status("Hex string must have even length")
                    return
                data = bytes.fromhex(text_clean)
            else:
                # ASCII mode
                data = text.encode("utf-8")

            await self.client.write_gatt_char(tx_uuid, data)

            ts = self.get_timestamp()
            hex_str = data.hex(" ")
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
            ch_name = "MOD" if self.active_channel == self.module_channel else "HOST"
            line = f"{ts}[TX-{ch_name}] {hex_str}  | {ascii_str}"
            self.active_channel.log.append(line)
            self.console_input = ""

        except Exception as e:
            self.set_status(f"Send error: {e}")

    # -------------------------------------------------------------------------
    # Drawing
    # -------------------------------------------------------------------------

    def safe_addstr(self, row: int, col: int, text: str, attr=curses.A_NORMAL):
        """Safely add string to screen, handling boundaries"""
        if row < 0 or row >= self.height or col < 0 or col >= self.width:
            return
        try:
            max_len = self.width - col - 1
            if max_len > 0:
                self.stdscr.addstr(row, col, text[:max_len], attr)
        except curses.error:
            pass

    def draw_status_bar(self):
        """Draw status bar at bottom of screen"""
        status = self.status_message[:self.width - 1]
        try:
            self.stdscr.attron(curses.A_REVERSE)
            self.stdscr.addstr(self.height - 1, 0, status.ljust(self.width - 2))
            self.stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

    def draw_devices_screen(self):
        """Draw device list screen"""
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        title = "CP-26 BLE Manager - Device Scan (48:87:2D:*)"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        help_line = "[s]can  [Enter]connect  [q]uit"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

        if not self.devices:
            self.safe_addstr(3, 0, "No CP-26 devices found. Press 's' to scan.")
        else:
            max_lines = self.height - 5
            start = 0
            if self.selected_device_idx >= max_lines:
                start = self.selected_device_idx - max_lines + 1

            for visual_row, idx in enumerate(range(start, min(len(self.devices), start + max_lines))):
                if 3 + visual_row >= self.height - 1:
                    break
                dev = self.devices[idx]
                prefix = "-> " if idx == self.selected_device_idx else "   "
                rssi_bar = "█" * max(0, min(5, (dev.rssi + 100) // 10))
                line = f"{prefix}{dev.name:<20} [{dev.address}] {rssi_bar} {dev.rssi}dBm"
                attr = curses.A_REVERSE if idx == self.selected_device_idx else curses.A_NORMAL
                self.safe_addstr(3 + visual_row, 0, line, attr)

        self.draw_status_bar()
        self.stdscr.refresh()

    def draw_config_screen(self):
        """Draw configuration screen"""
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        dev_name = self.connected_device.name if self.connected_device else "Not connected"
        title = f"CP-26 Configuration - {dev_name}"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        help_line = "[j/k]navigate  [Enter]edit  [c]onsole  [r]eset  [R]factory  [d]isconnect  [q]uit"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

        # Configuration menu items
        menu_items = [
            ("Device Name", self.config.name),
            ("Mode", self.config.mode.value),
            ("Baud Rate", self.config.baud_rate.value),
            ("Passthrough", "Enabled" if self.config.passthrough else "Disabled"),
            ("PIN", self.config.pin),
        ]

        for idx, (label, value) in enumerate(menu_items):
            row = 3 + idx
            if row >= self.height - 1:
                break
            prefix = "-> " if idx == self.config_menu_idx else "   "
            
            if self.config_editing and idx == self.config_menu_idx:
                line = f"{prefix}{label}: {self.config_edit_value}_"
                attr = curses.A_BOLD
            else:
                line = f"{prefix}{label}: {value}"
                attr = curses.A_REVERSE if idx == self.config_menu_idx else curses.A_NORMAL
            
            self.safe_addstr(row, 0, line, attr)

        # Channel info
        row = 3 + len(menu_items) + 1
        self.safe_addstr(row, 0, "─" * min(60, self.width - 1))
        row += 1
        self.safe_addstr(row, 0, "Available Channels:", curses.A_BOLD)
        row += 1
        mod_status = "✓ Ready" if self.module_channel.available else "✗ Not found"
        self.safe_addstr(row, 0, f"  Module: {mod_status}")
        row += 1
        host_status = "✓ Ready" if self.host_channel.available else "✗ Not found"
        self.safe_addstr(row, 0, f"  Host:   {host_status}")

        self.draw_status_bar()
        self.stdscr.refresh()

    def draw_console_screen(self):
        """Draw dual-channel console screen"""
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        # Title bar
        ch_name = self.active_channel.name
        mode_str = self.input_mode.value
        mod_notify = "M:ON" if self.module_channel.notifications_enabled else "M:off"
        host_notify = "H:ON" if self.host_channel.notifications_enabled else "H:off"
        
        title = f"Console [{ch_name}] Mode:{mode_str} {mod_notify} {host_notify}"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        help_line = "[Tab]channel [m]mode [1]mod-notify [2]host-notify [Enter]send [b]ack [q]uit"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

        # Calculate split - show both logs
        log_start = 2
        log_height = max(1, (self.height - 5) // 2)
        
        # Module channel log
        self.safe_addstr(log_start, 0, f"─ Module Channel {'(active)' if self.active_channel == self.module_channel else ''} ─", 
                        curses.A_BOLD if self.active_channel == self.module_channel else curses.A_DIM)
        
        mod_logs = list(self.module_channel.log)[-log_height:]
        for i, line in enumerate(mod_logs):
            row = log_start + 1 + i
            if row >= log_start + 1 + log_height:
                break
            color = curses.color_pair(1) if "[TX" in line else curses.color_pair(2)
            self.safe_addstr(row, 0, line, color if curses.has_colors() else curses.A_NORMAL)

        # Host channel log
        host_start = log_start + log_height + 2
        self.safe_addstr(host_start, 0, f"─ Host Channel {'(active)' if self.active_channel == self.host_channel else ''} ─",
                        curses.A_BOLD if self.active_channel == self.host_channel else curses.A_DIM)
        
        host_logs = list(self.host_channel.log)[-log_height:]
        for i, line in enumerate(host_logs):
            row = host_start + 1 + i
            if row >= self.height - 2:
                break
            color = curses.color_pair(1) if "[TX" in line else curses.color_pair(3)
            self.safe_addstr(row, 0, line, color if curses.has_colors() else curses.A_NORMAL)

        # Input line
        if self.height >= 3:
            prompt = f"[{mode_str}]> " + self.console_input
            try:
                self.stdscr.attron(curses.A_REVERSE)
                self.stdscr.addstr(self.height - 2, 0, prompt[:self.width - 2].ljust(self.width - 2))
                self.stdscr.attroff(curses.A_REVERSE)
            except curses.error:
                pass

        self.draw_status_bar()
        self.stdscr.refresh()

    # -------------------------------------------------------------------------
    # Key Handling
    # -------------------------------------------------------------------------

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

    async def handle_config_keys(self, ch: int):
        if self.config_editing:
            await self._handle_config_edit_keys(ch)
            return

        if ch == ord("q"):
            raise SystemExit
        elif ch == ord("d"):
            await self.disconnect()
            self.current_screen = "devices"
            self.set_status("Disconnected.")
        elif ch == ord("c"):
            self.current_screen = "console"
            self.set_status("Console mode. Press Tab to switch channels.")
        elif ch == ord("r"):
            await self.reset_device()
        elif ch == ord("R"):
            await self.factory_reset()
        elif ch in (curses.KEY_UP, ord("k")):
            self.config_menu_idx = max(0, self.config_menu_idx - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.config_menu_idx = min(4, self.config_menu_idx + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            self._start_config_edit()

    async def _handle_config_edit_keys(self, ch: int):
        if ch == 27:  # ESC
            self.config_editing = False
            self.config_edit_value = ""
        elif ch in (curses.KEY_ENTER, 10, 13):
            await self._apply_config_edit()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            self.config_edit_value = self.config_edit_value[:-1]
        elif 32 <= ch <= 126:
            self.config_edit_value += chr(ch)

    def _start_config_edit(self):
        self.config_editing = True
        if self.config_menu_idx == 0:
            self.config_edit_value = self.config.name
        elif self.config_menu_idx == 1:
            self.config_edit_value = ""  # Will cycle through modes
            self._cycle_mode()
            self.config_editing = False
        elif self.config_menu_idx == 2:
            self.config_edit_value = ""  # Will cycle through baud rates
            self._cycle_baud()
            self.config_editing = False
        elif self.config_menu_idx == 3:
            self.config.passthrough = not self.config.passthrough
            self.config_editing = False
            asyncio.create_task(self.set_passthrough(self.config.passthrough))
        elif self.config_menu_idx == 4:
            self.config_edit_value = self.config.pin

    def _cycle_mode(self):
        modes = list(DeviceMode)
        idx = modes.index(self.config.mode)
        new_mode = modes[(idx + 1) % len(modes)]
        asyncio.create_task(self.set_mode(new_mode))

    def _cycle_baud(self):
        bauds = list(BaudRate)
        idx = bauds.index(self.config.baud_rate)
        new_baud = bauds[(idx + 1) % len(bauds)]
        asyncio.create_task(self.set_baud_rate(new_baud))

    async def _apply_config_edit(self):
        self.config_editing = False
        value = self.config_edit_value.strip()
        
        if self.config_menu_idx == 0 and value:
            await self.set_device_name(value)
        elif self.config_menu_idx == 4 and value:
            await self.set_pin(value)
        
        self.config_edit_value = ""

    async def handle_console_keys(self, ch: int):
        if ch == ord("q"):
            raise SystemExit
        elif ch == ord("b"):
            self.current_screen = "config"
            self.clear_status()
        elif ch == ord("\t") or ch == 9:  # Tab - switch channel
            if self.active_channel == self.module_channel:
                self.active_channel = self.host_channel
                self.set_status("Switched to Host channel")
            else:
                self.active_channel = self.module_channel
                self.set_status("Switched to Module channel")
        elif ch == ord("m"):  # Toggle input mode
            if self.input_mode == InputMode.ASCII:
                self.input_mode = InputMode.HEX
                self.set_status("Input mode: HEX")
            else:
                self.input_mode = InputMode.ASCII
                self.set_status("Input mode: ASCII")
        elif ch == ord("1"):  # Toggle module notifications
            await self.toggle_module_notifications()
        elif ch == ord("2"):  # Toggle host notifications
            await self.toggle_host_notifications()
        elif ch in (curses.KEY_ENTER, 10, 13):
            await self.send_data()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.console_input:
                self.console_input = self.console_input[:-1]
        elif 32 <= ch <= 126:
            self.console_input += chr(ch)

    # -------------------------------------------------------------------------
    # Main Loop
    # -------------------------------------------------------------------------

    async def run(self):
        await self.scan_devices()

        while True:
            # Draw current screen
            if self.current_screen == "devices":
                self.draw_devices_screen()
            elif self.current_screen == "config":
                self.draw_config_screen()
            elif self.current_screen == "console":
                self.draw_console_screen()

            # Get key (non-blocking)
            try:
                ch = self.stdscr.getch()
            except curses.error:
                ch = -1

            if ch != -1:
                try:
                    if self.current_screen == "devices":
                        await self.handle_devices_keys(ch)
                    elif self.current_screen == "config":
                        await self.handle_config_keys(ch)
                    elif self.current_screen == "console":
                        await self.handle_console_keys(ch)
                except SystemExit:
                    break
                except Exception as e:
                    self.set_status(f"Error: {e}")

            await asyncio.sleep(0.05)

        # Cleanup
        await self.disconnect()


def main(stdscr):
    app = CP26TuiApp(stdscr)
    asyncio.run(app.run())


if __name__ == "__main__":
    curses.wrapper(main)
