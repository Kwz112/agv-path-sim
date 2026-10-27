"""Run only on loopback and open a browser after the server is ready."""
import threading
import time
import webbrowser
import uvicorn

server = uvicorn.Server(uvicorn.Config("backend.server:app", host="127.0.0.1", port=8765))

def open_when_ready():
    for _ in range(200):
        if server.started:
            webbrowser.open("http://127.0.0.1:8765/")
            return
        if server.should_exit:
            return
        time.sleep(0.1)

if __name__ == "__main__":
    threading.Thread(target=open_when_ready, daemon=True).start()
    print("Local address: http://127.0.0.1:8765/   Press Ctrl+C to stop.")
    server.run()
