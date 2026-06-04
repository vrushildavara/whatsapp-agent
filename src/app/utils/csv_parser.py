import csv
import io
import re
from typing import List, Tuple

from fastapi import UploadFile

# Pattern to detect component-wise column headers: body_1, header_1, button_0
_COMPONENT_COL_RE = re.compile(r"^(header|body|button)_(\d+)$", re.IGNORECASE)


def _parse_column_types(header_row: list[str]) -> list[dict]:
    """
    Determine the component type for each data column (columns[1:]).

    Returns a list of descriptors, one per column after phone_number:
      {"type": "body",   "param_index": 0}   ← body_1  (0-based)
      {"type": "header", "param_index": 0}   ← header_1
      {"type": "button", "btn_index": 0}     ← button_0
      {"type": "body",   "param_index": N}   ← legacy positional fallback
    """
    col_headers = [h.strip().lower() for h in header_row[1:]]
    has_typed = any(_COMPONENT_COL_RE.match(h) for h in col_headers)

    result: list[dict] = []
    for idx, col in enumerate(col_headers):
        m = _COMPONENT_COL_RE.match(col)
        if m:
            comp_type = m.group(1).lower()
            num = int(m.group(2))
            if comp_type == "button":
                result.append({"type": "button", "btn_index": num})
            else:
                result.append({"type": comp_type, "param_index": num - 1})
        else:
            # Legacy positional column → body text parameter
            result.append({"type": "body", "param_index": idx})

    return result


def _build_components(row: list[str], col_types: list[dict]) -> list[dict] | None:
    """
    Build a Meta-API-compatible components list from CSV row values.

    Returns None if there are no non-empty values.
    """
    header_params: dict[int, str] = {}
    body_params: dict[int, str] = {}
    button_params: dict[int, str] = {}

    for i, col_type in enumerate(col_types):
        col_pos = i + 1  # offset for phone column
        if col_pos >= len(row):
            break
        value = row[col_pos].strip() if row[col_pos] else ""
        if not value:
            continue

        if col_type["type"] == "header":
            header_params[col_type["param_index"]] = value
        elif col_type["type"] == "body":
            body_params[col_type["param_index"]] = value
        elif col_type["type"] == "button":
            button_params[col_type["btn_index"]] = value

    components: list[dict] = []

    if header_params:
        params = [
            {"type": "text", "text": v}
            for _, v in sorted(header_params.items())
        ]
        components.append({"type": "header", "parameters": params})

    if body_params:
        params = [
            {"type": "text", "text": v}
            for _, v in sorted(body_params.items())
        ]
        components.append({"type": "body", "parameters": params})

    for btn_idx, payload in sorted(button_params.items()):
        components.append({
            "type": "button",
            "sub_type": "quick_reply",
            "index": btn_idx,
            "parameters": [{"type": "payload", "payload": payload}],
        })

    return components if components else None


def _normalize_phone(phone: str) -> str | None:
    phone = str(phone).strip()

    # Handle scientific notation (e or E)
    if "e" in phone.lower():
        num = float(phone)

        # Reject very small numbers (invalid phones)
        if num < 1e9:  # less than 10-digit number
            return None

        phone = str(int(num))

    # Remove spaces
    phone = phone.replace(" ", "")

    # Remove decimal leftovers (just in case)
    if "." in phone:
        return None

    # Already international format
    if phone.startswith("+"):
        return phone

    # Indian number with country code but no "+"
    if phone.startswith("91") and len(phone) == 12:
        return "+" + phone

    # Plain 10-digit Indian number
    if len(phone) == 10 and phone.isdigit():
        return "+91" + phone

    return None


async def parse_csv_file(
    file: UploadFile, max_rows: int = 50000
) -> Tuple[List[dict], List[dict]]:
    """
    Parse CSV file with contacts.

    Args:
        file: Uploaded CSV file
        max_rows: Maximum number of rows to process

    Returns:
        Tuple of (valid_contacts, invalid_rows)
        Each valid_contact: {"phone_number": str, "variables": dict}
        Each invalid_row: {"row_number": int, "phone_number": str, "error": str}
    """
    valid_contacts = []
    invalid_rows = []

    try:
        content = await file.read()
        text_content = content.decode("utf-8")
        reader = csv.reader(io.StringIO(text_content))

        rows = list(reader)

        if not rows:
            return valid_contacts, [
                {
                    "row_number": 0,
                    "phone_number": "",
                    "error": "CSV file is empty",
                }
            ]

        # Determine component type for each data column from the header row
        col_types = _parse_column_types(rows[0]) if rows else []

        # Process data rows (skip header)
        for row_idx, row in enumerate(
            rows[1:], start=2
        ):  # Start from row 2 (accounting for header)
            if len(rows) > max_rows:
                invalid_rows.append(
                    {
                        "row_number": row_idx,
                        "phone_number": row[0] if row else "",
                        "error": f"CSV exceeds maximum of {max_rows} rows",
                    }
                )
                break

            if not row or not row[0]:
                continue  # Skip empty rows

            phone_number = _normalize_phone(row[0])

            # Validate phone number (E.164 format)
            if not is_valid_e164(phone_number):
                invalid_rows.append(
                    {
                        "row_number": row_idx,
                        "phone_number": phone_number,
                        "error": "Invalid E.164 phone number format",
                    }
                )
                continue

            # Clean phone number: remove '+' prefix
            clean_phone_number = phone_number.lstrip("+")

            # Check for duplicates
            if any(c["phone_number"] == clean_phone_number for c in valid_contacts):
                invalid_rows.append(
                    {
                        "row_number": row_idx,
                        "phone_number": phone_number,
                        "error": "Duplicate phone number",
                    }
                )
                continue

            # Build component-wise variables from remaining columns
            components = _build_components(row, col_types) if col_types else None

            valid_contacts.append(
                {
                    "phone_number": clean_phone_number,
                    "variables": components,
                }
            )

        return valid_contacts, invalid_rows

    except UnicodeDecodeError:
        return (
            valid_contacts,
            [
                {
                    "row_number": 0,
                    "phone_number": "",
                    "error": "File must be UTF-8 encoded CSV",
                }
            ],
        )
    except Exception as e:
        return (
            valid_contacts,
            [
                {
                    "row_number": 0,
                    "phone_number": "",
                    "error": f"Error parsing CSV: {str(e)}",
                }
            ],
        )


def is_valid_e164(phone_number: str) -> bool:
    """
    Validate E.164 phone number format.

    E.164 format: +[country code][number]
    - Must start with +
    - 1-3 digit country code
    - Up to 12 digits for the number
    - Total: 10-15 characters including +
    """
    # Basic E.164 validation pattern
    pattern = r"^\+[1-9]\d{9,14}$"
    return bool(re.match(pattern, phone_number))
