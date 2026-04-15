#!/usr/bin/env python3
"""
analyze_stats.py — Offline Statistics Analyzer
================================================
Reads the CSV log file produced by traffic_monitor.py and prints
a human-readable summary table of flow statistics per switch.

Usage:
  python3 analyze_stats.py                    # reads flow_stats.csv
  python3 analyze_stats.py --file my_log.csv  # reads custom file
"""

import csv
import argparse
from collections import defaultdict


def load_csv(path):
    rows = []
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
        print("  → Run the topology first to generate statistics.")
    return rows


def summarize(rows):
    """Aggregate packet/byte counts per (switch, src, dst) flow."""
    # latest entry per (switch, src, dst) key
    latest = {}
    for row in rows:
        key = (row["Switch"], row["SrcMAC"], row["DstMAC"])
        latest[key] = row

    # Group by switch
    by_switch = defaultdict(list)
    for key, row in latest.items():
        by_switch[row["Switch"]].append(row)

    print()
    for switch, flows in sorted(by_switch.items()):
        print(f"Switch: {switch}")
        print(f"  {'Src MAC':<20} {'Dst MAC':<20} {'Packets':>10} {'Bytes':>14} {'Duration(s)':>12}")
        print("  " + "-" * 78)
        total_pkts  = 0
        total_bytes = 0
        for f in sorted(flows, key=lambda x: int(x["PacketCount"]), reverse=True):
            pkts  = int(f["PacketCount"])
            byts  = int(f["ByteCount"])
            dur   = f["DurationSec"]
            total_pkts  += pkts
            total_bytes += byts
            print(f"  {f['SrcMAC']:<20} {f['DstMAC']:<20} {pkts:>10} {byts:>14} {dur:>12}")
        print(f"  {'TOTAL':<20} {'':20} {total_pkts:>10} {total_bytes:>14}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze flow_stats CSV log")
    parser.add_argument("--file", default="flow_stats.csv", help="CSV log file path")
    args = parser.parse_args()

    rows = load_csv(args.file)
    if rows:
        print(f"Loaded {len(rows)} entries from '{args.file}'")
        summarize(rows)
