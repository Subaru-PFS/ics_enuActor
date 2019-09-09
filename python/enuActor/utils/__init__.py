import socket
import time


def wait(secs=5):
    time.sleep(secs=secs)


def connectSock(host, port, timeout=1):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
    except:
        wait(secs=timeout)
        return False
    finally:
        s.close()

    return True


def waitForTcpServer(host, port, timeout=60):
    start = time.time()
    port = int(port)
    while not connectSock(host, port):
        if time.time() - start > timeout:
            raise TimeoutError('tcp server %s:%d is not running' % (host, port))

    wait()
    return True
