import os
import re
import subprocess
import sys
import threading
import time


def parse_bandwidth(bw: str) -> int:
    """解析頻寬字串為 bytes/sec。支援格式: 10Kbit/s, 1Mbit/s, 500Kbps, 100KB/s."""
    bw = bw.strip().lower()
    match = re.match(r"(\d+(?:\.\d+)?)\s*(k|m|g)?(bit|bps|b|byte)?(?:/s)?$", bw)
    if not match:
        raise ValueError(f"無法解析頻寬格式: {bw}")

    value = float(match.group(1))
    prefix = match.group(2) or ""
    unit = match.group(3) or "bit"

    multiplier = {"": 1, "k": 1_000, "m": 1_000_000, "g": 1_000_000_000}
    bits = value * multiplier[prefix]

    if unit in ("bit", "bps"):
        return int(bits / 8)
    else:
        return int(bits)


class Throttler:
    """流量限速引擎，使用 macOS dummynet 或 Windows pydivert。"""

    def __init__(self, targets: list[str], bandwidth: str = "10Kbit/s"):
        self.targets = targets
        self.bandwidth = bandwidth
        self.pipe_base = 100
        self._active = False
        self._win_threads: list[threading.Thread] = []
        self._win_stop_event = threading.Event()

    def start(self) -> None:
        if sys.platform == "darwin":
            self._start_macos()
        elif sys.platform == "win32":
            self._start_windows()
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return
        if sys.platform == "darwin":
            self._stop_macos()
        elif sys.platform == "win32":
            self._stop_windows()
        self._active = False

    # ── macOS: dnctl + pfctl ──

    @staticmethod
    def _to_dnctl_bw(bw: str) -> str:
        """將頻寬字串轉為 dnctl 認得的格式（純數字 + bit/s）。
        macOS dnctl 不認得 K/M/G 前綴，需要展開為純數字。"""
        bps = parse_bandwidth(bw) * 8  # parse_bandwidth 回傳 bytes/sec
        return f"{bps}bit/s"

    def _start_macos(self) -> None:
        dnctl_bw = self._to_dnctl_bw(self.bandwidth)
        for i, ip in enumerate(self.targets):
            pipe_in = self.pipe_base + i * 2
            pipe_out = self.pipe_base + i * 2 + 1

            subprocess.run(
                ["dnctl", "pipe", str(pipe_in), "config", "bw", dnctl_bw],
                check=True
            )
            subprocess.run(
                ["dnctl", "pipe", str(pipe_out), "config", "bw", dnctl_bw],
                check=True
            )

        rules = self._build_pf_rules_macos()
        anchor_conf = "/tmp/wifi_cut_pf.conf"
        with open(anchor_conf, "w") as f:
            f.write(rules)

        # 讀取原始 pf.conf，注入 wifi_cut anchor 引用
        try:
            with open("/etc/pf.conf", "r") as f:
                original_pf = f.read()
        except FileNotFoundError:
            original_pf = ""

        main_conf = "/tmp/wifi_cut_main_pf.conf"
        with open(main_conf, "w") as f:
            f.write(original_pf.rstrip() + "\n")
            f.write('dummynet-anchor "wifi_cut"\n')
            f.write('anchor "wifi_cut"\n')

        # 載入含 anchor 引用的主規則
        subprocess.run(["pfctl", "-f", main_conf], capture_output=True)
        # 載入 anchor 內容
        subprocess.run(
            ["pfctl", "-a", "wifi_cut", "-f", anchor_conf],
            check=True, capture_output=True
        )
        subprocess.run(["pfctl", "-E"], capture_output=True)

        print(f"[*] macOS dummynet throttle active: {self.bandwidth}")

    def _build_pf_rules_macos(self) -> str:
        lines = []
        for i, ip in enumerate(self.targets):
            pipe_in = self.pipe_base + i * 2
            pipe_out = self.pipe_base + i * 2 + 1
            lines.append(f"dummynet in quick proto {{ tcp, udp }} from {ip} to any pipe {pipe_in}")
            lines.append(f"dummynet in quick proto {{ tcp, udp }} from any to {ip} pipe {pipe_out}")
        return "\n".join(lines) + "\n"

    def _stop_macos(self) -> None:
        subprocess.run(
            ["pfctl", "-a", "wifi_cut", "-F", "all"],
            capture_output=True
        )
        for i in range(len(self.targets)):
            pipe_in = self.pipe_base + i * 2
            pipe_out = self.pipe_base + i * 2 + 1
            subprocess.run(
                ["dnctl", "pipe", "delete", str(pipe_in)],
                capture_output=True
            )
            subprocess.run(
                ["dnctl", "pipe", "delete", str(pipe_out)],
                capture_output=True
            )
        # 還原原始 pf 規則（移除 wifi_cut anchor 引用）
        if os.path.exists("/etc/pf.conf"):
            subprocess.run(["pfctl", "-f", "/etc/pf.conf"], capture_output=True)
        print("[*] macOS dummynet throttle removed")

    # ── Windows: pydivert token bucket ──

    def _start_windows(self) -> None:
        try:
            import pydivert
        except ImportError:
            print("[!] pydivert 未安裝，無法在 Windows 上限速。")
            print("[!] 請執行: pip install pydivert")
            return

        bytes_per_sec = parse_bandwidth(self.bandwidth)
        self._win_stop_event.clear()

        for ip in self.targets:
            filt = f"ip.DstAddr == {ip} or ip.SrcAddr == {ip}"
            t = threading.Thread(
                target=self._win_throttle_loop,
                args=(filt, bytes_per_sec),
                daemon=True,
            )
            self._win_threads.append(t)
            t.start()

        print(f"[*] Windows pydivert throttle active: {self.bandwidth} ({bytes_per_sec} B/s)")

    def _win_throttle_loop(self, filt: str, bytes_per_sec: int) -> None:
        import pydivert

        tokens = float(bytes_per_sec)
        last_time = time.monotonic()

        with pydivert.WinDivert(filt) as w:
            while not self._win_stop_event.is_set():
                try:
                    packet = w.recv()
                except OSError:
                    break

                now = time.monotonic()
                elapsed = now - last_time
                tokens = min(bytes_per_sec, tokens + bytes_per_sec * elapsed)
                last_time = now

                pkt_len = len(packet.raw)
                if tokens >= pkt_len:
                    tokens -= pkt_len
                    w.send(packet)
                else:
                    wait = (pkt_len - tokens) / bytes_per_sec
                    if wait < 2.0:
                        time.sleep(wait)
                        tokens = 0
                        w.send(packet)

    def _stop_windows(self) -> None:
        self._win_stop_event.set()
        for t in self._win_threads:
            t.join(timeout=3)
        self._win_threads.clear()
        print("[*] Windows pydivert throttle removed")


def build_pf_rules(targets: list[str], pipe_num: int) -> str:
    """測試用輔助函式。"""
    lines = []
    for i, ip in enumerate(targets):
        p_in = pipe_num + i * 2
        p_out = pipe_num + i * 2 + 1
        lines.append(f"dummynet in quick proto {{ tcp, udp }} from {ip} to any pipe {p_in}")
        lines.append(f"dummynet in quick proto {{ tcp, udp }} from any to {ip} pipe {p_out}")
    return "\n".join(lines) + "\n"


def build_dnctl_cmds(pipe_num: int, bandwidth: str) -> list[list[str]]:
    """測試用輔助函式。"""
    return [
        ["dnctl", "pipe", str(pipe_num), "config", "bw", bandwidth],
        ["dnctl", "pipe", str(pipe_num + 1), "config", "bw", bandwidth],
    ]
