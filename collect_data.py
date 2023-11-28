'''
Simulates archiving phase of the archive-based covert channel
'''


import csv
import pandas as pd
from itertools import count, filterfalse
import os
import sys
import logging


LOGFILE = os.path.join(sys.argv[1], "nearest_neighbors.log")
# Path to input data
VAL_DIR = "./sensor_data/"
COLUMN_NAMES = ["Flow rate (mL/min)", "R1 (MOhm)"]
MAXVAL = 10**8 - 1


# Collect sensor data from specified files and columns, return set of (unique) values for each column (i.e., sensor)
def collect_days(file_names):
    value_sets = [set()] * len(COLUMN_NAMES)
    for name in file_names:
        data = pd.read_csv(os.path.join(VAL_DIR, name))
        for i in range(len(COLUMN_NAMES)):
            val = data[COLUMN_NAMES[i]].tolist()
            val = [round(x*10000) for x in val]
            value_sets[i] = value_sets[i].union(val)
    values = [sorted(list(value_set)) for value_set in value_sets]
    return values


# Return value closest to given datum that is NOT in collected data
def find_nearest_new(datum, data):
    nearest_new = 0
    dist=1
    while (datum+dist <= data[-1] and datum-dist >= data[0]):
        if datum + dist not in data:
            nearest_new = datum + dist
            break
        elif datum - dist not in data:
            nearest_new = datum - dist
            break
        dist += 1
    if datum+dist > data[-1]:
        nearest_new = data[-1]+1
    if datum-dist < data[0]:
        nearest_new = data[0]-1
    return nearest_new


# Alternative implementation mitigating execution speed issues
def find_nearest_new(datum, gapgen, lower, upper):
    while datum > upper:
        lower = upper
        upper = next(gapgen)
    if lower < 0 and upper > MAXVAL:
        raise ValueError("No nearest value found in feasible interval!")
    if datum - lower < upper - datum or upper > MAXVAL:
        return [lower], lower, upper
    if datum - lower > upper - datum or lower < 0:
        return [upper], lower, upper
    # Both neighbors are within feasible interval and distances are equal
    return [lower, upper], lower, upper


################################################################
# Preparations
################################################################
logging.basicConfig(filename=LOGFILE, encoding='utf-8', level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

outpath = sys.argv[1]

file_names = ["20160930_203718_tenthpermill.csv", "20160930_203718_permill.csv", "20160930_203718_percent.csv", "20160930_203718_tenth.csv", "20160930_203718.csv", "20161001_231809.csv", "20161003_085624.csv", "20161004_104124.csv", "20161005_140846.csv", "20161006_182224.csv", "20161007_210049.csv", "20161008_234508.csv", "20161010_095046.csv", "20161011_113032.csv"]
periods=[0.0001, 0.001, 0.01, 0.1, 1, 10]
################################################################

# Collect data
transmitted_values_lists = [None] * len(periods)
for i in range(len(periods)):
    logging.info("Collecting {} days of data from columns {}...".format(periods[i], COLUMN_NAMES))
    if periods[i] <= 1:
        transmitted_values_lists[i] = collect_days([file_names[i]])
    else:
        transmitted_values_lists[i] = collect_days(file_names[periods.index(1):periods.index(1)+periods[i]])
    for j in range(len(transmitted_values_lists[i])):
        logging.info("Collected {} unique values for column {}".format(len(transmitted_values_lists[i][j]), COLUMN_NAMES[j]))

# Determine closest values
for i in range(len(transmitted_values_lists)):
    for j in range(len(COLUMN_NAMES)):
        data = transmitted_values_lists[i][j]
        list_of_nearest=[]
        # Use alternative implementation
        gapgen = (filterfalse(set(data).__contains__, count(data[0])))
        lower = data[0] - 1
        upper = next(gapgen)
        logging.info('Searching nearest neighbors to collected values in column {}...'.format(COLUMN_NAMES[j]))
        for datum in data:
            #list_of_nearest.append(find_nearest_new(datum, data))
            nearest, lower, upper = find_nearest_new(datum, gapgen, lower, upper)
            list_of_nearest.append(nearest)
        logging.info('Found all {} neighbors!'.format(len(list_of_nearest)))

        logging.info('Writing to file ...')
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        with open(os.path.join(outpath, "values_with_nearest_neighbors_{}_days_{}.csv".format(periods[i], COLUMN_NAMES[j].replace(" ", "_").replace("/", "-"))), 'w', newline='') as csvfile:
            fieldnames = ['value', 'nearest']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            for item in range(len(data)-1):
                writer.writerow({'value': data[item], 'nearest': list_of_nearest[item]})
        logging.info('Finished!')
