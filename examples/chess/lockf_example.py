#!/usr/bin/env python

import fcntl
import sys
import time

if __name__ == "__main__":
	handle = open("/tmp/lockfile", "w+")
	fd = handle.fileno()
	try:
		fcntl.flock(fd, fcntl.LOCK_EX)
	except OSError as e:
		print(f"Unable to lock file {e.errno}")
		sys.exit(1)

	print("lockf: Lock acquired")
	time.sleep(1000)
