import socket
import time


def connectSock(host, port, timeout=1):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
    except:
        time.sleep(1)
        return False

    return True


def waitForTcpServer(host, port, timeout=60):
    start = time.time()
    port = int(port)
    while not connectSock(host, port):
        if time.time() - start > timeout:
            raise TimeoutError('tcp server %s:%d is not running'%(host, port))

    return True
