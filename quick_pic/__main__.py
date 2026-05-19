import signal
import sys
import logging

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
