"""终端输出美化模块

统一的现代风格终端输出：彩色状态标签、分区标题、进度条。
不使用表情符号，仅使用 ANSI 颜色与 ASCII/制表符。
"""
import os
import sys
import time
import shutil

# Windows 终端启用 ANSI
if os.name == "nt":
    os.system("")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GREY = "\033[90m"
WHITE = "\033[97m"

BAR_FULL = "█"
BAR_EMPTY = "░"

_TTY = sys.stdout.isatty()


def _width() -> int:
    return shutil.get_terminal_size((80, 20)).columns


def _fmt_tag(tag: str, color: str) -> str:
    return f"{color}{BOLD}[ {tag} ]{RESET}"


def banner(title: str, subtitle: str = "") -> None:
    """程序启动横幅"""
    w = _width()
    line = "─" * w
    print()
    print(f"{CYAN}{line}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    if subtitle:
        print(f"{GREY}  {subtitle}{RESET}")
    print(f"{CYAN}{line}{RESET}")


def section(title: str) -> None:
    """任务分区标题"""
    w = _width()
    raw = f"  {title} "
    fill = "─" * max(0, w - len(title) - 4)
    print()
    print(f"{BOLD}{WHITE}{fill}{raw}{RESET}")


def info(msg: str) -> None:
    print(f"{_fmt_tag('INFO', CYAN)} {msg}")


def success(msg: str) -> None:
    print(f"{_fmt_tag(' OK ', GREEN)} {msg}")


def warn(msg: str) -> None:
    print(f"{_fmt_tag('WARN', YELLOW)} {msg}")


def error(msg: str) -> None:
    print(f"{_fmt_tag('FAIL', RED)} {msg}")


def skip(msg: str) -> None:
    print(f"{_fmt_tag('SKIP', GREY)} {msg}")


def detail(msg: str) -> None:
    print(f"{GREY}       {msg}{RESET}")


def kv(key: str, value: str) -> None:
    print(f"{GREY}  {key:<12}{RESET}{WHITE}{value}{RESET}")


def _fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class ProgressBar:
    """单行进度条

    非终端环境下降级为阶段性输出。
    """

    def __init__(self, total: int, desc: str = "", width: int = 22):
        self.total = max(1, int(total))
        self.desc = desc
        self.width = width
        self.done = 0
        self.start = time.time()
        self._last_len = 0

    def update(self, n: int = 1) -> None:
        self.done = min(self.total, self.done + n)
        self._draw()

    def _draw(self) -> None:
        if not _TTY:
            return
        pct = self.done / self.total
        filled = int(self.width * pct)
        bar = BAR_FULL * filled + BAR_EMPTY * (self.width - filled)
        elapsed = time.time() - self.start
        if self.done > 0:
            eta = elapsed / self.done * (self.total - self.done)
        else:
            eta = 0
        line = (
            f"{GREY}{self.desc}{RESET} "
            f"{WHITE}{self.done}/{self.total}{RESET} "
            f"{CYAN}{bar}{RESET} "
            f"{BOLD}{int(pct * 100):3d}%{RESET} "
            f"{GREY}{_fmt_time(elapsed)}<{_fmt_time(eta)}{RESET}"
        )
        pad = max(0, self._last_len - len(self._strip(line)))
        sys.stdout.write("\r" + line + " " * pad)
        sys.stdout.flush()
        self._last_len = len(self._strip(line))

    @staticmethod
    def _strip(s: str) -> str:
        import re
        return re.sub(r"\033\[[0-9;]*m", "", s)

    def finish(self, note: str = "") -> None:
        if _TTY:
            sys.stdout.write("\r" + " " * max(self._last_len, 1) + "\r")
            sys.stdout.flush()
        if note:
            print(note)
