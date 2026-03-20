import atexit
import signal
import sys
import time

from rich.console import Console
from rich.live import Live
from InquirerPy import inquirer

from wifi_cut.session import SessionManager
from wifi_cut.ui_helpers import make_device_table, make_status_panel, format_device_choice

console = Console()

MENU_SCAN = "Scan Network          掃描網路"
MENU_VIEW = "View Devices          查看裝置"
MENU_CUT = "Block Devices         封鎖裝置"
MENU_UNCUT = "Unblock Devices       解除封鎖"
MENU_THROTTLE = "Throttle Devices      限速裝置"
MENU_UNTHROTTLE = "Unthrottle Devices    解除限速"
MENU_STATUS = "Status Dashboard      狀態面板"
MENU_QUIT = "Quit                  離開"


def run_tui(timeout: int = 3, interval: float = 1.5) -> None:
    session = SessionManager()

    console.print("[bold cyan]wifi-cut[/bold cyan] Interactive Mode\n")

    try:
        session.initialize(interval=interval)
    except (RuntimeError, SystemExit) as e:
        console.print(f"[red]初始化失敗: {e}[/red]")
        return

    assert session.gateway is not None
    console.print(f"[dim]Gateway:[/dim] {session.gateway.ip} ({session.gateway.mac})")
    console.print(f"[dim]Network:[/dim] {session.cidr}")
    console.print(f"[dim]Local IP:[/dim] {session.local_ip}\n")

    def cleanup(*_args):
        console.print("\n[yellow]正在清理...[/yellow]")
        session.cleanup()
        console.print("[green]已還原所有設定。[/green]")

    atexit.register(cleanup)

    try:
        _main_loop(session, timeout)
    except KeyboardInterrupt:
        pass
    finally:
        atexit.unregister(cleanup)
        cleanup()


def _main_loop(session: SessionManager, timeout: int) -> None:
    while True:
        try:
            action = inquirer.select(
                message="wifi-cut",
                choices=[
                    MENU_SCAN,
                    MENU_VIEW,
                    MENU_CUT,
                    MENU_UNCUT,
                    MENU_THROTTLE,
                    MENU_UNTHROTTLE,
                    MENU_STATUS,
                    MENU_QUIT,
                ],
                default=MENU_SCAN,
            ).execute()
        except KeyboardInterrupt:
            return

        if action == MENU_SCAN:
            _handle_scan(session, timeout)
        elif action == MENU_VIEW:
            _handle_view(session)
        elif action == MENU_CUT:
            _handle_cut(session, timeout)
        elif action == MENU_UNCUT:
            _handle_uncut(session)
        elif action == MENU_THROTTLE:
            _handle_throttle(session, timeout)
        elif action == MENU_UNTHROTTLE:
            _handle_unthrottle(session)
        elif action == MENU_STATUS:
            _handle_status(session)
        elif action == MENU_QUIT:
            return

        console.print()


def _handle_scan(session: SessionManager, timeout: int) -> None:
    assert session.gateway is not None
    console.print(f"[dim]掃描 {session.cidr} ...[/dim]")
    devices = session.scan(timeout=timeout)
    table = make_device_table(
        devices, session.gateway.ip, session.local_ip,
        session.blocked_ips, session.throttled_ips,
    )
    console.print(table)
    console.print(f"找到 {len(devices)} 個裝置")


def _handle_view(session: SessionManager) -> None:
    assert session.gateway is not None
    if not session.devices:
        console.print("[yellow]尚未掃描，請先掃描網路。[/yellow]")
        return
    table = make_device_table(
        session.devices, session.gateway.ip, session.local_ip,
        session.blocked_ips, session.throttled_ips,
    )
    console.print(table)


def _handle_cut(session: SessionManager, timeout: int) -> None:
    assert session.gateway is not None
    if not session.devices:
        console.print("[dim]自動掃描中...[/dim]")
        session.scan(timeout=timeout)

    selectable = [
        d for d in session.selectable_devices()
        if d.ip not in session.blocked_ips
    ]
    if not selectable:
        console.print("[yellow]沒有可封鎖的裝置。[/yellow]")
        return

    choices = [
        {"name": format_device_choice(d, session.gateway.ip), "value": d.ip}
        for d in selectable
    ]

    try:
        selected = inquirer.checkbox(
            message="選擇要封鎖的裝置",
            choices=choices,
        ).execute()
    except KeyboardInterrupt:
        return

    if not selected:
        console.print("[dim]未選擇任何裝置。[/dim]")
        return

    added = session.cut(selected)
    for ip in added:
        console.print(f"[red]已封鎖:[/red] {ip}")


def _handle_uncut(session: SessionManager) -> None:
    if not session.blocked_ips:
        console.print("[yellow]目前沒有封鎖中的裝置。[/yellow]")
        return

    choices = [{"name": ip, "value": ip} for ip in sorted(session.blocked_ips)]

    try:
        selected = inquirer.checkbox(
            message="選擇要解除封鎖的裝置",
            choices=choices,
        ).execute()
    except KeyboardInterrupt:
        return

    if not selected:
        return

    removed = session.uncut(selected)
    for ip in removed:
        console.print(f"[green]已解除封鎖:[/green] {ip}")


def _handle_throttle(session: SessionManager, timeout: int) -> None:
    assert session.gateway is not None
    if not session.devices:
        console.print("[dim]自動掃描中...[/dim]")
        session.scan(timeout=timeout)

    selectable = [
        d for d in session.selectable_devices()
        if d.ip not in session.throttled_ips
    ]
    if not selectable:
        console.print("[yellow]沒有可限速的裝置。[/yellow]")
        return

    choices = [
        {"name": format_device_choice(d, session.gateway.ip), "value": d.ip}
        for d in selectable
    ]

    try:
        selected = inquirer.checkbox(
            message="選擇要限速的裝置",
            choices=choices,
        ).execute()
    except KeyboardInterrupt:
        return

    if not selected:
        console.print("[dim]未選擇任何裝置。[/dim]")
        return

    try:
        bw = inquirer.text(
            message="頻寬限制 (例: 100Kbit/s, 1Mbit/s)",
            default="100Kbit/s",
        ).execute()
    except KeyboardInterrupt:
        return

    added = session.throttle(selected, bw)
    for ip in added:
        console.print(f"[yellow]已限速:[/yellow] {ip} @ {bw}")


def _handle_unthrottle(session: SessionManager) -> None:
    if not session.throttled_ips:
        console.print("[yellow]目前沒有限速中的裝置。[/yellow]")
        return

    choices = [
        {"name": f"{ip} ({bw})", "value": ip}
        for ip, bw in sorted(session.throttled_ips.items())
    ]

    try:
        selected = inquirer.checkbox(
            message="選擇要解除限速的裝置",
            choices=choices,
        ).execute()
    except KeyboardInterrupt:
        return

    if not selected:
        return

    removed = session.unthrottle(selected)
    for ip in removed:
        console.print(f"[green]已解除限速:[/green] {ip}")


def _handle_status(session: SessionManager) -> None:
    console.print("[dim]按 Ctrl+C 返回主選單[/dim]\n")
    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                panel = make_status_panel(
                    blocked_count=len(session.blocked_ips),
                    throttled_count=len(session.throttled_ips),
                    packet_count=session.packet_count,
                    elapsed_seconds=session.elapsed,
                )
                live.update(panel)
                time.sleep(1)
    except KeyboardInterrupt:
        pass
