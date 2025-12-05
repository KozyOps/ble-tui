#!/usr/bin/env python3
"""
DX-BT24 BLE Adapter Configuration TUI

A specialized curses + asyncio TUI for managing DX-Smart DX-BT24 Bluetooth adapters.
(Sometimes sold as CP-26 or similar model numbers)

IMPORTANT - AT Command Limitations:
-----------------------------------
The DX-BT24 module has a critical limitation: AT commands only work when the module
is NOT connected via BLE! The manual states: "AT command mode when the module is
not connected."

To configure the device, you need to either:
1. Use a UART/serial connection directly to the module pins
2. Enable APPAT mode via UART first (AT+APPAT1), then AT commands work over BLE

The default is APPAT=0 (disabled), meaning you CANNOT send AT commands over BLE
until you first enable it via a direct UART connection.

Features:
- Scans only for DX-BT24/CP-26 devices (MAC prefix 48:87:2D)
- Interview/discover all GATT services and characteristics
- Assign any characteristic to Module or Host channel
- Send AT commands (if APPAT is enabled) - see note above
- Dual serial console with independent notifications
- Send data as ASCII or HEX

AT Command Reference (requires APPAT enabled):
- AT               Test command (returns OK)
- AT+VERSION       Query firmware version
- AT+LADDR         Query MAC address
- AT+NAMExxx       Set device name (max 20 bytes, no = sign)
- AT+NAME          Query device name
- AT+BAUDn         Set baud (0=9600,1=19200,2=38400,3=57600,4=115200, no = sign)
- AT+RESET         Software restart
- AT+DEFAULT       Restore factory settings
- AT+APPAT=1       Enable AT commands over BLE (must be done via UART first!)
"""

import asyncio
import curses
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable

from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

# DX-BT24 MAC prefix (sold as CP-26 and other names)
CP26_MAC_PREFIX = "48:87:2D"

# DX-BT24 Default UUIDs from datasheet
DEFAULT_SERVICE_UUID = "0000ffe0"
DEFAULT_NOTIFY_WRITE_UUID = "0000ffe1"  # Notify + Write
DEFAULT_WRITE_UUID = "0000ffe2"          # Write only


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
class CharacteristicInfo:
    """Information about a discovered characteristic"""
    service_uuid: str
    service_name: str
    char_uuid: str
    char_name: str
    properties: List[str]
    handle: int = 0
    
    def can_write(self) -> bool:
        return "write" in self.properties or "write-without-response" in self.properties
    
    def can_notify(self) -> bool:
        return "notify" in self.properties or "indicate" in self.properties
    
    def can_read(self) -> bool:
        return "read" in self.properties
    
    @property
    def props_str(self) -> str:
        abbrev = []
        if self.can_read():
            abbrev.append("R")
        if self.can_write():
            abbrev.append("W")
        if self.can_notify():
            abbrev.append("N")
        return "".join(abbrev)


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
    tx_char: Optional[CharacteristicInfo] = None
    rx_char: Optional[CharacteristicInfo] = None
    log: deque = field(default_factory=lambda: deque(maxlen=500))
    notifications_enabled: bool = False
    
    @property
    def tx_uuid(self) -> Optional[str]:
        return self.tx_char.char_uuid if self.tx_char else None
    
    @property
    def rx_uuid(self) -> Optional[str]:
        return self.rx_char.char_uuid if self.rx_char else None
    
    @property
    def available(self) -> bool:
        return self.tx_char is not None or self.rx_char is not None


# Well-known GATT service/characteristic names
KNOWN_SERVICES = {
    "00001800": "Generic Access",
    "00001801": "Generic Attribute",
    "0000180a": "Device Information",
    "0000180f": "Battery Service",
    "6e400001": "Nordic UART",
    "0000ffe0": "Serial/Config",
    "0000fff0": "Custom Serial",
}

KNOWN_CHARS = {
    "00002a00": "Device Name",
    "00002a01": "Appearance",
    "00002a04": "Peripheral Params",
    "00002a05": "Service Changed",
    "00002a19": "Battery Level",
    "00002a29": "Manufacturer",
    "00002a24": "Model Number",
    "00002a25": "Serial Number",
    "00002a26": "Firmware Rev",
    "00002a27": "Hardware Rev",
    "00002a28": "Software Rev",
    "6e400002": "UART TX",
    "6e400003": "UART RX",
    "0000ffe1": "Serial N+W",      # DX-BT24: Notify+Write
    "0000ffe2": "Serial Write",    # DX-BT24: Write only
    "0000fff1": "Custom TX",
    "0000fff2": "Custom RX",
}


def get_service_name(uuid: str) -> str:
    """Get human-readable service name"""
    uuid_lower = uuid.lower()
    for prefix, name in KNOWN_SERVICES.items():
        if uuid_lower.startswith(prefix):
            return name
    return uuid[:8]


def get_char_name(uuid: str) -> str:
    """Get human-readable characteristic name"""
    uuid_lower = uuid.lower()
    for prefix, name in KNOWN_CHARS.items():
        if uuid_lower.startswith(prefix):
            return name
    return uuid[:8]


# =============================================================================
# Main Application
# =============================================================================

