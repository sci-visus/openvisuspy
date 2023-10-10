import fcntl


def acquire(lock_file_path):
    try:
        handle = open(lock_file_path, "w+")
        fd = handle.fileno()
        fcntl.flock(fd, fcntl.LOCK_EX)
        return True, handle
    except OSError as e:
        return False, None


def check_and_acquire(lock_file_path):
    try:
        handle = open(lock_file_path, "r")
        fd = handle.fileno()
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True, handle
    except OSError as e:
        # This is redundant, but shows that
        # flock failed
        return False, None
