import argparse, socket, threading, json, collections,time

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
    proxy(args.listen_host, args.listen_port, args.cache_size, args.server_host, args.server_port)
    
def proxy(host: str, port: int, cache_size: int, server_host: str, server_port: int):
    """Starts a TCP proxy that forwards data between clients and a server, with caching."""
    cache = LRUCache(cache_size)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(16)
        print(f"[proxy] Listening on {host}:{port} "
              f"-> forwarding to {server_host}:{server_port}")
        while True:
            c, addr = s.accept()
            threading.Thread(
                target=handle,
                args=(c, server_host, server_port, cache),
                daemon=True
            ).start()

def handle(client_conn, server_host, server_port, cache: LRUCache):
    """Handles a client connection, forwarding requests to the server and caching responses."""
    with client_conn:
        with socket.create_connection((server_host, server_port), timeout=3) as srv:
            client_buff = b""
            server_buff = b""
            while True:
                chunk = client_conn.recv(4096)
                if not chunk:
                    break
                client_buff += chunk
                while b"\n" in client_buff:
                    line, _, client_buff = client_buff.partition(b"\n")
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        started = time.time()
                        msg = json.loads(line.decode("utf-8"))
                    except Exception as e:
                        err = {"ok": False, "error": f"Proxy malformed request: {e}"}
                        client_conn.sendall((json.dumps(err) + "\n").encode("utf-8"))
                        continue

                    cache_key = json.dumps(msg, sort_keys=True)
                    cached = cache.get(cache_key)
                    if cached is not None:
                        if isinstance(cached, dict) and "meta" in cached:
                            cached = dict(cached)            
                            cached["meta"] = dict(cached["meta"])
                            cached["meta"]["from_cache"] = True
                            cached["meta"]["took_ms"] = int((time.time()-started)*1000)
                        client_conn.sendall((json.dumps(cached) + "\n").encode("utf-8"))
                        continue
                    try:
                        
                            srv.sendall(line + b"\n")

                            while b"\n" not in server_buff:
                                part = srv.recv(4096)
                                if not part:
                                    break
                                server_buff += part
                            resp_line, _, server_buff = server_buff.partition(b"\n")
                            resp = json.loads(resp_line.decode("utf-8"))
                            cache.set(cache_key, resp)
                            if isinstance(resp, dict) and "meta" in resp:
                                resp = dict(resp)
                                resp["meta"] = dict(resp["meta"])
                                resp["meta"]["from_cache"] = False
                                resp["meta"]["took_ms"] = int((time.time()-started)*1000)
                            client_conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

                    except Exception as e:
                        err = {"ok": False, "error": f"Proxy could not reach server: {e}"}
                        client_conn.sendall((json.dumps(err) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
