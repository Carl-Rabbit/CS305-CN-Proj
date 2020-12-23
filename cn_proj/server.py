from rdt import RDTSocket
import socket

addr = ('127.0.0.1', 9000)
HOST = ''  # Symbolic name meaning all available interfaces
PORT = 50007  # Arbitrary non-privileged port

if __name__ == '__main__':
    server = RDTSocket()
    server.bind(addr)
    print('before accept')
    conn, addr = server.accept()
    print('after accept')
    print(conn, addr)
    while True:
        data = conn.recv(2048)
        if data is None:
            break
        # conn.send(data)
    # s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # s.bind((HOST, PORT))
    # s.listen(1)
    # conn, addr = s.accept()
    # print(conn, addr)
