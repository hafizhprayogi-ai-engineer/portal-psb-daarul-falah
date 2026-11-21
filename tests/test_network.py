from psb.network import local_address, resolve_base_url, resolve_listen


def test_auto_follows_changed_address(monkeypatch):
    monkeypatch.setattr(
        "psb.network.socket.gethostbyname_ex",
        lambda _: ("pc", [], ["169.254.1.2", "10.29.120.185"]),
    )
    assert resolve_listen("auto", 5000) == "127.0.0.1:5000 10.29.120.185:5000"
    assert resolve_base_url("auto", 5000) == "http://10.29.120.185:5000"


def test_no_network_keeps_loopback(monkeypatch):
    def unavailable(_):
        raise OSError("offline")

    monkeypatch.setattr("psb.network.socket.gethostbyname_ex", unavailable)
    assert local_address() == "127.0.0.1"
    assert resolve_listen("auto", 5000) == "127.0.0.1:5000"
    assert resolve_listen("", 5000) == "127.0.0.1:5000"
    assert resolve_listen("127.0.0.1:8000", 5000) == "127.0.0.1:8000"
    assert resolve_base_url("https://portal.example/", 5000) == "https://portal.example"
