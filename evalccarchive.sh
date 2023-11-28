#!/bin/bash

# Parameter: output path

# Examine cc for various sensor values and days 8-13 (or 11-13)
#fnames='20161008_234508.csv 20161010_095046.csv 20161011_113032.csv 20161013_143355.csv 20161014_184659.csv 20161016_053656.csv'
fnames='20161013_143355.csv 20161014_184659.csv 20161016_053656.csv'
periods='0.0001 0.001 0.01 0.1 1 10'
nnthresholds='10 100 1000 10000'
colnames='Flow_rate_(mL-min) R1_(MOhm)'

rm -r $1
mkdir -p $1

# Simulate archiving phase
python collect_data.py $1
pushd .
cd $1
for period in $periods
do
    mkdir ${period}days
    for colname in $colnames
    do
        mv values_with_nearest_neighbors_${period}_days_${colname}.csv ${period}days/values_with_nearest_neighbors_${colname}.csv
    done
done
popd

# Simulate active phase
for period in $periods
do
    for nnthreshold in $nnthresholds
    do
        mkdir $1/${period}days/$nnthreshold
        for fname in $fnames;
        do
            python ccarchive.py ./sensor_data/$fname 'Flow rate (mL/min)' $1/${period}days/$nnthreshold
            python ccarchive.py ./sensor_data/$fname 'R1 (MOhm)' $1/${period}days/$nnthreshold
        done
    done
done
