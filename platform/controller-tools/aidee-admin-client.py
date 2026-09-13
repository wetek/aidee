#!/usr/bin/env python3
import argparse
import json
import socket
import sys
from pathlib import Path


MAX_RESPONSE_BYTES = 65536


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument(
        "--socket",
        type=Path,
        default=Path("/run/aidee/admin.sock"),
    )
    arguments = parser.parse_args()

    try:
        request = json.loads(arguments.request.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    message = json.dumps(request, separators=(",", ":")).encode()
    if len(message) > 65536:
        print("error: request exceeds size limit", file=sys.stderr)
        return 1

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(str(arguments.socket))
            connection.sendall(message)
            response = connection.recv(MAX_RESPONSE_BYTES + 1)
    except OSError as error:
        print(f"error: administration helper unavailable: {error}", file=sys.stderr)
        return 1

    if len(response) > MAX_RESPONSE_BYTES:
        print("error: administration response exceeds size limit", file=sys.stderr)
        return 1

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        print("error: administration helper returned invalid JSON", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
