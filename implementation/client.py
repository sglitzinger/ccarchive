'''
Implements sender for experimental evaluation of archive-based covert channel.
'''


import socket
import sys
import os
import pandas as pd
import time
import random
import struct
from itertools import count, filterfalse
from bisect import bisect_left


# Match entries in server.py
#HOST = "192.168.137.31"
HOST = "132.176.77.133"
PORT = 44544

data = " ".join(sys.argv[1:])
MAXDIGITS = 8 # Should be multiple of 2
SECRET_MESSAGE_FNAME = "../pseudos.bin.gpg"
MAXVAL = 10**8 - 1
RANDOM_NEIGHBORS = True


# Produce regular output value
def create_regular_output(datum):
    return struct.pack('!f', datum)


# Create output with embedded cc
def create_cc_data(datum, secret_msg_gen, archive, neighbors):
    datum_int = round(datum*10000)
    if datum_int in neighbors:
        if RANDOM_NEIGHBORS:
            # If there are two closest values, choose randomly
            nearest = random.choice(neighbors[datum_int])
        else:
            # Deterministically choose upper neighbor
            nearest = neighbors[datum_int][-1]
    else:
        nearest = find_nearest(datum_int, archive)
    next_secret_bit = next(secret_msg_gen) 
    if next_secret_bit == 0:
        if datum_int in neighbors:
            return create_regular_output(datum)
        else:
            return create_regular_output(nearest/10000)
    else:    
        # Secret bit is 1
        if datum_int in neighbors:
            return create_regular_output(nearest/10000)
        else:
            return create_regular_output(datum) 


# Determine closest value in given (ordered) list of collected data for input datum
def find_nearest(datum, data):
    if datum >= data[-1]:
        return data[-1]
    if datum <= data[0]:
        return data[0]
    # Determine position for datum in given (ordered) list
    ind = bisect_left(data,datum)
    # If distance to both neighbors is equal, choose randomly if random choice is specified (see above)
    if data[ind] - datum == datum - data[ind-1] and RANDOM_NEIGHBORS:
        return random.choice([data[ind], data[ind-1]])
    # Deterministically always choose upper neighbor in case of equidistanced neighbors
    if datum - data[ind-1] < data[ind] - datum:
        return data[ind-1]
    return data[ind]


# Find neighbors *not* in archive for archived value
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


# Each call of next() yields 1 bit of secret message
def get_secret_message_bit_gen(msg):
    for byte in msg:
        for i in reversed(range(8)):
            yield (byte>>i)&1


def main():
    ################################################################
    # Preparations
    ################################################################
    if len(sys.argv) < 3:
        print("Please specify input file (including path) and column header, and number of values to be sent!")
        sys.exit(1)

    random.seed(2502)

    # Specify which column to examine
    column_header = sys.argv[2]
    num_vals = int(sys.argv[3])

    print("Processing {} values from column {}...".format(num_vals, column_header))

    # Read csv file with sensor values
    raw_data = pd.read_csv(sys.argv[1])
    input_data_total = raw_data[column_header].tolist()
    input_data = input_data_total[:num_vals]

    ################################################################
    # REGULAR OPERATION
    ################################################################
    start = time.process_time_ns()
    # Send sensor values at 3.5Hz
    for datum in input_data:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Connect to server and send data
            sock.connect((HOST, PORT))
            sock.sendall(create_regular_output(datum))
        time.sleep(1/3.5)
    end = time.process_time_ns()
    print("Process time for regular operation:", (end-start)/10**6, "ms")
    print("Process time for regular operation per value:", (end-start)/(num_vals * 10**6), "ms")
    with open("./results.csv", 'a') as rf:
        rf.write("archive-based cc, regular operation,{},{},{},{}\n".format(column_header, str(num_vals), str((end-start)/10**6), str((end-start)/(num_vals * 10**6))))
    ################################################################

    archive = []

    ################################################################
    # ARCHIVING PHASE
    ################################################################
    start = time.process_time_ns()
    # Send sensor values at 3.5Hz, log into archive
    for datum in input_data:
        archive.append(round(datum*10000))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Connect to server and send data
            sock.connect((HOST, PORT))
            sock.sendall(create_regular_output(datum))
        time.sleep(1/3.5)
    end = time.process_time_ns()
    print("Process time for archiving phase:", (end-start)/10**6, "ms")
    print("Process time for archiving phase per value:", (end-start)/(num_vals * 10**6), "ms")
    with open("./results.csv", 'a') as rf:
        rf.write("archive-based cc, archiving phase,{},{},{},{}\n".format(column_header, str(num_vals), str((end-start)/10**6), str((end-start)/(num_vals * 10**6))))
    ################################################################

    ################################################################
    # NEIGHBOR MAPPING PHASE
    ################################################################
    start = time.process_time_ns()
    archive = sorted(archive)
    neighbors = {}
    gapgen = (filterfalse(set(archive).__contains__, count(archive[0])))
    lower = archive[0] - 1
    upper = next(gapgen)
    for value in archive:
        nearest, lower, upper = find_nearest_new(value, gapgen, lower, upper)
        neighbors[value] = nearest
    end = time.process_time_ns()
    print("Process time for neighbor mapping phase:", (end-start)/10**6, "ms")
    print("Process time for neighbor mapping phase per value:", (end-start)/(num_vals * 10**6), "ms")
    with open("./results.csv", 'a') as rf:
        rf.write("archive-based cc, mapping phase,{},{},{},{}\n".format(column_header, str(num_vals), str((end-start)/10**6), str((end-start)/(num_vals * 10**6))))
    ################################################################
    
    # Proceed to inputs for cc phase
    input_data = input_data_total[num_vals:num_vals*2]
    
    # Prepare secret message
    with open(SECRET_MESSAGE_FNAME, 'rb') as smf:
        msg = smf.read()
    msggen = get_secret_message_bit_gen(msg)

    ################################################################
    # COVERT CHANNEL PHASE
    ################################################################
    start = time.process_time_ns()
    # Send sensor values at 3.5Hz, embed secret information
    for datum in input_data:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Connect to server and send data
            sock.connect((HOST, PORT))
            sock.sendall(create_cc_data(datum, msggen, archive, neighbors))
        time.sleep(1/3.5)
    end = time.process_time_ns()
    print("Process time for covert channel phase:", (end-start)/10**6, "ms")
    print("Process time for covert channel phase per value:", (end-start)/(num_vals * 10**6), "ms")
    with open("./results.csv", 'a') as rf:
        rf.write("archive-based cc, active phase,{},{},{},{}\n".format(column_header, str(num_vals), str((end-start)/10**6), str((end-start)/(num_vals * 10**6))))
    ################################################################


if __name__ == "__main__":
    main()
