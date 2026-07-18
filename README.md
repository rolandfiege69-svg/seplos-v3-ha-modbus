# Seplos BMS 3.0 → Home Assistant via plain Modbus YAML

Read a **Seplos BMS 3.0** (Mason / 10E series, 48 V 16S LiFePO₄ packs) directly in
**Home Assistant with nothing but the built-in `modbus` integration** — no custom
component, no ESP hardware, no MQTT bridge, no Windows software.

Plug a USB-RS485 adapter into your HA machine, paste one YAML block, restart. Done:
28 entities including all 16 cell voltages, FET states and protection status.

> Verified on a Seplos Mason 280 (10E BMS, BMS 3.0 firmware, 314 Ah cells) with
> Home Assistant OS on a Raspberry Pi, HA Core 2026.7.

## Why this repo?

Existing solutions are great but heavier:

| Project | Approach |
|---|---|
| [flip555/bms_connector](https://github.com/flip555/bms_connector) | HACS custom component |
| [syssi/esphome-seplos-bms](https://github.com/syssi/esphome-seplos-bms) | extra ESP32 hardware |
| [byte4geek/SEPLOS_MQTT](https://github.com/byte4geek/SEPLOS_MQTT) | shell script + MQTT |
| **this repo** | **pure `configuration.yaml`, zero dependencies** |

## Hardware

- Seplos USB-RS485 adapter (FTDI FT232R inside) — the one shipped with the battery
  works out of the box. Any RS485 stick with A/B terminals works too.
- RJ45 into the BMS port labelled **RS485-1** (RS485-2 is for pack daisy-chaining,
  CAN is for your inverter — leave it alone; both work in parallel with this).
- RJ45 pinout (both RS485 ports): **pin 1 = B−, pin 2 = A+, pins 3/6 = GND**
  (T568B colors: white-orange = B−, orange = A+).

## Protocol facts (the hard-won part)

- **Modbus RTU, 19200 baud, 8N1.**
- BMS 3.0 firmware does **not** speak the old Seplos ASCII/telnet protocol
  (`~2000...` frames) on this port — it silently ignores those frames. If your pack
  ignores ASCII telegrams, it is a V3: use Modbus.
- **Slave address = DIP switch address.** With all DIP switches OFF the pack
  answers on address **0** — yes, that is the Modbus broadcast address, and yes,
  it still answers, both to pymodbus (Home Assistant) and to raw serial frames.
  If your DIP is set to 1, use `slave: 1`, etc.
- Register map (function code 0x04, input registers):

| Address (hex/dec) | Content | Unit/scale |
|---|---|---|
| 0x1000 / 4096 | pack voltage | 0.01 V |
| 0x1001 / 4097 | current (signed, + = charge) | 0.01 A |
| 0x1002 / 4098 | remaining capacity | 0.01 Ah |
| 0x1003 / 4099 | total capacity | 0.01 Ah |
| 0x1005 / 4101 | SOC | 0.1 % |
| 0x1006 / 4102 | SOH | 0.1 % |
| 0x1007 / 4103 | cycle count | 1 |
| 0x1100–0x110F / 4352–4367 | cell voltages 1–16 | 1 mV |
| 0x1110–0x1113 / 4368–4371 | cell temperature sensors 1–4 | 0.1 K |
| 0x1118 / 4376 | MOSFET temperature | 0.1 K |
| 0x1119 / 4377 | environment temperature | 0.1 K |

- Status bits (function code 0x01, coils, base 0x1200 / 4608):

| Coil (hex/dec) | Meaning |
|---|---|
| 0x1240 / 4672 | discharging |
| 0x1241 / 4673 | charging |
| 0x1244 / 4676 | idle |
| 0x1278 / 4728 | **discharge FET on** |
| 0x1279 / 4729 | **charge FET on** |

## Install

1. Plug the adapter into your HA machine. Find its stable path under
   **Settings → System → Hardware → All Hardware** (search "FTDI" / "ttyUSB"),
   e.g. `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_XXXXXXXX-if00-port0`.
2. Copy the contents of [`seplos_modbus.yaml`](seplos_modbus.yaml) into your
   `configuration.yaml` (top level). Adjust `port:` and, if needed, `slave:`.
3. **Developer tools → YAML → Check configuration** → restart Home Assistant.
4. Filter entities for `seplos` — you should see 28 of them with live values.

## Troubleshooting

- **No serial port appears (macOS):** System Settings → Privacy & Security →
  "Allow accessories to connect" blocks unknown USB devices. Allow + replug.
- **BMS stays silent:** check baud (19200), try slave 0 *and* 1, swap A/B wires,
  make sure the RJ45 is in RS485-1 on the BMS module itself, wake the BMS
  (front panel button) if the pack went to sleep after a protection event.
- **Only ever one master on the bus** — don't run a second reader on the same
  adapter while HA is polling.

## Bonus: standalone diagnostic script

[`seplos_read.py`](seplos_read.py) reads the same data from any laptop
(macOS/Linux, `pip install pyserial`) — handy for bench diagnosis without HA:

```
$ python3 seplos_read.py
Pack:   53.30 V  +0.00 A  SOC 96.3 %  SOH 99.8 %  Cycles 19
Cells:  3330–3333 mV  (delta 3 mV)
Status: Discharge-FET=ON  Charge-FET=ON
```

## License

MIT
