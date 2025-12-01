import argparse, socket, json, sys


def request(host: str, port: int, payload: dict) -> dict:
    """Send a single JSON-line request and return a single JSON-line response."""
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(data)
        buff = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buff += chunk
            if b"\n" in buff:
                line, _, _ = buff.partition(b"\n")
                return json.loads(line.decode("utf-8"))
    return {"ok": False, "error": "No response"}


# ------------------- מצב אינטראקטיבי ------------------- #
def interactive_client(host, port):
    print("Interactive mode — type 'exit' to quit.\n")

    with socket.create_connection((host, port)) as s:
        while True:
            mode = input("Choose mode (calc/gpt/exit): ").strip()
            if mode == "exit":
                print("Closing connection... Bye!")
                return

            if mode not in ("calc", "gpt"):
                print("Invalid mode\n")
                continue

            if mode == "calc":
                expr = input("Enter expression to calculate: ").strip()
                payload = {"mode": "calc",
                           "data": {"expr": expr},
                           "options": {"cache": True}}
            else:
                prompt = input("Enter prompt for GPT: ").strip()
                payload = {"mode": "gpt",
                           "data": {"prompt": prompt},
                           "options": {"cache": True}}

            # שליחה
            s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))

            # קבלה
            buff = b""
            while b"\n" not in buff:
                buff += s.recv(4096)

            line, _, _ = buff.partition(b"\n")
            resp = json.loads(line.decode("utf-8"))
            print("\nResult:\n", json.dumps(resp, ensure_ascii=False, indent=2), "\n")


def main():
    ap = argparse.ArgumentParser(description="Client (calc/gpt over JSON TCP)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5555)

    # אם המשתמש לא מספק flags – נכנסים לאינטראקטיבי
    ap.add_argument("--mode", choices=["calc", "gpt"])
    ap.add_argument("--expr", help="Expression for mode=calc")
    ap.add_argument("--prompt", help="Prompt for mode=gpt")
    ap.add_argument("--no-cache", action="store_true", help="Disable caching")
    args = ap.parse_args()

    # אם אין mode -> נכנסים לאינטראקטיבי (שינוי מינימלי!)
    if args.mode is None:
        return interactive_client(args.host, args.port)

    # מצב רגיל — בקשה אחת כמו קודם
    if args.mode == "calc":
        if not args.expr:
            print("Missing --expr", file=sys.stderr)
            sys.exit(2)
        payload = {"mode": "calc", "data": {"expr": args.expr}, "options": {"cache": not args.no_cache}}
    else:
        if not args.prompt:
            print("Missing --prompt", file=sys.stderr)
            sys.exit(2)
        payload = {"mode": "gpt", "data": {"prompt": args.prompt}, "options": {"cache": not args.no_cache}}

    resp = request(args.host, args.port, payload)
    print(json.dumps(resp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
