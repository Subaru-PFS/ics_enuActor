#!/usr/bin/env python

import argparse
import datetime
import os
import time

import pandas as pd
from enuActor.drivers import hxp_drivers


def recordSlitPosition(host, sampleTime, port=5001, rootDir='.'):
    """
    This function records the slit position of a Hexapod for a given sample time.

    Parameters:
    host (str): The IP address of the Hexapod.
    sampleTime (int or float): The duration for which the slit position needs to be recorded in seconds.
    port (int): The port number of the Hexapod. Default is 5001.
    rootDir (str): The root directory where the recorded data will be saved. Default is the current directory.

    Returns:
    None

    Raises:
    RuntimeError: If the connection to the Hexapod fails.

    The function records the slit position of the Hexapod for the given sample time at a frequency of 100 Hz.
    The data is stored in a pandas DataFrame and saved as a CSV file in the specified root directory. The CSV file
    name contains the Hexapod's IP address, the start time of the recording in ISO format without microseconds,
    and the suffix '_slitPosition.csv'.
    """
    xps = hxp_drivers.XPS()
    socketId = xps.TCP_ConnectToServer(host, port, 300)

    if socketId == -1:
        raise RuntimeError('Connection to Hexapod failed check IP & Port')

    data = []
    timestamp = []
    start = time.time()

    while (time.time() - start) < sampleTime:
        s1 = time.time()
        data.append(xps.GroupPositionCurrentGet(socketId, 'HEXAPOD', 6))
        s2 = time.time()
        timestamp.append(((s1 + s2) / 2))

        time.sleep(0.01)

    # cleaning socket in the end.
    xps.TCP_CloseSocket(socketId)

    df = pd.DataFrame(data, columns=['status', 'X', 'Y', 'Z', 'U', 'V', 'W'])
    df['timestamp'] = timestamp

    try:
        specNum = int(host[-1])
    except:
        specNum = 0

    # Convert it to datetime obje
    dt_object = datetime.datetime.fromtimestamp(start)
    # Convert datetime object to ISO format without microseconds
    isoformat = dt_object.replace(microsecond=0).isoformat().replace(':', '-')
    fileName = f'SM{specNum}_slitPosition_{isoformat}.csv'

    filePath = os.path.join(rootDir, fileName)

    df.to_csv(filePath)


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Record slit position of a Hexapod for a given sample time.')
    parser.add_argument('host', type=str, help='The IP address of the Hexapod.')
    parser.add_argument('sampleTime', type=float,
                        help='The duration for which the slit position needs to be recorded in seconds.')
    parser.add_argument('--port', type=int, default=5001, help='The port number of the Hexapod. Default is 5001.')
    parser.add_argument('--rootDir', type=str, default='.',
                        help='The root directory where the recorded data will be saved. Default is the current directory.')

    args = parser.parse_args()

    # Call the recordSlitPosition function with the parsed arguments
    recordSlitPosition(args.host, args.sampleTime, args.port, args.rootDir)
