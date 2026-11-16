import argparse

from .columns import read_table
from .compare import compare_tables
from .report import format_summary, write_report


def build_parser():
    parser = argparse.ArgumentParser(description="Detect schema drift between two CSV files.")
    parser.add_argument("--old", required=True, help="path to the old CSV file")
    parser.add_argument("--new", required=True, help="path to the new CSV file")
    parser.add_argument("--primary-key", default="order_id", help="primary key column name")
    parser.add_argument("--threshold", type=float, default=0.6, help="rename similarity threshold")
    parser.add_argument("--out", required=True, help="path for the JSON report")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    old_table = read_table(args.old, args.primary_key)
    new_table = read_table(args.new, args.primary_key)
    report = compare_tables(old_table, new_table, args.threshold)
    write_report(report, args.out)
    print(format_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
