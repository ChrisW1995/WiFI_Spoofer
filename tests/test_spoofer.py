from unittest.mock import patch
from wifi_cut.spoofer import ARPSpoofer
from wifi_cut.gateway import GatewayInfo
from wifi_cut.scanner import Device


@patch("wifi_cut.spoofer.get_if_hwaddr", return_value="00:11:22:33:44:55")
def test_add_and_remove_target(mock_hwaddr):
    gw = GatewayInfo(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff", interface="en0")
    spoofer = ARPSpoofer(gw)
    dev = Device(ip="192.168.1.100", mac="11:22:33:44:55:66")
    spoofer.add_target(dev)
    assert "192.168.1.100" in spoofer.targets
    spoofer.remove_target("192.168.1.100")
    assert "192.168.1.100" not in spoofer.targets


@patch("wifi_cut.spoofer.get_if_hwaddr", return_value="00:11:22:33:44:55")
def test_cannot_target_gateway(mock_hwaddr):
    gw = GatewayInfo(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff", interface="en0")
    spoofer = ARPSpoofer(gw)
    dev = Device(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff")
    spoofer.add_target(dev)
    assert "192.168.1.1" not in spoofer.targets
