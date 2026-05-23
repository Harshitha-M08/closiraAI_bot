import urllib.request
import sys

URL = "http://127.0.0.1:3001/health"

def main():
    try:
        with urllib.request.urlopen(URL, timeout=5) as resp:
            print(resp.read().decode())
    except Exception as e:
        print("ERROR", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
