from .columns import duplicate_primary_keys
from .rename import match_renames


def compare_tables(old_table, new_table, threshold=0.6):
    old_by_name = {column.normalized_name: column for column in old_table.columns}
    new_by_name = {column.normalized_name: column for column in new_table.columns}
    common_names = [column.normalized_name for column in old_table.columns if column.normalized_name in new_by_name]

    unmatched_old = [
        column for column in old_table.columns if column.normalized_name not in new_by_name
    ]
    unmatched_new = [
        column for column in new_table.columns if column.normalized_name not in old_by_name
    ]

    rename_matches = match_renames(unmatched_old, unmatched_new, threshold)
    renamed_old_positions = {old_column.position for old_column, _, _ in rename_matches}
    renamed_new_positions = {new_column.position for _, new_column, _ in rename_matches}

    changes = []

    added_columns = [
        column for column in unmatched_new if column.position not in renamed_new_positions
    ]
    removed_columns = [
        column for column in unmatched_old if column.position not in renamed_old_positions
    ]

    for column in added_columns:
        changes.append(
            {
                "change": "added",
                "field": column.name,
                "evidence": {"position": column.position, "type": column.type},
            }
        )

    for column in removed_columns:
        changes.append(
            {
                "change": "removed",
                "field": column.name,
                "evidence": {"position": column.position, "type": column.type},
            }
        )

    for old_column, new_column, score in sorted(
        rename_matches, key=lambda item: (item[0].position, item[1].position)
    ):
        changes.append(
            {
                "change": "renamed",
                "field": old_column.name,
                "evidence": {
                    "old_name": old_column.name,
                    "new_name": new_column.name,
                    "similarity": score,
                },
            }
        )

    for normalized_name in common_names:
        old_column = old_by_name[normalized_name]
        new_column = new_by_name[normalized_name]
        if old_column.type != new_column.type:
            changes.append(
                {
                    "change": "type_changed",
                    "field": old_column.name,
                    "evidence": {
                        "old_type": old_column.type,
                        "new_type": new_column.type,
                    },
                }
            )

    common_old_order = [old_by_name[name] for name in common_names]
    reordered_pairs = []
    for previous_column, current_column in zip(common_old_order, common_old_order[1:]):
        previous_new = new_by_name[previous_column.normalized_name]
        current_new = new_by_name[current_column.normalized_name]
        if previous_new.position > current_new.position:
            reordered_pairs.append([previous_column.name, current_column.name])

    if reordered_pairs:
        changes.append(
            {
                "change": "reordered",
                "field": None,
                "evidence": {"columns": reordered_pairs},
            }
        )

    duplicate_keys = {
        "v1": duplicate_primary_keys(old_table),
        "v2": duplicate_primary_keys(new_table),
    }
    duplicate_count = len(duplicate_keys["v1"]) + len(duplicate_keys["v2"])

    reordered_count = 1 if reordered_pairs else 0

    summary = {
        "added": len(added_columns),
        "removed": len(removed_columns),
        "renamed": len(rename_matches),
        "type_changed": sum(1 for change in changes if change["change"] == "type_changed"),
        "reordered": reordered_count,
        "duplicate_primary_keys": duplicate_count,
        "threshold": threshold,
    }

    return {
        "v1_columns": [column_report(column) for column in old_table.columns],
        "v2_columns": [column_report(column) for column in new_table.columns],
        "changes": changes,
        "duplicate_primary_keys": duplicate_keys,
        "summary": summary,
    }


def column_report(column):
    return {"name": column.name, "type": column.type, "position": column.position}
