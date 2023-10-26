# Wikipedia Table Extractor

This project provides a Python script to extract tables from Wikipedia pages and save them as CSV files.

## Overview

The script uses the requests library to fetch the webpage and BeautifulSoup from bs4 to parse the HTML. It then detects tables marked as "wikitable" on the Wikipedia page, extracts their content, and saves them as separate CSV files. There's also a provision to target a specific table.