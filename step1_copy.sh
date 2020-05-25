#!/bin/bash
if [ "$#" -ne "2" ]; then
	echo "USAGE: $0 INPUT_FOLDER OUTPUT_FOLDER"
	echo "    output folder will be created"
	#echo "0=$0" "1=$1" "2=$2"
	exit 1
fi

## first goto memhook and compile

bash -c 'cd memhook ; make -j'
if [ "$?" -ne 0 ]; then echo "ERROR building memhook" ; exit 1 ; fi

## then goto type_analysis and compile

bash -c 'cd type_analysis ; make -j'
if [ "$?" -ne 0 ]; then echo "ERROR building type analysis tools" ; exit 1 ; fi

## copy the project
rm -r $2 ; cp -r $1 $2

echo ""
echo "codebase copied to $2"
echo ""
echo "next step: you need to navigate to $2 and run 'bear make'"
echo "    (prefixing bear on whatever make command you usually run)"
echo "    to generate a compilation_commands.json file."
echo "    "
echo "    This *may* be the correct command to run: cd $2 ; bear make"
echo ""

while true; do
    read -p "    Do you want to run this command [y/n]? " yn
    case $yn in
        [Yy]* ) echo ; cd $2 ; bear make ; break;;
        [Nn]* ) break;;
        * ) echo "Please answer (yY) or (nN).";;
    esac
done
