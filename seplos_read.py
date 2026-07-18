#!/usr/bin/env python3
"""Seplos BMS 3.0 (Mason/10E) standalone reader — Modbus RTU, 19200 8N1, slave 0.

Works on macOS and Linux with any USB-RS485 adapter (pip install pyserial).

Usage:
    python3 seplos_read.py             # read once
    python3 seplos_read.py --watch     # live view every 2 s (Ctrl-C to quit)
"""
import glob
import struct
import sys
import time

import serial

SLAVE = 0
BAUD = 19200


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def read_regs(p, func, reg, cnt):
    f = bytes([SLAVE, func, reg >> 8, reg & 0xFF, cnt >> 8, cnt & 0xFF])
    c = crc16(f)
    p.reset_input_buffer()
    p.write(f + bytes([c & 0xFF, c >> 8]))
    time.sleep(0.3)
    rx = p.read(300)
    if len(rx) < 5 or rx[1] & 0x80:
        raise IOError(f"Error at register {reg:#06x}: {rx.hex() or 'no reply'}")
    n = rx[2]
    return rx[3:3 + n]


def kelvin(v):
    return v / 10 - 273.15


def dump(p):
    pia = read_regs(p, 4, 0x1000, 0x12)
    r = struct.unpack(">9h9H", pia[:36]) if len(pia) >= 36 else None
    volt = int.from_bytes(pia[0:2], "big") / 100
    curr = int.from_bytes(pia[2:4], "big", signed=True) / 100
    rest = int.from_bytes(pia[4:6], "big") / 100
    total = int.from_bytes(pia[6:8], "big") / 100
    soc = int.from_bytes(pia[10:12], "big") / 10
    soh = int.from_bytes(pia[12:14], "big") / 10
    cyc = int.from_bytes(pia[14:16], "big")

    pib = read_regs(p, 4, 0x1100, 0x1A)
    cells = [int.from_bytes(pib[i * 2:i * 2 + 2], "big") for i in range(16)]
    temps = [kelvin(int.from_bytes(pib[32 + i * 2:34 + i * 2], "big")) for i in range(4)]
    t_mos = kelvin(int.from_bytes(pib[48:50], "big"))
    t_env = kelvin(int.from_bytes(pib[50:52], "big"))

    pic = read_regs(p, 1, 0x1200, 0x90)

    print(f"Pack:   {volt:.2f} V  {curr:+.2f} A  SOC {soc:.1f} %  SOH {soh:.1f} %  Cycles {cyc}")
    print(f"Cap:    {rest:.2f} / {total:.2f} Ah")
    print(f"Cells:  {min(cells)}–{max(cells)} mV  (delta {max(cells) - min(cells)} mV)")
    print(f"        {cells}")
    print(f"Temp:   cells {['%.1f' % t for t in temps]} °C  MOSFET {t_mos:.1f} °C  ambient {t_env:.1f} °C")
    state = pic[15] if len(pic) > 15 else None
    if state is not None:
        print(f"Status: Byte15=0x{state:02X}  Discharge-FET={'ON' if state & 1 else 'OFF'}  "
              f"Charge-FET={'ON' if state & 2 else 'OFF'}  (Bit6={'1' if state & 0x40 else '0'})")
    alarm_bytes = pic[:15]
    set_bits = [(i * 8 + b) for i, byte in enumerate(alarm_bytes) for b in range(8) if byte >> b & 1]
    print(f"Alarm/status bits (coil offsets): {set_bits or 'none'}")


def main():
    ports = sorted(glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/ttyUSB*"))
    if not ports:
        sys.exit("No USB-RS485 adapter found")
    with serial.Serial(ports[0], BAUD, timeout=0.6) as p:
        if "--watch" in sys.argv:
            while True:
                print("\x1b[2J\x1b[H" + time.strftime("%H:%M:%S"))
                dump(p)
                time.sleep(2)
        else:
            dump(p)


if __name__ == "__main__":
    main()
