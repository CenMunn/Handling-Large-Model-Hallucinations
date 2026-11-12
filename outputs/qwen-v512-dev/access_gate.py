"""OS-owned process lock: deadline bounded, automatically freed on process exit."""
import os,time
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def gate(path,deadline):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a+b') as f:
  if f.tell()==0:f.write(b'0');f.flush()
  locked=False
  try:
   while not locked:
    if time.monotonic()+.02>=deadline:raise TimeoutError('Evidence access queue deadline')
    try:
     f.seek(0)
     if os.name=='nt':
      import msvcrt
      msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
     else:
      import fcntl
      fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
     locked=True
    except (OSError,BlockingIOError):time.sleep(min(.025,max(0,deadline-time.monotonic())))
   yield
  finally:
   if locked:
    f.seek(0)
    if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
    else:fcntl.flock(f,fcntl.LOCK_UN)
