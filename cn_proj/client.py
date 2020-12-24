from rdt import RDTSocket
import time

addr = ('127.0.0.1', 9000)

if __name__ == '__main__':
    print('prepare data start')
    fin = open('./data/alice30.txt', 'rb')
    lines = fin.readlines()
    data = b''
    for line in lines:
        data += bytes(line)
    # print(data.decode())
    print('prepare data end')

    print('client start')
    start = time.time()
    client = RDTSocket()
    client.connect(addr)
    client.send(data)
    data = client.recv(2048)
    print(data.decode())
    end = time.time()
    print(end - start)
    print('client end')
