# ynab-util

Converts bank-exported CSV files into a YNAB-compatible CSV format.

Supports three Australian banks: **NAB**, **Commonwealth Bank**, and **Bank Australia**. This tool normalizes each bank's unique CSV format into columns `Date`, `Payee`, `Memo`, `Amount`.

## Output format

```csv
"Date","Payee","Memo","Amount"
"2026-05-09","Store Name","detail","-34.00"
"2026-05-09","Income source","detail","34.00"
```

- `Date`: `YYYY-MM-DD`
- `Amount`: signed decimal (negative for outflow)
- `Payee`: raw transaction description from the bank
- `Memo`: raw transaction description (+ `Merchant Name` and `Category` for NAB transactions, if available)

**NOTE:** The payee field is left intentionally noisy. On import, YNAB will match keywords within and use auto-naming rules to match to existing payees wherever possible.

## Usage

Drop bank CSV exports into `csv-export/` and run:

```sh
uv run clean-csv
```

The script auto-detects each bank's format based on the CSV header and writes output to `processed/<bank>-<YYYYMMDD>.csv`. Same-day output is overwritten. Unrecognized files are skipped.

To process a single file with an explicit bank flag:

```sh
uv run clean-csv path/to/file.csv --nab | --commbank | --bank-aust
```

## Column mapping

### NAB

**Headers:** `Date`, `Amount`, `Account Number`, (empty), `Transaction Type`, `Transaction Details`, `Balance`, `Category`, `Merchant Name`, `Processed On`

| Output | Input | Notes |
|--------|-------|-------|
| `Date` | `Date` | `DD Mon YY` → `YYYY-MM-DD` |
| `Payee` | `Transaction Details` | As-is |
| `Memo` | `Merchant Name` + `Category` + `Transaction Details` | Joined with ` \| `, empty fields omitted |
| `Amount` | `Amount` | As-is |

Dropped: `Account Number`, (empty), `Transaction Type`, `Balance`, `Processed On`

### BankAust

**Headers:** `Effective Date`, `Entered Date`, `Transaction Description`, `Amount`, `Balance`

| Output | Input | Notes |
|--------|-------|-------|
| `Date` | `Entered Date` | `DD/MM/YYYY` → `YYYY-MM-DD` |
| `Payee` | `Transaction Description` | As-is |
| `Memo` | `Transaction Description` | As-is |
| `Amount` | `Amount` | Strip `$` prefix |

Dropped: `Effective Date`, `Balance`

### CommBank

**Headers:** None — columns identified by position. Detected by checking first row has 4 columns and starts with a `DD/MM/YYYY` date.

| Output | Input | Notes |
|--------|-------|-------|
| `Date` | col 0 (`Date`) | `DD/MM/YYYY` → `YYYY-MM-DD` |
| `Payee` | col 2 (`Description`) | As-is |
| `Memo` | col 2 (`Description`) | As-is |
| `Amount` | col 1 (`Amount`) | Strip `+` prefix |

Dropped: col 3 (`Balance`)

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
