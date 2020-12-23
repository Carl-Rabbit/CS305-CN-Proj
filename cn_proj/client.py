from rdt import RDTSocket

addr = ('127.0.0.1', 9000)

if __name__ == '__main__':
    print('client start')
    client = RDTSocket()
    client.connect(addr)
    client.send(b'This is the first message.')
    # print('after sending msg 1')
    print('echo', client.recv(2048))

    client.send(b'This is the second message.')
    # print('after sending msg 2')
    print('echo', client.recv(2048))

    client.send(b'This is the third message.')
    # print('after sending msg 3')
    print('echo', client.recv(2048))

    print('client end')
