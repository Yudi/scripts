# Poliedro/Batch rename Python
# https://github.com/Yudi/scripts
#
# Usage: python batch_rename.py <data.csv> <directory>

import os, glob
import csv
from types import NoneType
from typing import TypedDict, List
import dateparser
import argparse

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
absolutedirectory = os.path.abspath(directory)

# Get the number of files in the directory
num_files = len(glob.glob(f"{absolutedirectory}/[!.]*.mp4"))

# Open the CSV file
csvfile = open(csvpath, "r")

csvreader = csv.reader(csvfile,delimiter=';')
next(csvreader)


row_count = 0


data: List[RowData] = []
for i, line in enumerate(csvreader):
    tempRow: RowData = {}

    tempDate= dateparser.parse(line[0], languages=['pt'])

    if type(tempDate) is NoneType:
        tempRow['date'] = line[0]
    else:
        tempRow['date'] = tempDate.strftime("%m-%d")

    tempRow['disciplina'] = line[2]
    tempRow['frente'] = line[3]
    tempRow['conteudo'] = line[4].replace("/", "-").replace(":", " -")
    row_count += 1

    data.append(tempRow)

i = 0
j = False
lado = "esq"

for filename in sorted(glob.glob(f"{absolutedirectory}/[!.]*.mp4")):
    info = data[i]
    os.rename(filename, f"{absolutedirectory}/{info['disciplina']} - {info['frente']} - {info['date']} - {info['conteudo']} - {lado}.mp4") 

    if j == False:
        lado= "dir"
        j = True
    elif j == True:
        lado="esq"
        i += 1
        j = False