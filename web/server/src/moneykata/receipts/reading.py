"""The reading queue (requirements S9.8.4): receipts are read in the background, never in a
request, by a separate worker process, so a hostile or broken file can't take the server down.

- An upload marks its receipt *waiting* and answers at once; the reader picks it up.
- Jobs run one at a time by default (Settings › Receipts), each in its own worker process with
  ONNX Runtime held to 2 threads, a lower CPU priority, a memory cap and 60 seconds per
  receipt. A worker that crashes or runs out of time is stopped and a new one started; the
  receipt is marked *couldn't read it*, with the reason, and stays usable by hand.
- What is read fills the receipt's empty fields as suggestions, marked as read from it; a value
  a person entered is never overwritten. The full text goes into the database and its search
  index, never into Activity or the log.
"""

import contextlib
import datetime as dt
import json
import logging
import multiprocessing
import os
import queue
import threading
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import text

from .. import clock, settings
from ..store.entities.accounts import Account
from ..store.entities.receipts import Receipt
from . import ocr, parser

log = logging.getLogger("moneykata.receipts")

TIME_LIMIT = 60
MEMORY_CAP = 1536 * 1024 * 1024
NICE = 10
FIELDS = ("date", "amount", "payee")


def _limit_self() -> None:
    """In the worker: a lower priority. Its memory is watched from outside (an address-space
    limit can't be used: ONNX Runtime and OpenCV map far more than they touch)."""
    with contextlib.suppress(OSError):
        os.nice(NICE)


def resident(pid: int) -> int:
    """A process's resident memory in bytes, from /proc; 0 where there is none."""
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def _serve(conn) -> None:
    """The worker process's loop: a file in, its lines (or why not) out."""
    os.environ["OMP_NUM_THREADS"] = str(ocr.THREADS)
    _limit_self()
    while True:
        try:
            job = conn.recv()
        except EOFError:
            return
        if job is None:
            return
        data, media = job
        try:
            r = ocr.read(data, media)
            conn.send(("ok", r.lines, r.method, r.engine))
        except ocr.ReadError as e:
            conn.send(("error", str(e)))
        except MemoryError:
            conn.send(("error", "it needed more memory than the reader may use"))
        except Exception as e:
            conn.send(("error", f"the reader failed ({type(e).__name__})"))


