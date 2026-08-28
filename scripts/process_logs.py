import argparse
import csv
import json
from pathlib import Path
from typing import Any


def flatten_value(
    value: Any,
    prefix: str = "",
    output: dict | None = None,
) -> dict:
    """
    Flatten nested dictionaries into separate CSV columns.
    """
    if output is None:
        output = {}

    if isinstance(value, dict):

        if "hex" in value and set(value).issubset({"hex", "repr"}):
            output[prefix] = value["hex"]
            return output

        for key, item in value.items():
            column_name = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            flatten_value(
                value=item,
                prefix=column_name,
                output=output,
            )

    elif isinstance(value, list):
        output[prefix] = ", ".join(
            str(item)
            for item in value
        )

    else:
        output[prefix] = "" if value is None else value

    return output


def flatten_json_column(
    value: str | None,
    prefix: str,
) -> dict:

    if not value:
        return {}

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:

        return {
            prefix: value,
        }

    return flatten_value(
        value=parsed_value,
        prefix=prefix,
    )


def flatten_migration_log(
    input_path: Path,
    output_path: Path,
) -> None:

    flattened_rows = []
    all_columns = set()

    with input_path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as input_file:
        reader = csv.DictReader(input_file)


        required_columns = {"row", "context"}
        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                "The input file is missing required columns: "
                f"{', '.join(sorted(missing_columns))}"
            )

        for source_row in reader:
            flattened_row = {
                key: value
                for key, value in source_row.items()
                if key not in {"row", "context"}
            }

            flattened_row.update(
                flatten_json_column(
                    value=source_row.get("row"),
                    prefix="row",
                )
            )

            flattened_row.update(
                flatten_json_column(
                    value=source_row.get("context"),
                    prefix="context",
                )
            )

            flattened_rows.append(flattened_row)
            all_columns.update(flattened_row.keys())

    if not flattened_rows:
        print("The input CSV contains no rows.")
        return

    preferred_columns = [
        "logged_at",
        "stage",
        "reason",
        "error_type",
        "error_message",
        "row.old_synset_id",
        "row.old_lexicon_id",
        "row.old_sense_id",
        "row.old_word_id",
        "row.old_relation_type_id",
        "row.old_synset_from_id",
        "row.old_synset_to_id",
        "row.status_id",
        "row.definition",
        "row.princeton_id",
        "row.word_text",
        "row.example_text",
        "row.language_id",
        "row.pos",
        "row.pos_count",
        "context.new_synset_id",
        "context.new_word_id",
        "context.new_sense_id",
        "context.new_relation_id",
        "context.new_relation_type_id",
        "context.word_length",
        "context.example_length",
        "context.display_name_length",
        "context.maximum_length",
        "context.selected_pos",
    ]

    ordered_columns = [
        column
        for column in preferred_columns
        if column in all_columns
    ]

    ordered_columns.extend(
        sorted(all_columns - set(ordered_columns))
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=ordered_columns,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(flattened_rows)

    print(f"Rows processed: {len(flattened_rows)}")
    print(f"Flattened CSV created: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Flatten the row and context JSON columns in a migration log CSV."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
    )

    args = parser.parse_args()

    input_path = args.input_file.resolve()
    output_path = (
        input_path.with_name(
            f"{input_path.stem}_flat.csv"
        )
    )
    flatten_migration_log(
        input_path=input_path,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()
