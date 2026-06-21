"""Boot main.py for ~15s (real window), report any crash. Path-corrected."""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
proc = subprocess.Popen([sys.executable, "main.py"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=HERE)
time.sleep(15)
proc.terminate()
try:
    _, stderr = proc.communicate(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
    _, stderr = proc.communicate()
rc = proc.returncode
err = stderr.decode("utf-8", errors="replace").strip()
if err:
    print("STDERR:\n" + err[-3000:])
print("exit:", rc)
