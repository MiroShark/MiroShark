"""
Generate review JSON with EN->FR pairs from git diff only.
Uses character-walking parser (no naive regex truncation).
Usage: python _generate_review.py
"""
import re, os, json

import subprocess
BASE = '38322e5'
wd = subprocess.check_output(
    ['git', 'diff', BASE, '--unified=0', '--', 'frontend/src'],
    encoding='utf-8', errors='replace'
)
# Also include uncommitted changes
uc = subprocess.check_output(
    ['git', 'diff', '--unified=0', '--', 'frontend/src'],
    encoding='utf-8', errors='replace'
)
diff = wd + '\n' + uc

def extract(line):
    m = re.search(r'\$?tr\s*\(', line)
    if not m:
        return None, None
    ps = m.end() - 1
    pos = ps + 1
    pd = 1
    st = None
    es = None
    en = None
    fr = None
    while pos < len(line) and pd > 0:
        c = line[pos]
        if st:
            if c == '\\':
                pos += 2; continue
            if c == st:
                if en is None and es is not None:
                    en = line[es:pos]
                st = None
                pos += 1; continue
            if st == '`' and c == '$' and pos+1 < len(line) and line[pos+1] == '{':
                pos += 2; d = 1
                while pos < len(line) and d > 0:
                    if line[pos] == '{': d += 1
                    elif line[pos] == '}': d -= 1
                    pos += 1
                continue
            pos += 1; continue
        if c in '\'"`':
            st = c
            if en is None:
                es = pos + 1
            pos += 1; continue
        if c == '(':
            pd += 1
        elif c == ')':
            pd -= 1
        elif c == '{' and pd == 1:
            be = pos + 1; bd = 1
            while be < len(line) and bd > 0:
                x = line[be]
                if x in '\'"`':
                    q = x; be += 1
                    while be < len(line):
                        if line[be] == '\\': be += 2; continue
                        if line[be] == q: break
                        if q == '`' and line[be] == '$' and be+1 < len(line) and line[be+1] == '{':
                            be += 2; dd = 1
                            while be < len(line) and dd > 0:
                                if line[be] == '{': dd += 1
                                elif line[be] == '}': dd -= 1
                                be += 1
                            continue
                        be += 1
                elif x == '{': bd += 1
                elif x == '}': bd -= 1
                be += 1
            loc = line[pos:be]
            fm = re.search(r"fr:\s*['\"`]([^'\"`]+?)['\"`]", loc)
            if fm:
                fr = fm.group(1)
            pos = be; continue
        pos += 1
    return (en.strip() if en else None, fr)

SKIP = {'width','height','viewBox','stroke','fill','edges','MUTE','IDLE','SEARCH','QUOTE','DOWNVOTE','r','cx','cy'}
review = []
cf = None

for line in diff.split('\n'):
    if line.startswith('diff --git'):
        p = line.split(' b/')
        cf = p[1] if len(p) > 1 else None
    elif line.startswith('+') and 'tr(' in line and 'fr:' in line:
        if not cf: continue
        en, fr = extract(line[1:])
        if en and fr and en not in SKIP and len(en) > 2:
            review.append({'file': cf, 'en': en, 'fr': fr})

seen = set()
uniq = []
for r in review:
    k = (r['file'], r['en'])
    if k not in seen:
        seen.add(k); uniq.append(r)
uniq.sort(key=lambda x: x['en'])

with open('_fr_review.json', 'w', encoding='utf-8') as f:
    json.dump({"total": len(uniq), "pairs": uniq}, f, ensure_ascii=False, indent=2)
print(f"OK: {len(uniq)} pairs EN->FR (git diff only)")
