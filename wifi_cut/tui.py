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
MENU_BW_TEST = "Bandwidth Test       頻寬測試"
MENU_PULSE = "Pulse Block          脈衝封鎖"
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
                    MENU_BW_TEST,
                    MENU_PULSE,
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
        elif action == MENU_BW_TEST:
            _handle_bw_test(session, timeout)
        elif action == MENU_PULSE:
            _handle_pulse_block(session, timeout)
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


def _handle_bw_test(session: SessionManager, timeout: int) -> None:
    assert session.gateway is not None
    if not session.devices:
        console.print("[dim]自動掃描中...[/dim]")
        session.scan(timeout=timeout)

    selectable = session.selectable_devices()
    if not selectable:
        console.print("[yellow]沒有可測試的裝置。[/yellow]")
        return

    choices = [
        {"name": format_device_choice(d, session.gateway.ip), "value": d.ip}
        for d in selectable
    ]

    try:
        selected = inquirer.checkbox(
            message="選擇要測試的裝置",
            choices=choices,
        ).execute()
    except KeyboardInterrupt:
        return

    if not selected:
        console.print("[dim]未選擇任何裝置。[/dim]")
        return

    try:
        start_bw = int(inquirer.text(
            message="起始頻寬 (Kbit/s)",
            default="100",
        ).execute())
        end_bw = int(inquirer.text(
            message="結束頻寬 (Kbit/s)",
            default="10",
        ).execute())
        step_bw = int(inquirer.text(
            message="每步遞減 (Kbit/s)",
            default="10",
        ).execute())
        step_duration = int(inquirer.text(
            message="每步持續時間 (秒)",
            default="120",
        ).execute())
    except (KeyboardInterrupt, ValueError):
        return

    last_online_bw = None
    offline_bw = None
    current_bw = start_bw

    console.print(f"\n[bold cyan]開始頻寬測試: {start_bw}Kbit/s → {end_bw}Kbit/s[/bold cyan]\n")

    try:
        step_num = 0
        total_steps = max(1, (start_bw - end_bw) // step_bw + 1)

        while current_bw >= end_bw:
            step_num += 1
            bw_str = f"{current_bw}Kbit/s"

            if step_num == 1:
                session.throttle(selected, bw_str)
            else:
                session.update_throttle_bandwidth(selected, bw_str)

            console.print(f"[cyan]Step {step_num}/{total_steps}:[/cyan] 限速 {bw_str}")

            ping_ok = True
            try:
                with Live(console=console, refresh_per_second=1) as live:
                    for remaining in range(step_duration, 0, -1):
                        if remaining % 30 == 0:
                            ping_ok = session.ping_target(selected[0])

                        mins, secs = divmod(remaining, 60)
                        ping_status = "[green]Online[/green]" if ping_ok else "[red]WiFi Lost![/red]"
                        from rich.panel import Panel
                        panel = Panel(
                            f"[cyan]頻寬:[/cyan]     {bw_str}\n"
                            f"[dim]剩餘:[/dim]     {mins:02d}:{secs:02d}\n"
                            f"[dim]ARP Ping:[/dim] {ping_status}\n"
                            f"[dim]進度:[/dim]     Step {step_num}/{total_steps}",
                            title="Bandwidth Test",
                            border_style="cyan",
                        )
                        live.update(panel)
                        time.sleep(1)
            except KeyboardInterrupt:
                console.print("[yellow]測試中斷。[/yellow]")
                break

            if not ping_ok:
                console.print(f"[red]警告: 裝置在 {bw_str} 時 WiFi 連線中斷！[/red]")
                offline_bw = current_bw
                break

            try:
                still_online = inquirer.confirm(
                    message=f"請檢查 App，裝置在 {bw_str} 下是否仍在線？",
                    default=True,
                ).execute()
            except KeyboardInterrupt:
                break

            if still_online:
                last_online_bw = current_bw
                current_bw -= step_bw
            else:
                offline_bw = current_bw
                break
    finally:
        session.unthrottle(selected)

    console.print()
    from rich.panel import Panel
    if last_online_bw is not None:
        result_text = (
            f"[green]最後在線頻寬:[/green]  {last_online_bw}Kbit/s\n"
            f"[red]首次離線頻寬:[/red]  {offline_bw}Kbit/s\n"
            f"\n[bold]建議使用頻寬:  {last_online_bw}Kbit/s[/bold]"
        )
    elif offline_bw is not None:
        result_text = (
            f"[red]起始頻寬 {start_bw}Kbit/s 就離線了。[/red]\n"
            f"[dim]建議提高起始頻寬重新測試。[/dim]"
        )
    else:
        result_text = (
            f"[green]測試完成，裝置在 {end_bw}Kbit/s 下仍在線。[/green]\n"
            f"[bold]建議使用頻寬:  {end_bw}Kbit/s[/bold]"
        )
    console.print(Panel(result_text, title="Bandwidth Test Result", border_style="bright_green"))


def _handle_pulse_block(session: SessionManager, timeout: int) -> None:
    assert session.gateway is not None
    if not session.devices:
        console.print("[dim]自動掃描中...[/dim]")
        session.scan(timeout=timeout)

    selectable = [
        d for d in session.selectable_devices()
        if d.ip not in session.throttled_ips and d.ip not in session.blocked_ips
    ]
    if not selectable:
        console.print("[yellow]沒有可用的裝置。[/yellow]")
        return

    choices = [
        {"name": format_device_choice(d, session.gateway.ip), "value": d.ip}
        for d in selectable
    ]

    try:
        selected = inquirer.checkbox(
            message="選擇目標裝置",
            choices=choices,
        ).execute()
    except KeyboardInterrupt:
        return

    if not selected:
        console.print("[dim]未選擇任何裝置。[/dim]")
        return

    try:
        bw = inquirer.text(
            message="基礎限速頻寬 (例: 40Kbit/s)",
            default="40Kbit/s",
        ).execute()
        block_secs = float(inquirer.text(
            message="封鎖時長 (秒)",
            default="2",
        ).execute())
        allow_secs = float(inquirer.text(
            message="放行間隔 (秒)",
            default="5",
        ).execute())
    except (KeyboardInterrupt, ValueError):
        return

    session.start_pulse_block(selected, bw, block_secs, allow_secs)
    console.print(f"[bold magenta]Pulse Block 啟動[/bold magenta]")
    console.print(f"  限速: {bw} | 封鎖: {block_secs}s | 間隔: {allow_secs}s")
    console.print("[dim]按 Ctrl+C 返回主選單（Pulse Block 持續運行）[/dim]\n")

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                from rich.panel import Panel
                ping_ok = session.ping_target(selected[0])
                ping_status = "[green]Online[/green]" if ping_ok else "[red]Offline![/red]"
                panel = Panel(
                    f"[magenta]模式:[/magenta]     Pulse Block\n"
                    f"[cyan]限速:[/cyan]     {bw}\n"
                    f"[dim]週期:[/dim]     封鎖 {block_secs}s / 放行 {allow_secs}s\n"
                    f"[dim]ARP Ping:[/dim] {ping_status}\n"
                    f"[dim]Packets:[/dim]  {session.packet_count}",
                    title="Pulse Block Status",
                    border_style="magenta",
                )
                live.update(panel)
                time.sleep(3)
    except KeyboardInterrupt:
        try:
            stop = inquirer.confirm(
                message="要停止 Pulse Block 嗎？",
                default=False,
            ).execute()
        except KeyboardInterrupt:
            stop = False

        if stop:
            session.stop_pulse_block()
            session.unthrottle(selected)
            console.print("[green]Pulse Block 已停止。[/green]")


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
