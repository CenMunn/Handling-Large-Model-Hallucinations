"""Epoch reservations survive reboot; in-process deadlines remain monotonic.

Legacy uptime-based tables are intentionally not read or removed. The new table
names its clock explicitly, so a saved uptime can never become an epoch slot.
"""
import math,sqlite3,time
from contextlib import closing
from pathlib import Path


def acquire(path,namespace,interval,deadline):
    remaining=deadline-time.monotonic()
    if remaining<.05:raise TimeoutError('Retrieval deadline before rate acquisition')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=min(remaining,1))) as db,db:
        db.execute('CREATE TABLE IF NOT EXISTS epoch_slots_v2 (endpoint TEXT PRIMARY KEY,next_epoch REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        now=time.time();mono=time.monotonic()
        row=db.execute('SELECT next_epoch FROM epoch_slots_v2 WHERE endpoint=?',(namespace,)).fetchone()
        saved=row[0] if row else now
        if not isinstance(saved,(float,int)) or not math.isfinite(saved):raise ValueError('Invalid persisted rate reservation')
        wait=max(0,saved-now)
        if mono+wait+.05>=deadline:raise TimeoutError('Rate queue exceeds retrieval deadline')
        db.execute('INSERT OR REPLACE INTO epoch_slots_v2 VALUES (?,?)',(namespace,now+wait+interval))
        wake=mono+wait
    # Database/commit time counts toward the reservation and the request budget.
    delay=wake-time.monotonic()
    if delay>0:time.sleep(delay)
    if time.monotonic()+.05>=deadline:raise TimeoutError('Retrieval deadline after rate wait')
