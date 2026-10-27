from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="capservice")
    parser.add_argument("command", choices=("api", "worker", "all"))
    args = parser.parse_args()

    if args.command == "api":
        raise SystemExit(_run_api())
    if args.command == "worker":
        from capservice.worker import main as worker_main

        worker_main()
        return

    api = subprocess.Popen([sys.executable, "-m", "capservice", "api"])
    worker = subprocess.Popen([sys.executable, "-m", "capservice", "worker"])
    try:
        finished = wait_any([api, worker])
    except KeyboardInterrupt:
        _stop(api, worker)
        raise SystemExit(0) from None
    _stop(api, worker)
    raise SystemExit(finished.returncode or 1)


def _run_api() -> int:
    import uvicorn

    return uvicorn.run(
        "capservice.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        log_config=None,
    )


def wait_any(processes: list[subprocess.Popen[bytes]]) -> subprocess.Popen[bytes]:
    import time

    while True:
        for process in processes:
            code = process.poll()
            if code is not None:
                return process
        time.sleep(0.5)


def _stop(*processes: subprocess.Popen[bytes]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
