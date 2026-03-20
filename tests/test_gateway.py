from wifi_cut.gateway import parse_route_output, parse_ipconfig_gateway


def test_parse_route_output():
    mock_output = """\
   route to: default
destination: default
       mask: default
    gateway: 192.168.1.1
  interface: en0
      flags: <UP,GATEWAY,DONE,STATIC,PRCLONING,AUTOCONF>
"""
    ip, iface = parse_route_output(mock_output)
    assert ip == "192.168.1.1"
    assert iface == "en0"


def test_parse_route_output_different_gateway():
    mock_output = """\
   route to: default
    gateway: 10.0.0.1
  interface: en1
"""
    ip, iface = parse_route_output(mock_output)
    assert ip == "10.0.0.1"
    assert iface == "en1"


def test_parse_ipconfig_gateway():
    mock_output = """\
Wireless LAN adapter Wi-Fi:

   Connection-specific DNS Suffix  . :
   IPv4 Address. . . . . . . . . . . : 192.168.50.100
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.50.1
"""
    assert parse_ipconfig_gateway(mock_output) == "192.168.50.1"


def test_parse_ipconfig_gateway_different():
    mock_output = """\
Ethernet adapter Ethernet:

   IPv4 Address. . . . . . . . . . . : 10.0.0.50
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 10.0.0.1
"""
    assert parse_ipconfig_gateway(mock_output) == "10.0.0.1"
