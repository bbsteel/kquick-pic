import signal
import sys
import logging

if getattr(sys, 'frozen', False):
    import os as _os
    _py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    _system_paths = [
        f"/usr/lib/python{_py_version}",
        f"/usr/lib/python{_py_version}/lib-dynload",
        f"/usr/lib/python{_py_version}/site-packages",
        "/usr/lib/python3/dist-packages",
    ]
    for _p in _system_paths:
        if _os.path.isdir(_p) and _p not in sys.path:
            sys.path.append(_p)

from quick_pic.app import QuickPicApp


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    app = QuickPicApp()

    def _handle_signal(signum, frame):
        logging.info(f"Received signal {signum}, shutting down")
        app.shutdown()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception:
        logging.exception("Fatal error")
        app.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
