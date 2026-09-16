import os
import re
import ast

errors = []
for root, dirs, files in os.walk(r'd:\media\voice_agent'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                src = fp.read()
            try:
                tree = ast.parse(src)
            except Exception as e:
                print(f"Failed to parse AST for {f}: {e}")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check if call is re.<func>
                    is_re = False
                    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 're':
                        is_re = True
                    if is_re and node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                            pat = first_arg.value
                            try:
                                re.compile(pat)
                            except re.PatternError as pe:
                                errors.append((f, first_arg.lineno, str(pe), pat[:80]))

print(f"Total regex errors found via full AST: {len(errors)}")
for f, idx, err, pat in errors:
    print(f"[{f}:{idx}] {err} | Pattern: {pat}")
