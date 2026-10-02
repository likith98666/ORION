"""Enable running ORION via `python -m orion`."""

import sys

from orion.main import main

if __name__ == "__main__":
    sys.exit(main())
