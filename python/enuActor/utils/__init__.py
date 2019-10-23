import socket
import time


def wait(secs=5):
    time.sleep(secs)


def serverIsUp(host, port, timeout=1):
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


def waitForTcpServer(host, port, cmd=None, mode='operation', timeout=60):
    start = time.time()
    port = int(port)

    if cmd is not None:
        cmd.inform(f'text="waiting for {host}:{port} server..."')

    while not serverIsUp(host, port):
        if mode != 'operation':
            break
        if time.time() - start > timeout:
            raise TimeoutError('tcp server %s:%d is not running' % (host, port))

    wait()
    return True
