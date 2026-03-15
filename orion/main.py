#!/usr/bin/env python3
"""Top-level runner that delegates to `modules.orchestrator`.

`OrionSentinel` implementation now lives in `orion/modules/orchestrator.py`.
This file keeps a tiny runnable entrypoint for backwards compatibility.
"""

from modules.orchestrator import OrionSentinel


def main():
    s = OrionSentinel()
    s.run()


if __name__ == '__main__':
    main()
