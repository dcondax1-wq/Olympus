"""PIDs listening on a TCP port (Linux /proc), for the Get-NetTCPConnection stub in tests/win_harness/profile.ps1."""
import os
import sys

port = int(sys.argv[1])
inodes = set()
for f in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        for ln in open(f).read().splitlines()[1:]:
            p = ln.split()
            if p[3] == "0A" and int(p[1].rsplit(":", 1)[1], 16) == port:
                inodes.add(p[9])
    except OSError:
        pass
pids = set()
if inodes:
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            for fd in os.listdir(f"/proc/{d}/fd"):
                if os.readlink(f"/proc/{d}/fd/{fd}") in {f"socket:[{i}]" for i in inodes}:
                    pids.add(int(d))
        except OSError:
            continue
for p in sorted(pids):
    print(p)
