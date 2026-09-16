import re
import subprocess
import os

with open(r'd:\media\voice_agent\templates\chat_bot.html', 'r', encoding='utf-8') as f:
    html = f.read()

html_clean = re.sub(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}', '', html, flags=re.DOTALL)
html_clean = re.sub(r'\{\{.*?\}\}', '""', html_clean)
html_clean = re.sub(r'\{%.*?%\}', '', html_clean)

scripts = re.findall(r'<script>(.*?)</script>', html_clean, flags=re.DOTALL)
for i, s in enumerate(scripts):
    fname = f'd:\\media\\scratch\\test_script_{i}.js'
    os.makedirs(os.path.dirname(fname), exist_ok=True)
    with open(fname, 'w', encoding='utf-8') as sf:
        sf.write(s)
    res = subprocess.run(['node', '--check', fname], capture_output=True, text=True)
    print(f"Script {i} (len {len(s)}): returncode={res.returncode}")
    if res.returncode != 0:
        print("STDERR:", res.stderr)
