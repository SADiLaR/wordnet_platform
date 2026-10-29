import csv
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from html import unescape
from pathlib import Path

import pymysql
from django.core.management.base import BaseCommand

from lex.models import (
    Language,
    PartOfSpeech,
    Relation,
    RelationType,
    Sense,
    SenseExample,
    Synset,
    SynsetExample,
    Word,
    Wordnet,
)


class Command(BaseCommand):
    help = "Migrate legacy MySQL WordNetLoom data to new PostgreSQL schema"

    def handle(self, *args, **options):
        self.setup_migration_logging()

        try:
            # NOTE: Add database credentials before running the script.
            conn = pymysql.connect(
                host="",
                port=3307,
                database="",
                user="",
                password="",
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )

            self.migrate_languages(conn)
            self.migrate_wordnets(conn)
            self.migrate_parts_of_speech()
            self.build_pos_id_map()

            self.migrate_synsets(conn)
            self.migrate_words_and_senses(conn)
            self.migrate_examples(conn)
            self.migrate_relation_types_and_relations(conn)

            conn.close()
            self.close_migration_logging()

        except Exception as e:
            self.log_skip(
                stage="command",
                reason="migration_aborted",
                error=e,
            )
            raise

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    # Data is first saved in JSON format because skipped rows can contain
    # different fields and nested values and then later converted to CSV for
    # easier viewing and filtering.

    def setup_migration_logging(self):
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.log_directory = Path("scripts/migration_logs") / run_timestamp
        self.log_directory.mkdir(parents=True, exist_ok=True)

        self.skipped_log_path = self.log_directory / "skipped_rows.csv"

        self.skipped_log_file = self.skipped_log_path.open(
            "w", newline="", encoding="utf-8-sig"
        )

        self.skipped_log_writer = csv.DictWriter(
            self.skipped_log_file,
            fieldnames=[
                "logged_at",
                "stage",
                "reason",
                "error_type",
                "error_message",
                "row",
                "context",
            ],
        )

        self.skipped_log_writer.writeheader()

        self.skip_counts = Counter()
        self.migrated_counts = Counter()

        self.total_logged_skips = 0
        self.total_migrated = 0

    @classmethod
    def json_safe(cls, value):
        """
        Convert values into JSON-compatible values.
        """

        if isinstance(value, dict):
            return {str(key): cls.json_safe(item) for key, item in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [cls.json_safe(item) for item in value]

        if isinstance(value, (bytes, bytearray)):
            binary_value = bytes(value)

            return {"hex": binary_value.hex(), "repr": repr(binary_value)}
        return value

    def log_skip(
        self,
        stage,
        reason,
        row=None,
        error=None,
        context=None,
    ):
        self.skip_counts[(stage, reason)] += 1
        self.total_logged_skips += 1

        row = self.json_safe(dict(row)) if row is not None else None

        safe_context = self.json_safe(context)

        self.skipped_log_writer.writerow(
            {
                "logged_at": datetime.now(UTC).isoformat(),
                "stage": stage,
                "reason": reason,
                "error_type": type(error).__name__ if error is not None else "",
                "error_message": str(error) if error is not None else "",
                "row": json.dumps(row, ensure_ascii=False) if row is not None else "",
                "context": json.dumps(safe_context, ensure_ascii=False)
                if safe_context is not None
                else "",
            }
        )

        if self.total_logged_skips % 1000 == 0:
            self.skipped_log_file.flush()

    def record_migrated(self, stage, count=1):
        """
        Record source rows that were processed successfully.

        This updates the summary only. Successfully migrated rows are not
        written to the detailed skipped-rows log.
        """
        self.migrated_counts[stage] += count
        self.total_migrated += count

    def close_migration_logging(self):

        summary_path = self.log_directory / "log_summary.csv"

        with summary_path.open("w", newline="", encoding="utf-8-sig") as summary_file:
            summary_writer = csv.DictWriter(
                summary_file, fieldnames=["stage", "reason", "count"]
            )

            summary_writer.writeheader()

            # Successfully migrated rows per stage
            for stage, count in sorted(self.migrated_counts.items()):
                summary_writer.writerow(
                    {"stage": stage, "reason": "migrated", "count": count}
                )

            # Skipped rows per stage and reason
            for (stage, reason), count in sorted(self.skip_counts.items()):
                summary_writer.writerow(
                    {"stage": stage, "reason": reason, "count": count}
                )

            summary_writer.writerow(
                {
                    "stage": "TOTAL",
                    "reason": "all_migrated_rows",
                    "count": self.total_migrated,
                }
            )

            summary_writer.writerow(
                {
                    "stage": "TOTAL",
                    "reason": "all_skipped_rows",
                    "count": self.total_logged_skips,
                }
            )

        print(f"Recorded {self.total_migrated} migrated rows")
        print(f"Logged {self.total_logged_skips} skipped rows")
        print(f"Migration summary written to {summary_path}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def clean_text(value):

        if value is None:
            return ""

        return " ".join(unescape(str(value)).split())

    @staticmethod
    def clean_example(value):
        if value is None:
            return ""

        text = unescape(str(value))
        text = re.compile('["“”]').sub("", text)
        text = re.sub(r"\\[nrt]", " ", text)
        text = " ".join(text.split())

        return text.strip(";: ")

    @staticmethod
    def normalize_relation_name(name):

        relation_prefixes = ("awn_", "pwn_")
        relation_name_aliases = {
            "holo_mem": "holo_member",
            "mero_mem": "mero_member",
            "causes": "cause",
            "sim": "similar_to",
            "has_hyperonym": "hyper",
        }

        if name.lower().startswith(relation_prefixes):
            name = name[4:]

        name = re.compile(r"\s*:\s*").sub("_", name)

        return relation_name_aliases.get(name, name)

    @staticmethod
    def split_word(text, language_id):
        """
        Only split when the word uses exactly one kind of separator
        ("/", "," or ";") and has no brackets. English words are excluded.
        """
        word_separators = "/,;"
        if language_id == "ENG":
            return [text], None

        found = [sep for sep in word_separators if sep in text]
        if not found:
            return [text], None

        if len(found) > 1:
            return [text], "not_split_mixed_separators"
        if "(" in text or ")" in text:
            return [text], "not_split_brackets"

        parts = []
        for part in text.split(found[0]):
            part = part.strip()

            if part and part not in parts:
                parts.append(part)

        if len(parts) < 2:
            return [text], None

        return parts, "split_word"

    # ------------------------------------------------------------------
    # Languages
    # ------------------------------------------------------------------

    def migrate_languages(self, conn):
        print("Migrating languages...")

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    identifier AS iso_code,
                    language_name AS name

                FROM tbl_lexicon
                """
            )
            rows = cursor.fetchall()

        migrated = 0
        skipped = 0

        for row in rows:
            iso_code = row["iso_code"]
            name = row["name"]

            try:
                Language.objects.create(
                    iso_code=iso_code,
                    name=name,
                )

            except Exception as e:
                skipped += 1

                self.log_skip(
                    stage="languages",
                    reason="db_upload_error",
                    row=row,
                    error=e,
                    context={"iso_code": iso_code, "name": name},
                )
                continue

            migrated += 1
            self.record_migrated("languages")

        print(f"Migrated {migrated} languages; skipped {skipped}")

    # ------------------------------------------------------------------
    # Wordnets
    # ------------------------------------------------------------------

    def migrate_wordnets(self, conn):
        print("Migrating wordnets...")

        self.wordnet_id_map = {}

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    id AS old_lexicon_id,
                    identifier AS language_id,
                    name

                FROM tbl_lexicon
                """
            )
            rows = cursor.fetchall()

        migrated = 0
        skipped = 0

        for row in rows:
            old_lexicon_id = row["old_lexicon_id"]
            language_id = row["language_id"]
            name = row["name"]

            try:
                wordnet = Wordnet.objects.create(name=name, language_id=language_id)

            except Exception as e:
                skipped += 1

                self.log_skip(
                    stage="wordnets",
                    reason="db_upload_error",
                    row=row,
                    error=e,
                    context={"language_id": language_id, "name": name},
                )
                continue

            self.wordnet_id_map[old_lexicon_id] = wordnet.id

            migrated += 1
            self.record_migrated("wordnets")

        print(f"Migrated {migrated} wordnets; skipped {skipped}")

    # ------------------------------------------------------------------
    # Parts of speech
    # ------------------------------------------------------------------

    def migrate_parts_of_speech(self):
        print("Migrating parts of speech...")

        parts_of_speech = [
            {"name": "noun", "short_name": "n"},
            {"name": "verb", "short_name": "v"},
            {"name": "adjective", "short_name": "a"},
            {"name": "adverb", "short_name": "r"},
            {"name": "unknown", "short_name": "u"},
            {"name": "multiple", "short_name": "m"},
        ]

        for pos in parts_of_speech:
            PartOfSpeech.objects.create(short_name=pos["short_name"], name=pos["name"])

    def build_pos_id_map(self):
        print("Building POS map...")

        self.pos_id_map = {}

        for pos in PartOfSpeech.objects.all():
            self.pos_id_map[pos.name] = pos.id

    # ------------------------------------------------------------------
    # Synsets
    # ------------------------------------------------------------------

    def migrate_synsets(self, conn):
        print("Migrating synsets...")

        self.synset_id_map = {}

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ts.id AS old_synset_id,
                    ts.lexicon_id AS old_lexicon_id,

                    MAX(tsa.definition) AS definition,
                    MAX(tsa.princeton_id) AS princeton_id,

                    MIN(LOWER(tals.value)) AS pos,
                    COUNT(DISTINCT LOWER(tals.value)) AS pos_count,
                    COUNT(DISTINCT old_sense.id) AS sense_count,
                    EXISTS (
                        SELECT 1
                        FROM tbl_synset_examples e
                        WHERE e.synset_attribute_id = ts.id
                        AND TRIM(e.example) <> ''
                    ) AS has_examples,
                    EXISTS (
                        SELECT 1
                        FROM tbl_synset_relation r
                        WHERE r.parent_synset_id = ts.id
                        OR r.child_synset_id = ts.id
                    ) AS has_relations

                FROM tbl_synset ts

                LEFT JOIN tbl_synset_attributes tsa
                    ON tsa.synset_id = ts.id

                LEFT JOIN tbl_sense old_sense
                    ON old_sense.synset_id = ts.id

                LEFT JOIN tbl_part_of_speech tpos
                    ON tpos.id = old_sense.part_of_speech_id

                LEFT JOIN
                    tbl_application_localised_string tals
                    ON tals.id = tpos.name_id

                GROUP BY
                    ts.id,
                    ts.lexicon_id
                """
            )
            rows = cursor.fetchall()

        migrated = 0
        skipped = 0
        batch = []

        def flush():
            nonlocal migrated, skipped
            inserted = self.insert_batch("synsets", Synset, batch)

            for row, synset in inserted:
                self.synset_id_map[row["old_synset_id"]] = synset.id

            migrated += len(inserted)
            skipped += len(batch) - len(inserted)
            batch.clear()

            print(f"  Migrated {migrated} synsets...")

        for row in rows:
            old_synset_id = row["old_synset_id"]
            old_lexicon_id = row["old_lexicon_id"]
            definition = self.clean_text(row["definition"])
            princeton_id = row["princeton_id"]
            pos_value = self.clean_text(row["pos"]).lower()
            pos_count = row["pos_count"]

            if pos_count == 0 or not pos_value:
                pos_value = "unknown"

            has_content = (
                definition
                or row["sense_count"] > 0
                or row["princeton_id"]
                or row["has_examples"]
                or row["has_relations"]
            )

            if not has_content:
                skipped += 1

                self.log_skip(
                    stage="synsets",
                    reason="empty_synset",
                    row=row,
                    context={"old_synset_id": old_synset_id},
                )
                continue

            # NOTE:
            # The current migration assumes that each synset has only one POS.
            # Need to discuss how to handle cases with multiple POS and update.
            if pos_count > 1:
                pos_value = "multiple"

            pos_id = self.pos_id_map.get(pos_value)

            batch.append(
                (
                    row,
                    Synset(
                        wordnet_id=self.wordnet_id_map[old_lexicon_id],
                        definition=definition,
                        status="complete",
                        display_name="",
                        pos_id=pos_id,
                        lexicalised=True,
                        princeton_id=princeton_id,
                    ),
                    {
                        "old_synset_id": old_synset_id,
                        "wordnet_id": self.wordnet_id_map[old_lexicon_id],
                        "pos_id": pos_id,
                        "definition": definition,
                        "definition_length": len(definition),
                        "princeton_id": princeton_id,
                    },
                )
            )

            if len(batch) >= BATCH_SIZE:
                flush()

        if batch:
            flush()

        print(f"Migrated {migrated} synsets; skipped {skipped}")

    # ------------------------------------------------------------------
    # Words and senses
    # ------------------------------------------------------------------
    def migrate_words_and_senses(self, conn):
        self.sense_id_map = {}
        self.word_id_map = {}

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    s.id AS old_sense_id,
                    s.synset_id AS old_synset_id,

                    tw.id AS old_word_id,
                    tw.word AS word_text,

                    tl.identifier AS language_id,

                    tsa.comment AS comment,

                    LOWER(tals.value) AS pos

                FROM tbl_sense s

                LEFT JOIN tbl_lexicon tl
                    ON tl.id = s.lexicon_id

                LEFT JOIN tbl_part_of_speech tpos
                    ON tpos.id = s.part_of_speech_id

                LEFT JOIN tbl_sense_attributes tsa
                    ON tsa.sense_id = s.id

                LEFT JOIN tbl_application_localised_string tals
                    ON tals.id = tpos.name_id

                LEFT JOIN tbl_word tw
                    ON tw.id = s.word_id
                """
            )
            rows = cursor.fetchall()

        migrated_words = 0
        skipped_words = 0
        entries = []
        splits = []

        migrated_senses = 0
        skipped_senses = 0

        word_txt_max = Word._meta.get_field("text").max_length
        for row in rows:
            word_text = self.clean_text(row["word_text"])
            parts, reason = self.split_word(word_text, row["language_id"])

            if reason:
                splits.append([row["language_id"], word_text, reason])

            for part in parts:
                entries.append((row, part))

        def word_key(row, text):
            return (
                text,
                row["language_id"],
                self.pos_id_map.get(row["pos"]),
            )

        # ---------------------------------------------------------
        # MIGRATE WORDS
        # ---------------------------------------------------------
        seen_word_keys = set()
        word_batch = []

        def flush_words():
            nonlocal migrated_words, skipped_words

            inserted = self.insert_batch("words", Word, word_batch)

            for _, word in inserted:
                self.word_id_map[(word.text, word.language_id, word.pos_id)] = word.id

            migrated_words += len(inserted)
            skipped_words += len(word_batch) - len(inserted)
            word_batch.clear()

            print(f"  Migrated {migrated_words} words...")

        for row, part in entries:
            old_word_id = row["old_word_id"]
            word_text, language_id, pos_id = word_key(row, part)

            if not word_text:
                skipped_words += 1

                self.log_skip(
                    stage="words",
                    reason="empty_word_text",
                    row=row,
                    context={"old_word_id": old_word_id},
                )
                continue

            if word_txt_max is not None and len(word_text) > word_txt_max:
                skipped_words += 1

                self.log_skip(
                    stage="words",
                    reason="word_text_too_long",
                    row=row,
                    context={
                        "old_word_id": old_word_id,
                        "word_length": len(word_text),
                        "maximum_length": word_txt_max,
                        "cleaned_word_text": word_text,
                    },
                )
                continue

            key = word_key(row, part)
            # Make sure not to upload duplicated words after text has been cleaned
            if key in seen_word_keys:
                continue

            seen_word_keys.add(key)

            word_batch.append(
                (
                    row,
                    Word(text=word_text, language_id=language_id, pos_id=pos_id),
                    {
                        "old_word_id": old_word_id,
                        "cleaned_word_text": word_text,
                        "language_id": language_id,
                        "pos_id": pos_id,
                    },
                )
            )

            if len(word_batch) >= BATCH_SIZE:
                flush_words()

        if word_batch:
            flush_words()

        # ---------------------------------------------------------
        # MIGRATE SENSES
        # ---------------------------------------------------------
        sense_batch = []

        def flush():
            nonlocal migrated_senses, skipped_senses

            inserted = self.insert_batch("senses", Sense, sense_batch)

            for row, sense in inserted:
                self.sense_id_map.setdefault(row["old_sense_id"], sense.id)

            migrated_senses += len(inserted)
            skipped_senses += len(sense_batch) - len(inserted)
            sense_batch.clear()

            print(f"  Migrated {migrated_senses} senses...")

        seen_senses = set()

        for row, part in entries:
            old_sense_id = row["old_sense_id"]
            old_synset_id = row["old_synset_id"]
            old_word_id = row["old_word_id"]
            comment = row["comment"] or ""
            new_synset_id = self.synset_id_map.get(old_synset_id)
            new_word_id = self.word_id_map.get(word_key(row, part))

            if new_word_id is None:
                skipped_senses += 1

                self.log_skip(
                    stage="senses",
                    reason="word_not_migrated",
                    row=row,
                    context={"old_word_id": old_word_id},
                )
                continue

            if new_synset_id is None and old_sense_id is not None:
                skipped_senses += 1

                self.log_skip(
                    stage="senses",
                    reason="synset_not_migrated",
                    row=row,
                    context={"old_synset_id": old_synset_id},
                )
                continue

            sense_key = (new_synset_id, new_word_id)

            if sense_key in seen_senses:
                skipped_senses += 1

                self.log_skip(
                    stage="senses",
                    reason="duplicate_sense",
                    row=row,
                    context={"new_synset_id": new_synset_id, "word_text": part},
                )
                continue

            seen_senses.add(sense_key)

            sense_batch.append(
                (
                    row,
                    Sense(
                        word_id=new_word_id, synset_id=new_synset_id, comment=comment
                    ),
                    {
                        "old_sense_id": old_sense_id,
                        "old_synset_id": old_synset_id,
                        "new_synset_id": new_synset_id,
                        "old_word_id": old_word_id,
                        "new_word_id": new_word_id,
                    },
                )
            )

            if len(sense_batch) >= BATCH_SIZE:
                flush()

        if sense_batch:
            flush()

        print("Words:")
        print(f"  Migrated: {migrated_words}")
        print(f"  Skipped:  {skipped_words}")

        print("Senses:")
        print(f"  Migrated:   {migrated_senses}")
        print(f"  Skipped:    {skipped_senses}")
        # Write split words to file
        path = self.log_directory / "word_splits.csv"
        with path.open("w") as f:
            writer = csv.writer(f)
            writer.writerow(["language", "original_text", "reason"])
            writer.writerows(splits)

    # ------------------------------------------------------------------
    # Examples
    # ------------------------------------------------------------------

    def migrate_examples(self, conn):
        print("Migrating examples...")

        sources = (
            ("synset", SynsetExample, self.synset_id_map),
            ("sense", SenseExample, self.sense_id_map),
        )

        for table, model, id_map in sources:
            self.migrate_example_table(conn, table, model, id_map)

    def migrate_example_table(self, conn, table, model, id_map):
        stage = f"examples_{table}"

        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    tse.id AS old_example_id,
                    tse.{table}_attribute_id AS old_{table}_id,
                    tse.example AS example_text

                FROM tbl_{table}_examples tse

                """
            )
            rows = cursor.fetchall()

        # Get the maximum number of characters allowed for the Example field.
        example_max_len = model._meta.get_field("text").max_length
        migrated = 0
        skipped = 0
        seen = set()
        batch = []

        def flush():
            nonlocal migrated, skipped

            inserted = self.insert_batch(stage, model, batch)

            migrated += len(inserted)
            skipped += len(batch) - len(inserted)
            batch.clear()

            print(f"  Migrated {migrated} {table} examples...")

        for row in rows:
            old_id = row[f"old_{table}_id"]
            example_text = self.clean_example(row["example_text"])

            if not example_text:
                skipped += 1

                self.log_skip(
                    stage=stage,
                    reason="empty_example",
                    row=row,
                    context={f"old_{table}_id": old_id},
                )
                continue

            new_id = id_map.get(old_id)

            if new_id is None:
                skipped += 1

                self.log_skip(
                    stage=stage,
                    reason=f"{table}_not_migrated",
                    row=row,
                    context={f"old_{table}_id": old_id},
                )
                continue

            if len(example_text) > example_max_len:
                skipped += 1

                self.log_skip(
                    stage=stage,
                    reason="example_text_too_long",
                    row=row,
                    context={
                        f"new_{table}_id": new_id,
                        "example_length": len(example_text),
                        "maximum_length": example_max_len,
                        "cleaned_example_text": example_text,
                    },
                )
                continue

            key = (new_id, example_text)
            if key in seen:
                skipped += 1

                self.log_skip(
                    stage=stage,
                    reason="duplicate_after_cleaning",
                    row=row,
                    context={
                        f"new_{table}_id": new_id,
                        "cleaned_example_text": example_text,
                    },
                )
                continue

            seen.add(key)

            batch.append(
                (
                    row,
                    model(**{f"{table}_id": new_id, "text": example_text}),
                    {
                        "new_id": new_id,
                        "old_id": old_id,
                        "example": example_text,
                        "example_length": len(example_text),
                    },
                )
            )

            if len(batch) >= BATCH_SIZE:
                flush()

        if batch:
            flush()

        print(f"Migrated {migrated} {table} examples; skipped {skipped}")

    # ------------------------------------------------------------------
    # Relation types and relations
    # ------------------------------------------------------------------

    def migrate_relation_types_and_relations(self, conn):
        print("Migrating relation types and relations...")

        self.relation_type_id_map = {}
        relation_type_name_map = {}
        merged_names = defaultdict(set)

        migrated_relation_types = 0
        migrated_relations = 0
        skipped = 0

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    trt.id AS old_relation_type_id,
                    COALESCE(
                        NULLIF(TRIM(short_display_text.value), ''),
                        NULLIF(TRIM(relation_name.value), '')
                    ) AS relation_type_name

                FROM tbl_relation_type AS trt

                LEFT JOIN tbl_application_localised_string
                    AS short_display_text
                    ON short_display_text.id = trt.short_display_text_id

                LEFT JOIN tbl_application_localised_string
                    AS relation_name
                    ON relation_name.id = trt.name_id
                """
            )
            relation_type_rows = cursor.fetchall()

        for row in relation_type_rows:
            old_relation_type_id = row["old_relation_type_id"]
            original_name = row["relation_type_name"]

            if not original_name:
                skipped += 1

                self.log_skip(
                    stage="relation_types",
                    reason="empty_relation_type_name",
                    row=row,
                )
                continue

            relation_type_name = self.normalize_relation_name(original_name)
            merged_names[relation_type_name].add(original_name)
            existing_id = relation_type_name_map.get(relation_type_name)

            if existing_id is not None:
                self.relation_type_id_map[old_relation_type_id] = existing_id
                continue

            try:
                relation_type = RelationType.objects.create(name=relation_type_name)

            except Exception as e:
                skipped += 1

                self.log_skip(
                    stage="relation_types",
                    reason="db_upload_error",
                    row=row,
                    error=e,
                    context={"relation_type_name": relation_type_name},
                )
                continue

            relation_type_name_map[relation_type_name] = relation_type.id
            self.relation_type_id_map[old_relation_type_id] = relation_type.id

            if relation_type:
                migrated_relation_types += 1
                self.record_migrated("relation_types")

        # Show which differently spelled names were merged
        for name, originals in sorted(merged_names.items()):
            if len(originals) > 1:
                print(f"  {name} <- {', '.join(sorted(originals))}")

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    tsr.parent_synset_id AS old_synset_from_id,
                    tsr.child_synset_id AS old_synset_to_id,
                    tsr.synset_relation_type_id AS old_relation_type_id,

                    LOWER(tals.value) AS display_name

                FROM tbl_synset_relation tsr

                LEFT JOIN tbl_relation_type trt
                    ON trt.id = tsr.synset_relation_type_id

                LEFT JOIN
                    tbl_application_localised_string tals
                    ON tals.id = trt.display_text_id
                """
            )
            relation_rows = cursor.fetchall()

        seen_relations = set()
        batch = []

        def flush():
            nonlocal migrated_relations, skipped

            inserted = self.insert_batch("relations", Relation, batch)

            migrated_relations += len(inserted)
            skipped += len(batch) - len(inserted)
            batch.clear()

            print(f"  Migrated {migrated_relations} relations...")

        for row in relation_rows:
            old_synset_from_id = row["old_synset_from_id"]
            old_synset_to_id = row["old_synset_to_id"]
            old_relation_type_id = row["old_relation_type_id"]

            # Same normalisation as the type name, so a relation of type
            # holo_member does not keep the display name "holo_mem".
            display_name = (
                self.normalize_relation_name(row["display_name"])
                if row["display_name"] is not None
                else None
            )

            new_synset_from_id = self.synset_id_map.get(old_synset_from_id)
            new_synset_to_id = self.synset_id_map.get(old_synset_to_id)
            new_relation_type_id = self.relation_type_id_map.get(old_relation_type_id)

            if new_synset_from_id is None:
                skipped += 1

                self.log_skip(
                    stage="relations",
                    reason=("parent_synset_not_migrated"),
                    row=row,
                    context={"old_synset_from_id": old_synset_from_id},
                )
                continue

            if new_synset_to_id is None:
                skipped += 1

                self.log_skip(
                    stage="relations",
                    reason=("child_synset_not_migrated"),
                    row=row,
                    context={"old_synset_to_id": old_synset_to_id},
                )
                continue

            if new_relation_type_id is None:
                skipped += 1

                self.log_skip(
                    stage="relations",
                    reason=("relation_type_not_migrated"),
                    row=row,
                    context={"old_relation_type_id": old_relation_type_id},
                )
                continue

            relation_key = (new_synset_from_id, new_synset_to_id, new_relation_type_id)

            if relation_key in seen_relations:
                skipped += 1

                self.log_skip(
                    stage="relations",
                    reason="duplicate_relation",
                    row=row,
                    context={
                        "new_synset_from_id": new_synset_from_id,
                        "new_synset_to_id": new_synset_to_id,
                        "new_relation_type_id": new_relation_type_id,
                    },
                )
                continue

            seen_relations.add(relation_key)

            batch.append(
                (
                    row,
                    Relation(
                        synset_from_id=new_synset_from_id,
                        synset_to_id=new_synset_to_id,
                        type_id=new_relation_type_id,
                    ),
                    {
                        "new_synset_from_id": new_synset_from_id,
                        "new_synset_to_id": new_synset_to_id,
                        "new_relation_type_id": new_relation_type_id,
                        "display_name": display_name,
                    },
                )
            )

            if len(batch) >= BATCH_SIZE:
                flush()

        if batch:
            flush()

        print(
            f"Migrated {migrated_relation_types} relation types and ",
            f"{migrated_relations} relations; skipped {skipped}",
        )
