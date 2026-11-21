import os
from psb.app import create_app
from psb.network import resolve_listen

app = create_app()

if __name__ == "__main__":
    from waitress import serve

    port = int(os.getenv("PORT", "5000"))
    listen = resolve_listen(os.getenv("LISTEN", "").strip(), port)
    print(f"Buka di komputer: http://127.0.0.1:{port}/login", flush=True)
    print(f'Buka di HP pada Wi-Fi yang sama: {app.config["BASE_URL"]}/login', flush=True)
    serve(app, listen=listen, threads=8)
