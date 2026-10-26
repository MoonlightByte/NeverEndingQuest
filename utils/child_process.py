"""A child-process wait that a stop can end (#1529).

The encounter builder runs as a child process (and its monster builder as a
grandchild). A player's Load or Reset must be able to end that wait the way it
ends a live provider call: the waiter polls a stop check, asks the child to
stop through a stop file, gives it a grace period to stop its own child, then
terminates or kills it and reaps it before re-raising. There is no timeout
(D-214): only the stop check ends a wait early.
"""
import os
import subprocess
import threading
import time


# A builder that stopped on the stop file exits with this code (#1529).
STOPPED_EXIT = 3


class ChildStopped(BaseException):
    """A builder process saw the stop file before a write; it writes nothing.

    A BaseException, so no broad ``except Exception`` in the builders turns a
    stop into an ordinary build failure.
    """


def stop_file_set(stop_file):
    """Whether the waiter asked this process to stop: the stop file exists, or
    its directory (the waiter's result directory) is already gone. Without a
    stop file nothing ever asks."""
    if not stop_file:
        return False
    return os.path.exists(stop_file) or not os.path.isdir(os.path.dirname(stop_file))


def _drain(stream, sink):
    try:
        sink.append(stream.read())
    except (OSError, ValueError):
        pass


def _feed(stream, text):
    try:
        if text:
            stream.write(text)
    except (OSError, ValueError):
        pass  # a dead child breaks the pipe; its exit is seen by the poll
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _end_process(process, soft_seconds=2.0):
    """Terminate, then kill until the process is reaped."""
    if process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass
    soft_deadline = time.monotonic() + soft_seconds
    while process.poll() is None and time.monotonic() < soft_deadline:
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass
    while process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass


def run_fenced(argv, input_text=None, stop_check=None, stop_file=None,
               poll=0.25, grace=5.0, env=None):
    """Run ``argv`` to its end and return ``(returncode, stdout, stderr)``.

    ``stop_check()`` is called every ``poll`` seconds; when it raises, the
    stop file (if any) is written, the child gets ``grace`` seconds to exit on
    its own, then it is terminated or killed and reaped, and the exception is
    re-raised. The child's stdin carries ``input_text`` on its own thread, so
    a large request never stalls the poll (the #428 shape).
    """
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace", env=env,
    )
    out, err = [], []
    threads = [
        threading.Thread(target=_drain, args=(process.stdout, out), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, err), daemon=True),
    ]
    if input_text is not None:
        threads.append(threading.Thread(target=_feed, args=(process.stdin, input_text), daemon=True))
    for thread in threads:
        thread.start()
    stopped = None
    try:
        while process.poll() is None:
            if stop_check is not None:
                try:
                    stop_check()
                except BaseException as exc:
                    stopped = exc
                    break
            try:
                process.wait(timeout=poll)
            except subprocess.TimeoutExpired:
                pass
        if stopped is not None:
            if stop_file:
                try:
                    with open(stop_file, "w", encoding="utf-8"):
                        pass
                except OSError:
                    pass  # the child also stops when the directory is gone
            deadline = time.monotonic() + grace
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    process.wait(timeout=poll)
                except subprocess.TimeoutExpired:
                    pass
    finally:
        if process.poll() is None:
            _end_process(process)
        for thread in threads:
            thread.join()
    if stopped is not None:
        raise stopped
    return process.returncode, "".join(out), "".join(err)
