from decimal import Decimal, ROUND_HALF_UP


def edit_distance(left, right):
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            substitution_cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def similarity(left, right):
    maximum_length = max(len(left), len(right))
    if maximum_length == 0:
        return 1.0
    score = Decimal(1) - Decimal(edit_distance(left, right)) / Decimal(maximum_length)
    return float(score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def match_renames(old_columns, new_columns, threshold):
    candidates = []

    for old_position, old_column in enumerate(old_columns):
        for new_position, new_column in enumerate(new_columns):
            if old_column.position != new_column.position:
                continue
            if old_column.type != new_column.type:
                continue
            score = similarity(old_column.normalized_name, new_column.normalized_name)
            if score >= threshold:
                candidates.append((score, old_position, new_position, old_column, new_column))

    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1],
            item[2],
            item[3].normalized_name,
            item[4].normalized_name,
        )
    )

    matches = []
    matched_old = set()
    matched_new = set()
    for score, _, _, old_column, new_column in candidates:
        if old_column.position in matched_old or new_column.position in matched_new:
            continue
        matched_old.add(old_column.position)
        matched_new.add(new_column.position)
        matches.append((old_column, new_column, score))

    return matches
