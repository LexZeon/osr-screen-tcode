from __future__ import annotations

import argparse
import sys
import time

from .sinks import SerialSink, choose_best_serial_port, list_serial_ports
from .tcode import TCodeMapper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a safe narrow TCode test pattern.")
    parser.add_argument("--port", default="", help="Serial port, for example COMx. If omitted, the best detected USB serial port is used.")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--min", type=int, default=4700)
    parser.add_argument("--max", type=int, default=5300)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--list", action="store_true", help="List serial ports and exit")
    args = parser.parse_args(argv)

    if args.list:
        for port in list_serial_ports():
            print(port)
        return 0

    port_name = args.port or choose_best_serial_port(list_serial_ports())
    if not port_name:
        print("No serial port found. Connect the device or pass --port COMx.", file=sys.stderr)
        return 2

    mapper = TCodeMapper("L0", args.min, args.max, False, 280)
    sink = SerialSink(port_name, args.baudrate)
    sink.open()
    try:
        sequence = [0.5, 0.42, 0.58, 0.5]
        for _ in range(max(1, args.cycles)):
            for position in sequence:
                command = mapper.map_position(position)
                payload = command.encode()
                sink.write(payload)
                print(payload.decode("ascii").strip())
                time.sleep(0.34)
    finally:
        sink.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
