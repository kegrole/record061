import csv
from dataclasses import dataclass

from .infer import infer_type
from .normalize import normalize_name, normalize_value


@dataclass(frozen=True)
class Column:
    name: str
    normalized_name: str
    position: int
    type: str


@dataclass(frozen=True)
class Table:
    path: str
    columns: tuple
    rows: tuple
    primary_key: str

    def column_by_normalized_name(self, name):
        for column in self.columns:
            if column.normalized_name == name:
                return column
        return None


def read_table(path, primary_key="order_id"):
    with open(path, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        try:
            raw_header = next(reader)
        except StopIteration:
            raise ValueError(f"CSV file has no header: {path}")
        rows = tuple(reader)

    normalized_header = [normalize_name(name) for name in raw_header]
    if normalize_name(primary_key) not in normalized_header:
        raise ValueError(f"primary key column not found: {primary_key}")

    columns = []
    for position, (name, normalized) in enumerate(zip(raw_header, normalized_header)):
        values = tuple(row[position] if position < len(row) else "" for row in rows)
        columns.append(
            Column(
                name=name,
                normalized_name=normalized,
                position=position,
                type=infer_type(values, primary_key=(normalized == normalize_name(primary_key))),
            )
        )

    return Table(path=path, columns=tuple(columns), rows=rows, primary_key=primary_key)


def duplicate_primary_keys(table):
    normalized_primary_key = normalize_name(table.primary_key)
    key_position = next(
        index
        for index, column in enumerate(table.columns)
        if column.normalized_name == normalized_primary_key
    )
    seen = set()
    duplicates = []
    for row in table.rows:
        value = normalize_value(row[key_position] if key_position < len(row) else "")
        if value in seen:
            if value not in duplicates:
                duplicates.append(value)
        else:
            seen.add(value)
    return duplicates
