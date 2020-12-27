
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
import time

if __name__=='__main__':
    # server = RDTSocket()
    server = socket(AF_INET, SOCK_STREAM) # check what python socket does
    server.bind(('127.0.0.1', 9999))
    server.listen(0) # check what python socket does

    while True:
        conn, client_addr = server.accept()
        start = time.perf_counter()
        while True:
            # time.sleep(5)
            data = conn.recv(2)
            print(data.decode())
            if data:
                conn.send(data)
            else:
                break
        '''
        make sure the following is reachable
        '''
        conn.close()
        print(f'connection finished in {time.perf_counter()-start}s')