# File Overview
- `collect_data.py`: simulates archiving phase of archive-based covert channel
- `ccarchive.py`: evaluation of archive-based covert channel detectability
- `pseudos.bin.gpg`: secret message for experimental evaluation
- `sensor_data/*`: example data set from UCI Machine Learning Repository, see below
- `implementation/server.py`: implementation of receiver for experimental evaluation of computational overhead
- `implementation/client.py`: implementation of sender for experimental evaluation of computational overhead

Data in folder `sensor_data` originates from:
Burgus, Javier (2019). Gas sensor array temperature modulation. UCI Machine Learning Repository. https://doi.org/10.24432/C5S302.

# Evaluation
To compute the metrics presented in the paper, simply run the `evalccarchive.sh` script.
To experimentally evaluate the runtime overhead, run `client.py` and `server.py` after setting host addresses and port numbers in the respective files.
A conda environment containing the required modules can be created using the `environment.yml` file.
