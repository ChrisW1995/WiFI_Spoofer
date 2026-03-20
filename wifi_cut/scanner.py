import ipaddress
import socket
import subprocess
import sys
import re
from dataclasses import dataclass
from typing import Optional

from scapy.all import Ether, ARP, srp


@dataclass
class Device:
    ip: str
    mac: str
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    is_gateway: bool = False


def calculate_cidr(ip: str, mask: str) -> str:
    network = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
    return str(network)


def get_local_ip_and_mask(interface: str) -> tuple[str, str]:
    """取得本機 IP 和子網路遮罩（跨平台）。"""
    if sys.platform == "win32":
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True
        )
        ip_match = re.search(r"IPv4 Address[.\s]*:\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
        mask_match = re.search(r"Subnet Mask[.\s]*:\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
        if not ip_match or not mask_match:
            raise RuntimeError("無法從 ipconfig 取得 IP 資訊")
        return ip_match.group(1), mask_match.group(1)
    else:
        result = subprocess.run(
            ["ifconfig", interface], capture_output=True, text=True
        )
        ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
        mask_match = re.search(r"netmask\s+(0x[0-9a-f]+)", result.stdout)
        if not ip_match or not mask_match:
            raise RuntimeError(f"無法從 {interface} 取得 IP 資訊")

        ip = ip_match.group(1)
        hex_mask = int(mask_match.group(1), 16)
        mask = str(ipaddress.IPv4Address(hex_mask))
        return ip, mask


def resolve_hostname(ip: str) -> Optional[str]:
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return None


def scan_network(cidr: str, interface: str, timeout: int = 3) -> list[Device]:
    """ARP 掃描子網路，回傳所有活躍裝置。"""
    ans, _ = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=cidr),
        iface=interface, timeout=timeout, verbose=False
    )

    devices = []
    for sent, received in ans:
        ip = received.psrc
        mac = received.hwsrc
        hostname = resolve_hostname(ip)
        devices.append(Device(ip=ip, mac=mac, hostname=hostname))

    devices.sort(key=lambda d: ipaddress.IPv4Address(d.ip))
    return devices
