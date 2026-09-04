"""Steam OpenID 2.0 login using a temporary local callback server."""
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
STEAM_ID_PREFIX = "https://steamcommunity.com/openid/id/"

class SteamOpenIDError(RuntimeError): pass

@dataclass(frozen=True)
class SteamLoginResult:
    steam_id64: str

def make_state() -> str:
    return secrets.token_urlsafe(32)

def build_login_url(return_to: str, state: str) -> str:
    query = {"openid.ns":"http://specs.openid.net/auth/2.0", "openid.mode":"checkid_setup", "openid.return_to":f"{return_to}?state={state}", "openid.realm":return_to, "openid.identity":"http://specs.openid.net/auth/2.0/identifier_select", "openid.claimed_id":"http://specs.openid.net/auth/2.0/identifier_select"}
    return f"{OPENID_ENDPOINT}?{urlencode(query)}"

def extract_steam_id64(claimed_id: str) -> str:
    if not claimed_id.startswith(STEAM_ID_PREFIX): raise SteamOpenIDError("Steam returned an invalid claimed identity")
    steam_id = claimed_id[len(STEAM_ID_PREFIX):]
    if not steam_id.isdigit() or len(steam_id) != 17: raise SteamOpenIDError("Steam returned an invalid SteamID64")
    return steam_id

def verify_response(params: dict[str, str], opener=urlopen) -> str:
    payload = {key: value for key, value in params.items() if key.startswith("openid.")}
    payload["openid.mode"] = "check_authentication"
    request = Request(OPENID_ENDPOINT, data=urlencode(payload).encode(), headers={"Content-Type":"application/x-www-form-urlencoded"})
    try:
        with opener(request, timeout=20) as response: verified = response.read().decode("utf-8", "replace")
    except OSError as error: raise SteamOpenIDError("Steam OpenID verification failed") from error
    if "is_valid:true" not in verified: raise SteamOpenIDError("Steam rejected the signed login response")
    return extract_steam_id64(params.get("openid.claimed_id", ""))

def login(timeout: int = 180, opener=urlopen, browser=webbrowser.open) -> SteamLoginResult:
    """Open the system browser, wait once for the signed redirect, then verify."""
    result, event, state = {}, threading.Event(), make_state()
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            values = {key: value[-1] for key, value in parse_qs(urlparse(self.path).query).items()}
            if values.get("state") != state: result["error"] = SteamOpenIDError("Steam login state did not match")
            else: result["params"] = values
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(b"<h3>Steam sign-in complete. You can return to Dota Draft Assistant.</h3>"); event.set()
    server = HTTPServer(("127.0.0.1", 0), Callback)
    return_to = f"http://127.0.0.1:{server.server_port}/steam-callback"
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        browser(build_login_url(return_to, state))
        if not event.wait(timeout): raise SteamOpenIDError("Steam login timed out or was cancelled")
        if "error" in result: raise result["error"]
        return SteamLoginResult(verify_response(result["params"], opener))
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=2)
