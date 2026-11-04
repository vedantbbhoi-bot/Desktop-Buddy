import threading
import time

import main


def test_worker_runs_jobs_in_order_on_a_daemon_thread():
    out, done = [], threading.Event()
    w = main.Worker(threading.Event())
    w.submit(out.append, 1)
    w.submit(out.append, 2)
    w.submit(done.set)
    assert done.wait(2)
    assert out == [1, 2]
    assert any(t.name == "buddy-worker" and t.daemon for t in threading.enumerate())


def test_worker_survives_a_failing_job():
    done = threading.Event()
    w = main.Worker(threading.Event())
    w.submit(lambda: 1 / 0)
    w.submit(done.set)
    assert done.wait(2)


def test_worker_stays_quiet_when_closing(caplog):
    closing = threading.Event()
    w = main.Worker(closing)
    started, release = threading.Event(), threading.Event()

    def slow():
        started.set()
        release.wait(2)
        raise RuntimeError("database closed")

    w.submit(slow)
    assert started.wait(2)
    closing.set()          # user clicked Quit mid-job
    release.set()
    time.sleep(0.2)
    assert "Background job failed" not in caplog.text
