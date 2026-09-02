from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


APP_NAME = "pc-nerd-stats"
AUTHOR = "https://github.com/izzydizzyy"

def human_bytes(value: float) -> str:
    size = float(value)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} TB"


def human_uptime(seconds: float) -> str:
    uptime = timedelta(seconds=int(seconds))

    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours or days:
        parts.append(f"{hours}h")

    parts.append(f"{minutes}m")

    return " ".join(parts)


def run_powershell(command: str) -> str | None:
    if os.name != "nt":
        return None

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=4,
        )

        if result.returncode != 0:
            return None

        output = result.stdout.strip()

        return output or None

    except (OSError, subprocess.SubprocessError):
        return None

def get_windows_name() -> str:
    output = run_powershell(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object -ExpandProperty Caption"
    )

    if output:
        return output

    return f"{platform.system()} {platform.release()}"


def get_cpu_name() -> str:
    output = run_powershell(
        "Get-CimInstance Win32_Processor | "
        "Select-Object -First 1 -ExpandProperty Name"
    )

    if output:
        return output

    return platform.processor().strip() or "Unknown CPU"


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))

            return sock.getsockname()[0]

    except OSError:
        return "Unavailable"

def get_display_info():
    output = run_powershell(
        "Get-CimInstance Win32_VideoController | "
        "Where-Object {$_.CurrentHorizontalResolution -ne $null} | "
        "Select-Object -First 1 "
        "CurrentHorizontalResolution,"
        "CurrentVerticalResolution,"
        "CurrentRefreshRate | "
        "ConvertTo-Json -Compress"
    )

    if not output:
        return "Unknown", "Unknown"

    try:
        data = json.loads(output)

        width = data.get("CurrentHorizontalResolution")
        height = data.get("CurrentVerticalResolution")
        refresh = data.get("CurrentRefreshRate")

        resolution = (
            f"{width}x{height}"
            if width and height
            else "Unknown"
        )

        refresh_rate = (
            f"{refresh} Hz"
            if refresh
            else "Unknown"
        )

        return resolution, refresh_rate

    except json.JSONDecodeError:
        return "Unknown", "Unknown"

def get_cpu_temperature():
    try:
        temperatures = psutil.sensors_temperatures()

    except (AttributeError, OSError):
        return "Not supported"

    if not temperatures:
        return "Not supported"

    for sensor_group in temperatures.values():

        for sensor in sensor_group:

            if sensor.current is not None:
                return f"{sensor.current:.0f}°C"

    return "Not supported"

def get_gpu_info():
    gpu = {
        "name": "Unknown GPU",
        "usage": None,
        "temperature": None,
        "vram_used": None,
        "vram_total": None,
    }

    output = run_powershell(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object -First 1 Name,AdapterRAM | "
        "ConvertTo-Json -Compress"
    )

    if output:

        try:
            data = json.loads(output)

            gpu["name"] = data.get("Name") or gpu["name"]

            if data.get("AdapterRAM"):
                gpu["vram_total"] = float(data["AdapterRAM"])

        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if shutil.which("nvidia-smi"):

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",

                    "--query-gpu="
                    "name,"
                    "utilization.gpu,"
                    "memory.used,"
                    "memory.total,"
                    "temperature.gpu",

                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )

            if result.returncode == 0:

                line = result.stdout.strip().splitlines()[0]

                values = [
                    value.strip()
                    for value in line.split(",")
                ]

                if len(values) >= 5:

                    gpu["name"] = values[0]

                    gpu["usage"] = float(values[1])

                    gpu["vram_used"] = (
                        float(values[2])
                        * 1024
                        * 1024
                    )

                    gpu["vram_total"] = (
                        float(values[3])
                        * 1024
                        * 1024
                    )

                    gpu["temperature"] = float(values[4])

        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
            IndexError,
        ):
            pass

    return gpu

def stat_table(rows):
    table = Table.grid(
        padding=(0, 2)
    )

    table.add_column(
        style="dim",
        width=14,
    )

    table.add_column()

    for key, value in rows:
        table.add_row(
            key,
            str(value),
        )

    return table


