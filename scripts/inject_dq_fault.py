import argparse
import json
from datetime import datetime, timezone


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit a demo DQ fault payload.")
    parser.add_argument("--freeze", help="Point identifier to freeze")
    parser.add_argument("--drift", help="Point identifier to drift")
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument("--slope", type=float, default=0.0)
    parser.add_argument("--hours", type=int, default=0)
    args = parser.parse_args()

    if not args.freeze and not args.drift:
        parser.error("Provide either --freeze or --drift.")

    payload = {
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "fault_type": "freeze" if args.freeze else "drift",
        "point_id": args.freeze or args.drift,
        "seconds": args.seconds,
        "hours": args.hours,
        "slope": args.slope,
        "note": "Scaffold payload for wiring into the eventual fault-injection endpoint."
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
