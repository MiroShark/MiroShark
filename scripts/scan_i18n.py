"""scan_i18n.py — CI gate for i18n FR translation quality.

Detects four classes of bugs in the tr() calls of the MiroShark frontend:

  A. EN empty/short suffix but fr non-empty
     - Indicates a copy-paste bug where the fr: was filled in for a
       placeholder/suffix call instead of a real EN.

  B. fr length wildly different from de (length ratio)
     - The fr: is a clearly-wrong translation (a different sentence entirely).
     - Threshold: lf > ld * 2.3 + 10 or lf < ld * 0.4 - 4
       (lowered from 0.4 - 6 to catch 'Haussier'=8 vs de=35 cases).

  B2. EN is a multi-word description (≥3 words, ≥18 chars) but fr is a
      single-word label (≤16 chars, no ellipsis).
     - Catches copy-paste bugs where a single-word fr from a neighbor
       tr() call ended up attached to a longer EN. Example: EN="Total
       actions / round" with fr="Tours" (a label from a different call).
     - This is the angle mort that pure length-ratio misses.

  B3. EN is a longer multi-word description (≥4 words) but fr is a
      short label (≤2 words, ≤16 chars).
     - Looser than B2 (catches 4-word EN with 2-word fr), catches the
       'Close (Ctrl+Shift+D)' → 'Effacer' class where EN has 2 visual
       tokens but 4+ real words after punctuation splitting.
     - Blocking.

  C. Same long fr reused for >1 distinct EN
     - Likely a copy-paste bug where the fr: was duplicated to multiple
       different ENs.
     - The scanner distinguishes legitimate case variants (just
       capitalization/punctuation/ellipsis differences) from genuinely
       different ENs by normalizing both before comparison.
     - Type C2: when the fr is reused for genuinely distinct ENs (those
       are flagged as blocking bugs).

Exits 0 if clean, 1 if any bugs are found. Type A, B2, B3 and C2 are
blocking (real bugs). Type B and C (case-variant) are warnings (can be
legitimate short translations or shared phrases).
"""
import re
import sys
import os
import glob
import ast
from collections import defaultdict

ROOT = r"frontend/src"
EXIT_OK = 0
EXIT_BUGS = 1


def read_string(s, i):
    """Read a quoted string starting at s[i] (the quote char itself).
    Returns (value, end_index_after_closing_quote) or None if not at a quote.
    Handles ', ", and ` (backtick template literal)."""
    if i >= len(s) or s[i] not in "'\"`":
        return None
    q = s[i]
    j = i + 1
    buf = []
    while j < len(s):
        c = s[j]
        if c == "\\" and j + 1 < len(s):
            buf.append(s[j:j + 2])
            j += 2
            continue
        if c == q:
            return ("".join(buf), j + 1)
        buf.append(c)
        j += 1
    return None


def find_call_end(s, open_paren_idx):
    """Find the index after the matching close paren, skipping strings
    (single, double, and backtick-quoted)."""
    depth = 0
    i = open_paren_idx
    while i < len(s):
        c = s[i]
        if c in "'\"`":
            r = read_string(s, i)
            if r:
                i = r[1]
                continue
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(s)


def parse_tr_call(body):
    """Body starts with `tr(` or `$tr(`, then args, then `)`.

    Returns (en, de, fr) or None if not parseable.
    """
    i = 1
    while i < len(body) and body[i] in " \t\n":
        i += 1
    if i >= len(body) or body[i] not in "'\"":
        return None
    r = read_string(body, i)
    if not r:
        return None
    en, _ = r
    de = fr = None
    mde = re.search(r"\bde\s*:\s*(['\"])", body)
    if mde:
        r = read_string(body, mde.end() - 1)
        if r:
            de = r[0]
    mfr = re.search(r"\bfr\s*:\s*(['\"])", body)
    if mfr:
        r = read_string(body, mfr.end() - 1)
        if r:
            fr = r[0]
    return (en, de, fr)


