# Poliedro/Batch rename Python
# https://github.com/Yudi/scripts
#
# Usage: python batch_rename.py <data.csv> <directory>

import os
import glob
import csv
from typing import TypedDict, List
import dateparser
import argparse

# Validate if the directory exists
def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

# Validate if the file exists
def csv_path(string):
    if os.path.isfile(string):
        return string
    else:
        raise FileNotFoundError(string)

# CLI argument parser
parser = argparse.ArgumentParser()
parser.add_argument('csvpath', type=csv_path)
parser.add_argument('directorypath', type=dir_path)

# Define the structure of the CSV data
class RowData(TypedDict):
    date: str
    disciplina: str
    frente: str
    conteudo: str

args = parser.parse_args()

csvpath = args.csvpath
directory = args.directorypath
absolutedirectory = os.path.abspath(directory)

# Count the number of files in the directory
num_files = len(glob.glob(f"{absolutedirectory}/[!.]*.mp4"))

# Read the CSV file and parse the data
data: List[RowData] = []

with open(csvpath, "r") as csvfile:
    csvreader = csv.reader(csvfile, delimiter=';')
    next(csvreader)  # Skip the header

    for i, line in enumerate(csvreader):
        # If line is empty or has less than 5 columns, throw
        if len(line) < 5:
            raise Exception(f"Line {i + 1} is empty or has less than 5 columns. Also check delimeter")

        tempRow: RowData = {}

        tempDate = dateparser.parse(line[0], languages=['pt'])

        if tempDate is None:
            tempRow['date'] = line[0]
        else:
            tempRow['date'] = tempDate.strftime("%m-%d")

        tempRow['disciplina'] = line[2]
        tempRow['frente'] = line[3]
        tempRow['conteudo'] = line[4].replace("/", "-").replace(":", " -")

        data.append(tempRow)

# Check if the number of files matches the number of rows in the CSV
row_count = len(data)
if num_files != row_count * 2:
    raise Exception(f"Number of files ({num_files}) and number of rows times 2 ({row_count * 2}) do not match.")

# Rename files
i = 0
side = "esq"
isEven = False

for filename in sorted(glob.glob(f"{absolutedirectory}/[!.]*.mp4")):
    info = data[i]
    new_name = f"{info['disciplina']} - {info['frente']} - {info['date']} - {info['conteudo']} - {side}.mp4"
    new_path = os.path.join(absolutedirectory, new_name)
    os.rename(filename, new_path)

    if not isEven:
        side = "dir"
        isEven = True
    else:
        side = "esq"
        i += 1
        isEven = False
