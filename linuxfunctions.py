import os
import subprocess

def find_vlc_plugin_path():
    candidates = [
        "/usr/lib/vlc/plugins",
        "/usr/lib64/vlc/plugins",
        "/usr/local/lib/vlc/plugins",
        "/usr/local/lib64/vlc/plugins",
    ]

    vlc_path = subprocess.getoutput("which vlc")
    if vlc_path and os.path.exists(vlc_path):
        base = os.path.dirname(os.path.dirname(vlc_path))
        candidates.append(os.path.join(base, "lib", "vlc", "plugins"))
        candidates.append(os.path.join(base, "lib64", "vlc", "plugins"))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None