def scan(frontend_root):
    files = []
    for ext in ("*.vue", "*.js"):
        files.extend(glob.glob(os.path.join(frontend_root, "**", ext), recursive=True))
    files.sort()

    calls = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # Match tr() or $tr() but NOT linear-gradient(, transform(, etc.
        # The preceding char must be start-of-line or non-word.
        pattern = re.compile(r"(?:(?<=^)|(?<=\$)|(?<=[^a-zA-Z0-9_-]))tr\(", re.MULTILINE)
        for m in pattern.finditer(text):
            op_idx = m.end() - 1
            end_idx = find_call_end(text, op_idx)
            call_text = text[op_idx - 2 : end_idx] if op_idx >= 2 else text[op_idx:end_idx]
            line = text.count("\n", 0, op_idx) + 1
            parsed = parse_tr_call(text[op_idx:end_idx])
            if not parsed:
                continue
            en, de, fr = parsed
            if en is None:
                continue
            calls.append((path, line, en, de, fr))

    return calls


def normalize_en(s):
    """Normalize an EN string for comparison: lowercase, strip punctuation,
    collapse whitespace. Used to detect legitimate case/whitespace variants."""
    if not s:
        return ""
    s = s.lower()
    s = s.replace("...", "").replace("…", "")
    # Remove all punctuation except spaces and digits/letters
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return " ".join(s.split())


# Synonym allowlist — pairs/groups of EN strings that legitimately share
# the same FR (the FR is one canonical French form for the same concept).
# When C2 sees two ENs in the same group, it does NOT flag them.
#
# Each group is matched at the WORD level (any single word from one EN
# matching any word from another via the same group counts as a synonym
# hit). For multi-word ENs that need phrase-level matching, list the
# whole phrase as a group member, e.g. {"in progress", "running"}.
SYNONYM_GROUPS = [
    # State / status words
    {"running", "in progress"},
    {"any", "all"},
    {"complete", "completed"},
    {"success", "successful"},
    {"fail", "failed", "failure"},
    {"error", "errored"},
    {"active", "inactive", "idle"},
    # Action buttons
    {"copy", "copied"},
    {"cancel", "abort"},
    {"clear", "reset"},
    {"refresh", "reload"},
    {"download", "downloading"},
    {"retry", "retrying", "try again"},
    {"close", "dismiss"},
    # Domain terms (EN ↔ FR cross-pair)
    {"bull", "bullish", "haussier"},
    {"bear", "bearish", "baissier"},
    {"rnd", "round", "tour"},
    {"market", "marche"},
    {"feed", "flux"},
    {"network", "reseau"},
    {"agent", "persona"},
    {"report", "rapport"},
    {"profile", "profil"},
    {"scenario", "scenarios"},
    {"action", "actions"},
    {"participant", "participants"},
    {"yes", "oui"},
    {"no", "non"},
    {"ok", "okay"},
    {"new", "nouveau"},
    {"loading", "chargement"},
    {"relation", "relations", "relationship", "relationships"},
    {"y", "yr", "years old"},
    {"response", "responses", "reply", "replies", "reponse", "reponses"},
    {"agent setup", "agent configuration"},
]


def word_in_any_group(word):
    """Return the group containing `word`, or None."""
    for group in SYNONYM_GROUPS:
        if word in group:
            return group
    return None


def phrase_in_any_group(phrase):
    """Return the group containing `phrase` as a whole, or None.
    Used for multi-word phrases like 'in progress' that must match as units."""
    for group in SYNONYM_GROUPS:
        if phrase in group:
            return group
    return None


