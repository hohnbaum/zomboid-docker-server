"""Small Source RCON client. Password stays in memory, never argv or logs."""
import socket
import struct
import re
from pzops.util import PZError


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise PZError("RCON_DISCONNECTED")
        data.extend(part)
    return bytes(data)


def packet(sock):
    length = struct.unpack("<i", read_exact(sock, 4))[0]
    if length < 10 or length > 1024 * 1024:
        raise PZError("RCON_PROTOCOL")
    body = read_exact(sock, length)
    if body[-2:] != b"\x00\x00":
        raise PZError("RCON_PROTOCOL")
    ident, kind = struct.unpack("<ii", body[:8])
    return ident, kind, body[8:-2].decode("utf-8", errors="replace")


def send(sock, ident, kind, text):
    body = struct.pack("<ii", ident, kind) + text.encode("utf-8") + b"\0\0"
    sock.sendall(struct.pack("<i", len(body)) + body)


def command(host, port, password, action, timeout=5):
    if action not in ("players", "save", "quit"):
        raise PZError("RCON_ACTION_NOT_ALLOWED")
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            send(sock, 10, 3, password)
            for _ in range(5):
                ident, kind, text = packet(sock)
                if ident == -1:
                    raise PZError("RCON_AUTH_FAILED")
                if ident == 10 and kind == 2:
                    break
            else:
                raise PZError("RCON_PROTOCOL")
            send(sock, 11, 2, action)
            if action == "quit":
                return ""
            for _ in range(5):
                ident, kind, text = packet(sock)
                if ident == 11:
                    return text
            raise PZError("RCON_PROTOCOL")
    except (OSError, ValueError, struct.error):
        raise PZError("RCON_UNAVAILABLE") from None


def parse_players(text):
    m = re.search(r"Players connected\s*\((\d+)\):", text)
    if not m:
        raise PZError("PLAYERS_UNKNOWN")
    return {"count": int(m[1]), "names": [m[1].strip() for m in
            re.finditer(r"^\s*-\s*(.+)$", text, re.M)]}
