from rdt import RDTSocket

addr = ('127.0.0.1', 9000)

if __name__ == '__main__':
    client = RDTSocket()
    client.connect(addr)
    client.send(b'abc')
    print('client end')
