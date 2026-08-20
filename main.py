import subprocess
import sys
import os
import signal

processes = []

def shutdown(sig, frame):
    for p in processes:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

base = os.path.dirname(__file__)

core = subprocess.Popen(
    ["uvicorn", "app.main:app", "--reload", "--port", "8000"],
    cwd=os.path.join(base, "swiftcare-core"),
)
processes.append(core)

# relay: uncomment when built
# relay = subprocess.Popen(
#     ["celery", "-A", "app.celery", "worker", "--loglevel=info"],
#     cwd=os.path.join(base, "swiftcare-notify"),
# )
# processes.append(relay)

print("SwiftCare started. Ctrl+C to stop.")
for p in processes:
    p.wait()
