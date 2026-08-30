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
