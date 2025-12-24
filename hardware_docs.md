# DX-BT24 Bluetooth Module User Manual

**Product Name:** Bluetooth module  
**Model Name:** DX-BT24  
**Manufacturer:** SHEN ZHEN DX-SMART TECHNOLOGY CO., LTD  
**Website:** http://www.szdx-smart.com/  
**Phone:** 0755-29978125

---

## Table of Contents

1. [Overview](#1-overview)
2. [Module Default Parameters](#2-module-default-parameters)
3. [Application Area](#3-application-area)
4. [Power Consumption Parameters](#4-power-consumption-parameters)
5. [Radio Frequency Characteristics](#5-radio-frequency-characteristics)
6. [Transparent Transmission Parameters](#6-transparent-transmission-parameters)
7. [Module Pin Description and Minimum Circuit Diagram](#7-module-pin-description-and-minimum-circuit-diagram)
8. [Pin Function Description](#8-pin-function-description)
9. [Detailed Description of Function Pins](#9-detailed-description-of-function-pins)
10. [Dimensions](#10-dimensions)
11. [LAYOUT Precautions](#11-layout-precautions)
12. [AT Command](#12-at-command)
13. [Contact Us](#13-contact-us)

---

## 1. Overview

DX-BT24 5.1 Bluetooth module is built by Shenzhen DX-SMART Technology Co., Ltd. for intelligent wireless data transmission. It uses the British DAILOG 14531 chip, configures 256Kb space, and follows V5.1 BLE Bluetooth specification. Support AT command, users can change the serial port baud rate, device name, pairing password and other parameters as needed, flexible use.

This module supports UART interface and supports Bluetooth serial port transparent transmission. It has the advantages of low cost, small size, low power consumption, high sensitivity of sending and receiving, etc. It can realize its powerful functions with only a few peripheral components simple operation, high cost performance and technology leading edge.

---

## 2. Module Default Parameters

| Parameter                | Value                                                                                        |
| ------------------------ | -------------------------------------------------------------------------------------------- |
| Bluetooth Protocol       | Bluetooth Specification V5.1 BLE                                                             |
| Working Frequency        | 2.4GHz ISM band                                                                              |
| Communication Interface  | UART                                                                                         |
| Power Supply             | 3.3V                                                                                         |
| Communication Distance   | 80M (Open and unobstructed environment)                                                      |
| Physical Dimension       | 27(L)mm x 13(W)mm x 2(H)mm                                                                   |
| Bluetooth Authentication | FCC CE ROHS REACH                                                                            |
| Bluetooth Name           | BT24                                                                                         |
| Serial Port Parameters   | 9600, 8 data bits, 1 stop bit, No check, No flow control                                     |
| Service UUID             | FFE0                                                                                         |
| Notify\Write UUID        | FFE1                                                                                         |
| Write UUID               | FFE2                                                                                         |
| Work Temperature         | MIN: -40℃ - MAX: +85℃                                                                        |
| Customized Requirements  | If you have other special function requirements, you can contact us to customize the module. |

---

## 3. Application Area

DX-BT24 module supports BT5.1 BLE protocol, which can be directly connected to iOS devices that have BLE Bluetooth function, and supports background program resident operation.

**Successful applications of BT24 module:**

- Bluetooth wireless data transmission
- Mobile phones, computer peripherals
- Handheld POS device
- Medical equipment wireless data transmission
- Smart Home Control
- Automotive Inspection OBD Equipment
- Bluetooth printer
- Bluetooth remote control toy
- Anti-lost device, LED light control

---

## 4. Power Consumption Parameters

**Broadcast interval:** 540ms

| Mode                                                 | Status       | Current               | Unit    |
| ---------------------------------------------------- | ------------ | --------------------- | ------- |
| Low power mode                                       | Discoverable | 19                    | uA      |
| Low power mode                                       | Connected    | 341                   | uA      |
| Normal working mode                                  | Discoverable | 270                   | uA      |
| Normal working mode                                  | Connected    | 341                   | uA      |
| When transparently transmitting data (11520 Bytes/s) | Connected    | MIN: 341uA / MAX: 3.5 | uA / mA |

_MIN is the minimum amount of data, MAX is the power consumption at the maximum amount of data_

---

## 5. Radio Frequency Characteristics

| Rating             | Value        | Unit |
| ------------------ | ------------ | ---- |
| BLE Transmit Power | -19.5 ~ +2.5 | dBm  |
| BLE Sensitivity    | -94          | dBm  |

---

## 6. Transparent Transmission Parameters

### Data Throughput

**Note:** This table parameter is for reference only and does not represent the maximum data throughput that the module can support.

#### Android → BT24 → UART

| Parameter                  | Value                  |
| -------------------------- | ---------------------- |
| Baud rate                  | 115200                 |
| Connection interval (ms)   | 15                     |
| Serial packet size (bytes) | 230                    |
| Transmission interval (ms) | 20                     |
| Throughput (bytes/s)       | 10120                  |
| Characteristic             | Write without Response |

#### UART → BT24 → Android

| Parameter                  | Value  |
| -------------------------- | ------ |
| Baud rate                  | 115200 |
| Connection interval (ms)   | 15     |
| Serial packet size (bytes) | 320    |
| Transmission interval (ms) | 20     |
| Throughput (bytes/s)       | 10626  |
| Characteristic             | Notify |

#### iPhone 6 → BT24 → UART

| Parameter                  | Value                  |
| -------------------------- | ---------------------- |
| Baud rate                  | 115200                 |
| Connection interval (ms)   | 30                     |
| Serial packet size (bytes) | 140                    |
| Transmission interval (ms) | 20                     |
| Throughput (bytes/s)       | 5600                   |
| Characteristic             | Write without Response |

#### UART → BT24 → iPhone 6

| Parameter                  | Value  |
| -------------------------- | ------ |
| Baud rate                  | 115200 |
| Connection interval (ms)   | 30     |
| Serial packet size (bytes) | 180    |
| Transmission interval (ms) | 50     |
| Throughput (bytes/s)       | 3240   |
| Characteristic             | Notify |

---

## 7. Module Pin Description and Minimum Circuit Diagram

_[Circuit diagram would be included here if image data was available]_

---

## 8. Pin Function Description

| Pin Number | Pin Name | Pin Description                                                                                               |
| ---------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| 1          | P0_6     | Serial data output                                                                                            |
| 2          | P0_7     | Serial data input                                                                                             |
| 3          | NC       | NC                                                                                                            |
| 4          | NC       | NC                                                                                                            |
| 5          | NC       | NC                                                                                                            |
| 6          | NC       | NC                                                                                                            |
| 7          | SWDIO    | Debug data port                                                                                               |
| 8          | SWCLK    | Debug clock port                                                                                              |
| 9          | SWDIO    | Connected to pin 7, IO port can be customized                                                                 |
| 10         | SWCLK    | Connected to pin 8, IO port can be customized                                                                 |
| 11         | Reset    | Reset (Input 200ms low level pulse)                                                                           |
| 12         | VCC      | V3.3                                                                                                          |
| 13         | GND      | Land                                                                                                          |
| 14         | GND      | Land                                                                                                          |
| 15         | P0_9     | Disconnect pin (200ms low power pulse disconnection) / Low power mode wake up (200ms low power pulse wake up) |
| 16         | P0_8     | LED light pin (Not connected: 1s on, 1s off, connected: 3s on, 50ms off)                                      |
| 17         | P0_11    | Bluetooth connection indicator (not connected low, connection high)                                           |
| 18         | P0_1     | NC (Can only be left floating)                                                                                |
| 19         | P0_3     | NC (Can only be left floating)                                                                                |
| 20         | P0_4     | NC (Can only be left floating)                                                                                |
| 21         | P0_0     | Programmable input and output                                                                                 |
| 22         | NC       | NC                                                                                                            |
| 23         | P0_9     | Connected to pin 15, IO port can be customized                                                                |
| 24         | P0_8     | Connected to pin 16, IO port can be customized                                                                |
| 25         | P0_11    | Connected to pin 17, IO port can be customized                                                                |
| 26         | P0_11    | Connected to pin 17, IO port can be customized                                                                |

---

## 9. Detailed Description of Function Pins

### 1. Pin 16 (P0_8): LED Indicator Pin

Used to indicate the status of the Bluetooth module. The LED flashing mode corresponds to the status of the Bluetooth module:

| Module       | LED Display                                 | Module Status     |
| ------------ | ------------------------------------------- | ----------------- |
| Slave module | Flashes slowly and evenly (1s-on, 1s-off)   | Standby mode      |
| Slave module | Bright 3s Extinguish 50ms (3s-on, 50ms-off) | Connection Status |
| Slave module | Light off                                   | Low power mode    |

### 2. Pin 17 (P0_11): Connection Status Indication Pin

| Pin Status        | Module Status     |
| ----------------- | ----------------- |
| Output low        | Standby mode      |
| Output high level | Connection Status |

### 3. Pin 15 (P0_9): Connection Interruption Pin

_The module is in the connected state is valid_

| Pin Status                                  | Module Status                                                                                                                                                     |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No action                                   | Connection Status                                                                                                                                                 |
| Input 200ms low-level pulse from the module | The connection is interrupted and the module enters low power consumption mode (Enter the previously set working mode, if not set, it is the normal working mode) |

### 4. Pin 15 (P0_9): Low-Power Mode Wake-Up Pin

_The module is effective in low-power mode_

| Pin Status                                  | Module Status                                                    |
| ------------------------------------------- | ---------------------------------------------------------------- |
| No action                                   | Low power mode                                                   |
| Input 200ms low-level pulse from the module | Wake up from low power mode, the module enters the standby state |

### 5. Comparison of Low Power Mode and Normal Working Mode

| Feature      | Normal Working Mode             | Low Power Mode                                         |
| ------------ | ------------------------------- | ------------------------------------------------------ |
| AT command   | Send AT commands after power-on | P0_9: 200ms low power pulse wake up to send AT command |
| Light status | Even slow blinking              | Light is not on                                        |

---

## 10. Dimensions

_[Dimension diagram would be included here if image data was available]_

**Physical Dimension:** 27(L)mm x 13(W)mm x 2(H)mm

---

## 11. LAYOUT Precautions

The DX-BT24 Bluetooth module works in the 2.4G wireless band. It should try to avoid the influence of various factors on the wireless transceiver. Pay attention to the following points:

1. The product shell surrounding the Bluetooth module to avoid the use of metal. When using part of the metal shell, should try to make the module antenna part away from the metal part.

2. The internal metal connecting wires or metal screws of the product should be far away from the antenna part of the module.

3. The antenna part of the module should be placed around the PCB of the carrier board. It is not allowed to be placed in the board, and the carrier board under the antenna is slotted. The direction parallel to the antenna is not allowed to be copper or traced. It is also a good choice to directly expose the antenna part out of the carrier board.

4. It is recommended to use insulating material for isolation at the module mounting position on the substrate. For example, put a block of screen printing (TopOverLay) at this position.

**Recommended:** Proper antenna placement with clearance  
**Not Recommended:** Antenna blocked by PCB or metal

---

## 12. AT Command

**Note:** AT command mode when the module is not connected

### General Information

1. AT command, which belongs to the character line instruction, is parsed according to the line (that is, AT command must be returned by carriage return or `\r\n`, hexadecimal number is 0D0A)

2. The AT command supports case and the instruction prefix is `AT+`, which can be divided into parameter setting instructions and read instructions.

3. **Set instruction format:** `AT+<CMD><PARAM>`  
   Operation returns successfully: `+<CMD>=<PARAM>\r\n OK\r\n`  
   Failure does not return characters. In addition to the 9th and 10th settings, the other parameters need to be restarted after setting the parameters for the new parameters to take effect.

4. **Read instruction format:** `AT+<CMD>`  
   Operation succeeds: `+<CMD>=<PARAM>\r\n`  
   Failure does not return a return character.

### 12.1 Test Command

| Function          | Command  | Response | Description |
| ----------------- | -------- | -------- | ----------- |
| Test instructions | `AT\r\n` | `OK\r\n` | -           |

### 12.2 Get The Software Version

| Function             | Command          | Response                        | Description                         |
| -------------------- | ---------------- | ------------------------------- | ----------------------------------- |
| Query version number | `AT+VERSION\r\n` | `+VERSION=<version>\r\n OK\r\n` | `<version>` Software version number |

**Note:** The version will be different depending on different modules and customization requirements.

### 12.3 Query Module Bluetooth MAC

| Function                 | Command        | Response             | Description                                 |
| ------------------------ | -------------- | -------------------- | ------------------------------------------- |
| Query module MAC address | `AT+LADDR\r\n` | `+LADDR=<laddr>\r\n` | `<laddr>` Bluetooth 12-bit MAC Address Code |

### 12.4 Set/Query Device Name

| Function                      | Command             | Response              | Description                                                 |
| ----------------------------- | ------------------- | --------------------- | ----------------------------------------------------------- |
| Query module Bluetooth name   | `AT+NAME\r\n`       | `+NAME=<name>\r\n`    | `<name>` Bluetooth name, up to 20 bytes. Default name: BT24 |
| Set the module Bluetooth name | `AT+NAME<name>\r\n` | `+NAME=<name>\r\n OK` | -                                                           |

**Example:**

1. Send Settings:

   ```
   AT+NAME=DX-BT24\r\n
   ```

   Set module device name: "DX-BT24"

   Return:

   ```
   +NAME=DX-BT24\r\n
   OK\r\n
   ```

2. Send inquiry:
   ```
   AT+NAME\r\n
   ```
   Return:
   ```
   +NAME=DX-BT24\r\n
   ```

### 12.5 Settings\Query - Bluetooth Name Suffix MAC

| Function                        | Command               | Response                | Description                                                                                                                       |
| ------------------------------- | --------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Query Bluetooth name suffix MAC | `AT+NAMAC\r\n`        | `+NAMAC=<Param>\r\n`    | `<Param>` (0,1,2): 0: No MAC suffix after the name, 1: Open name suffix 12-digit MAC, 2: Open name suffix 6-digit MAC. Default: 0 |
| Set Bluetooth name suffix MAC   | `AT+NAMAC<Param>\r\n` | `+NAMAC=<Param>\r\n OK` | -                                                                                                                                 |

### 12.6 Set/Query - Serial Port Baud Rate

| Function            | Command             | Response                  | Description                                                                                                                    |
| ------------------- | ------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Query module baud   | `AT+BAUD\r\n`       | `+BAUD=<baud>\r\n`        | `<baud>` Baud rate corresponding serial number: 1:2400, 2:4800, 3:9600, 4:19200, 5:38400, 6:57600, 7:115200. Default: 3 (9600) |
| Set the module baud | `AT+BAUD<baud>\r\n` | `+BAUD=<baud>\r\n OK\r\n` | -                                                                                                                              |

**Note:** The module must be re-powered after setting the baud rate, enabling the new baud rate for data communication and AT command resolution.

**Example: Setting the Serial Port Baud Rate to 57600**

1. Send Settings:

   ```
   AT+BAUD6\r\n
   ```

   Return:

   ```
   +BAUD=6\r\n
   OK\r\n
   ```

2. Send inquiry:
   ```
   AT+BAUD?\r\n
   ```
   Return:
   ```
   +BAUD=6\r\n
   OK\r\n
   ```

### 12.7 Set/Query - Serial Port Stop Bit

| Function                          | Command              | Response               | Description                                                    |
| --------------------------------- | -------------------- | ---------------------- | -------------------------------------------------------------- |
| Query module serial port stop bit | `AT+STOP\r\n`        | `+STOP=<Param>\r\n`    | `<Param>` Stop bit: 0 - 1 Stop bit, 1 - 2 Stop bit. Default: 0 |
| Set module serial port stop bit   | `AT+STOP<Param>\r\n` | `+STOP=<Param>\r\n OK` | -                                                              |

### 12.8 Set/Query - Serial Parity Bit

| Function                         | Command              | Response               | Description                                                                      |
| -------------------------------- | -------------------- | ---------------------- | -------------------------------------------------------------------------------- |
| Query module serial parity bit   | `AT+PARI\r\n`        | `+PARI=<Param>\r\n`    | `<Param>` Check Digit: 0 - No check, 1 - Odd parity, 2 - Even parity. Default: 0 |
| Set the module serial parity bit | `AT+PARI<Param>\r\n` | `+PARI=<Param>\r\n OK` | -                                                                                |

### 12.9 Set/Query - Notify the Host Computer Connection Status

The connection success module returns `OK+CONN`

| Function     | Command              | Response               | Description                                                     |
| ------------ | -------------------- | ---------------------- | --------------------------------------------------------------- |
| Query status | `AT+NOTI\r\n`        | `+NOTI=<Param>\r\n`    | `<Param>` Check Digit: 0 - Not notified, 1 - Notice. Default: 0 |
| Set status   | `AT+NOTI<Param>\r\n` | `+NOTI=<Param>\r\n OK` | -                                                               |

### 12.10 Set/Query - Notification Connection with Address Code

The connection success module returns `OK+CONN0x112233445566`

| Function                                  | Command              | Response               | Description                                                     |
| ----------------------------------------- | -------------------- | ---------------------- | --------------------------------------------------------------- |
| Notification connection with address code | `AT+NOTP\r\n`        | `+NOTP=<Param>\r\n`    | `<Param>` Check Digit: 0 - Not notified, 1 - Notice. Default: 0 |
| Notification connection with address code | `AT+NOTP<Param>\r\n` | `+NOTP=<Param>\r\n OK` | -                                                               |

### 12.11 Settings\Query - SERVICE UUID

| Function           | Command                | Response                 | Description                                                                              |
| ------------------ | ---------------------- | ------------------------ | ---------------------------------------------------------------------------------------- |
| Query service UUID | `AT+UUID\r\n`          | `+UUID=<service>\r\n`    | `<service>` UUID. Default service UUID: FFE0 (This UUID is a 4-digit hexadecimal number) |
| Set service UUID   | `AT+UUID<service>\r\n` | `+UUID=<service>\r\n OK` | -                                                                                        |

**Example: Set the service UUID to FE00**

1. Send Settings:
   ```
   AT+UUID0XFF00\r\n
   ```
   Return:
   ```
   +UUID=0XFF00\r\n
   OK
   ```

### 12.12 Settings\Query - NOTIFY UUID\WRITE UUID

| Function                       | Command             | Response              | Description                                                                           |
| ------------------------------ | ------------------- | --------------------- | ------------------------------------------------------------------------------------- |
| Query module notify\write UUID | `AT+CHAR\r\n`       | `+CHAR=<UUID>\r\n`    | `<UUID>` notify\write UUID. Default: FFE1 (This UUID is a 4-digit hexadecimal number) |
| Set module notify\write UUID   | `AT+CHAR<UUID>\r\n` | `+CHAR=<UUID>\r\n OK` | -                                                                                     |

**Note:** This channel is a readable and writable channel (i.e., it can be read or written)

**Example: Set the notify\write UUID to FE01**

1. Send settings:
   ```
   AT+CHAR0XFE01\r\n
   ```
   Return:
   ```
   +CHAR=FE01\r\n
   OK\r\n
   ```

### 12.13 Settings\Query - WRITE UUID

| Function                | Command              | Response               | Description                                                                    |
| ----------------------- | -------------------- | ---------------------- | ------------------------------------------------------------------------------ |
| Query module write UUID | `AT+WRITE\r\n`       | `+WRITE=<UUID>\r\n`    | `<UUID>` write UUID. Default: FFE2 (This UUID is a 4-digit hexadecimal number) |
| Set module write UUID   | `AT+WRITE<UUID>\r\n` | `+WRITE=<UUID>\r\n OK` | -                                                                              |

### 12.14 Settings\Query - Low Power Mode

| Function                    | Command              | Response               | Description                                                      |
| --------------------------- | -------------------- | ---------------------- | ---------------------------------------------------------------- |
| Query module low power mode | `AT+PWRM\r\n`        | `+PWRM=<Param>\r\n`    | `<Param>` (0, 1): 0: Low power mode, 1: Working mode. Default: 1 |
| Set module low power mode   | `AT+PWRM<Param>\r\n` | `+PWRM=<Param>\r\n OK` | -                                                                |

### 12.15 Settings\Query - Broadcast Time Interval

| Function                      | Command              | Response               | Description                                                                                                                                                                                     |
| ----------------------------- | -------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Query Broadcast time interval | `AT+ADVI\r\n`        | `+ADVI=<Param>\r\n`    | Param: 0~F: 0—100ms, 1—152.5ms, 2—211.25ms, 3—318.75ms, 4—417.5ms, 5—546.25ms, 6—760ms, 7—852.5ms, 8—1022.5ms, 9—1285ms, A—2000ms, B—3000ms, C—4000ms, D—5000ms, E—6000ms, F—7000ms. Default: 5 |
| Set Broadcast time interval   | `AT+ADVI<Param>\r\n` | `+ADVI=<Param>\r\n OK` | -                                                                                                                                                                                               |

**Note:** This instruction can be used to reduce power consumption

### 12.16 Settings\Query - Module Transmit Power

| Function                    | Command             | Response                  | Description                                                                                                                                    |
| --------------------------- | ------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Query module transmit power | `AT+POWE\r\n`       | `+POWE=<POWE>\r\n`        | `<POWE>`: 1: -19.5 dB, 2: -13.5 dB, 3: -10dB, 4: -7dB, 5: -5dB, 6: -3.5dB, 7: -2dB, 8: -1dB, 9: 0dB, A: +1dB, B: +1.5dB, C: +2.5dB. Default: C |
| Set module transmit power   | `AT+POWE<POWE>\r\n` | `+POWE=<POWE>\r\n OK\r\n` | -                                                                                                                                              |

### 12.17 Settings\Query - APP AT Command

| Function              | Command               | Response                | Description                                                                      |
| --------------------- | --------------------- | ----------------------- | -------------------------------------------------------------------------------- |
| Query APP AT commands | `AT+APPAT\r\n`        | `+APPAT=<Param>\r\n`    | `<Param>` (0, 1, 2): 0: Close APP AT command, 1: Open APP AT command. Default: 0 |
| Set APP AT command    | `AT+APPAT<Param>\r\n` | `+APPAT=<Param>\r\n OK` | -                                                                                |

**Note:** This command opens the user to send AT commands with APP. (Note: APPAT command can only be enabled through UART; if you need to enter transparent transmission mode, you need to set to disable APP AT command.)

---

### Important: BLE AT Command Mode vs Passthrough Mode

**All BLE communication happens on a single characteristic: FFE1 (Notify+Write)**

The module operates in two modes:

1. **Passthrough Mode (Default, APPAT=0):**

   - All data written to FFE1 is passed through to the UART TX pin
   - All data received on the UART RX pin is notified on FFE1
   - AT commands are NOT processed - they pass through like any other data

2. **AT Command Mode (APPAT=1):**
   - Data written to FFE1 is interpreted as AT commands to the module itself
   - The module processes AT commands and returns responses on FFE1
   - UART passthrough is disabled while in this mode

**To configure the module over BLE:**

1. First enable AT mode: Send `AT+APPAT1\r\n` on FFE1
2. Send your AT commands (AT+NAME, AT+BAUD, etc.)
3. When done, disable AT mode: Send `AT+APPAT0\r\n` on FFE1
4. Module returns to passthrough mode

**Critical:** You must send `AT+APPAT0\r\n` after configuration to restore passthrough functionality. If you send `AT+RESET` while APPAT=1, the module will restart with APPAT still enabled (settings persist).

**FFE2 (Write-only characteristic):** This is an alternate write path that also goes to the same UART. It does NOT provide a separate AT command channel.

### 12.18 Settings\Query - Bluetooth Device Type

| Function                    | Command              | Response               | Description                                                                                                                                    |
| --------------------------- | -------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Query Bluetooth device type | `AT+TYPE\r\n`        | `+TYPE=<Param>\r\n`    | `<Param>`: 0x0000: No type specified, 0x0040: Phone type, 0x0080: Laptop type, 0x03c1: Keyboard type, 0x03c2: Mouse type, etc. Default: 0x0000 |
| Set Bluetooth device type   | `AT+TYPE<Param>\r\n` | `+TYPE=<Param>\r\n OK` | -                                                                                                                                              |

### 12.19 Software Restart

| Function         | Command        | Response | Description |
| ---------------- | -------------- | -------- | ----------- |
| Software restart | `AT+RESET\r\n` | `OK\r\n` | -           |

### 12.20 Restore Default Settings

| Function                 | Command          | Response | Description |
| ------------------------ | ---------------- | -------- | ----------- |
| Restore default settings | `AT+DEFAULT\r\n` | `OK\r\n` | -           |

---

## 13. Contact Us

**Shen Zhen DX-SMART Technology Co., Ltd.**

**Address:** 511, Building C, Yuxing Technology Park, Yuxing Chuanggu, Bao'an District, Shenzhen, China

**Tel:** 0755-2997 8125  
**Fax:** 0755-2997 8369  
**Website:** http://www.szdx-smart.com/

---

## FCC Statement

**FCC standards:** FCC CFR Title 47 Part 15 Subpart C Section 15.247  
**Integral antenna with antenna gain:** 2.5dBi

This device complies with part 15 of the FCC Rules. Operation is subject to the following two conditions:

1. This device may not cause harmful interference, and
2. This device must accept any interference received, including interference that may cause undesired operation.

Any changes or modifications not expressly approved by the party responsible for compliance could void the user's authority to operate the equipment.

**Note:** This equipment has been tested and found to comply with the limits for a Class B digital device, pursuant to part 15 of the FCC Rules. These limits are designed to provide reasonable protection against harmful interference in a residential installation. This equipment generates, uses and can radiate radio frequency energy and, if not installed and used in accordance with the instructions, may cause harmful interference to radio communications. However, there is no guarantee that interference will not occur in a particular installation. If this equipment does cause harmful interference to radio or television reception, which can be determined by turning the equipment off and on, the user is encouraged to try to correct the interference by one or more of the following measures:

- Reorient or relocate the receiving antenna.
- Increase the separation between the equipment and receiver.
- Connect the equipment into an outlet on a circuit different from that to which the receiver is connected.
- Consult the dealer or an experienced radio/TV technician for help.

### FCC Radiation Exposure Statement

This modular complies with FCC RF radiation exposure limits set forth for an uncontrolled environment.

If the FCC identification number is not visible when the module is installed inside another device, then the outside of the device into which the module is installed must also display a label referring to the enclosed module. This exterior label can use wording such as the following: "Contains Transmitter Module FCC ID: 2AKS8DX-BT24" or "Contains FCC ID: 2AKS8DX-BT24"

When the module is installed inside another device, the user manual of the host must contain below warning statements:

1. This device complies with Part 15 of the FCC Rules. Operation is subject to the following two conditions:
   - (1) This device may not cause harmful interference.
   - (2) This device must accept any interference received, including interference that may cause undesired operation.

**Note:** This equipment has been tested and found to comply with the limits for a Class B digital device, pursuant to part 15 of the FCC Rules. These limits are designed to provide reasonable protection against harmful interference in a residential installation. This equipment generates, uses and can radiate radio frequency energy and, if not installed and used in accordance with the instructions, may cause harmful interference to radio communications.

However, there is no guarantee that interference will not occur in a particular installation. If this equipment does cause harmful interference to radio or television reception, which can be determined by turning the equipment off and on, the user is encouraged to try to correct the interference by one or more of the following measures:

- Reorient or relocate the receiving antenna.
- Increase the separation between the equipment and receiver.
- Connect the equipment into an outlet on a circuit different from that to which the receiver is connected.
- Consult the dealer or an experienced radio/TV technician for help.

2. Changes or modifications not expressly approved by the party responsible for compliance could void the user's authority to operate the equipment.

The devices must be installed and used in strict accordance with the manufacturer's instructions as described in the user documentation that comes with the product.

Any company of the host device which install this modular with single modular approval should perform the test of radiated & conducted emission and spurious emission, etc. according to FCC part 15C: 15.247 and 15.209 & 15.207, 15B Class B requirement. Only if the test result comply with FCC part 15C: 15.247 and 15.209 & 15.207, 15B Class B requirement, then the host can be sold legally.
