from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def info(message: str) -> None:
    console.print(f"[cyan][INFO][/cyan] {message}")


def success(message: str) -> None:
    console.print(f"[green][SUCCESS][/green] {message}")


def warning(message: str) -> None:
    console.print(f"[yellow][WARNING][/yellow] {message}")


def error(message: str) -> None:
    console.print(f"[bold red][ERROR][/bold red] {message}")


def step(title: str) -> None:
    console.print(Panel.fit(f"[bold blue]{title}[/bold blue]"))


def kv(label: str, value: str) -> None:
    console.print(f"[magenta]{label}:[/magenta] {value}")


def banner(title: str, subtitle: str = "") -> None:
    text = Text()
    text.append(title, style="bold white on blue")
    if subtitle:
        text.append(f"\n{subtitle}", style="white")
    console.print(Panel(text, expand=False))