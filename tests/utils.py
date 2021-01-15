from datetime import datetime
from contextlib import AbstractContextManager
import sys
import signal

import subprocess

def run_command(command: str, input: str = None, verbose: bool = True):
    parsed_command = command.split(' ')
    proc = subprocess.Popen(parsed_command,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            )
    if input:
        stdout, stderr = proc.communicate(input.encode())
    else:
        stdout, stderr = proc.communicate()

    if verbose:
        print('$ ' + command)
        print(stdout.decode())
        print(stderr.decode())

    return proc.returncode, stdout.decode(), stderr.decode()

class Progress:

    start_time = datetime.now()
    cursor_column = 0

    @classmethod
    def report(cls, message):
        if not message == "":
            sys.stdout.write(cls._elapsed_time() + " " + message)
            if not message.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()

    @classmethod
    def _elapsed_time(cls):
        elapsed_delta = datetime.now() - cls.start_time
        return cls._duration_h_mm_ss(elapsed_delta.seconds)

    @staticmethod
    def _duration_h_mm_ss(duration_secs):
        m, s = divmod(duration_secs, 60)
        h, m = divmod(m, 60)
        return "%d:%02d:%02d" % (h, m, s)


class Timeout(AbstractContextManager):
    def __init__(self, seconds_remaining: int) -> None:
        self.did_timeout = False
        self.seconds_remaining = seconds_remaining

    def __enter__(self):
        def _timeout_handler(signum, frame):
            self.did_timeout = True
            raise TimeoutError("time's up!")

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(self.seconds_remaining)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.alarm(0)

        return (None is exc_type) or (TimeoutError is exc_type)