class CP26TuiApp:
    """
    Curses + asyncio TUI for CP-26 BLE adapter management.
    
    Screens:
    - devices: Scan and select CP-26 devices
    - interview: Discover and explore all characteristics
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

        # Discovered characteristics
        self.characteristics: List[CharacteristicInfo] = []
        self.selected_char_idx: int = 0
        self.char_scroll_offset: int = 0

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
        
        # AT Command mode state
        self.at_mode_enabled: bool = False

        # Screen state
        self.current_screen: str = "devices"
        self.status_message: str = ""
        self.interview_action_menu: bool = False
        self.action_menu_idx: int = 0
        
        # Setup wizard state
        self.setup_step: int = 0
        self.setup_field_idx: int = 0
        self.setup_editing: bool = False
        self.setup_edit_value: str = ""
        self.setup_name: str = "NewDevice"
        self.setup_baud: BaudRate = BaudRate.B9600
        self.setup_running: bool = False
        self.setup_log: deque = deque(maxlen=20)

        # Curses config
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.nodelay(True)
        curses.curs_set(0)
        
        # Initialize colors if available
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)   # TX / Write
            curses.init_pair(2, curses.COLOR_CYAN, -1)    # RX Module / Notify
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # RX Host / Read
            curses.init_pair(4, curses.COLOR_RED, -1)     # Error
            curses.init_pair(5, curses.COLOR_MAGENTA, -1) # Info / Selected

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
        self.set_status("Scanning for DX-BT24 devices (48:87:2D:*)...")
        self.devices = []
        self.selected_device_idx = 0
        
        try:
            found = await BleakScanner.discover(timeout=5.0, return_adv=True)
            for address, (device, adv_data) in found.items():
                # Filter for DX-BT24/CP-26 MAC prefix
                if address.upper().startswith(CP26_MAC_PREFIX):
                    name = device.name or adv_data.local_name or "DX-BT24 Unknown"
                    rssi = adv_data.rssi if adv_data.rssi else -100
                    self.devices.append(DeviceEntry(address=address, name=name, rssi=rssi))
            
            # Sort by signal strength
            self.devices.sort(key=lambda d: d.rssi, reverse=True)
            
            if not self.devices:
                self.set_status("No DX-BT24 devices found (48:87:2D:*). Press F1 to rescan.")
            else:
                self.set_status(f"Found {len(self.devices)} DX-BT24 device(s).")
        except Exception as e:
            self.set_status(f"Scan error: {e}")

    async def connect_selected_device(self):
        if not self.devices:
            self.set_status("No devices to connect. Press F1 to scan.")
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
            await self.discover_characteristics()
            await self.read_config()
            self.current_screen = "interview"
            
            # Build status message about auto-assignments
            assignments = []
            if self.module_channel.tx_char or self.module_channel.rx_char:
                assignments.append("Module")
            if self.host_channel.tx_char or self.host_channel.rx_char:
                assignments.append("Host")
            if assignments:
                self.set_status(f"Auto-assigned: {', '.join(assignments)}. Press 'c' for console or adjust assignments.")
            else:
                self.set_status(f"Found {len(self.characteristics)} chars. Assign TX/RX manually.")
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
            except Exception:
                pass
            try:
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
        self.characteristics = []
        self.selected_char_idx = 0
        self.module_channel = SerialChannel(name="Module")
        self.host_channel = SerialChannel(name="Host")
        self.active_channel = self.module_channel

    async def discover_characteristics(self):
        """Discover all GATT services and characteristics"""
        self.characteristics = []
        
        if not self.client or not self.client.services:
            return

        for svc in self.client.services:
            svc_uuid = str(svc.uuid)
            svc_name = get_service_name(svc_uuid)
            
            for ch in svc.characteristics:
                char_uuid = str(ch.uuid)
                char_name = get_char_name(char_uuid)
                props = [str(p) for p in ch.properties]
                
                self.characteristics.append(CharacteristicInfo(
                    service_uuid=svc_uuid,
                    service_name=svc_name,
                    char_uuid=char_uuid,
                    char_name=char_name,
                    properties=props,
                    handle=ch.handle if hasattr(ch, 'handle') else 0,
                ))
        
        # Auto-assign best guess for Module and Host channels
        self._auto_assign_channels()

    def _auto_assign_channels(self):
        """
        Auto-assign TX/RX based on DX-BT24 datasheet:
        - Service: FFE0
        - FFE1: Notify + Write (primary serial data)
        - FFE2: Write only (secondary/command)
        
        For this module, FFE1 is typically used for both TX and RX (bidirectional).
        """
        # Find FFE1 (primary - Notify+Write)
        ffe1_char = None
        ffe2_char = None
        
        for char in self.characteristics:
            uuid_lower = char.char_uuid.lower()
            if uuid_lower.startswith("0000ffe1"):
                ffe1_char = char
            elif uuid_lower.startswith("0000ffe2"):
                ffe2_char = char
        
        # Module channel uses FFE1 for both TX and RX (it supports both Write and Notify)
        if ffe1_char:
            if ffe1_char.can_write():
                self.module_channel.tx_char = ffe1_char
            if ffe1_char.can_notify():
                self.module_channel.rx_char = ffe1_char
        
        # Host channel uses FFE2 for TX if available (Write only)
        if ffe2_char and ffe2_char.can_write():
            self.host_channel.tx_char = ffe2_char
        
        # If we didn't find FFE1/FFE2, fall back to generic patterns
        if not self.module_channel.tx_char and not self.module_channel.rx_char:
            self._auto_assign_generic()

    def _auto_assign_generic(self):
        """Fallback: find any writable/notifiable characteristics for non-DX-BT24 devices"""
        # Look for Nordic UART or any serial-like characteristics
        patterns = ["6e4000", "0000fff", "0000ffe"]
        
        for char in self.characteristics:
            uuid_lower = char.char_uuid.lower()
            for pattern in patterns:
                if pattern in uuid_lower:
                    if char.can_write() and not self.module_channel.tx_char:
                        self.module_channel.tx_char = char
                    if char.can_notify() and not self.module_channel.rx_char:
                        self.module_channel.rx_char = char

    async def read_characteristic(self, char: CharacteristicInfo) -> Optional[bytes]:
        """Read value from a characteristic"""
        if not self.client or not char.can_read():
            return None
        
        try:
            data = await self.client.read_gatt_char(char.char_uuid)
            return data
        except Exception as e:
            self.set_status(f"Read error: {e}")
            return None

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    async def read_config(self):
        """Read current configuration from device"""
        if not self.client:
            return

        # Try to read device name from GAP service
        try:
            name_data = await self.client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
            self.config.name = name_data.decode("utf-8").rstrip("\x00")
        except Exception:
            if self.connected_device:
                self.config.name = self.connected_device.name

    async def write_raw(self, data: bytes):
        """Write raw bytes to the module TX characteristic"""
        if not self.client:
            return False
        tx_uuid = self.module_channel.tx_uuid
        if not tx_uuid:
            return False
        try:
            await self.client.write_gatt_char(tx_uuid, data)
            return True
        except Exception:
            return False

    async def enter_at_mode(self):
        """
        Note: AT commands on DX-BT24 only work if:
        1. APPAT is enabled (AT+APPAT1 sent via UART first)
        2. The module is connected
        
        Default is APPAT=0 (disabled), so AT commands won't work over BLE
        unless you first enable it via a direct UART connection.
        """
        if not self.client or not self.module_channel.tx_uuid:
            self.set_status("No TX characteristic assigned")
            return False
        
        self.set_status("Sending AT test command...")
        
        # Send AT test command with proper terminator
        await self.write_raw(b"AT\r\n")
        await asyncio.sleep(0.3)
        
        self.at_mode_enabled = True
        self.set_status("AT mode ON. If no response, APPAT may be disabled (see docs).")
        return True

    async def exit_at_mode(self):
        """Exit AT command mode - reset the UI flag"""
        self.at_mode_enabled = False
        self.set_status("AT mode flag OFF. (Module stays in current mode)")

    async def write_config_command(self, command: str):
        """Send a configuration command to the device"""
        if not self.client:
            self.set_status("Not connected")
            return False

        tx_uuid = self.module_channel.tx_uuid
        if not tx_uuid:
            self.set_status("No TX characteristic assigned to Module channel")
            return False

        try:
            # Try with \r\n terminator
            data = (command + "\r\n").encode("utf-8")
            await self.client.write_gatt_char(tx_uuid, data)
            self.set_status(f"Sent: {command}")
            return True
        except Exception as e:
            self.set_status(f"Write error: {e}")
            return False

    async def set_device_name(self, name: str):
        """Set device name. Format: AT+NAMExxx (max 20 bytes, no = sign)"""
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        await self.write_config_command(f"AT+NAME{name}")
        self.config.name = name

    async def set_baud_rate(self, baud: BaudRate):
        """Set baud rate. Codes: 0=9600, 1=19200, 2=38400, 3=57600, 4=115200 (no = sign)"""
        baud_codes = {
            BaudRate.B9600: "0", BaudRate.B19200: "1", BaudRate.B38400: "2",
            BaudRate.B57600: "3", BaudRate.B115200: "4",
        }
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        await self.write_config_command(f"AT+BAUD{baud_codes.get(baud, '0')}")
        self.config.baud_rate = baud

    async def set_mode(self, mode: DeviceMode):
        """Note: DX-BT24 is BLE peripheral only - mode setting may not apply"""
        mode_codes = {DeviceMode.PERIPHERAL: "0", DeviceMode.CENTRAL: "1", DeviceMode.BEACON: "2"}
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        # Note: DX-BT24 may not support mode changes - it's a peripheral device
        await self.write_config_command(f"AT+TYPE={mode_codes.get(mode, '0')}")
        self.config.mode = mode

    async def set_passthrough(self, enabled: bool):
        """Note: passthrough is default behavior for DX-BT24"""
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        # This command may not exist on DX-BT24 - it's transparent by default
        self.set_status("Note: DX-BT24 is transparent by default")
        self.config.passthrough = enabled

    async def set_pin(self, pin: str):
        """Set PIN code"""
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        await self.write_config_command(f"AT+PIN={pin}")
        self.config.pin = pin

    async def reset_device(self):
        """Reset the device - AT+RESET"""
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        
        await self.write_config_command("AT+RESET")
        self.set_status("Reset sent. Device will disconnect and restart.")

    async def factory_reset(self):
        """Factory reset - AT+DEFAULT"""
        if not self.at_mode_enabled:
            await self.enter_at_mode()
        
        await self.write_config_command("AT+DEFAULT")
        self.set_status("Factory reset sent. Device will restart with defaults.")

    # -------------------------------------------------------------------------
    # Serial Communication
    # -------------------------------------------------------------------------

    def module_notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        ts = self.get_timestamp()
        hex_str = data.hex(" ")
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        line = f"{ts}[RX-MOD] {hex_str}  | {ascii_str}"
        self.module_channel.log.append(line)

    def host_notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        ts = self.get_timestamp()
        hex_str = data.hex(" ")
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        line = f"{ts}[RX-HOST] {hex_str}  | {ascii_str}"
        self.host_channel.log.append(line)

    async def toggle_channel_notifications(self, channel: SerialChannel):
        """Toggle notifications on a channel"""
        if not self.client or not channel.rx_uuid:
            self.set_status(f"{channel.name} RX not assigned")
            return

        handler = self.module_notification_handler if channel == self.module_channel else self.host_notification_handler

        try:
            if not channel.notifications_enabled:
                await self.client.start_notify(channel.rx_uuid, handler)
                channel.notifications_enabled = True
                self.set_status(f"{channel.name} notifications ON")
            else:
                await self.client.stop_notify(channel.rx_uuid)
                channel.notifications_enabled = False
                self.set_status(f"{channel.name} notifications OFF")
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
            self.set_status(f"{self.active_channel.name} TX not assigned")
            return

        try:
            if self.input_mode == InputMode.HEX:
                text_clean = text.replace(" ", "").replace(":", "").replace("-", "")
                if not re.match(r'^[0-9a-fA-F]*$', text_clean):
                    self.set_status("Invalid hex format")
                    return
                if len(text_clean) % 2 != 0:
                    self.set_status("Hex string must have even length")
                    return
                data = bytes.fromhex(text_clean)
            else:
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
        if row < 0 or row >= self.height or col < 0 or col >= self.width:
            return
        try:
            max_len = self.width - col - 1
            if max_len > 0:
                self.stdscr.addstr(row, col, text[:max_len], attr)
        except curses.error:
            pass

    def draw_status_bar(self):
        status = self.status_message[:self.width - 1]
        try:
            self.stdscr.attron(curses.A_REVERSE)
            self.stdscr.addstr(self.height - 1, 0, status.ljust(self.width - 2))
            self.stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

    def draw_devices_screen(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        title = "DX-BT24 BLE Manager - Device Scan (48:87:2D:*)"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        help_line = "[F1]scan  [Enter]connect  [F10]quit"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

        if not self.devices:
            self.safe_addstr(3, 0, "No DX-BT24 devices found. Press F1 to scan.")
        else:
            max_lines = self.height - 5
            start = 0
            if self.selected_device_idx >= max_lines:
                start = self.selected_device_idx - max_lines + 1

            for visual_row, idx in enumerate(range(start, min(len(self.devices), start + max_lines))):
                if 3 + visual_row >= self.height - 1:
                    break
                dev = self.devices[idx]
                prefix = ">" if idx == self.selected_device_idx else " "
                rssi_bar = "█" * max(0, min(5, (dev.rssi + 100) // 10))
                line = f"{prefix} {dev.name:<20} [{dev.address}] {rssi_bar} {dev.rssi}dBm"
                attr = curses.A_REVERSE if idx == self.selected_device_idx else curses.A_NORMAL
                self.safe_addstr(3 + visual_row, 0, line, attr)

        self.draw_status_bar()
        self.stdscr.refresh()

    def draw_interview_screen(self):
        """Draw the characteristic interview/discovery screen"""
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        dev_name = self.connected_device.name if self.connected_device else "Unknown"
        title = f"Characteristic Interview - {dev_name}"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        help_line = "[↑↓]nav [Enter]action [F2]read [F3]console [F4]config [F8]setup [F9]disconn [F10]quit"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

        # Channel assignments summary
        row = 2
        mod_tx = self.module_channel.tx_char.char_name if self.module_channel.tx_char else "---"
        mod_rx = self.module_channel.rx_char.char_name if self.module_channel.rx_char else "---"
        host_tx = self.host_channel.tx_char.char_name if self.host_channel.tx_char else "---"
        host_rx = self.host_channel.rx_char.char_name if self.host_channel.rx_char else "---"
        
        self.safe_addstr(row, 0, f"Module: TX={mod_tx} RX={mod_rx}  |  Host: TX={host_tx} RX={host_rx}", 
                        curses.color_pair(5) if curses.has_colors() else curses.A_DIM)
        row += 1
        self.safe_addstr(row, 0, "─" * min(80, self.width - 1))
        row += 1

        # Characteristic list
        if not self.characteristics:
            self.safe_addstr(row, 0, "No characteristics found.")
        else:
            max_lines = self.height - row - 2
            
            # Adjust scroll offset
            if self.selected_char_idx < self.char_scroll_offset:
                self.char_scroll_offset = self.selected_char_idx
            elif self.selected_char_idx >= self.char_scroll_offset + max_lines:
                self.char_scroll_offset = self.selected_char_idx - max_lines + 1

            current_service = None
            visual_row = 0
            
            for idx in range(self.char_scroll_offset, min(len(self.characteristics), self.char_scroll_offset + max_lines)):
                char = self.characteristics[idx]
                
                # Service header (inline with first char of that service)
                if char.service_name != current_service:
                    current_service = char.service_name
                
                is_selected = idx == self.selected_char_idx
                prefix = ">" if is_selected else " "
                
                # Show assignment indicators
                assignments = []
                if char == self.module_channel.tx_char:
                    assignments.append("M-TX")
                if char == self.module_channel.rx_char:
                    assignments.append("M-RX")
                if char == self.host_channel.tx_char:
                    assignments.append("H-TX")
                if char == self.host_channel.rx_char:
                    assignments.append("H-RX")
                assign_str = f" [{','.join(assignments)}]" if assignments else ""
                
                # Format: > [RWN] CharName (ServiceName) [M-TX]
                line = f"{prefix} [{char.props_str:3}] {char.char_name:<18} ({char.service_name}){assign_str}"
                
                if is_selected:
                    attr = curses.A_REVERSE
                elif assignments:
                    attr = curses.color_pair(5) if curses.has_colors() else curses.A_BOLD
                else:
                    attr = curses.A_NORMAL
                
                self.safe_addstr(row + visual_row, 0, line, attr)
                visual_row += 1
                
                if row + visual_row >= self.height - 2:
                    break

        # Action menu popup
        if self.interview_action_menu and self.characteristics:
            self._draw_action_menu()

        self.draw_status_bar()
        self.stdscr.refresh()

    def _draw_action_menu(self):
        """Draw the action popup menu for characteristic assignment"""
        char = self.characteristics[self.selected_char_idx]
        
        # Build menu options based on characteristic properties
        options = []
        if char.can_write():
            options.append(("Set as Module TX", "mod_tx"))
            options.append(("Set as Host TX", "host_tx"))
        if char.can_notify():
            options.append(("Set as Module RX", "mod_rx"))
            options.append(("Set as Host RX", "host_rx"))
        if char.can_read():
            options.append(("Read Value", "read"))
        options.append(("Clear Assignments", "clear"))
        options.append(("Cancel", "cancel"))
        
        self.action_options = options
        
        # Draw menu box
        menu_width = 30
        menu_height = len(options) + 2
        start_row = max(2, (self.height - menu_height) // 2)
        start_col = max(0, (self.width - menu_width) // 2)
        
        # Box border
        self.safe_addstr(start_row, start_col, "┌" + "─" * (menu_width - 2) + "┐")
        for i in range(len(options)):
            self.safe_addstr(start_row + 1 + i, start_col, "│" + " " * (menu_width - 2) + "│")
        self.safe_addstr(start_row + len(options) + 1, start_col, "└" + "─" * (menu_width - 2) + "┘")
        
        # Menu items
        for i, (label, _) in enumerate(options):
            is_sel = i == self.action_menu_idx
            attr = curses.A_REVERSE if is_sel else curses.A_NORMAL
            prefix = ">" if is_sel else " "
            self.safe_addstr(start_row + 1 + i, start_col + 1, f"{prefix} {label:<{menu_width - 4}}", attr)

    def draw_config_screen(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        dev_name = self.connected_device.name if self.connected_device else "Not connected"
        title = f"DX-BT24 Configuration - {dev_name}"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        at_status = "AT:ON" if self.at_mode_enabled else "AT:off"
        help_line = f"[↑↓]nav [Enter]edit [F5]at [F2]intrv [F3]cons [F6]rst [F7]fact [F8]setup [F9]disc  {at_status}"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

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
            prefix = ">" if idx == self.config_menu_idx else " "
            
            if self.config_editing and idx == self.config_menu_idx:
                line = f"{prefix} {label}: {self.config_edit_value}_"
                attr = curses.A_BOLD
            else:
                line = f"{prefix} {label}: {value}"
                attr = curses.A_REVERSE if idx == self.config_menu_idx else curses.A_NORMAL
            
            self.safe_addstr(row, 0, line, attr)

        # Channel assignments
        row = 3 + len(menu_items) + 1
        self.safe_addstr(row, 0, "─" * min(60, self.width - 1))
        row += 1
        self.safe_addstr(row, 0, "Channel Assignments:", curses.A_BOLD)
        row += 1
        
        mod_tx = self.module_channel.tx_char.char_name if self.module_channel.tx_char else "Not assigned"
        mod_rx = self.module_channel.rx_char.char_name if self.module_channel.rx_char else "Not assigned"
        self.safe_addstr(row, 0, f"  Module TX: {mod_tx}")
        row += 1
        self.safe_addstr(row, 0, f"  Module RX: {mod_rx}")
        row += 1
        
        host_tx = self.host_channel.tx_char.char_name if self.host_channel.tx_char else "Not assigned"
        host_rx = self.host_channel.rx_char.char_name if self.host_channel.rx_char else "Not assigned"
        self.safe_addstr(row, 0, f"  Host TX:   {host_tx}")
        row += 1
        self.safe_addstr(row, 0, f"  Host RX:   {host_rx}")
        row += 2
        
        # Important note about AT commands
        self.safe_addstr(row, 0, "─" * min(60, self.width - 1))
        row += 1
        note_color = curses.color_pair(4) if curses.has_colors() else curses.A_BOLD
        self.safe_addstr(row, 0, "NOTE: AT commands only work if APPAT is enabled via UART!", note_color)
        row += 1
        self.safe_addstr(row, 0, "Default is APPAT=0 (disabled). See module docs.", curses.A_DIM)

        self.draw_status_bar()
        self.stdscr.refresh()

    def draw_console_screen(self):
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        ch_name = self.active_channel.name
        mode_str = self.input_mode.value
        mod_notify = "M:ON" if self.module_channel.notifications_enabled else "M:off"
        host_notify = "H:ON" if self.host_channel.notifications_enabled else "H:off"
        
        title = f"Console [{ch_name}] Mode:{mode_str} {mod_notify} {host_notify}"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        help_line = "[F1]ch [F5]mode [F6]M-notif [F7]H-notif [F8]setup [F2]intrv [F4]cfg [Enter]send [F10]quit"
        self.safe_addstr(1, 0, help_line, curses.A_DIM)

        # Calculate split
        log_start = 2
        log_height = max(1, (self.height - 5) // 2)
        
        # Module channel log
        mod_active = "(active)" if self.active_channel == self.module_channel else ""
        mod_header = f"─ Module {mod_active} ─"
        self.safe_addstr(log_start, 0, mod_header, 
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
        host_active = "(active)" if self.active_channel == self.host_channel else ""
        host_header = f"─ Host {host_active} ─"
        self.safe_addstr(host_start, 0, host_header,
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
        if ch == curses.KEY_F10:
            raise SystemExit
        elif ch == curses.KEY_F1:
            await self.scan_devices()
        elif ch == curses.KEY_UP:
            if self.devices:
                self.selected_device_idx = max(0, self.selected_device_idx - 1)
        elif ch == curses.KEY_DOWN:
            if self.devices:
                self.selected_device_idx = min(len(self.devices) - 1, self.selected_device_idx + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            await self.connect_selected_device()

    async def handle_interview_keys(self, ch: int):
        if self.interview_action_menu:
            await self._handle_action_menu_keys(ch)
            return

        if ch == curses.KEY_F10:
            raise SystemExit
        elif ch == curses.KEY_F9:
            await self.disconnect()
            self.current_screen = "devices"
            self.set_status("Disconnected.")
        elif ch == curses.KEY_F3:
            self.current_screen = "console"
            self.set_status("Console mode. F1 to switch channels.")
        elif ch == curses.KEY_F4:
            self.current_screen = "config"
            self.set_status("Configuration mode.")
        elif ch == curses.KEY_F8:
            self._init_setup_wizard()
            self.current_screen = "setup"
        elif ch == curses.KEY_UP:
            if self.characteristics:
                self.selected_char_idx = max(0, self.selected_char_idx - 1)
        elif ch == curses.KEY_DOWN:
            if self.characteristics:
                self.selected_char_idx = min(len(self.characteristics) - 1, self.selected_char_idx + 1)
        elif ch == curses.KEY_F2:
            # Quick read
            if self.characteristics:
                char = self.characteristics[self.selected_char_idx]
                if char.can_read():
                    data = await self.read_characteristic(char)
                    if data:
                        hex_str = data.hex(" ")
                        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
                        self.set_status(f"Read: {hex_str} | {ascii_str}")
                else:
                    self.set_status("Characteristic not readable")
        elif ch in (curses.KEY_ENTER, 10, 13):
            if self.characteristics:
                self.interview_action_menu = True
                self.action_menu_idx = 0

    async def _handle_action_menu_keys(self, ch: int):
        if ch == 27:  # ESC
            self.interview_action_menu = False
            return
        elif ch == curses.KEY_UP:
            self.action_menu_idx = max(0, self.action_menu_idx - 1)
        elif ch == curses.KEY_DOWN:
            if hasattr(self, 'action_options'):
                self.action_menu_idx = min(len(self.action_options) - 1, self.action_menu_idx + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            await self._execute_action()
            self.interview_action_menu = False

    async def _execute_action(self):
        if not hasattr(self, 'action_options') or not self.characteristics:
            return
        
        char = self.characteristics[self.selected_char_idx]
        _, action = self.action_options[self.action_menu_idx]
        
        if action == "mod_tx":
            self.module_channel.tx_char = char
            self.set_status(f"Module TX = {char.char_name}")
        elif action == "mod_rx":
            self.module_channel.rx_char = char
            self.set_status(f"Module RX = {char.char_name}")
        elif action == "host_tx":
            self.host_channel.tx_char = char
            self.set_status(f"Host TX = {char.char_name}")
        elif action == "host_rx":
            self.host_channel.rx_char = char
            self.set_status(f"Host RX = {char.char_name}")
        elif action == "read":
            data = await self.read_characteristic(char)
            if data:
                hex_str = data.hex(" ")
                ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
                self.set_status(f"Read: {hex_str} | {ascii_str}")
        elif action == "clear":
            # Clear this char from any assignments
            if self.module_channel.tx_char == char:
                self.module_channel.tx_char = None
            if self.module_channel.rx_char == char:
                self.module_channel.rx_char = None
            if self.host_channel.tx_char == char:
                self.host_channel.tx_char = None
            if self.host_channel.rx_char == char:
                self.host_channel.rx_char = None
            self.set_status("Assignments cleared")

    async def handle_config_keys(self, ch: int):
        if self.config_editing:
            await self._handle_config_edit_keys(ch)
            return

        if ch == curses.KEY_F10:
            raise SystemExit
        elif ch == curses.KEY_F9:
            await self.disconnect()
            self.current_screen = "devices"
            self.set_status("Disconnected.")
        elif ch == curses.KEY_F2:
            self.current_screen = "interview"
            self.set_status("Interview mode.")
        elif ch == curses.KEY_F3:
            self.current_screen = "console"
            self.set_status("Console mode.")
        elif ch == curses.KEY_F5:
            # Toggle AT command mode
            if self.at_mode_enabled:
                await self.exit_at_mode()
            else:
                await self.enter_at_mode()
        elif ch == curses.KEY_F6:
            await self.reset_device()
        elif ch == curses.KEY_F7:
            await self.factory_reset()
        elif ch == curses.KEY_F8:
            self._init_setup_wizard()
            self.current_screen = "setup"
        elif ch == curses.KEY_UP:
            self.config_menu_idx = max(0, self.config_menu_idx - 1)
        elif ch == curses.KEY_DOWN:
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
            self._cycle_mode()
            self.config_editing = False
        elif self.config_menu_idx == 2:
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
        asyncio.create_task(self.set_mode(modes[(idx + 1) % len(modes)]))

    def _cycle_baud(self):
        bauds = list(BaudRate)
        idx = bauds.index(self.config.baud_rate)
        asyncio.create_task(self.set_baud_rate(bauds[(idx + 1) % len(bauds)]))

    async def _apply_config_edit(self):
        self.config_editing = False
        value = self.config_edit_value.strip()
        
        if self.config_menu_idx == 0 and value:
            await self.set_device_name(value)
        elif self.config_menu_idx == 4 and value:
            await self.set_pin(value)
        
        self.config_edit_value = ""

    # -------------------------------------------------------------------------
    # Setup Wizard (Configure new module via passthrough)
    # -------------------------------------------------------------------------

    def _init_setup_wizard(self):
        """Initialize the setup wizard state"""
        self.setup_step = 0  # 0=configure, 1=running, 2=done
        self.setup_field_idx = 0
        self.setup_editing = False
        self.setup_edit_value = ""
        self.setup_name = "NewDevice"
        self.setup_baud = BaudRate.B9600
        self.setup_running = False
        self.setup_log = deque(maxlen=20)
        self.set_status("Setup wizard: Configure new module via passthrough serial")

    def draw_setup_screen(self):
        """Draw the setup wizard screen"""
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.clear()

        title = "Setup New Module (via Passthrough)"
        self.safe_addstr(0, 0, title, curses.A_BOLD)
        
        if self.setup_step == 0:
            # Configuration step
            help_line = "[↑↓]nav [Enter]edit/cycle [F5]run setup [Esc]cancel [F10]quit"
            self.safe_addstr(1, 0, help_line, curses.A_DIM)
            
            row = 3
            self.safe_addstr(row, 0, "This wizard sends AT commands through the connected", curses.A_DIM)
            row += 1
            self.safe_addstr(row, 0, "module to configure another module on its serial port.", curses.A_DIM)
            row += 2
            
            # Show TX channel being used
            tx_name = self.module_channel.tx_char.char_name if self.module_channel.tx_char else "NOT ASSIGNED"
            rx_name = self.module_channel.rx_char.char_name if self.module_channel.rx_char else "NOT ASSIGNED"
            self.safe_addstr(row, 0, f"TX via: {tx_name}  |  RX via: {rx_name}")
            row += 2
            
            self.safe_addstr(row, 0, "─" * min(50, self.width - 1))
            row += 1
            self.safe_addstr(row, 0, "New Module Settings:", curses.A_BOLD)
            row += 1
            
            fields = [
                ("Device Name", self.setup_name),
                ("Baud Rate", self.setup_baud.value),
                ("Mode", "Peripheral (fixed)"),
            ]
            
            for idx, (label, value) in enumerate(fields):
                prefix = ">" if idx == self.setup_field_idx else " "
                
                if self.setup_editing and idx == self.setup_field_idx:
                    line = f"{prefix} {label}: {self.setup_edit_value}_"
                    attr = curses.A_BOLD
                else:
                    line = f"{prefix} {label}: {value}"
                    attr = curses.A_REVERSE if idx == self.setup_field_idx else curses.A_NORMAL
                
                self.safe_addstr(row, 0, line, attr)
                row += 1
            
            row += 1
            self.safe_addstr(row, 0, "─" * min(50, self.width - 1))
            row += 1
            self.safe_addstr(row, 0, "Commands that will be sent:", curses.A_BOLD)
            row += 1
            
            baud_code = {"9600": "0", "19200": "1", "38400": "2", "57600": "3", "115200": "4"}.get(self.setup_baud.value, "0")
            commands = [
                f"AT+NAME{self.setup_name}",
                f"AT+BAUD{baud_code}",
                "AT+APPAT=1  (enable BLE AT commands)",
                "AT+RESET    (save & restart)",
            ]
            for cmd in commands:
                self.safe_addstr(row, 0, f"  • {cmd}", curses.A_DIM)
                row += 1
            
            row += 1
            note_color = curses.color_pair(3) if curses.has_colors() else curses.A_DIM
            self.safe_addstr(row, 0, "Note: Settings are saved on RESET (no separate save cmd)", note_color)
                
        elif self.setup_step == 1:
            # Running step
            help_line = "Running setup... please wait"
            self.safe_addstr(1, 0, help_line, curses.A_DIM)
            
            row = 3
            self.safe_addstr(row, 0, "Sending AT commands to target module...", curses.A_BOLD)
            row += 2
            
            # Show log
            for line in self.setup_log:
                if row >= self.height - 2:
                    break
                color = curses.A_NORMAL
                if line.startswith("TX:"):
                    color = curses.color_pair(1) if curses.has_colors() else curses.A_BOLD
                elif line.startswith("RX:"):
                    color = curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL
                elif line.startswith("OK") or line.startswith("✓"):
                    color = curses.color_pair(1) if curses.has_colors() else curses.A_BOLD
                elif line.startswith("ERR") or line.startswith("✗"):
                    color = curses.color_pair(4) if curses.has_colors() else curses.A_BOLD
                self.safe_addstr(row, 0, line, color)
                row += 1
                
        elif self.setup_step == 2:
            # Done step
            help_line = "[Enter]return to console [F10]quit"
            self.safe_addstr(1, 0, help_line, curses.A_DIM)
            
            row = 3
            self.safe_addstr(row, 0, "Setup Complete!", curses.A_BOLD)
            row += 2
            
            # Show log
            for line in self.setup_log:
                if row >= self.height - 2:
                    break
                color = curses.A_NORMAL
                if "✓" in line:
                    color = curses.color_pair(1) if curses.has_colors() else curses.A_BOLD
                elif "✗" in line:
                    color = curses.color_pair(4) if curses.has_colors() else curses.A_BOLD
                self.safe_addstr(row, 0, line, color)
                row += 1
            
            row += 1
            self.safe_addstr(row, 0, "The target module should now restart with new settings.")
            row += 1
            self.safe_addstr(row, 0, "You can scan for it with its new name after a few seconds.")

        self.draw_status_bar()
        self.stdscr.refresh()

    async def handle_setup_keys(self, ch: int):
        """Handle keys in setup wizard"""
        if self.setup_step == 0:
            # Configuration step
            if self.setup_editing:
                if ch == 27:  # ESC
                    self.setup_editing = False
                    self.setup_edit_value = ""
                elif ch in (curses.KEY_ENTER, 10, 13):
                    # Apply edit
                    if self.setup_field_idx == 0 and self.setup_edit_value.strip():
                        self.setup_name = self.setup_edit_value.strip()[:20]  # Max 20 chars
                    self.setup_editing = False
                    self.setup_edit_value = ""
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    self.setup_edit_value = self.setup_edit_value[:-1]
                elif 32 <= ch <= 126:
                    self.setup_edit_value += chr(ch)
            else:
                if ch == curses.KEY_F10:
                    raise SystemExit
                elif ch == 27:  # ESC - cancel
                    self.current_screen = "console"
                    self.set_status("Setup cancelled")
                elif ch == curses.KEY_UP:
                    self.setup_field_idx = max(0, self.setup_field_idx - 1)
                elif ch == curses.KEY_DOWN:
                    self.setup_field_idx = min(2, self.setup_field_idx + 1)
                elif ch in (curses.KEY_ENTER, 10, 13):
                    if self.setup_field_idx == 0:
                        # Edit name
                        self.setup_editing = True
                        self.setup_edit_value = self.setup_name
                    elif self.setup_field_idx == 1:
                        # Cycle baud rate
                        bauds = list(BaudRate)
                        idx = bauds.index(self.setup_baud)
                        self.setup_baud = bauds[(idx + 1) % len(bauds)]
                    # Field 2 (mode) is fixed to Peripheral
                elif ch == curses.KEY_F5:
                    # Run setup
                    await self._run_setup_wizard()
                    
        elif self.setup_step == 2:
            # Done step
            if ch == curses.KEY_F10:
                raise SystemExit
            elif ch in (curses.KEY_ENTER, 10, 13, 27):
                self.current_screen = "console"
                self.set_status("Setup complete. Scan for the new device.")

    async def _run_setup_wizard(self):
        """Execute the setup wizard commands"""
        if not self.client or not self.module_channel.tx_uuid:
            self.set_status("Error: No TX channel assigned!")
            return
        
        self.setup_step = 1
        self.setup_log.clear()
        
        # Calculate baud code
        baud_code = {"9600": "0", "19200": "1", "38400": "2", "57600": "3", "115200": "4"}.get(self.setup_baud.value, "0")
        
        # Commands to send (settings are stored immediately, RESET applies them)
        commands = [
            ("Set Name", f"AT+NAME{self.setup_name}"),
            ("Set Baud", f"AT+BAUD{baud_code}"),
            ("Enable APPAT", "AT+APPAT=1"),
            ("Save & Reset", "AT+RESET"),
        ]
        
        self.setup_log.append("Starting setup...")
        self.draw_setup_screen()
        await asyncio.sleep(0.1)
        
        for label, cmd in commands:
            self.setup_log.append(f"TX: {cmd}")
            self.draw_setup_screen()
            
            try:
                data = (cmd + "\r\n").encode("utf-8")
                await self.client.write_gatt_char(self.module_channel.tx_uuid, data)
                self.setup_log.append(f"  ✓ {label} sent")
            except Exception as e:
                self.setup_log.append(f"  ✗ {label} failed: {e}")
            
            self.draw_setup_screen()
            await asyncio.sleep(0.5)  # Give module time to process
        
        self.setup_log.append("")
        self.setup_log.append("─" * 30)
        self.setup_log.append("Setup commands sent!")
        self.setup_log.append(f"New name: {self.setup_name}")
        self.setup_log.append(f"Baud: {self.setup_baud.value}")
        self.setup_log.append("Mode: Peripheral")
        self.setup_log.append("APPAT: Enabled")
        
        self.setup_step = 2
        self.set_status("Setup complete!")

    async def handle_console_keys(self, ch: int):
        if ch == curses.KEY_F10:
            raise SystemExit
        elif ch == curses.KEY_F2:
            self.current_screen = "interview"
            self.clear_status()
        elif ch == curses.KEY_F4:
            self.current_screen = "config"
            self.clear_status()
        elif ch == curses.KEY_F8:
            self._init_setup_wizard()
            self.current_screen = "setup"
        elif ch == curses.KEY_F1:
            if self.active_channel == self.module_channel:
                self.active_channel = self.host_channel
                self.set_status("Switched to Host channel")
            else:
                self.active_channel = self.module_channel
                self.set_status("Switched to Module channel")
        elif ch == curses.KEY_F5:
            if self.input_mode == InputMode.ASCII:
                self.input_mode = InputMode.HEX
                self.set_status("Input mode: HEX")
            else:
                self.input_mode = InputMode.ASCII
                self.set_status("Input mode: ASCII")
        elif ch == curses.KEY_F6:
            await self.toggle_channel_notifications(self.module_channel)
        elif ch == curses.KEY_F7:
            await self.toggle_channel_notifications(self.host_channel)
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
            if self.current_screen == "devices":
                self.draw_devices_screen()
            elif self.current_screen == "interview":
                self.draw_interview_screen()
            elif self.current_screen == "config":
                self.draw_config_screen()
            elif self.current_screen == "console":
                self.draw_console_screen()
            elif self.current_screen == "setup":
                self.draw_setup_screen()

            try:
                ch = self.stdscr.getch()
            except curses.error:
                ch = -1

            if ch != -1:
                try:
                    if self.current_screen == "devices":
                        await self.handle_devices_keys(ch)
                    elif self.current_screen == "interview":
                        await self.handle_interview_keys(ch)
                    elif self.current_screen == "config":
                        await self.handle_config_keys(ch)
                    elif self.current_screen == "console":
                        await self.handle_console_keys(ch)
                    elif self.current_screen == "setup":
                        await self.handle_setup_keys(ch)
                except SystemExit:
                    break
                except Exception as e:
                    self.set_status(f"Error: {e}")

            await asyncio.sleep(0.05)

        await self.disconnect()


def main(stdscr):
    app = CP26TuiApp(stdscr)
    asyncio.run(app.run())


if __name__ == "__main__":
    curses.wrapper(main)
