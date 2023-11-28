'''
Evaluates archive-based covert channel.
'''


import sys
import os
import pandas as pd
import json
import csv
import bisect
from scipy.stats import entropy
import random
import struct
import gzip


SECRET_MESSAGE_FNAME = "./pseudos.bin.gpg"
WORK_DIR = os.path.join(os.path.abspath(os.sep), "tmp")
# Number of last digits for bigram computation
NUM_LAST_DIGITS = [4, 2, 1]
# Parameters for results plots
COMPRESSIBILITY_Y_AXIS_RANGE = 0.75
BIGRAMS_X_AXIS_NUM_TICKS = 5
# Toggle deterministic or probabilistic behavior in case of multiple nearest neighbors
RANDOM_NEIGHBORS = True


# Create binary file with stream of sensor data values
def create_regular_output(input_data, output_fname):
    if os.path.exists(output_fname):
        os.remove(output_fname)
    regnumbers = []
    with open(output_fname, 'ab') as dgf:
        for datum in input_data:
            dgf.write(struct.pack('!f', datum))
            regnumbers.append(datum)
    return regnumbers


# Covert channel simulation, creates output stream with embedded cc
"""
check if next bit of secret msg is 0 or 1 
if 0, check if next value in input_data is also in collect_seven_days, if so, do nothing (means 0 for cr), 
if value is not in collection, change value to next value with min_dist, which IS in collection (also means 0 for cr). 
if next bit of secret msg is 1, do nothing if next value of input_data is not in collection, change to nearest value, which IS in collection (both means 1 for cr)
"""
def create_cc_data(input_data, output_fname, secret_msg_gen, period, threshold):
    # Obtain collected data from archiving phase
    rootpath = os.path.split(output_fname)[0]
    dict_of_collected_data = {}
    with open(os.path.join(os.path.dirname(rootpath), 'values_with_nearest_neighbors_{}.csv'.format(column_fname)), 'r') as nnf:
        reader = csv.reader(nnf)
        for row in reader:
            k, v = row
            dict_of_collected_data[int(k)] = json.loads(v)
    
    # Create cc data stream
    cc_data = []
    colldata = list(dict_of_collected_data.keys())
    values_used = 0
    for datum in input_data:
        datum_as_int = round(datum*10000)
        # Determine closest value
        if datum_as_int in dict_of_collected_data:
            if RANDOM_NEIGHBORS:
                # If there are two closest values, choose randomly
                nearest_as_int = random.choice(dict_of_collected_data[datum_as_int])
            else:
                # Deterministically choose upper neighbor
                nearest_as_int = dict_of_collected_data[datum_as_int][-1]
        else:
            nearest_as_int = find_nearest(datum_as_int, colldata)
        nearest = nearest_as_int / 10000
        if abs(datum_as_int - nearest_as_int) > nn_threshold:
            # Skip value
            cc_data.append(datum)
            continue
        values_used += 1
        # Transmit secret message bit
        next_secret_bit = next(secret_msg_gen) 
        if next_secret_bit == 0:
            if datum_as_int in dict_of_collected_data:
                cc_data.append(datum)
            else:
                cc_data.append(nearest)
        else:    
            # Secret bit is 1
            if datum_as_int in dict_of_collected_data:
                cc_data.append(nearest)
            else:
                cc_data.append(datum)

    # Compute bandwidths and errors
    errorpath = os.path.join(rootpath, "errorlists")
    subdir = rootpath.split('/')[0]
    with open(os.path.join(rootpath, "bandwidths.csv"), 'a') as bwf:
        if os.path.getsize(os.path.join(rootpath, "bandwidths.csv")) == 0:
            bwf.write("date,column,bits_transmitted,total_no_values,coverage\n")
        bwf.write("{},{},{},{},{}\n".format(date, column_fname, values_used, len(cc_data), values_used/len(cc_data)))
    with open(os.path.join(subdir, "bandwidths.csv"), 'a') as bwf:
        if os.path.getsize(os.path.join(subdir, "bandwidths.csv")) == 0:
            bwf.write("date,column,period,threshold,bits_transmitted,total_no_values,coverage\n")
        bwf.write("{},{},{},{},{},{},{}\n".format(date, column_fname, period, threshold, values_used, len(cc_data), values_used/len(cc_data)))
    mape = calculate_mape(input_data, cc_data, column_fname, date, errorpath, subdir, period, threshold)
    print("CC coverage:", values_used/len(cc_data))
    print("MAPE:", mape)

    return create_regular_output(cc_data, output_fname)


