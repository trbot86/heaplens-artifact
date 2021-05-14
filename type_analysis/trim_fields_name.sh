# Deprecated
cat fielddump.txt | while read line ; do
    echo -n $line | cut -d"|" -f3 | rev | cut -d":" -f3- | rev | tr -d " " | tr -d "\n"
    echo -n "|"
    echo -n $line | cut -d"|" -f2 | tr -d "\n"
    echo -n "|"
    echo $line | cut -d"|" -f3 | rev | cut -d":" -f1 | rev | tr -d "\n"
    echo -n "|"
    echo $line | cut -d"|" -f4-
done