import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
import numpy as np
import uuid
import re

def get_html_tables(html):
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.findAll("table", {"class": "wikitable"})
    return [{'id': str(uuid.uuid4()), 'table': table} for table in tables]

def parse_cell(cell):
    text = ' '.join(cell.stripped_strings)

    # Remove content within square brackets and replace multiple spaces with a single space
    text = re.sub(r'\[.*?\]', '', text).strip()
    text = re.sub(r'\s+', ' ', text)

    # Clean up numbers
    if text.replace(',', '').isnumeric():
        csv_text = text.replace(',', '')
    else:
        csv_text = text.replace('"', '""')
        # If the value contains special characters, enclose it in quotes.
        if any(ch in csv_text for ch in [',', '"', '\n', '\r']):
            csv_text = f'"{csv_text}"'

    return {'id': str(uuid.uuid4()), 'text': text, 'csv_text': csv_text}

def parse_table(table_tag):
    rows = []
    headers_length = len(table_tag.find("tr").findAll(['td', 'th']))  # Get the length of the first row (usually the headers)
    pending_inserts = [0] * headers_length  # initialize list to track pending inserts

    for tr in table_tag.findAll("tr"):
        row_cells = [None] * headers_length  # initialize cells for the current row

        cell_index = 0  # current cell index in the row

        for cell in tr.findAll(['td', 'th']):
            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))
            cell_data = parse_cell(cell)

            # move the index if we have pending inserts
            while cell_index < headers_length and pending_inserts[cell_index] > 0:
                cell_index += 1

            # place the cell data in the current position
            for _ in range(colspan):
                # check if we are exceeding the list boundaries
                if cell_index >= headers_length:
                    row_cells.extend([None] * (cell_index - headers_length + 1))
                    headers_length = len(row_cells)
                row_cells[cell_index] = cell_data
                cell_index += 1

            # if rowspan is greater than 1, we'll have to insert this cell in future rows
            if rowspan > 1:
                for j in range(cell_index - colspan, cell_index):
                    pending_inserts[j] += rowspan - 1

        # decrement the pending_inserts counters
        for j in range(len(pending_inserts)):
            if pending_inserts[j] > 0:
                pending_inserts[j] -= 1

        # fill None cells with empty data
        for j in range(len(row_cells)):
            if row_cells[j] is None:
                row_cells[j] = {'id': str(uuid.uuid4()), 'text': '', 'csv_text': ''}

        rows.append({'id': str(uuid.uuid4()), 'cells': row_cells})

    return rows



def extract_tables_from_wikipedia(url, target_table=None):
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to retrieve the webpage.")
        return

    tables_data = get_html_tables(response.text)

    # Initialize table counter
    table_counter = 1

    for table_info in tables_data:
        # If target_table is specified and it's not the current table, skip this iteration
        if target_table and table_counter != target_table:
            table_counter += 1
            continue

        parsed_rows = parse_table(table_info['table'])
        rows = [row['cells'] for row in parsed_rows]
        headers = [cell['text'] for cell in rows[0]]
        data = [[cell['csv_text'] for cell in row] for row in rows[1:]]
        df = pd.DataFrame(data)

        # Rename the columns after creating the DataFrame
        if len(df.columns) == len(headers):
            df.columns = headers
        else:
            print(f"Warning: Header mismatch. Expected {len(headers)} columns but got {len(df.columns)} columns.")

        # Remove footnotes
        df = df[~df[df.columns[0]].str.startswith('^')]
        df = df[~df[df.columns[0]].str.startswith('"^')]
        df = df[~df[df.columns[0]].str.startswith('""^')]

        # Remove columns that are entirely empty
        df = df.dropna(axis=1, how="all")

        # Remove columns that have only empty strings or whitespace after converting NaN to empty strings
        df = df.replace(r'^\s*$', np.nan, regex=True).dropna(axis=1, how='all')

        # Remove rows that are entirely NaN
        df = df.dropna(how='all')

        # Convert cells with only empty strings or whitespace to NaN
        df = df.replace(r'^\s*$', np.nan, regex=True)

        # Remove rows that are entirely NaN after converting empty strings to NaN
        df = df.dropna(how='all')

        # Check if DataFrame is empty or has 3 rows or less
        if df.empty or len(df) <= 2:  # Remember, headers are not counted in the DataFrame's row count
            print("The DataFrame is empty or has too few rows. Skipping saving process.")
        else:
            # Use the table counter for the filename
            csv_filename = f"table_{table_counter}.csv"
            df.to_csv(csv_filename, index=False)
            print(f"Saved {csv_filename}")

            # Increment table counter
            table_counter += 1

            # If we've saved our target table, we can break out of the loop
            if target_table and table_counter > target_table:
                break

if __name__ == "__main__":
    # Directly invoke the function with the desired URL
    extract_tables_from_wikipedia("https://en.wikipedia.org/wiki/COVID-19_pandemic_by_country_and_territory", target_table=3)
