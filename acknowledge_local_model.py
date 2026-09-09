"""Review/record local-model consent without starting a game or making AI calls."""
import argparse
import sys


def main():
    import model_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accept", metavar="VERSION", help="Explicit acknowledgment for automated setup")
    args = parser.parse_args()
    print(model_config.LOCAL_MODEL_DISCLAIMER)
    print("Disclaimer version:", model_config.LOCAL_MODEL_CONSENT_VERSION)
    if args.accept is None:
        if not sys.stdin.isatty():
            print("No acknowledgment recorded. Review the disclaimer, then use --accept VERSION.")
            return 1
        if input("Type ACCEPT to acknowledge, or press Enter to cancel: ").strip() != "ACCEPT":
            print("No acknowledgment recorded.")
            return 1
    try:
        model_config.acknowledge_local_model(args.accept or model_config.LOCAL_MODEL_CONSENT_VERSION)
    except ValueError as exc:
        print(str(exc))
        return 1
    print("Acknowledgment saved locally. Your selected provider has not been changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
