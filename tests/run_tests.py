"""Run the suite with settings, generated previews and GPU paths isolated."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]


def main():
    # Redirect before importing any GUI/runtime module that copies APP_DIR.
    from osr_screen_tcode import config
    personal = config.CONFIG_PATH
    fingerprint = lambda: hashlib.sha256(personal.read_bytes()).digest() if personal.exists() else None
    before = fingerprint()
    with tempfile.TemporaryDirectory(prefix='osr-test-suite-') as folder:
        config.APP_DIR = Path(folder)
        config.CONFIG_PATH = config.APP_DIR / 'config.json'
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        result = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1).run(suite)
        if fingerprint() != before:
            raise RuntimeError('Personal configuration changed during tests; inspect before continuing.')
    print('Personal settings unchanged; test settings and previews were isolated.')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
