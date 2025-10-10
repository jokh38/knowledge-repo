#!/usr/bin/env python3
import os
import sys

# Ensure krepo conda environment takes precedence
krepo_site = "/home/jokh38/miniconda3/envs/krepo/lib/python3.10/site-packages"
if os.path.exists(krepo_site) and krepo_site not in sys.path:
    sys.path.insert(0, krepo_site)

# Also include base miniconda environment as fallback
miniconda_site = "/home/jokh38/miniconda3/lib/python3.10/site-packages"
if miniconda_site not in sys.path:
    sys.path.insert(1, miniconda_site)

# Remove user local site-packages to avoid conflicts
user_local = "/home/jokh38/.local/lib/python3.10/site-packages"
if user_local in sys.path:
    sys.path.remove(user_local)

if __name__ == "__main__":
    # Try to use krepo environment Python if available
    krepo_python = "/home/jokh38/miniconda3/envs/krepo/bin/python3"
    if os.path.exists(krepo_python):
        os.execv(krepo_python, [krepo_python] + sys.argv[1:])
    else:
        os.execv(sys.executable, [sys.executable] + sys.argv[1:])