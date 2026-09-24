import urllib.request
import urllib.error

host_headers = [
    "localhost",
    "127.0.0.1",
    "localhost:1234",
    "127.0.0.1:1234",
    None
]

for h in host_headers:
    url = "http://127.0.0.1:1234/v1/models"
    headers = {"User-Agent": "curl/7.68.0", "Accept": "*/*"}
    if h is not None:
        headers["Host"] = h
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            print(f"Host={h!r} -> OK {resp.status}: {resp.read().decode('utf-8')[:150]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:100]
        print(f"Host={h!r} -> HTTP {e.code}: {body.strip()}")
    except Exception as e:
        print(f"Host={h!r} -> ERR: {e}")
