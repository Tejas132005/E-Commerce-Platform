import subprocess
import webbrowser
import time
import sys
import os
import socket

PROJECT_PATH = r"C:\Users\Laptop\OneDrive\Desktop\E-Commerce"
PORT = 8000

def is_server_running(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

manage_py = os.path.join(PROJECT_PATH, "manage.py")
os.chdir(PROJECT_PATH)

# 👉 Check if server already running
if is_server_running(PORT):
    print("Server already running. Opening browser only...")
    webbrowser.open("http://127.0.0.1:8000")
    sys.exit()

# 👉 Start server
process = subprocess.Popen(
    [sys.executable, manage_py, "runserver", f"127.0.0.1:{PORT}"],
)

# Wait for server to start
time.sleep(3)

# Open browser once
webbrowser.open("http://127.0.0.1:8000")

# 👉 Exit immediately (no loop, no repeat)
sys.exit()