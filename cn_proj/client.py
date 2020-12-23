from rdt import RDTSocket

addr = ('127.0.0.1', 9000)

if __name__ == '__main__':
    client = RDTSocket()
    client.connect(addr)
    client.send(b'This is the first message.')
    client.send(b'This is the second message.')
    client.send(b'This is the third message.')
    print(client.recvfrom(2048))
    print('client end')