# Determine closest value in given (ordered) list of collected data for input datum
def find_nearest(datum, data):
    if datum >= data[-1]:
        return data[-1]
    if datum <= data[0]:
        return data[0]
    # Determine position for datum in given (ordered) list
    ind = bisect.bisect_left(data,datum)
    # If distance to both neighbors is equal, choose randomly if random choice is specified (see above)
    if data[ind] - datum == datum - data[ind-1] and RANDOM_NEIGHBORS:
        return random.choice([data[ind], data[ind-1]])
    # Deterministically always choose upper neighbor in case of equidistanced neighbors
    if datum - data[ind-1] < data[ind] - datum:
        return data[ind-1]
    return data[ind]


# Calculate mean absolute percentage error (MAPE) and create a list of relative errors
def calculate_mape(list1, list2, column_fname, date, errorpath, subdir, period, threshold):
    # Exclude initialization phase where values could be 0
    list_of_rel_err = [(abs(list1[i]-list2[i])/abs(list1[i])) for i in range(len(list1)) if abs(list1[i]) > 0]
    mape= 100 * (sum(list_of_rel_err) / len(list_of_rel_err))
    # Write to file
    fn = os.path.join(errorpath, date + '_' + column_fname+'.csv')
    with open(fn, 'w') as temp_file:
        for item in list_of_rel_err:
            temp_file.write("%s\n" % item)
    if not os.path.exists(os.path.join(errorpath, "mape.csv")):
        with open(os.path.join(errorpath, "mape.csv"), 'w') as maf:
            maf.write("date,column,mape,max. error (%)\n")
    with open(os.path.join(errorpath, "mape.csv"), 'a') as maf:
        maf.write("{},{},{},{}\n".format(date, column_fname, mape,max(list_of_rel_err)))
    if not os.path.exists(os.path.join(subdir, "mape.csv")):
        with open(os.path.join(subdir, "mape.csv"), 'w') as maf:
            maf.write("date,column,period,threshold,mape,max. error (%)\n")
    with open(os.path.join(subdir, "mape.csv"), 'a') as maf:
        maf.write("{},{},{},{},{},{}\n".format(date, column_fname, period, threshold, mape, max(list_of_rel_err)))
    return mape


# Compute absolute frequencies of bigrams in data stream
def compute_bigrams(stream_fname, value_range):
    values = []
    with open(stream_fname, "rb") as sf:
        bytes_read = sf.read(4)
        while bytes_read:
            values.append(int.from_bytes(bytes_read, "big"))
            bytes_read = sf.read(4)
    bigram_occurences = {}
    for i in range(len(values)-1):
        current_key = (values[i]%value_range, values[i+1]%value_range)
        if current_key in bigram_occurences:
            bigram_occurences[current_key] += 1
        else:
            bigram_occurences[current_key] = 1
    absolute_occurences = sorted(list(bigram_occurences.values()), reverse=True)
    return absolute_occurences, bigram_occurences


# Compute compressibility
def compute_compressibility(filename, work_dir):
    cprs = []
    # Increase offset by 10 each time
    for i in range(0,1000,10):
        with open(filename, 'rb') as infile:
            infile.seek(4*i)
            # 1000 consecutive values
            data = infile.read(4096)
            with gzip.open(os.path.join(work_dir, "compr_data.bin.gz"), 'wb') as outfile:
                outfile.write(data)
        fs_compr=os.path.getsize(os.path.join(work_dir, 'compr_data.bin.gz'))
        cprs.append(4096/fs_compr)
    return cprs       


# Compute Shannon Entropy 
def compute_shannon_entropy(values):
    pd_series = pd.Series(values)
    counts = pd_series.value_counts()
    ent = entropy(counts, base=2)
    return ent


# Each call of next() yields 1 bit of secret message
def get_secret_message_bit_gen(filename):
    with open(filename, 'rb') as smf:
        msg = smf.read()
    for byte in msg:
        for i in reversed(range(8)):
            yield (byte>>i)&1


################################################################
# Preparations
################################################################
random.seed(1337)

if not os.path.isdir(WORK_DIR):
    os.mkdir(WORK_DIR)

if len(sys.argv) < 3:
    print("Please specify input file (including path), column header, and path to results directory!")
    sys.exit(1)

data_filename = os.path.splitext(os.path.split(sys.argv[1])[1])[0]
# Specify which column to examine
column_header = sys.argv[2]
column_fname = column_header.replace(" ", "_").replace("/", "-")
date = data_filename.split('_')[0]
regular_output_fname = "{}_{}_sensorreg.bin".format(column_fname, date)
cc_output_fname = "{}_{}_sensorcc.bin".format(column_fname, date)
respath = sys.argv[3]
if not os.path.exists(respath):
    os.makedirs(respath)
