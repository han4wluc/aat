
import os
import jsonlines
import requests
import json

from itertools import islice



import json

valid_column_names = [
    "id",
    "title",
    "url",
    "source",
    "source_type",
    "text",
    "date_published",
    "authors",
    "summaries",
    "doi",
    "comment",
    "abstract",
    "categories",
    "journal_ref",
    "author_comment",
    "primary_category",
    "data_last_modified",
    "status"
]

def filter_dict_by_valid_columns(data, valid_columns):
    """
    Filters a dictionary to only include keys that are in the list of valid columns.

    :param data: The dictionary to filter.
    :param valid_columns: The list of valid column names.
    :return: A new dictionary containing only the valid keys.
    """
    return {key: value for key, value in data.items() if key in valid_columns}


def generate_insert_string(table_name, data):
    """
    Generate an SQL INSERT string for the given table and data.

    :param table_name: Name of the table to insert into.
    :param data: Dictionary of column-value pairs.
    :return: The generated SQL INSERT string.
    """
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    query = f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})'
    return query

def escape_sqlite_value(value):
    """
    Escapes a single value for SQLite.

    :param value: The value to escape.
    :return: The escaped value as a string.
    """
    if value is None:
        return 'NULL'
    if isinstance(value, str):
        return f"'{value.replace("'", "''")}'"
    if isinstance(value, (dict, list)):
        return f"'{json.dumps(value).replace("'", "''")}'"
    return str(value)

def generate_insert_string_with_values(table_name, data):
    """
    Generate an SQL INSERT string with escaped values for the given table and data.

    :param table_name: Name of the table to insert into.
    :param data: Dictionary of column-value pairs.
    :return: The generated SQL INSERT string with values.
    """
    filtered_data = filter_dict_by_valid_columns(data, valid_column_names)
    query = generate_insert_string(table_name, filtered_data)
    escaped_values = [escape_sqlite_value(value) for value in filtered_data.values()]
    query_with_values = query.replace('?', '{}').format(*escaped_values)
    return query_with_values


def chunked_enumerate(arr, chunk_size):
    # Create a generator that yields chunks of the specified size
    for i in range(0, len(arr), chunk_size):
        yield i, arr[i:i + chunk_size]

source_folder = "./ard"

file_paths = []
for filename in os.listdir(source_folder):
    if filename.endswith(".jsonl"):
        file_paths.append(f"{os.path.join(source_folder, filename)}")


create_table_query = """
    CREATE TABLE IF NOT EXISTS articles (
        id CHAR(32) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        url VARCHAR(255) NOT NULL,
        source VARCHAR(255) NOT NULL,
        source_type VARCHAR(255) NOT NULL,
        comment VARCHAR(255),
        version VARCHAR(255),
        text TEXT,
        date_published DATETIME,
        authors JSONB,
        summaries JSONB,
        doi VARCHAR(255),
        abstract TEXT,
        categories JSONB,
        journal_ref VARCHAR(255),
        author_comment VARCHAR(255),
        primary_category VARCHAR(255),
        data_last_modified DATETIME,
        status VARCHAR(255),
        relevancy INT
    );
"""

res = requests.post("http://localhost:4001/db/execute?pretty&timings", json=[create_table_query])

def insert_jsonl_to_sqlite(chunk):
    # Ensure all keys are present in each item, providing defaults if necessary
    insert_strings = []
    for item in chunk:
        insert_string = generate_insert_string_with_values("articles", item)
        insert_strings.append(insert_string)
    return requests.post("http://localhost:4001/db/execute?pretty&timings", json=insert_strings)

for file_path in file_paths:
    with jsonlines.open(file_path) as reader:
        data = [item for item in reader]
        # print(data)

        for index, chunk in chunked_enumerate(data, 20):
            res = insert_jsonl_to_sqlite(chunk)
            print(res.json())