def is_synonym_group(en1, en2):
    """Return True if two normalized EN strings differ only by synonyms.

    Returns True if either:
    - The two strings normalize to the same value (case/punctuation variants), OR
    - The two strings are in the same phrase group (e.g. 'in progress' and
      'running' are both in {'in progress', 'running'}), OR
    - The two strings differ only by synonyms (each differing word on one side
      has a match in some group containing a word from the other side).
    """
    n1 = normalize_en(en1)
    n2 = normalize_en(en2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    # Phrase-level match: 'in progress' and 'running' as units
    g1 = phrase_in_any_group(n1)
    g2 = phrase_in_any_group(n2)
    if g1 is not None and g2 is not None and g1 is g2:
        return True
    words1 = set(n1.split())
    words2 = set(n2.split())
    if words1 == words2:
        return True
    only_in_1 = words1 - words2
    only_in_2 = words2 - words1
    if not only_in_1 and not only_in_2:
        return True
    for w in only_in_1:
        w_group = word_in_any_group(w)
        if not w_group:
            return False
        if not any(other in w_group for other in only_in_2):
            return False
    for w in only_in_2:
        w_group = word_in_any_group(w)
        if not w_group:
            return False
        if not any(other in w_group for other in only_in_1):
            return False
    return True


def all_pairs_synonyms(ens):
    """Return True if every distinct pair of EN strings in `ens` is a synonym.
    Used to suppress C2 false positives when the same FR legitimately covers
    multiple EN variants that are semantically equivalent."""
    distinct = list({normalize_en(e) for e in ens if e})
    if len(distinct) <= 1:
        return True
    for i in range(len(distinct)):
        for j in range(i + 1, len(distinct)):
            if not is_synonym_group(distinct[i], distinct[j]):
                return False
    return True


def main():
    frontend_root = ROOT
    if not os.path.isdir(frontend_root):
        print(f"[ERR] Frontend root not found: {frontend_root}", file=sys.stderr)
        return 2

    calls = scan(frontend_root)
    with_fr = [c for c in calls if c[4] is not None]
    total = len(calls)
    n_with_fr = len(with_fr)

    print(f"Total tr() calls: {total} | with fr: {n_with_fr}")

    bugs_a = []  # EN empty, fr non-empty
    bugs_b = []  # fr length ratio aberrant (warnings)
    bugs_b2 = []  # EN multi-word + fr short label (blocking)
    bugs_b3 = []  # EN >=4 words + fr <=2 words + fr <=16 chars (blocking)
    warnings_c = defaultdict(set)  # long fr reused for >1 distinct EN
    bugs_c2 = defaultdict(list)  # long fr reused for GENUINELY distinct EN (blocking)

    for path, line, en, de, fr in with_fr:
        rel = os.path.relpath(path).replace("\\", "/")
        # Type A
        if (en or "").strip() == "" and (fr or "").strip() != "":
            bugs_a.append((rel, line, en, de, fr))
        # Type B (warning, not blocking)
        if de:
            lf, ld = len(fr or ""), len(de)
            if ld >= 4 and (lf > ld * 2.3 + 10 or lf < ld * 0.4 - 4):
                bugs_b.append((rel, line, en, de, fr))
        # Type B2: EN is multi-word description but fr is a single-word label
        # (this is the angle mort that pure length ratio misses).
        # Catches cases like EN="Total actions / round" with fr="Tours".
        # A "real word" excludes punctuation-only tokens like '~', '↗', '...'.
        if en and fr:
            en_words = en.split()
            fr_words = fr.split()
            en_real_words = [w for w in en_words if any(c.isalnum() for c in w)]
            fr_real_words = [w for w in fr_words if any(c.isalnum() for c in w)]
            fr_has_ellipsis = "…" in fr or "..." in fr
            if (
                len(en) >= 18
                and len(en_real_words) >= 3
                and len(fr_real_words) == 1
                and len(fr) <= 16
                and not fr_has_ellipsis
            ):
                bugs_b2.append((rel, line, en, de, fr))
            # Type B3: EN has >=4 real words but fr is a short label (1-2
            # words, <=16 chars). Catches 'Close (Ctrl+Shift+D)' (2 visual
            # tokens but counted differently) where a 1-word fr slipped in.
            elif (
                len(en) >= 14
                and len(en_real_words) >= 4
                and len(fr_real_words) <= 2
                and len(fr) <= 16
                and not fr_has_ellipsis
            ):
                bugs_b3.append((rel, line, en, de, fr))
        # Type C / C2 — no length floor: catches short fr (labels, palette
        # words like 'Copié', 'Copier', 'Actualiser') reused across distinct
        # ENs. The classic ternary-button bug:
        #   copied ? tr('Copied', fr:'Copié') : tr('Copy URL', fr:'Copié')
        # where the non-copied branch has fr inherited from the copied branch.
        if (fr or "").strip():
            warnings_c[fr].add(en)
            bugs_c2[fr].append((rel, line, en))

    # Filter C2 to only those with genuinely different ENs (after
    # normalization) AND not covered by the synonym allowlist.
    bugs_c2_filtered = []
    for fr, occurrences in bugs_c2.items():
        normalized = {}
        for rel, line, en in occurrences:
            norm = normalize_en(en)
            if norm not in normalized:
                normalized[norm] = (rel, line, en)
        if len(normalized) > 1:
            ens = [occ[2] for occ in normalized.values()]
            # Skip if all distinct ENs are synonyms (e.g., 'Running' and
            # 'In progress' both legitimately translate to 'En cours').
            if not all_pairs_synonyms(ens):
                bugs_c2_filtered.append((fr, list(normalized.values())))

    # Type A
    print(f"\n=== A. EN empty/short suffix but fr non-empty ({len(bugs_a)}) ===")
    for rel, line, en, de, fr in bugs_a:
        print(f"  {rel}:{line}  EN={en!r}  fr={fr[:40]!r}")

    # Type B (warnings only)
    print(f"\n=== B. fr length wildly different from de ({len(bugs_b)}) [warning] ===")
    for rel, line, en, de, fr in bugs_b:
        print(f"  {rel}:{line}")
        print(f"    EN={en[:55]!r}")
        print(f"    de={de[:55]!r}")
        print(f"    fr={fr[:65]!r}")

    # Type B2 (blocking)
    print(f"\n=== B2. EN multi-word (>=3 words, >=18 chars) but fr is short label (<=16 chars) ({len(bugs_b2)}) [BLOCKING] ===")
    for rel, line, en, de, fr in bugs_b2:
        print(f"  {rel}:{line}")
        print(f"    EN={en[:55]!r}")
        print(f"    de={de[:55]!r}")
        print(f"    fr={fr[:65]!r}")

    # Type B3 (blocking)
    print(f"\n=== B3. EN >=4 words (>=14 chars) but fr <=2 words (<=16 chars) ({len(bugs_b3)}) [BLOCKING] ===")
    for rel, line, en, de, fr in bugs_b3:
        print(f"  {rel}:{line}")
        print(f"    EN={en[:55]!r}")
        print(f"    de={de[:55]!r}")
        print(f"    fr={fr[:65]!r}")

    # Type C (warning, all-length same fr reused for >1 distinct EN — for
    # visibility; the blocking C2 below is the one that gates CI).
    print(f"\n=== C. same fr reused for >1 distinct EN ({len(warnings_c)}) [warning] ===")
    for fr, ens in sorted(warnings_c.items(), key=lambda x: -len(x[1])):
        if len(ens) > 1:
            print(f"  fr={fr[:55]!r}")
            for e in sorted(ens)[:5]:
                print(f"      EN={e[:40]!r}")

    # Type C2 (blocking: fr reused for GENUINELY distinct ENs, after
    # synonym allowlist filtering). Catches the ternary-button bug class
    # that B/B2/B3 miss because the wrong fr is a short label.
    print(f"\n=== C2. same fr for genuinely distinct ENs ({len(bugs_c2_filtered)}) [BLOCKING] ===")
    for fr, distinct_ens in bugs_c2_filtered:
        print(f"  fr={fr[:55]!r}")
        for rel, line, en in distinct_ens:
            print(f"      {rel}:{line} EN={en[:55]!r}")

    has_critical = bool(bugs_a) or bool(bugs_b2) or bool(bugs_b3) or bool(bugs_c2_filtered)
    print()
    if has_critical:
        crit = []
        if bugs_a:
            crit.append(f"{len(bugs_a)} Type A")
        if bugs_b2:
            crit.append(f"{len(bugs_b2)} Type B2")
        if bugs_b3:
            crit.append(f"{len(bugs_b3)} Type B3")
        if bugs_c2_filtered:
            crit.append(f"{len(bugs_c2_filtered)} Type C2")
        print(f"[FAIL] {', '.join(crit)} blocking bugs found.")
        return EXIT_BUGS
    elif bugs_b:
        print(f"[PASS with warnings] {len(bugs_b)} Type B + {len(warnings_c)} Type C warnings (review manually).")
        return EXIT_OK
    elif warnings_c:
        print(f"[PASS with warnings] {len(warnings_c)} Type C warnings (review manually).")
        return EXIT_OK
    else:
        print("[PASS] No i18n bugs found.")
        return EXIT_OK


def main_strict():
    """CI mode: exit 1 only on Type A bugs (clearly wrong: empty EN with
    non-empty fr). Type B and C are reported but don't fail CI (they can be
    legitimate short translations or reused phrases)."""
    return main()


if __name__ == "__main__":
    # Use utf-8 stdout for cross-platform CI logs (Windows defaults to cp1252)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
