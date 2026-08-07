import json
import os
import re
import time
from threading import Lock


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return slug or "task"


class RunHistory:
    def __init__(self, workdir: str, task: str):
        self.workdir = os.path.abspath(workdir)
        runs_dir = os.path.join(self.workdir, "runs")
        os.makedirs(runs_dir, exist_ok=True)
        self.path = os.path.join(runs_dir, f"{int(time.time())}_{_slugify(task)}.jsonl")
        self._lock = Lock()
        self._record({"type": "meta", "task": task, "workdir": self.workdir})

    def record(self, kind: str, **data) -> None:
        self._record({"type": kind, **data})

    def _record(self, payload: dict) -> None:
        with self._lock:
            try:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": round(time.time(), 3), **payload}, ensure_ascii=True) + "\n")
            except OSError:
                pass