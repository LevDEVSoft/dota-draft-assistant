import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

@dataclass(frozen=True)
class SteamProfile:
    steam_id64: str
    display_name: str | None = None
    avatar_url: str | None = None
    signed_in: bool = True
    linked_at: str | None = None

class ProfileStore:
    def __init__(self, path: Path): self.path = path
    def load(self) -> SteamProfile | None:
        if not self.path.exists(): return None
        try: return SteamProfile(**json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError): return None
    def save(self, steam_id64: str) -> SteamProfile:
        profile = SteamProfile(steam_id64=steam_id64, linked_at=datetime.now(UTC).isoformat())
        self.path.parent.mkdir(parents=True, exist_ok=True); self.path.write_text(json.dumps(asdict(profile), indent=2) + "\n", encoding="utf-8"); return profile
    def sign_out(self):
        if self.path.exists(): self.path.unlink()

def default_store() -> ProfileStore:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DotaDraftAssistant"
    return ProfileStore(root / "steam_profile.json")
