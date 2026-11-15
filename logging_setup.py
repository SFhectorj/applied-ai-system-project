"""Shared logging config: INFO to pawpal.log, WARNING+ to the console."""

import logging


def setup_logging(path: str = "pawpal.log") -> None:
    root = logging.getLogger("pawpal")
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)
    fh = logging.FileHandler(path)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(fh)
    root.addHandler(ch)
