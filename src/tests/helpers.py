from io import BytesIO


def create_csv_file(content: str, filename="contacts.csv"):
    return ("file", (filename, BytesIO(content.encode()), "text/csv"))
