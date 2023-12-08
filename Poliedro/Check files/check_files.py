# Poliedro/Check files Python
# https://github.com/Yudi/scripts
#
# Usage: python check_files.py <data.csv> <directory>

import os, glob
import csv
from types import NoneType
from typing import TypedDict, List
import dateparser
import argparse
import re
from natsort import natsorted
from unidecode import unidecode

def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

def csv_path(string):
    if os.path.isfile(string):
        return string
    else:
        raise FileNotFoundError(string)

parser = argparse.ArgumentParser()
parser.add_argument('csvpath', type=csv_path)
parser.add_argument('directorypath', type=dir_path)

class RowData(TypedDict):
    date: str
    disciplina: str
    frente: str
    conteudo: str

args = parser.parse_args()

csvpath = args.csvpath
directory = args.directorypath
workingDirectory = os.path.abspath(directory)

# Duplicate directory
if os.path.exists(f"{workingDirectory}/../{os.path.basename(workingDirectory)}_copy"):
    raise Exception("Directory already exists")
else:
    os.mkdir(f"{workingDirectory}/../{os.path.basename(workingDirectory)}_copy")

# Copy files to $PWD/../directory_copy
os.system(f'cp -c -r "{workingDirectory}/"* "{workingDirectory}/../{os.path.basename(workingDirectory)}_copy"')

# Set the new directory as the current directory
workingDirectory = f"{workingDirectory}/../{os.path.basename(workingDirectory)}_copy"

# Get the number of files in the directory
num_files = len(glob.glob(f"{workingDirectory}/[!.]*"))

# Open the CSV file
csvfile = open(csvpath, "r")

csvreader = csv.reader(csvfile,delimiter=';')
next(csvreader)

row_count = 0

parsedDataset = {}

for i, line in enumerate(csvreader):

    tempRow: RowData = {}

    tempDate= dateparser.parse(line[0], languages=['pt'])

    if type(tempDate) is NoneType:
        tempRow['date'] = line[0]
    else:
        tempRow['date'] = unidecode(tempDate.strftime("%m-%d"))

    tempRow['disciplina'] = unidecode(line[2])
    tempRow['frente'] = unidecode(line[3])
    tempRow['conteudo'] = unidecode(line[4].replace("/", "-").replace(":", " -"))
    row_count += 1

    # TODO: Fix me
    if tempRow['frente'] == "":
        tempRow['frente'] = "empty"
        
    if not tempRow['frente'] in parsedDataset:
        parsedDataset[tempRow['frente']] = []

    parsedDataset[tempRow['frente']].append(tempRow)

# if num_files != row_count * 2:
#     raise Exception("Number of files in the directory and number of rows in the CSV file are not equal")

directoryFileList = []

expression = r"\-(.*?)\-"
for filename in glob.glob(f"{workingDirectory}/[!.]*"):
    match = re.search(expression, filename)

    matchItem = match.group(0).strip(" -")

    if matchItem == "":
        matchItem = "empty"

    if not os.path.exists(f"{workingDirectory}/{matchItem}"):
        os.mkdir(f"{workingDirectory}/{matchItem}")

    os.system(f"mv '{filename}' '{workingDirectory}/{matchItem}'")

for key in parsedDataset:
    i = 0 
    j = False

    # Sort the items in the key by date, if date is the same sort by conteudo
    parsedDataset[key] = sorted(parsedDataset[key], key=lambda k: (k['date'], k['conteudo']))

    directoryFileList = natsorted(glob.glob(f"{workingDirectory}/{key}/*"))

    print(f"\n\nChecking {key}...")

    keyLength = len(parsedDataset[key])

    # For every file in the key directory
    for filename in directoryFileList:
        expression = rf"^\b({re.escape(parsedDataset[key][i]['disciplina'])})( - )({re.escape(parsedDataset[key][i]['frente'])})( - )({re.escape(parsedDataset[key][i]['date'])})( - )({re.escape(parsedDataset[key][i]['conteudo'])})( - )((esq)|(dir))\b"

        shortFilename = unidecode(os.path.basename(filename))
        if not re.search(expression, shortFilename):
            print(f"   Found: {shortFilename}")
            print(f"Expected: {parsedDataset[key][i]['disciplina']} - {parsedDataset[key][i]['frente']} - {parsedDataset[key][i]['date']} - {parsedDataset[key][i]['conteudo']} - esq|dir\n")

        if j == False:
               j = True
        elif j == True:
            if i == keyLength - 1:
                break
            i += 1
            j = False

os.system(f"rm -rf '{workingDirectory}'")