def usage_bar(percent: float, width: int = 22):
    percent = max(
        0,
        min(float(percent), 100),
    )

    filled = round(
        percent / 100 * width
    )

    bar = Text()

    bar.append(
        "▣" * filled,
        style="cyan",
    )

    bar.append(
        "▢" * (width - filled), 
        style="bright_black",
    )

    bar.append(
        f"  {percent:5.1f}%"
    )

    return bar

class StatsCollector:

    def __init__(self):

        self.os_name = get_windows_name()

        self.cpu_name = get_cpu_name()

        (
            self.resolution,
            self.refresh_rate,
        ) = get_display_info()

        self.local_ip = get_local_ip()

        network = psutil.net_io_counters()

        self.last_sent = network.bytes_sent
        self.last_received = network.bytes_recv

        self.last_network_time = time.monotonic()


    def get_network_speed(self):

        network = psutil.net_io_counters()

        now = time.monotonic()

        elapsed = max(
            now - self.last_network_time,
            0.001,
        )

        download = (
            network.bytes_recv
            - self.last_received
        ) / elapsed

        upload = (
            network.bytes_sent
            - self.last_sent
        ) / elapsed

        self.last_received = network.bytes_recv
        self.last_sent = network.bytes_sent

        self.last_network_time = now

        return download, upload


    def collect(self):

        cpu_percent = psutil.cpu_percent(
            interval=None
        )

        cpu_frequency = psutil.cpu_freq()

        memory = psutil.virtual_memory()

        disk_path = Path.home().anchor or "/"

        disk = psutil.disk_usage(
            disk_path
        )

        download, upload = (
            self.get_network_speed()
        )

        return {

            "time": datetime.now(),

            "os": self.os_name,

            "uptime": human_uptime(
                time.time()
                - psutil.boot_time()
            ),

            "username":
                os.getenv("USERNAME")
                or os.getenv("USER")
                or "Unknown",

            "cpu_name":
                self.cpu_name,

            "cpu_percent":
                cpu_percent,

            "cpu_cores":
                psutil.cpu_count(
                    logical=False
                ) or 0,

            "cpu_threads":
                psutil.cpu_count(
                    logical=True
                ) or 0,

            "cpu_frequency":
                (
                    cpu_frequency.current
                    if cpu_frequency
                    else None
                ),

            "cpu_temperature":
                get_cpu_temperature(),

            "gpu":
                get_gpu_info(),

            "memory":
                memory,

            "disk":
                disk,

            "disk_path":
                disk_path,

            "resolution":
                self.resolution,

            "refresh_rate":
                self.refresh_rate,

            "local_ip":
                self.local_ip,

            "download":
                download,

            "upload":
                upload,
        }

