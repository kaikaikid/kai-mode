# Smoke reviewer for real `travel auto` runs. Not used by unit tests.
import sys, json, re, subprocess, os

prompt = sys.argv[1] if len(sys.argv) > 1 else ""
m = re.search(r'"review_report_path":\s*"([^"]+)"', prompt)
if not m:
    print("no review_report_path"); sys.exit(2)
p = m.group(1).replace("\\", "/")
real = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
full = os.path.join(real, p) if not os.path.isabs(p) else p
os.makedirs(os.path.dirname(full), exist_ok=True)
open(full, "w", encoding="utf-8").write(json.dumps({
    "verdict": "accept", "defects": [], "reason": "smoke"}))
print("accept ->", full)
