import os
import time


def getVersion(productName):
    return os.environ[f'{productName.upper()}_DIR']


def waitForHost(hostname, timeout=30):
    start = time.time()
    while os.system('ping -c 1 %s' % hostname) != 0:
        if time.time() - start > timeout:
            raise TimeoutError('host %s not on the network')

    return os.system('ping -c 1 %s' % hostname)
