#!/usr/bin/env python
import errno
import fcntl

if __name__ == "__main__":
    handle = open("/tmp/lockfile", "r")
    fd = handle.fileno()
    got_lock = False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        got_lock = True
    except OSError as e:
        print(f"Unable to lock file {e.errno}")
        if e.errno == errno.EWOULDBLOCK:
            print("Error is EWOULDBLOCK")

    if got_lock:
        print("checklock: Lock acquired")