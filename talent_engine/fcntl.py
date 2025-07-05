# talent_engine/fcntl.py
import platform

if platform.system() == "Windows":
    # Dummy fcntl module for Windows
    def flock(fd, operation):
        pass  # No-op for Windows

    def lockf(fd, operation, length=0, start=0, whence=0):
        pass  # No-op for Windows

    LOCK_SH = 1
    LOCK_EX = 2
    LOCK_NB = 4
    LOCK_UN = 8
else:
    import fcntl as real_fcntl
    flock = real_fcntl.flock
    lockf = real_fcntl.lockf
    LOCK_SH = real_fcntl.LOCK_SH
    LOCK_EX = real_fcntl.LOCK_EX
    LOCK_NB = real_fcntl.LOCK_NB
    LOCK_UN = real_fcntl.LOCK_UN