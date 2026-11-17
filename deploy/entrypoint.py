#!/usr/bin/env python3
"""Container start: make sure the data folder belongs to the app user, then run the app as that user.

Hosts like Railway attach the persistent disk (/data) owned by root. Starting as root, fixing ownership
and dropping privileges keeps the app itself from running as root while still being able to write there.
"""
from __future__ import annotations

import os
import pwd
import sys

DATA = os.environ.get("AURELIA_DATA_DIR", "/data")
USER = "aurelia"

if os.geteuid() == 0:
    pw = pwd.getpwnam(USER)
    os.makedirs(DATA, exist_ok=True)
    for root, dirs, files in os.walk(DATA):
        for name in [root] + [os.path.join(root, x) for x in dirs + files]:
            try:
                st = os.lstat(name)
                if st.st_uid != pw.pw_uid:
                    os.lchown(name, pw.pw_uid, pw.pw_gid)
            except OSError:
                pass
    os.setgroups([])
    os.setgid(pw.pw_gid)
    os.setuid(pw.pw_uid)
    os.environ["HOME"] = pw.pw_dir

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.execv(sys.executable, [sys.executable, "run.py", *sys.argv[1:]])
