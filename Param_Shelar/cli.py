"""Subsystem-only implementation of the ICD train/backtest/BIT commands."""
from __future__ import annotations

import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["train", "backtest", "bit"])
    args, remaining = parser.parse_known_args(argv)
    try:
        from . import train, backtest, bit
    except ImportError:
        import train, backtest, bit
    if args.command == "bit":
        if remaining:
            parser.error("bit takes no arguments")
        return bit.main()
    return train.main(remaining) if args.command == "train" else backtest.main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
