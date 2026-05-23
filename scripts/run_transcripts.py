import urllib.request
import json

def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode()

def main():
    base = "http://127.0.0.1:3001"
    tests = [
        ("test-in", "What are your Botox prices?"),
        ("test-out", "Do you offer microneedling packages?"),
        ("test-escal", "I am really angry. Your service was terrible and I want a refund."),
    ]

    for sid, msg in tests:
        try:
            resp = post(f"{base}/chat", {"session_id": sid, "message": msg})
            print(f"CHAT {sid}:", resp)
        except Exception as e:
            print(f"ERROR CHAT {sid}: {e}")

    # Qualification multi-turn
    sid = "test-qual"
    seq = [
        "What are your Botox prices?",
        "We run a small wellness studio.",
        "8 people.",
        "We use WhatsApp, Instagram, and a booking form on our website.",
    ]

    for msg in seq:
        try:
            resp = post(f"{base}/chat", {"session_id": sid, "message": msg})
            print(f"CHAT {sid} -> {msg}:", resp)
        except Exception as e:
            print(f"ERROR CHAT {sid} -> {msg}: {e}")

    # Summaries
    for sid in ["test-in", "test-out", "test-escal", "test-qual"]:
        try:
            resp = post(f"{base}/summary", {"session_id": sid})
            print(f"SUMMARY {sid}:", resp)
        except Exception as e:
            print(f"ERROR SUMMARY {sid}: {e}")

if __name__ == "__main__":
    main()
