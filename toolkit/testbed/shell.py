"""A step is one shell command. The runner prints it exactly, then runs it unless this is a dry run."""

import shlex
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    argv: tuple[str, ...]
    cwd: str | None = None
    stdin: str | None = None
    quiet: bool = False

    def render(self) -> str:
        line = shlex.join(self.argv)
        if self.cwd:
            line = f"cd {shlex.quote(self.cwd)} && {line}"
        if self.quiet:
            line += " > /dev/null"
        if self.stdin is not None:
            line += " <<'EOF'\n" + self.stdin.rstrip("\n") + "\nEOF"
        return line


def step(*argv, cwd=None, stdin=None, quiet=False) -> Step:
    return Step(tuple(str(arg) for arg in argv), str(cwd) if cwd else None, stdin, quiet)


class Runner:
    def __init__(self, dry_run: bool, out=None):
        self.dry_run = dry_run
        self.out = out or sys.stdout

    def say(self, text: str) -> None:
        print(text, file=self.out, flush=True)

    def run(self, steps) -> int:
        for item in steps:
            self.say("$ " + item.render())
            if self.dry_run:
                continue
            code = self._call(item, stdout=subprocess.DEVNULL if item.quiet else None).returncode
            if code:
                self.say(f"# stopped: exit {code}")
                return code
        return 0

    def capture(self, item: Step) -> tuple[int, str]:
        self.say("$ " + item.render())
        if self.dry_run:
            return 0, ""
        result = self._call(item, stdout=subprocess.PIPE)
        return result.returncode, result.stdout

    def succeeds(self, item: Step) -> bool:
        return self._call(item, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    @staticmethod
    def _call(item: Step, **streams) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(item.argv, cwd=item.cwd, input=item.stdin, text=True, **streams)
        except FileNotFoundError:
            return subprocess.CompletedProcess(item.argv, 127, "", "")
