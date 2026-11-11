"""One-time helper: run on your own PC to get the YouTube refresh token.

    python get_refresh_token.py

Needs only the Python standard library. Paste the OAuth client ID / secret of a
"Desktop app" client, sign in with the Google account that owns the channel,
then store the printed value as the YT_REFRESH_TOKEN repository secret.
"""
import getpass
import http.server
import json
import secrets
import urllib.parse
import urllib.request
import webbrowser

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def main():
    client_id = input("OAuth client ID: ").strip()
    client_secret = getpass.getpass("OAuth client secret (hidden): ").strip()
    state = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
    })
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state:
                result.update(code=q.get("code", [""])[0], error=q.get("error", [""])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("完了しました。このタブを閉じてターミナルに戻ってください。".encode())

        def log_message(self, *args):
            pass

    print("\nブラウザで次のURLを開いてログインしてください:\n" + url + "\n")
    webbrowser.open(url)
    with http.server.HTTPServer(("127.0.0.1", PORT), Handler) as server:
        while not result:
            server.handle_request()
    if not result.get("code"):
        raise SystemExit(f"認可に失敗しました: {result.get('error')}")

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=urllib.parse.urlencode({
        "code": result["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }).encode())
    with urllib.request.urlopen(req) as resp:
        token = json.load(resp)
    print("YT_REFRESH_TOKEN に設定する値:\n" + token["refresh_token"])


if __name__ == "__main__":
    main()
