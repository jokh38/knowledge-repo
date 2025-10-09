#!/usr/bin/env python3
import os
import sys

# Ensure miniconda environment takes precedence
miniconda_site = "/home/jokh38/miniconda3/lib/python3.10/site-packages"
if miniconda_site not in sys.path:
    sys.path.insert(0, miniconda_site)

# Remove user local site-packages to avoid conflicts
user_local = "/home/jokh38/.local/lib/python3.10/site-packages"
if user_local in sys.path:
    sys.path.remove(user_local)

if __name__ == "__main__":
    os.execv(sys.executable, [sys.executable] + sys.argv[1:])