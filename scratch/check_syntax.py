import re
import subprocess

with open(r'd:\media\voice_agent\templates\chat_bot.html', 'r', encoding='utf-8') as f:
    html = f.read()

scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', html, re.DOTALL)
s = scripts[3]

code_cleaned = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '', s, flags=re.DOTALL)
code_cleaned = re.sub(r'\{%.*?%\}', '// django_tag', code_cleaned)
code_cleaned = re.sub(r'\{\{.*?\}\}', '"django_val"', code_cleaned)

with open(r'd:\media\scratch\test_clean.js', 'w', encoding='utf-8') as f:
    f.write(code_cleaned)

res = subprocess.run(['node', '--check', r'd:\media\scratch\test_clean.js'], capture_output=True, text=True)
print('Return code:', res.returncode)
print('Stdout:', res.stdout)
print('Stderr:', res.stderr)
