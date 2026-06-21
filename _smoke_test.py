"""Smoke test: run main.py for ~7 seconds, report any crash."""
import subprocess, sys, time

proc = subprocess.Popen(
    [sys.executable, "main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=r"i:\rpg",
)
time.sleep(7)
proc.terminate()
try:
    _, stderr = proc.communicate(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
    _, stderr = proc.communicate()

rc = proc.returncode
err_text = stderr.decode("utf-8", errors="replace").strip()
if err_text:
    print(f"STDERR:\n{err_text}")
if rc is not None and rc != 0 and rc != 1 and rc != -15:
    print(f"CRASH exit code={rc}")
    sys.exit(1)
else:
    print(f"OK (exit={rc})")
