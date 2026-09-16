import os
import sys
import glob
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def get_active_daphne_log():
    # 1. Check direct shared live_conversation.log in project root
    project_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_conversation.log")
    if os.path.exists(project_log):
        return project_log

    # 2. Fallback to background task logs if present
    patterns = [
        r"C:\Users\HP\.gemini\antigravity-ide\brain\*\.system_generated\tasks\task-*.log",
        r"C:\Users\HP\.gemini\antigravity-ide\brain\11619124-e219-411e-b96a-a39a405a415f\.system_generated\tasks\task-*.log",
        r"C:\Users\HP\.gemini\antigravity-ide\brain\1196eed9-4084-4983-a28b-85e2d998cd04\.system_generated\tasks\task-*.log",
    ]
    all_logs = []
    for pat in patterns:
        all_logs.extend(glob.glob(pat))
    daphne_logs = []
    for f in set(all_logs):
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                c = fp.read(2500)
                if 'manage.py runserver' in c or 'Starting ASGI/Daphne' in c or 'Django version' in c or 'WebSocket' in c:
                    daphne_logs.append(f)
        except Exception:
            pass
    if daphne_logs:
        return max(daphne_logs, key=os.path.getmtime)
    return None

active_log = get_active_daphne_log()
if not active_log:
    print("[!] Active Daphne server log not found. Is manage.py runserver running?")
    sys.exit(1)

print("\n" + "=" * 70)
print("  USD LIVE CONVERSATION TERMINAL MONITOR")
print(f"  Connected to Server Log: {os.path.basename(active_log)}")
print("  Streaming live Voice & Text conversations in real-time...")
print("=" * 70 + "\n")

# Print the last 40 lines of existing conversation
try:
    with open(active_log, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        for line in lines[-40:]:
            if "⚡ [" in line or "USER :" in line or "RIYA :" in line or "SLOTS:" in line or "======" in line:
                print(line, end="", flush=True)
            elif "[INFO] Submitting English appointment booking" in line or "[INFO] Appointment lead email dispatched" in line or "Outgoing API Payload:" in line:
                print(f"[SUBMIT] {line}", end="", flush=True)
except Exception:
    pass

last_pos = os.path.getsize(active_log) if os.path.exists(active_log) else 0

while True:
    try:
        # Check if a newer Daphne log file appeared (e.g. server restarted)
        newer_log = get_active_daphne_log()
        if newer_log and newer_log != active_log:
            active_log = newer_log
            last_pos = 0
            print(f"\n[Reconnected to New Server Task Log: {os.path.basename(active_log)}]\n", flush=True)

        if not os.path.exists(active_log):
            time.sleep(0.5)
            continue

        curr_size = os.path.getsize(active_log)
        if curr_size > last_pos:
            with open(active_log, 'rb') as f:
                f.seek(last_pos)
                new_bytes = f.read(curr_size - last_pos)
                last_pos = f.tell()

            text_chunk = new_bytes.decode('utf-8', errors='replace')
            for line in text_chunk.splitlines(keepends=True):
                if "⚡ [" in line or "USER :" in line or "RIYA :" in line or "SLOTS:" in line or "======" in line:
                    print(line, end="", flush=True)
                elif "[INFO] Submitting English appointment booking" in line:
                    print(f"[SUBMIT] {line}", end="", flush=True)
                elif "Outgoing API Payload:" in line:
                    print(f"[PAYLOAD] {line}", end="", flush=True)
                elif "[INFO] Direct Gmail SMTP delivery successful" in line:
                    print(f"[EMAIL] {line}", end="", flush=True)
                elif "[INFO] Appointment lead email dispatched" in line:
                    print(f"[EMAIL] {line}", end="", flush=True)
                elif "WebSocket CONNECT" in line or "WebSocket DISCONNECT" in line:
                    print(f"[WS] {line}", end="", flush=True)
        elif curr_size < last_pos:
            # File was truncated/restarted
            last_pos = curr_size

        time.sleep(0.15)
    except KeyboardInterrupt:
        print("\n[Monitor Stopped]")
        break
    except Exception as e:
        time.sleep(0.5)
