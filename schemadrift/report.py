import json
import os


def write_report(report, path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, sort_keys=False)
        output.write("\n")


def format_summary(report):
    summary = report["summary"]
    total_changes = sum(
        summary[name]
        for name in ("added", "removed", "renamed", "type_changed", "reordered")
    )
    distribution = {
        name: summary[name]
        for name in ("added", "removed", "renamed", "type_changed", "reordered")
    }
    return (
        f"changes={total_changes} distribution={distribution} "
        f"renamed={summary['renamed']} duplicate_primary_keys={summary['duplicate_primary_keys']}"
    )
