#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def get_conda_env_path():
    """Get conda environment path from environment or detect common locations"""
    # Allow override via environment variable
    if os.getenv("CONDA_PREFIX"):
        return os.getenv("CONDA_PREFIX")

    # Common conda installation paths
    home = Path.home()
    possible_paths = [
        home / "miniconda3" / "envs" / "krepo",
        home / "anaconda3" / "envs" / "krepo",
        home / "miniforge3" / "envs" / "krepo",
        Path(os.getenv("CONDA_ENV_PATH", "")) if os.getenv("CONDA_ENV_PATH") else None
    ]

    for path in possible_paths:
        if path and path.exists():
            return str(path)

    return None

def get_conda_base_path():
    """Get conda base installation path"""
    home = Path.home()
    possible_bases = [
        home / "miniconda3",
        home / "anaconda3",
        home / "miniforge3"
    ]

    for base in possible_bases:
        if base.exists():
            return str(base)

    return None

# Remove user local site-packages to avoid conflicts first
user_local = Path.home() / ".local" / "lib" / f"python3.{sys.version_info.minor}" / "site-packages"
user_local_str = str(user_local)
while user_local_str in sys.path:
    sys.path.remove(user_local_str)

# Ensure krepo conda environment takes precedence
krepo_env = get_conda_env_path()
if krepo_env:
    krepo_site = os.path.join(krepo_env, "lib", f"python3.{sys.version_info.minor}", "site-packages")
    if os.path.exists(krepo_site) and krepo_site not in sys.path:
        sys.path.insert(0, krepo_site)

# Also include base miniconda environment as fallback
conda_base = get_conda_base_path()
if conda_base:
    miniconda_site = os.path.join(conda_base, "lib", f"python3.{sys.version_info.minor}", "site-packages")
    if miniconda_site not in sys.path:
        sys.path.insert(1, miniconda_site)

if __name__ == "__main__":
    # Try to use krepo environment Python if available
    if krepo_env:
        krepo_python = os.path.join(krepo_env, "bin", "python3")
        if os.path.exists(krepo_python):
            os.execv(krepo_python, [krepo_python] + sys.argv[1:])

    # Fallback to current Python executable
    os.execv(sys.executable, [sys.executable] + sys.argv[1:])