from io import BytesIO
from pathlib import Path

import pytest

from draft_assistant.auth import steam_openid
from draft_assistant.profile.profile_state import ProfileStore
from draft_assistant.data_sources.stratz import PlayerAccessProbe


def test_url_state_and_steam_id_validation():
    state = steam_openid.make_state()
    assert len(state) >= 32 and state in steam_openid.build_login_url("http://127.0.0.1:1234/callback", state)
    assert steam_openid.extract_steam_id64("https://steamcommunity.com/openid/id/76561198000000000") == "76561198000000000"
    with pytest.raises(steam_openid.SteamOpenIDError): steam_openid.extract_steam_id64("https://invalid/1")


def test_verification_rejects_failed_or_malformed_response():
    params = {"openid.claimed_id":"https://steamcommunity.com/openid/id/76561198000000000"}
    class Response:
        def __init__(self, body): self.body=body
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def read(self): return self.body
    with pytest.raises(steam_openid.SteamOpenIDError): steam_openid.verify_response(params, lambda *_a, **_k: Response(b"is_valid:false"))
    assert steam_openid.verify_response(params, lambda *_a, **_k: Response(b"is_valid:true\n")) == "76561198000000000"


def test_profile_persistence_and_sign_out():
    path=Path("data/generated/profile-test.json"); store=ProfileStore(path); profile=store.save("76561198000000000")
    assert store.load() == profile
    store.sign_out(); assert store.load() is None


def test_probe_result_is_explicit_and_safe(monkeypatch):
    from draft_assistant.data_sources import stratz
    monkeypatch.setattr(stratz, "execute", lambda *_: {"player": {"matches": [{"id": 1}]}})
    result=stratz.probe_player_access("76561198000000000")
    assert result == PlayerAccessProbe(39734272, True, True, True, 1, None, False, "YES", None)
    monkeypatch.setattr(stratz, "execute", lambda *_: (_ for _ in ()).throw(stratz.StratzError("denied test-token")))
    monkeypatch.setattr(stratz, "token", lambda: "test-token")
    assert "test-token" not in stratz.probe_player_access("76561198000000000").reason
