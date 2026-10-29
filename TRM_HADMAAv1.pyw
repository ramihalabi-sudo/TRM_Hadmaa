"""TRM_HADMAAv1 desktop launcher - double-click to start the GUI without a console window."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trm4.gui import main  # noqa: E402

if __name__ == "__main__":       # the advisor's worker processes re-import this file - no GUI there
    main()
