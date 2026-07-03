from core.net_utils import detect_lan_ip

def test_returns_ipv4_string():
    ip = detect_lan_ip()
    assert isinstance(ip, str)
    parts = ip.split(".")
    assert len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

def test_never_raises_and_is_nonempty():
    assert detect_lan_ip()  # non-empty, no exception
