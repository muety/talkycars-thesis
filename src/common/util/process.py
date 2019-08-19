import logging
import signal


# https://stackoverflow.com/a/31464349
class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


# https://stackoverflow.com/a/46414361/3112139
def proc_wrapper(func, *args, **kwargs):
    """Print exception because multiprocessing lib doesn't return them right."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.exception(e)
        raise
