import argparse
import csv
import re
import sys
from datetime import datetime, date
from pathlib import Path

INPUT_DIR = Path("csv-export")

EXPECTED_NAB_HEADER = [
    "Date", "Amount", "Account Number", "", "Transaction Type",
    "Transaction Details", "Balance", "Category", "Merchant Name", "Processed On",
]
EXPECTED_BANKAUST_HEADER = [
    "Effective Date", "Entered Date", "Transaction Description", "Amount", "Balance",
]
OUTPUT_HEADER = ["Date", "Payee", "Memo", "Amount"]


def parse_date_nab(raw: str) -> str:
    return datetime.strptime(raw.strip(), "%d %b %y").strftime("%Y-%m-%d")


def parse_date_ddmmyyyy(raw: str) -> str:
    return datetime.strptime(raw.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")


def clean_amount_bankaust(raw: str) -> str:
    return raw.strip().replace("$", "")


def clean_amount_commbank(raw: str) -> str:
    return raw.strip().lstrip("+")


def build_nab_memo(merchant: str, category: str, details: str) -> str:
    parts = [p for p in [merchant, category, details] if p]
    return " | ".join(parts)


def validate_rows(rows: list, filepath: str):
    for i, row in enumerate(rows, start=1):
        if len(row) != 4:
            print(f"Error: Row {i} in {filepath} has {len(row)} columns, expected 4", file=sys.stderr)
            sys.exit(1)
        try:
            datetime.strptime(row[0], "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date on row {i} in {filepath}: '{row[0]}'", file=sys.stderr)
            sys.exit(1)
        try:
            float(row[3])
        except ValueError:
            print(f"Error: Invalid amount on row {i} in {filepath}: '{row[3]}'", file=sys.stderr)
            sys.exit(1)


def process_nab(reader, rows_out: list, filepath: str):
    header = next(reader)
    if header != EXPECTED_NAB_HEADER:
        print(f"Error: NAB header mismatch in {filepath}", file=sys.stderr)
        print(f"  Expected: {EXPECTED_NAB_HEADER}", file=sys.stderr)
        print(f"  Got:      {header}", file=sys.stderr)
        sys.exit(1)

    for i, row in enumerate(reader, start=2):
        try:
            dt = parse_date_nab(row[0])
        except ValueError:
            print(f"Error: Failed to parse date on row {i}: '{row[0]}'", file=sys.stderr)
            sys.exit(1)

        amount = row[1].strip()
        details = row[5].strip()
        category = row[7].strip()
        merchant = row[8].strip()
        memo = build_nab_memo(merchant, category, details)
        rows_out.append([dt, details, memo, amount])


def process_bankaust(reader, rows_out: list, filepath: str):
    header = next(reader)
    if header != EXPECTED_BANKAUST_HEADER:
        print(f"Error: BankAust header mismatch in {filepath}", file=sys.stderr)
        print(f"  Expected: {EXPECTED_BANKAUST_HEADER}", file=sys.stderr)
        print(f"  Got:      {header}", file=sys.stderr)
        sys.exit(1)

    for i, row in enumerate(reader, start=2):
        try:
            dt = parse_date_ddmmyyyy(row[1])
        except ValueError:
            print(f"Error: Failed to parse date on row {i}: '{row[1]}'", file=sys.stderr)
            sys.exit(1)

        amount = clean_amount_bankaust(row[3])
        description = row[2].strip()
        rows_out.append([dt, description, description, amount])


def process_commbank(reader, rows_out: list, filepath: str):
    for i, row in enumerate(reader, start=1):
        if len(row) != 4:
            print(f"Error: CommBank row {i} has {len(row)} columns, expected 4", file=sys.stderr)
            sys.exit(1)

        try:
            dt = parse_date_ddmmyyyy(row[0])
        except ValueError:
            print(f"Error: Failed to parse date on row {i}: '{row[0]}'", file=sys.stderr)
            sys.exit(1)

        amount = clean_amount_commbank(row[1])
        description = row[2].strip()
        rows_out.append([dt, description, description, amount])


def detect_bank(filepath: Path) -> str:
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        first_row = next(reader)

    if first_row == EXPECTED_NAB_HEADER:
        return "nab"
    if first_row == EXPECTED_BANKAUST_HEADER:
        return "bank-aust"
    if len(first_row) == 4 and re.match(r"\d{2}/\d{2}/\d{4}$", first_row[0].strip()):
        return "commbank"

    return ""


def process_file(filepath: Path, bank: str):
    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        if bank == "nab":
            process_nab(reader, rows, str(filepath))
        elif bank == "bank-aust":
            process_bankaust(reader, rows, str(filepath))
        elif bank == "commbank":
            process_commbank(reader, rows, str(filepath))

    if not rows:
        print(f"Error: No data rows found in {filepath}", file=sys.stderr)
        sys.exit(1)

    validate_rows(rows, str(filepath))

    out_dir = Path("processed")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{bank}-{date.today().strftime('%Y%m%d')}.csv"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(OUTPUT_HEADER)
        writer.writerows(rows)

    print(f"  {filepath.name} -> {out_path} ({len(rows)} rows)")


def main():
    parser = argparse.ArgumentParser(description="Convert bank CSV to YNAB format")
    parser.add_argument("input_file", nargs="?", type=Path, help="Path to bank CSV file")
    bank_group = parser.add_mutually_exclusive_group()
    bank_group.add_argument("--nab", action="store_const", const="nab", dest="bank")
    bank_group.add_argument("--commbank", action="store_const", const="commbank", dest="bank")
    bank_group.add_argument("--bank-aust", action="store_const", const="bank-aust", dest="bank")
    args = parser.parse_args()

    # Batch mode: no args, process all CSVs in csv-export/
    if args.input_file is None and args.bank is None:
        if not INPUT_DIR.is_dir():
            print(f"Error: Directory not found: {INPUT_DIR}", file=sys.stderr)
            sys.exit(1)

        files = sorted(INPUT_DIR.glob("*.csv"))
        if not files:
            print(f"Error: No CSV files in {INPUT_DIR}", file=sys.stderr)
            sys.exit(1)

        skipped = []
        processed = 0
        for f in files:
            bank = detect_bank(f)
            if not bank:
                skipped.append(f.name)
                continue
            process_file(f, bank)
            processed += 1

        if skipped:
            print(f"Skipped (unrecognized format): {', '.join(skipped)}")
        if processed == 0:
            print("Error: No files matched a known bank format", file=sys.stderr)
            sys.exit(1)
        return

    # Single-file mode
    if args.input_file is None or args.bank is None:
        parser.error("Provide both an input file and a bank flag, or run with no args for batch mode")

    if not args.input_file.is_file():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    process_file(args.input_file, args.bank)


if __name__ == "__main__":
    main()
