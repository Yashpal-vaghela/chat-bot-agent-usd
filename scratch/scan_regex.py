import os
import re
import ast

errors = []
for root, dirs, files in os.walk(r'd:\media\voice_agent'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                for idx, line in enumerate(fp, 1):
                    # Check regexes in line
                    for fn in ['search', 'match', 'findall', 'sub', 'compile']:
                        token = f're.{fn}('
                        if token in line:
                            start = line.find(token) + len(token)
                            # Find first argument
                            arg_part = line[start:].strip()
                            if arg_part.startswith('r"') or arg_part.startswith('r\'') or arg_part.startswith('"') or arg_part.startswith('\''):
                                try:
                                    tree = ast.parse(arg_part.split(',')[0].strip())
                                    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                                        pat = tree.body[0].value.value
                                        try:
                                            re.compile(pat)
                                        except re.PatternError as pe:
                                            errors.append((f, idx, str(pe), pat[:60]))
                                except Exception:
                                    pass

print(f"Total regex errors found: {len(errors)}")
for f, idx, err, pat in errors:
    print(f"[{f}:{idx}] {err} | Pattern: {pat}")
