"""Serve a pasta publico/ na porta 8080 com o tipo certo de APK (o Android reconhece como instalador)."""
import http.server
import os
import sys

PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publico")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".apk": "application/vnd.android.package-archive",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PASTA, **kwargs)


if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORTA), Handler) as servidor:
        print(f"Servindo {PASTA} em http://0.0.0.0:{PORTA}/NutriIA.apk", flush=True)
        servidor.serve_forever()
