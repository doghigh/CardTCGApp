"""Network helpers for LAN sync."""
import socket


def detect_lan_ip() -> str:
    """Return this machine's primary LAN IPv4 address, or '127.0.0.1' on failure.

    Uses the standard UDP-connect trick: connecting a datagram socket to a public
    address forces the OS to pick the outbound interface, whose address we read.
    No packets are actually sent.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