class Worker:
    """One worker process, started when first needed and again after a crash or a timeout."""

    def __init__(self) -> None:
        self.proc = None
        self.conn = None

    def _start(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        here, there = ctx.Pipe()
        self.proc = ctx.Process(target=_serve, args=(there,), daemon=True, name="mk-reader")
        self.proc.start()
        there.close()
        self.conn = here

    def read(self, data: bytes, media: str, limit: float = TIME_LIMIT) -> tuple:
        if self.proc is None or not self.proc.is_alive():
            self._start()
        try:
            self.conn.send((data, media))
            waited = 0.0
            while not self.conn.poll(min(0.25, limit)):
                waited += 0.25
                if resident(self.proc.pid) > MEMORY_CAP:
                    self.stop()
                    return ("error", "it needed more memory than the reader may use")
                if waited >= limit:
                    self.stop()
                    return ("error", f"it took longer than {int(limit)} seconds")
            return self.conn.recv()
        except (EOFError, BrokenPipeError, OSError):
            self.stop()
            return ("error", "the reader stopped while reading it")

    def stop(self) -> None:
        if self.proc is not None:
            if self.proc.is_alive():
                self.proc.kill()
            self.proc.join(5)
        self.proc = self.conn = None


class Reader:
    """The queue and its threads, one per job allowed at a time."""

    def __init__(self, server, workers: int | None = None) -> None:
        self.server = server
        self.jobs: queue.Queue[str | None] = queue.Queue()
        self.threads: list[threading.Thread] = []
        self.workers: list[Worker] = []
        self.count = workers
        self.stopping = threading.Event()
        self.last_run: dt.datetime | None = None

    def start(self) -> None:
        if self.threads:
            return
        with self.server.db.read() as s:
            n = self.count or settings.get(s, "receiptReadJobs")
            pending = [
                rid
                for (rid,) in s.execute(
                    text(
                        "SELECT id FROM \"Receipt\" WHERE \"readStatus\" IN ('waiting', 'reading')"
                        ' AND NOT deleted ORDER BY "createdAt"'
                    )
                )
            ]
        for i in range(n):
            w = Worker()
            t = threading.Thread(target=self._loop, args=(w,), daemon=True, name=f"mk-read-{i}")
            self.workers.append(w)
            self.threads.append(t)
            t.start()
        for rid in pending:
            self.jobs.put(rid)

    def stop(self) -> None:
        self.stopping.set()
        for _ in self.threads:
            self.jobs.put(None)
        for w in self.workers:
            w.stop()

    def queue(self, receipt_id: str) -> None:
        self.jobs.put(receipt_id)

    def waiting(self) -> int:
        return self.jobs.qsize()

    def _loop(self, worker: Worker) -> None:
        while not self.stopping.is_set():
            rid = self.jobs.get()
            if rid is None:
                return
            try:
                self.read_one(rid, worker)
            except Exception:
                log.exception("reading a receipt failed")

    def read_one(self, rid: str, worker: Worker) -> None:
        from . import whole

        srv = self.server
        with srv.db.tx() as s:
            r = s.get(Receipt, rid)
            if (
                r is None
                or r.deleted
                or r.filePrunedAt is not None
                or r.readStatus not in ("waiting", "reading")
            ):
                return
            if not settings.get(s, "readReceipts"):
                r.readStatus = "off"
                return
            r.readStatus = "reading"
            media = r.mediaType
            owner = r.ownerId
            file = SimpleNamespace(fileId=r.fileId, sha256=r.sha256)
        srv.events.publish("receipt", {"id": rid}, users=[owner])
        try:
            data = whole(srv, file)
            outcome = worker.read(data, media)
        except Exception as e:
            outcome = ("error", f"its file can't be opened ({type(e).__name__})")
        self.last_run = clock.now()
        with srv.db.tx() as s:
            r = s.get(Receipt, rid)
            if r is None:
                return
            if outcome[0] == "ok":
                _, lines, method, engine = outcome
                save_reading(s, r, lines, method, engine)
            else:
                r.readStatus, r.readError, r.readAt = "failed", outcome[1], clock.now()
        srv.events.publish("receipt", {"id": rid}, users=[owner])


def _not_before(s, r: Receipt):
    """A receipt's date can't be before the opening of the accounts its owner keeps."""
    from sqlalchemy import func, select

    return s.scalar(
        select(func.min(Account.openingDate)).where(
            Account.ownerId == r.ownerId, Account.openingDate.is_not(None)
        )
    )


def save_reading(s, r: Receipt, lines: list[str], method: str, engine: str) -> None:
    """Store what was read, and fill the fields nobody typed (S9.8.1)."""
    found = parser.parse(lines, clock.today(), _not_before(s, r))
    r.text = "\n".join(lines)
    r.readMethod, r.readEngine = method, engine
    r.readStatus, r.readError, r.readAt = "read", None, clock.now()
    r.suggested = json.dumps(found.as_dict())
    filled = set(json.loads(r.filled or "[]"))
    values = {
        "date": found.date.value if found.date else None,
        "amount": found.total.value if found.total else None,
        "payee": found.merchant.value if found.merchant else None,
    }
    for f in FIELDS:
        empty = getattr(r, f) in (None, "")
        if (empty or f in filled) and values[f] is not None:
            v = values[f]
            setattr(r, f, Decimal(v) if f == "amount" else v)
            filled.add(f)
    r.filled = json.dumps(sorted(filled))
    index(s, r)


def index(s, r: Receipt) -> None:
    s.execute(text('DELETE FROM "ReceiptSearch" WHERE "receiptId" = :id'), {"id": r.id})
    if r.text and not r.deleted:
        s.execute(
            text('INSERT INTO "ReceiptSearch" ("receiptId", text) VALUES (:id, :t)'),
            {"id": r.id, "t": r.text},
        )


def search(s, query: str) -> set[str]:
    """Receipt ids whose text has every word of the query (`blue bottle`, `142.18`)."""
    words = [w.replace('"', "") for w in query.split() if w.strip('"')]
    if not words:
        return set()
    match = " ".join(f'"{w}"' for w in words)
    return {
        rid
        for (rid,) in s.execute(
            text('SELECT "receiptId" FROM "ReceiptSearch" WHERE "ReceiptSearch" MATCH :q'),
            {"q": match},
        )
    }


def read_again(s, r: Receipt) -> None:
    """Queue it again: only empty or suggested fields will be replaced (S9.8.6)."""
    r.readStatus, r.readError = "waiting", None
