import os
import time
import random
import io


def safe_read(filepath):
    """
    safely reads a file with try-except jitter to avoid file locks.
    cross-compatible with python 2.7 and python 3.x
    """
    for _ in range(5):
        try:
            if not os.path.exists(filepath):
                return ""
            with io.open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        except IOError:
            time.sleep(0.05 + random.uniform(0, 0.02))
    return ""


def safe_write(filepath, content):
    """
    safely writes a file with try-except jitter to avoid file locks.
    cross-compatible with python 2.7 and python 3.x
    """
    # ensure string type for writing in python 2
    try:
        content = unicode(content)
    except NameError:
        pass  # python 3 strings are already unicode

    for _ in range(5):
        try:
            with io.open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except IOError:
            time.sleep(0.05 + random.uniform(0, 0.02))
    return False

def get_env_var(key, default=None, env_path=None):
    """
    Parses a .env file natively to avoid requiring python-dotenv in Python 2.7.
    """
    if env_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(base_dir, ".env")
        
    if not os.path.exists(env_path):
        return default
        
    try:
        with io.open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == key:
                        v = v.strip()
                        # strip quotes if present
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        elif v.startswith("'") and v.endswith("'"):
                            v = v[1:-1]
                        # In Python 2, ALProxy requires str (bytes), not unicode
                        try:
                            if isinstance(v, unicode):
                                v = v.encode("utf-8")
                        except NameError:
                            pass # Python 3
                        return v
    except IOError:
        pass
    return default
