import os

def getVersion(productName):
    return os.environ[f'{productName.upper()}_DIR']
