from wifi_cut.scanner import calculate_cidr


def test_calculate_cidr_24():
    assert calculate_cidr("192.168.1.50", "255.255.255.0") == "192.168.1.0/24"


def test_calculate_cidr_16():
    assert calculate_cidr("10.0.5.100", "255.255.0.0") == "10.0.0.0/16"
