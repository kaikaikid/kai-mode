# Smoke worker for real `travel auto` runs. Not used by unit tests.
import sys, json, re, subprocess, os

prompt = sys.argv[1] if len(sys.argv) > 1 else ""
m = re.search(r'"report_path":\s*"([^"]+)"', prompt)
if not m:
    print("no report_path"); sys.exit(2)
p = m.group(1).replace("\\", "/")
real = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
full = os.path.join(real, p) if not os.path.isabs(p) else p
os.makedirs(os.path.dirname(full), exist_ok=True)
open(full, "w", encoding="utf-8").write(json.dumps({
    "result": "done", "files_changed": [], "commit": "",
    "verification": ["noop -> ok"], "open_questions": [], "notes": "smoke"}))
print("wrote", full)
