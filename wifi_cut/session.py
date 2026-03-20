import time

from wifi_cut.gateway import get_gateway_info, get_mac_by_ip, GatewayInfo
from wifi_cut.platform_check import (
    check_root,
    check_platform,
    get_ip_forwarding,
    set_ip_forwarding,
)
from wifi_cut.scanner import (
    get_local_ip_and_mask,
    calculate_cidr,
    scan_network,
    Device,
)
from wifi_cut.spoofer import ARPSpoofer
from wifi_cut.throttler import Throttler


class SessionManager:
    def __init__(self):
        self.gateway: GatewayInfo | None = None
        self.devices: list[Device] = []
        self.local_ip: str = ""
        self.cidr: str = ""
        self.blocked_ips: set[str] = set()
        self.throttled_ips: dict[str, str] = {}  # ip -> bandwidth
        self._spoofer: ARPSpoofer | None = None
        self._throttler: Throttler | None = None
        self._original_forwarding: bool | None = None
        self._start_time: float = time.time()
        self._interval: float = 1.5

    def initialize(self, interval: float = 1.5) -> None:
        check_root()
        check_platform()
        self._interval = interval
        self.gateway = get_gateway_info()
        local_ip, mask = get_local_ip_and_mask(self.gateway.interface)
        self.local_ip = local_ip
        self.cidr = calculate_cidr(local_ip, mask)
        self._original_forwarding = get_ip_forwarding()
        self._start_time = time.time()

    def scan(self, timeout: int = 3) -> list[Device]:
        assert self.gateway is not None
        self.devices = scan_network(self.cidr, self.gateway.interface, timeout=timeout)
        for d in self.devices:
            if d.ip == self.gateway.ip:
                d.is_gateway = True
        return self.devices

    def _ensure_spoofer(self) -> ARPSpoofer:
        assert self.gateway is not None
        if self._spoofer is None:
            self._spoofer = ARPSpoofer(self.gateway)
        return self._spoofer

    def cut(self, ips: list[str]) -> list[str]:
        """封鎖裝置，回傳成功封鎖的 IP 列表。"""
        assert self.gateway is not None
        set_ip_forwarding(False)

        spoofer = self._ensure_spoofer()
        added = []
        for ip in ips:
            if ip in self.blocked_ips:
                continue
            try:
                mac = self._resolve_mac(ip)
                device = Device(ip=ip, mac=mac)
                spoofer.add_target(device)
                self.blocked_ips.add(ip)
                added.append(ip)
            except RuntimeError as e:
                print(f"[!] Skip {ip}: {e}")

        if not spoofer._running and spoofer.targets:
            spoofer.start(interval=self._interval)

        return added

    def uncut(self, ips: list[str]) -> list[str]:
        """解除封鎖，回傳成功解除的 IP 列表。"""
        removed = []
        if self._spoofer is None:
            return removed
        for ip in ips:
            if ip not in self.blocked_ips:
                continue
            self._spoofer.remove_target(ip)
            self.blocked_ips.discard(ip)
            removed.append(ip)

        if not self.blocked_ips and not self.throttled_ips and self._spoofer:
            self._spoofer.stop()
            self._spoofer = None
            if self._original_forwarding is not None:
                set_ip_forwarding(self._original_forwarding)

        return removed

    def throttle(self, ips: list[str], bandwidth: str) -> list[str]:
        """限速裝置，回傳成功限速的 IP 列表。"""
        assert self.gateway is not None
        set_ip_forwarding(True)

        spoofer = self._ensure_spoofer()
        new_ips = []
        for ip in ips:
            if ip in self.throttled_ips:
                continue
            try:
                mac = self._resolve_mac(ip)
                device = Device(ip=ip, mac=mac)
                spoofer.add_target(device)
                self.throttled_ips[ip] = bandwidth
                new_ips.append(ip)
            except RuntimeError as e:
                print(f"[!] Skip {ip}: {e}")

        if not spoofer._running and spoofer.targets:
            spoofer.start(interval=self._interval)

        if new_ips:
            if self._throttler:
                self._throttler.stop()
            all_throttled = list(self.throttled_ips.keys())
            self._throttler = Throttler(targets=all_throttled, bandwidth=bandwidth)
            self._throttler.start()

        return new_ips

    def unthrottle(self, ips: list[str]) -> list[str]:
        """解除限速，回傳成功解除的 IP 列表。"""
        removed = []
        for ip in ips:
            if ip not in self.throttled_ips:
                continue
            self.throttled_ips.pop(ip)
            removed.append(ip)

        if removed and self._throttler:
            self._throttler.stop()
            self._throttler = None
            if self.throttled_ips:
                bw = next(iter(self.throttled_ips.values()))
                self._throttler = Throttler(
                    targets=list(self.throttled_ips.keys()), bandwidth=bw
                )
                self._throttler.start()

        if not self.blocked_ips and not self.throttled_ips:
            if self._spoofer:
                for ip in removed:
                    self._spoofer.remove_target(ip)
                if not self._spoofer.targets:
                    self._spoofer.stop()
                    self._spoofer = None
            if self._original_forwarding is not None:
                set_ip_forwarding(self._original_forwarding)

        return removed

    @property
    def packet_count(self) -> int:
        if self._spoofer:
            return self._spoofer.packet_count
        return 0

    @property
    def elapsed(self) -> int:
        return int(time.time() - self._start_time)

    def selectable_devices(self) -> list[Device]:
        assert self.gateway is not None
        return [
            d for d in self.devices
            if d.ip != self.gateway.ip and d.ip != self.local_ip
        ]

    def cleanup(self) -> None:
        if self._throttler:
            self._throttler.stop()
            self._throttler = None
        if self._spoofer:
            self._spoofer.stop()
            self._spoofer = None
        if self._original_forwarding is not None:
            set_ip_forwarding(self._original_forwarding)
        self.blocked_ips.clear()
        self.throttled_ips.clear()

    def _resolve_mac(self, ip: str) -> str:
        for d in self.devices:
            if d.ip == ip:
                return d.mac
        assert self.gateway is not None
        return get_mac_by_ip(ip, self.gateway.interface)
