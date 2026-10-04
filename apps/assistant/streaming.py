"""Bounded WSGI SSE transport. No durable jobs, answers or replay store.

One computation per process leaves WSGI threads available for ordinary requests.
The slot belongs to the computation, including after a browser disconnects.
"""
import json
from queue import Empty, Queue
from threading import BoundedSemaphore, Lock, Thread
from time import monotonic

from django.db import close_old_connections, connections
from django.http import StreamingHttpResponse

HEARTBEAT_SECONDS = 10
STREAM_LIMIT_SECONDS = 600
_slot = BoundedSemaphore(1)


def _frame(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


class _AskStream:
    def __init__(self, execute, on_failure):
        self._results = Queue(maxsize=1)
        self._lock = Lock()
        self._closed = False
        self._first = True
        self._started = monotonic()
        self._thread = Thread(
            target=self._run, args=(execute, on_failure), name="ask-delisky-stream", daemon=True
        )
        self._thread.start()

    def _run(self, execute, on_failure):
        frame = _frame("error", {
            "ok": False, "status": 503,
            "error": {"code": "ASSISTANT_UNAVAILABLE", "message": "تعذر إكمال الطلب."},
        })
        try:
            close_old_connections()
            try:
                response = execute()
            except Exception:
                # Never expose exceptions, SQL, prompts or context to the browser.
                response = on_failure()
            payload = json.loads(response.content)
            payload["status"] = response.status_code
            frame = _frame("result" if payload.get("ok") else "error", payload)
        except Exception:
            # Audit persistence failure must not be reported as a successful answer.
            pass
        finally:
            try:
                connections.close_all()
            finally:
                _slot.release()
                with self._lock:
                    if not self._closed:
                        self._results.put_nowait(frame)

    def __iter__(self):
        return self

    def __next__(self):
        if self._closed:
            raise StopIteration
        if self._first:
            self._first = False
            return _frame("accepted", {"ok": True})
        remaining = STREAM_LIMIT_SECONDS - (monotonic() - self._started)
        if remaining <= 0:
            self.close()
            return _frame("error", {"ok": False, "status": 504, "error": {
                "code": "STREAM_TIMEOUT", "message": "انتهت مهلة الانتظار. أعد المحاولة لاحقًا."
            }})
        try:
            result = self._results.get(timeout=min(HEARTBEAT_SECONDS, remaining))
        except Empty:
            return _frame("progress", {"elapsed_seconds": round(monotonic() - self._started)})
        self.close()
        return result

    def close(self):
        with self._lock:
            self._closed = True
            # Disconnect/refresh discards any undelivered answer. Never replay it.
            try:
                self._results.get_nowait()
            except Empty:
                pass


def stream_ask_response(execute, *, on_failure):
    if not _slot.acquire(blocking=False):
        return None
    try:
        stream = _AskStream(execute, on_failure)
    except Exception:
        _slot.release()
        raise
    response = StreamingHttpResponse(stream, content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-store, no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response
