import argparse, socket, threading, json, collections

class LRUCache:
    def __init__(self, capacity=128):
        self.capacity = capacity
        self._d = collections.OrderedDict()

    def get(self, key):
        if key not in self._d:
            return None
        self._d.move_to_end(key)
        return self._d[key]

    def set(self, key, value):
        self._d[key] = value
        self._d.move_to_end(key)
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)


# ---- פרוקסי ----
def main():
    ap = argparse.ArgumentParser(description="Transparent TCP proxy with caching")
    ap.add_argument("--listen-host", default="127.0.0.1")
    ap.add_argument("--listen-port", type=int, default=5554)
    ap.add_argument("--server-host", default="127.0.0.1")
    ap.add_argument("--server-port", type=int, default=5555)
    ap.add_argument("--cache-size", type=int, default=128)
    args = ap.parse_args()

    cache = LRUCache(args.cache_size)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.listen_host, args.listen_port))
        s.listen(16)
        print(f"[proxy] Listening on {args.listen_host}:{args.listen_port} "
              f"-> forwarding to {args.server_host}:{args.server_port}")
        while True:
            c, addr = s.accept()
            threading.Thread(
                target=handle,
                args=(c, args.server_host, args.server_port, cache),
                daemon=True
            ).start()


def handle(client_conn, server_host, server_port, cache: LRUCache):
    with client_conn:
        buff = b""
        while True:
            chunk = client_conn.recv(4096)
            if not chunk:
                break
            buff += chunk
            while b"\n" in buff:
                line, _, buff = buff.partition(b"\n")
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except Exception as e:
                    err = {"ok": False, "error": f"Proxy malformed request: {e}"}
                    client_conn.sendall((json.dumps(err) + "\n").encode("utf-8"))
                    continue

                cache_key = json.dumps(msg, sort_keys=True)
                cached = cache.get(cache_key)
                if cached is not None:
                    client_conn.sendall((json.dumps(cached) + "\n").encode("utf-8"))
                    continue
                try:
                    with socket.create_connection((server_host, server_port), timeout=3) as srv:
                        srv.sendall(line + b"\n")

                        resp_buff = b""
                        while b"\n" not in resp_buff:
                            part = srv.recv(4096)
                            if not part:
                                break
                            resp_buff += part

                        resp_line, _, _ = resp_buff.partition(b"\n")
                        resp = json.loads(resp_line.decode("utf-8"))

                        cache.set(cache_key, resp)

                        client_conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

                except Exception as e:
                    err = {"ok": False, "error": f"Proxy could not reach server: {e}"}
                    client_conn.sendall((json.dumps(err) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
