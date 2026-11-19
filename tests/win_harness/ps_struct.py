"""A PowerShell structure check that needs no PowerShell (the tests' pwsh lint only runs where pwsh is installed).

    from tests.win_harness.ps_struct import check_script
    problems = check_script(text)      # [] when fine, else plain lines ("line 12: '}' closes the '(' of line 10")

It reads the script the way PowerShell does for the parts that break a whole script when they are wrong: '...' strings
('' inside), "..." strings (`x escapes, "" inside, $( ... ) code inside), @'...'@ / @"..."@ here-strings, # and <# #>
comments. Outside those it pairs every ( ) { } [ ] and then looks for PowerShell-7-only operators that Windows
PowerShell 5.1 (the owner's PCs) cannot parse: && || ?? ?. ?[ and the a ? b : c ternary.
"""
from __future__ import annotations

import re

PAIRS = {")": "(", "}": "{", "]": "["}
PS7_ONLY = re.compile(r"&&|\|\||\?\?|\?\.|\?\[|\s\?\s[^:\n]+\s:\s")


def scan(src: str):
    """(first structure problem or None, the code with every string and comment blanked; newlines kept)."""
    out = list(src)
    n, i, line = len(src), 0, 1
    stack = []                     # open brackets (char, line); '$(' = code inside a "..." string
    mode = ["code"]                # 'code' or 'dq' (inside a double-quoted string)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if mode[-1] == "dq":
            if c == "\n":
                line += 1
            if c == "`":
                blank(i, i + 2)
                if i + 1 < n and src[i + 1] == "\n":
                    line += 1
                i += 2
                continue
            if c == '"':
                if i + 1 < n and src[i + 1] == '"':
                    blank(i, i + 2)
                    i += 2
                    continue
                mode.pop()
                i += 1
                continue
            if c == "$" and i + 1 < n and src[i + 1] == "(":
                mode.append("code")
                stack.append(("$(", line))
                i += 2
                continue
            blank(i, i + 1)
            i += 1
            continue
        if c == "\n":
            line += 1
            i += 1
            continue
        prev = src[i - 1] if i else "\n"
        if src.startswith("<#", i):
            j = src.find("#>", i + 2)
            if j < 0:
                return f"line {line}: block comment <# is not closed", "".join(out)
            line += src.count("\n", i, j)
            blank(i, j + 2)
            i = j + 2
            continue
        if c == "#" and (prev.isspace() or prev in "({;,|="):
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if c == "@" and i + 1 < n and src[i + 1] in "'\"" and src[i + 2:i + 3] in ("\n", "\r"):
            q = src[i + 1]
            j = src.find("\n" + q + "@", i + 2)
            if j < 0:
                return f"line {line}: here-string @{q} is not closed", "".join(out)
            line += src.count("\n", i, j + 1)
            blank(i, j + 3)
            i = j + 3
            continue
        if c == "'":
            j = i + 1
            while True:
                k = src.find("'", j)
                if k < 0:
                    return f"line {line}: a '...' string is not closed", "".join(out)
                if k + 1 < n and src[k + 1] == "'":
                    j = k + 2
                    continue
                break
            line += src.count("\n", i, k)
            blank(i + 1, k)
            i = k + 1
            continue
        if c == '"':
            mode.append("dq")
            i += 1
            continue
        if c == "`":
            if i + 1 < n and src[i + 1] == "\n":
                line += 1
            i += 2
            continue
        if c in "({[":
            stack.append((c, line))
        elif c in ")}]":
            if not stack:
                return f"line {line}: '{c}' closes nothing", "".join(out)
            o, ol = stack.pop()
            if o == "$(":
                if c != ")":
                    return f"line {line}: '{c}' closes the $( of line {ol}", "".join(out)
                mode.pop()                                     # back inside the "..." string
            elif PAIRS[c] != o:
                return f"line {line}: '{c}' closes the '{o}' of line {ol}", "".join(out)
        i += 1
    if len(mode) > 1:
        return "end of file: a \"...\" string or its $( ) is not closed", "".join(out)
    if stack:
        o, ol = stack[-1]
        return f"end of file: the '{o}' of line {ol} is not closed", "".join(out)
    return None, "".join(out)


def check_script(src: str) -> list:
    """Plain problems of one script ([] = the structure is sound and no PowerShell-7-only operator is used)."""
    err, code = scan(src.lstrip("\ufeff"))
    if err:
        return [err]
    return [f"line {code.count(chr(10), 0, m.start()) + 1}: '{m.group(0).strip()}' is PowerShell 7 only (the PCs run 5.1)"
            for m in PS7_ONLY.finditer(code)][:5]


if __name__ == "__main__":
    import sys
    bad = 0
    for p in sys.argv[1:]:
        probs = check_script(open(p, encoding="utf-8-sig", errors="replace").read())
        print(("OK   " if not probs else "BAD  ") + p + ("" if not probs else "  " + "; ".join(probs)))
        bad += bool(probs)
    sys.exit(1 if bad else 0)