def build_dashboard(stats):

    memory = stats["memory"]
    disk = stats["disk"]
    gpu = stats["gpu"]

    title = Text()

    title.append(
        APP_NAME,
        style="bold cyan",
    )

    title.append(
        " // made by ",
        style="dim",
    )

    title.append(
        AUTHOR,
        style="bold",
    )

    system = Panel(
        stat_table([
            (
                "os",
                stats["os"],
            ),
            (
                "uptime",
                stats["uptime"],
            ),
            (
                "user",
                stats["username"],
            ),
            (
                "updated",
                stats["time"].strftime(
                    "%I:%M:%S %p"
                ),
            ),
        ]),
        title="system",
        border_style="bright_black",
    )


    cpu_speed = "Unknown"

    if stats["cpu_frequency"]:

        cpu_speed = (
            f'{stats["cpu_frequency"] / 1000:.2f} GHz'
        )


    cpu = Panel(
        stat_table([
            (
                "processor",
                stats["cpu_name"],
            ),
            (
                "usage",
                f'{stats["cpu_percent"]:.1f}%',
            ),
            (
                "cores",
                f'{stats["cpu_cores"]} cores / '
                f'{stats["cpu_threads"]} threads',
            ),
            (
                "speed",
                cpu_speed,
            ),
            (
                "temperature",
                stats["cpu_temperature"],
            ),
        ]),
        title="cpu",
        border_style="bright_black",
    )


    if gpu["vram_total"]:

        if gpu["vram_used"] is not None:

            vram = (
                f'{human_bytes(gpu["vram_used"])} / '
                f'{human_bytes(gpu["vram_total"])}'
            )

        else:

            vram = human_bytes(
                gpu["vram_total"]
            )

    else:

        vram = "Unavailable"


    gpu_usage = (
        f'{gpu["usage"]:.1f}%'
        if gpu["usage"] is not None
        else "Unavailable"
    )


    gpu_temperature = (
        f'{gpu["temperature"]:.0f}°C'
        if gpu["temperature"] is not None
        else "Unavailable"
    )


    gpu_panel = Panel(
        stat_table([
            (
                "gpu",
                gpu["name"],
            ),
            (
                "usage",
                gpu_usage,
            ),
            (
                "vram",
                vram,
            ),
            (
                "temperature",
                gpu_temperature,
            ),
        ]),
        title="gpu",
        border_style="bright_black",
    )


    resources = Panel(
        stat_table([
            (
                "ram",
                f"{human_bytes(memory.used)} / "
                f"{human_bytes(memory.total)}",
            ),
            (
                "ram usage",
                f"{memory.percent:.1f}%",
            ),
            (
                f"disk {stats['disk_path']}",
                f"{human_bytes(disk.used)} / "
                f"{human_bytes(disk.total)}",
            ),
            (
                "disk usage",
                f"{disk.percent:.1f}%",
            ),
        ]),
        title="memory + storage",
        border_style="bright_black",
    )


    display = Panel(
        stat_table([
            (
                "resolution",
                stats["resolution"],
            ),
            (
                "refresh rate",
                stats["refresh_rate"],
            ),
            (
                "fps",
                "game-specific — planned",
            ),
        ]),
        title="display",
        border_style="bright_black",
    )


    network = Panel(
        stat_table([
            (
                "local ip",
                stats["local_ip"],
            ),
            (
                "download",
                f"{human_bytes(stats['download'])}/s",
            ),
            (
                "upload",
                f"{human_bytes(stats['upload'])}/s",
            ),
        ]),
        title="network",
        border_style="bright_black",
    )


    usage = Table.grid(
        padding=(0, 2)
    )

    usage.add_column(
        style="dim",
        width=7,
    )

    usage.add_column()

    usage.add_row(
        "cpu",
        usage_bar(
            stats["cpu_percent"]
        ),
    )

    usage.add_row(
        "ram",
        usage_bar(
            memory.percent
        ),
    )

    usage.add_row(
        "disk",
        usage_bar(
            disk.percent
        ),
    )


    usage_panel = Panel(
        usage,
        title="live usage",
        border_style="bright_black",
    )


    info_panel = Panel(
        Align.center(
            Text(
                "Ctrl+C to exit\n"
                "refreshes automatically",
                justify="center",
                style="dim",
            ),
            vertical="middle",
        ),
        title=APP_NAME,
        border_style="bright_black",
    )


    layout = Table.grid(
        expand=True
    )

    layout.add_column(
        ratio=1
    )

    layout.add_column(
        ratio=1
    )

    layout.add_row(
        system,
        cpu,
    )

    layout.add_row(
        gpu_panel,
        resources,
    )

    layout.add_row(
        display,
        network,
    )

    layout.add_row(
        usage_panel,
        info_panel,
    )


    return Group(
        Align.center(title),
        Text(""),
        layout,
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "live terminal stats "
            "for your pc"
        )
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="refresh interval",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="show one snapshot and exit",
    )

    args = parser.parse_args()

    args.interval = max(
        args.interval,
        0.5,
    )

    collector = StatsCollector()

    psutil.cpu_percent(
        interval=None
    )

    time.sleep(0.2)


    if args.once:

        Console().print(
            build_dashboard(
                collector.collect()
            )
        )

        return


    try:

        with Live(
            build_dashboard(
                collector.collect()
            ),
            screen=True,
            refresh_per_second=4,
        ) as live:

            while True:

                time.sleep(
                    args.interval
                )

                live.update(
                    build_dashboard(
                        collector.collect()
                    ),
                    refresh=True,
                )

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
