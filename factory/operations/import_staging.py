"""Reclaim only duplicate import chunks backed by a deeply verified dataset."""

import argparse
import json

from factory.data.resume import reclaim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=".local/historical-catalog")
    parser.add_argument("--checkpoint-id", required=True)
    args = parser.parse_args()
    print(json.dumps(reclaim(args.catalog, args.checkpoint_id)))


if __name__ == "__main__":
    main()