if not os.path.exists(os.path.join(respath, "bigrams")):
    os.makedirs(os.path.join(respath, "bigrams"))
if not os.path.exists(os.path.join(respath, "compressibilities")):
    os.makedirs(os.path.join(respath, "compressibilities"))
if not os.path.exists(os.path.join(respath, "errorlists")):
    os.makedirs(os.path.join(respath, "errorlists"))

folders = respath.split('/')
subdir = folders[0]
if folders[-1]:
    nn_threshold = int(folders[-1])
    period = folders[-2]
else:
    nn_threshold = int(folders[-2])
    period = folders[-3]

print("Processing column {} in {}, period length {}, threshold {}...".format(column_header, data_filename, period, nn_threshold))
################################################################

# Read csv file with sensor values
raw_data = pd.read_csv(sys.argv[1])
input_data = raw_data[column_header].tolist()

# Create regular output
print("Creating sensor data stream file...")
regnumbers = create_regular_output(input_data, os.path.join(respath, "{}_{}_sensorreg.bin".format(column_fname, date)))

print("Establishing covert channel...")
# Obtain generator for secret message bits
msggen = get_secret_message_bit_gen(SECRET_MESSAGE_FNAME)
# Create output with embedded cc
ccnumbers = create_cc_data(input_data, os.path.join(respath, "{}_{}_sensorcc.bin".format(column_fname, date)), msggen, period, nn_threshold)

# Compute Shannon entropy
entropy_reg = compute_shannon_entropy(regnumbers)
entropy_cc = compute_shannon_entropy(ccnumbers)
print("Shannon entropy regular stream:", entropy_reg)
print("Shannon entropy cc stream:", entropy_cc)
if not os.path.exists(os.path.join(respath, "./entropies.csv")):
    with open(os.path.join(respath, "./entropies.csv"), 'w') as etf:
        etf.write("quantity,date,entropy regular,entropy cc\n")
with open(os.path.join(respath, "./entropies.csv"), 'a') as etf:
    etf.write("{},{},{},{}\n".format(column_fname, data_filename.split('_')[0], entropy_reg, entropy_cc))
if not os.path.exists(os.path.join(subdir, "entropies.csv")):
    with open(os.path.join(subdir, "entropies.csv"), 'w') as etf:
        etf.write("quantity,date,period,threshold,entropy regular,entropy cc\n")
with open(os.path.join(subdir, "entropies.csv"), 'a') as etf:
    etf.write("{},{},{},{},{},{}\n".format(column_fname, data_filename.split('_')[0], period, nn_threshold, entropy_reg, entropy_cc))

# Compute bigrams
print("Counting bigram occurrences...")
bigrams_reg = [None] * len(NUM_LAST_DIGITS)
bigrams_cc = [None] * len(NUM_LAST_DIGITS)
for i in range(len(NUM_LAST_DIGITS)):
    # Regular output
    bigrams_reg[i], bigrams_dict_reg = compute_bigrams(os.path.join(respath, "{}_{}_sensorreg.bin".format(column_fname, date)), 2**NUM_LAST_DIGITS[i])
    bgdf = pd.DataFrame.from_dict(bigrams_dict_reg, orient='index').reset_index()
    bgdf.columns = ["bigram", "occurences"]
    bgdf = bgdf.sort_values("occurences", ascending=False)
    bgdf.to_csv(os.path.join(respath, "bigrams/bigrams_reg_{}_{}_{}.csv".format(column_fname, date, NUM_LAST_DIGITS[i])), index=False)
    # Output with cc
    bigrams_cc[i], bigrams_dict_cc = compute_bigrams(os.path.join(respath, "{}_{}_sensorcc.bin".format(column_fname, date)), 2**NUM_LAST_DIGITS[i])
    bgdf = pd.DataFrame.from_dict(bigrams_dict_cc, orient='index').reset_index()
    bgdf.columns = ["bigram", "occurences"]
    bgdf = bgdf.sort_values("occurences", ascending=False)
    bgdf.to_csv(os.path.join(respath, "bigrams/bigrams_cc_{}_{}_{}.csv".format(column_fname, date, NUM_LAST_DIGITS[i])), index=False)

# Compute compressibility
print("Computing compressibility...")
compressibilities_reg = compute_compressibility(os.path.join(respath, regular_output_fname), WORK_DIR)
compressibilities_cc = compute_compressibility(os.path.join(respath, cc_output_fname), WORK_DIR)

print("Done.")
