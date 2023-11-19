# Batch rename

Renames .mp4 files from Zoom based on the .csv file provided by the school.

## Usage

```bash
$ ./batch_rename.sh <folder with .mp4 files>
```

```bash
$ python batch_rename.py <data.csv> <folder with .mp4 files>
```

## input.csv

```csv
date;teacher;subject;division;title;url
pt_BR dd/mmm;string;string;string;string;string
```
