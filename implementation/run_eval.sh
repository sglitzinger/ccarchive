#!/bin/bash

# Run on sender

column_headers=("Flow rate (mL/min)" "R1 (MOhm)")

python client.py ../sensor_data/20160930_203718.csv "${column_headers[0]}" 10000
python client.py ../sensor_data/20160930_203718.csv "${column_headers[1]}" 10000
