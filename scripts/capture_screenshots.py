"""
Utility script to capture high-definition output screenshots of the Web UI using headless Edge.
Generates:
  1. docs/assets/ui_fast_track_triage.png
  2. docs/assets/ui_custom_story_triage.png
"""

import os
import subprocess

INDEX_HTML_PATH = os.path.abspath("src/api/static/index.html")
ASSETS_DIR = os.path.abspath("docs/assets")
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
    base_html = f.read()

# 1. Prepare Fast-Track Triage State
fast_track_script = """
<script>
window.addEventListener('DOMContentLoaded', () => {
  loadPersona('fast_track');
  ['step-guard', 'step-class', 'step-cov', 'step-fraud', 'step-route'].forEach(s => setStepState(s, 'done'));
  document.getElementById('agentStatusBadge').textContent = 'Triage Complete (872 ms)';
  document.getElementById('agentStatusBadge').className = 'text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-mono font-bold';
  renderDecision({
    claim_id: 'CLM-2026-BENCH-01',
    trace_id: '4f29a88c7d1e4b3fa59902bd3e9198aa',
    routing_queue: 'fast-track',
    auto_approved: true,
    claim_type: 'Auto Collision',
    severity: 'Low',
    estimated_damage: 1200.0,
    is_covered: true,
    applied_clause_id: 'POL-SEC-04-COLLISION',
    fraud_risk_score: 0.12,
    risk_tier: 'LOW',
    escalation_reason: null
  });
});
</script>
"""
fast_track_html = base_html.replace("</body>", fast_track_script + "\n</body>")
fast_track_file = os.path.join(ASSETS_DIR, "temp_fast_track.html")
with open(fast_track_file, "w", encoding="utf-8") as f:
    f.write(fast_track_html)

# 2. Prepare Custom Story Triage State (Hailstorm)
custom_story_script = """
<script>
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('claimId').value = 'CLM-CUSTOM-HAIL-09';
  document.getElementById('policyNumber').value = 'POL-554432-CA';
  document.getElementById('claimantId').value = 'CLM-7712-US';
  document.getElementById('lossLocation').value = 'Austin, TX';
  document.getElementById('narrative').value = 'Severe hail storm yesterday afternoon while parked outside at work. Hood and roof have multiple dimple dents. Windshield chipped. No injuries.';
  
  ['step-guard', 'step-class', 'step-cov', 'step-fraud', 'step-route'].forEach(s => setStepState(s, 'done'));
  document.getElementById('agentStatusBadge').textContent = 'Custom Triage Complete (940 ms)';
  document.getElementById('agentStatusBadge').className = 'text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-mono font-bold';
  renderDecision({
    claim_id: 'CLM-CUSTOM-HAIL-09',
    trace_id: 'b78a991c0e3341ab8ef90123ca49bf55',
    routing_queue: 'standard',
    auto_approved: false,
    claim_type: 'Comprehensive / Weather',
    severity: 'Medium',
    estimated_damage: 3200.0,
    is_covered: true,
    applied_clause_id: 'POL-SEC-05-COMPREHENSIVE',
    fraud_risk_score: 0.08,
    risk_tier: 'LOW',
    escalation_reason: 'Paintless dent repair appraisal required by field partner.'
  });
});
</script>
"""
custom_story_html = base_html.replace("</body>", custom_story_script + "\n</body>")
custom_story_file = os.path.join(ASSETS_DIR, "temp_custom_story.html")
with open(custom_story_file, "w", encoding="utf-8") as f:
    f.write(custom_story_html)

# Capture screenshots using headless Edge
out_img1 = os.path.join(ASSETS_DIR, "ui_fast_track_triage.png")
out_img2 = os.path.join(ASSETS_DIR, "ui_custom_story_triage.png")

cmd1 = f'cmd /c "start /wait \\"\\" \\"{EDGE_PATH}\\" --headless=new --disable-gpu --window-size=1240,820 --screenshot=\\"{out_img1}\\" \\"{fast_track_file}\\""'
cmd2 = f'cmd /c "start /wait \\"\\" \\"{EDGE_PATH}\\" --headless=new --disable-gpu --window-size=1240,820 --screenshot=\\"{out_img2}\\" \\"{custom_story_file}\\""'

print("Capturing Screenshot 1: Fast-Track...")
subprocess.run(cmd1, shell=True, check=True)
print("Capturing Screenshot 2: Custom Story...")
subprocess.run(cmd2, shell=True, check=True)

# Cleanup temp files
if os.path.exists(fast_track_file):
    os.remove(fast_track_file)
if os.path.exists(custom_story_file):
    os.remove(custom_story_file)

print(f"Screenshots captured successfully:\n 1. {out_img1}\n 2. {out_img2}")
