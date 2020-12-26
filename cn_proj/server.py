from rdt import RDTSocket
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
import time

if __name__ == '__main__':
    server = RDTSocket()
    # server = socket(AF_INET, SOCK_STREAM) # check what python socket does
    server.bind(('127.0.0.1', 9999))
    # check what python socket does
    # server.listen(0)

    while True:
        print('accepting')
        conn, client_addr = server.accept()
        start = time.perf_counter()
        i: int = 0
        while True:
            data = conn.recv(4096)
            if data:
                conn.send(data)
                print(i)
            else:
                print('break')
                break
            i += 1
        '''
        make sure the following is reachable
        '''
        print('before close')
        conn.close()
        print(f'connection finished in {time.perf_counter() - start}s')
