# ollama_utils.py
# Utility functions to start and stop the Ollama CLI server without external HTTP or requests dependency.
import subprocess
import socket
import time
import sys
from config import OLLAMA_PORT


def is_port_listening(port: int) -> bool:
    """Check if local TCP port is open."""
    with socket.socket() as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            return False


def start_ollama():
    """
    Start the Ollama CLI server and wait until the TCP port is listening.
    Does not print server logs to console.
    """
    print("[INFO] Starting Ollama service...")
    # Ensure any previous instance is terminated
    kill_ollama()

    # Launch the Ollama server quietly
    CREATE_NO_WINDOW = 0x08000000
    cmd = ["ollama", "serve"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW
    )

    # Wait for TCP port to become available
    for i in range(40):
        if is_port_listening(OLLAMA_PORT):
            print(f"[INFO] Ollama TCP port {OLLAMA_PORT} open after {i * 0.5:.1f}s")
            break
        time.sleep(0.5)
    else:
        print(f"[ERROR] TCP port {OLLAMA_PORT} did not open. Check Ollama CLI installation.")

    return proc


def kill_ollama():
    """Kill all Ollama-related processes using taskkill."""
    subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["taskkill", "/IM", "ollama app.exe", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[INFO] Ollama processes killed.")


def kill_ollama_and_exit():
    """Kill Ollama processes and exit the script."""
    kill_ollama()
    sys.exit(0)