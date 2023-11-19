#!/bin/ksh

# Poliedro/Batch rename
# https://github.com/Yudi/scripts

# Get directory from argument input
cd "$PWD/$1" || exit

date=()
# Convert date from dd/mmm to mm-dd
tail -n +2 ../input.csv | cut -d ';' -f1 |  while IFS="" read -r line; do date+=("$(LANG=pt_BR date -jf "%d/%b" +"%m-%d" "$line")"); done

# //\//- replaces "/" with "-"
disciplina=()
tail -n +2 ../input.csv | cut -d ';' -f3 |  while IFS="" read -r line; do disciplina+=("$line"); done

frente=()
tail -n +2 ../input.csv | cut -d ';' -f4 |  while IFS="" read -r line; do frente+=("$line"); done

conteudo=()
tail -n +2 ../input.csv | cut -d ';' -f5 |  while IFS="" read -r line; do conteudo+=("$line"); done

files=(*.mp4)
filecount=${#files[@]}

# Check if number of files is double to the number of entries in the input.csv file
if [ $((filecount/2)) -ne ${#date[@]} ]; then
    echo "Número de arquivos não corresponde ao número de linhas do arquivo input.csv"
    exit
fi

# Replace : with - in the array
for i in "${!conteudo[@]}"; do
    conteudo[i]="${conteudo[$i]//:/ - }"
done


# zsh array starts at 1
i=1
j=0
lado="esq"

for file in *.mp4
do
    mv "$file" "${disciplina[$i]//\//-} - ${frente[$i]//\//-} - ${date[$i]//\//-} - ${conteudo[$i]//\//-} - $lado.mp4"

    if [ $j -eq 0 ]; then
        lado="dir"
        j=1
    elif [ $j -eq 1 ]; then
        lado="esq"
        j=0
        i=$((i+1))
    fi
done
