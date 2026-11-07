"""Where the toolkit works on the VM, read from the environment."""

import os
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Settings:
    home: PurePosixPath
    domain: str
    tunnel_id: str | None

    @property
    def repo(self) -> PurePosixPath:
        return self.home / "repo"

    @property
    def worktrees(self) -> PurePosixPath:
        return self.home / "worktrees"

    @property
    def secrets(self) -> PurePosixPath:
        return self.home / "secrets"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            home=PurePosixPath(os.environ.get("TESTBED_HOME", "/opt/testbed")),
            domain=os.environ.get("TESTBED_DOMAIN", "example.dev"),
            tunnel_id=os.environ.get("TESTBED_TUNNEL_ID") or None,
        )
