from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from wifi_cut.scanner import Device


def make_device_table(
    devices: list[Device],
    gateway_ip: str,
    local_ip: str,
    blocked_ips: set[str] | None = None,
    throttled_ips: dict[str, str] | None = None,
) -> Table:
    blocked_ips = blocked_ips or set()
    throttled_ips = throttled_ips or {}

    table = Table(title="Network Devices", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("IP", min_width=16)
    table.add_column("MAC", min_width=18)
    table.add_column("Vendor", min_width=15)
    table.add_column("Hostname", min_width=20)
    table.add_column("Note", min_width=10)
    table.add_column("Status", min_width=12)

    for i, d in enumerate(devices, 1):
        note = ""
        if d.ip == gateway_ip:
            note = "[blue]Gateway[/blue]"
        elif d.ip == local_ip:
            note = "[green]You[/green]"

        vendor = d.vendor or "--"
        hostname = d.hostname or "--"

        if d.ip in blocked_ips:
            status = "[red]Blocked[/red]"
        elif d.ip in throttled_ips:
            bw = throttled_ips[d.ip]
            status = f"[yellow]Throttled ({bw})[/yellow]"
        else:
            status = ""

        table.add_row(str(i), d.ip, d.mac, vendor, hostname, note, status)

    return table


def make_status_panel(
    blocked_count: int,
    throttled_count: int,
    packet_count: int,
    elapsed_seconds: int,
) -> Panel:
    mins, secs = divmod(elapsed_seconds, 60)
    hours, mins = divmod(mins, 60)

    lines = []
    lines.append(f"[red]Blocked:[/red]    {blocked_count} device(s)")
    lines.append(f"[yellow]Throttled:[/yellow]  {throttled_count} device(s)")
    lines.append(f"[cyan]Packets:[/cyan]    {packet_count}")
    if hours:
        lines.append(f"[dim]Elapsed:[/dim]    {hours:02d}:{mins:02d}:{secs:02d}")
    else:
        lines.append(f"[dim]Elapsed:[/dim]    {mins:02d}:{secs:02d}")

    content = "\n".join(lines)
    return Panel(content, title="wifi-cut Status", border_style="bright_blue")


def format_device_choice(device: Device, gateway_ip: str) -> str:
    name = device.hostname or device.vendor or "--"
    label = f"{device.ip:<16} {device.mac:<18} {name}"
    if device.ip == gateway_ip:
        label += "  (Gateway)"
    return label
