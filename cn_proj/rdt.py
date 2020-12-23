from USocket import UnreliableSocket
# import threading
# import time
import utils
import USocket


class RDTSocket(UnreliableSocket):
    """
    The functions with which you are to build your RDT.
    -   recvfrom(bufsize)->bytes, addr
    -   sendto(bytes, address)
    -   bind(address)

    You can set the mode of the socket.
    -   settimeout(timeout)
    -   setblocking(flag)
    By default, a socket is created in the blocking mode. 
    https://docs.python.org/3/library/socket.html#socket-timeouts

    """

    def __init__(self, rate=None, debug=True):
        super().__init__(rate=rate)
        self._rate = rate
        self._send_to = None
        self._recv_from = None
        self.debug = debug
        self.target_addr = None
        self.seq_num = 0
        self.seqack_num = 0
        #############################################################################
        # TODO: ADD YOUR NECESSARY ATTRIBUTES HERE
        #############################################################################

        #############################################################################
        #                             END OF YOUR CODE                              #
        #############################################################################

    def accept(self) -> ('RDTSocket', (str, int)):
        """
        Accept a connection. The socket must be bound to an address and listening for 
        connections. The return value is a pair (conn, address) where conn is a new 
        socket object usable to send and receive data on the connection, and address 
        is the address bound to the socket on the other end of the connection.

        This function should be blocking. 
        """
        conn, addr = RDTSocket(self._rate), None
        #############################################################################
        # TODO: YOUR CODE HERE                                                      #
        #############################################################################
        data, addr = self.recvfrom(2048)
        if data != utils.get_handshake_1_packet():
            raise Exception(f'msg {data} != handshake1 {utils.get_handshake_1_packet()}')
        print('before sending handshake 2')
        rpl = utils.get_handshake_2_packet()
        conn.sendto(rpl, addr)
        print('after sending handshake 2')
        print('before receiving handshake 3')
        data, addr = self.recvfrom(2048)
        if data != utils.get_handshake_3_packet():
            raise Exception(f'msg {data} != handshake3 {utils.get_handshake_3_packet()}')
        print('after receiving handshake 3')
        conn._recv_from = self.recvfrom
        conn.target_addr = addr
        return conn, addr
        #############################################################################
        #                             END OF YOUR CODE                              #
        #############################################################################

    def connect(self, address: (str, int)):
        """
        According to the professor, I was completely wrong.
        3-way handshake is not necessary.
        Connect to a remote socket at address.
        Corresponds to the process of establishing a connection on the client side.
        """
        #############################################################################
        # TODO: YOUR CODE HERE                                                      #
        #############################################################################
        print('before sending handshake 1')
        data = utils.get_handshake_1_packet()
        self.sendto(data, address)
        print('after sending handshake 1')
        print('before receiving handshake 2')
        while True:
            rpl, frm = self.recvfrom(2048)
            if rpl != utils.get_handshake_2_packet():
                raise Exception(f'rpl {rpl} != handshake2 {utils.get_handshake_2_packet()}')
            print('after receiving handshake 2')
            print('before sending handshake 3')
            data = utils.get_handshake_3_packet()
            self.sendto(data, address)
            self.target_addr = address
            self._recv_from = self.recvfrom
            print('after sending handshake 3')
            break
        # print(self.seq_num, self.seqack_num)
        return
        #############################################################################
        #                             END OF YOUR CODE                              #
        #############################################################################

    def recv(self, buff_size: int) -> bytes:
        """
        Receive data from the socket. 
        The return value is a bytes object representing the data received. 
        The maximum amount of data to be received at once is specified by bufsize. 
        
        Note that ONLY data send by the peer should be accepted.
        In other words, if someone else sends data to you from another address,
        it MUST NOT affect the data returned by this function.
        """
        assert self._recv_from, "Connection not established yet. Use recvfrom instead."
        #############################################################################
        # TODO: YOUR CODE HERE                                                      #
        #############################################################################
        # print(self.seq_num, self.seqack_num)
        msg, addr = self._recv_from(buff_size)
        data, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
        if new_seq_num != self.seqack_num:
            raise Exception(f'new_seq_num: {new_seqack_num} != seqack_num: {self.seqack_num}')
        self.seqack_num += data_length
        ack_msg: bytes = utils.generate_ack_msg(self.seq_num, self.seqack_num)
        # print(ack_msg)
        self.rpl_ack(ack_msg)
        #############################################################################
        #                             END OF YOUR CODE                              #
        #############################################################################
        return data

    def send(self, data: bytes):
        """
        Send data to the socket. 
        The socket must be connected to a remote socket, i.e. self._send_to must not be none.
        """
        self.set_send_to(USocket.get_sendto(id(self)))
        data_length = len(data)
        assert self._send_to, "Connection not established yet. Use sendto instead."
        assert self.target_addr, 'You did not specify where to send.'
        msg = utils.generate_data_msg(seq_num=self.seq_num, seqack_num=self.seqack_num, data=data)
        while True:
            self.sendto(msg, self.target_addr)
            ack_msg, frm = self.recvfrom(2048)
            print(ack_msg)
            if utils.checksum(ack_msg):
                seqack_num = utils.get_seqack_num(ack_msg)
                if seqack_num == self.seq_num + data_length:
                    print('seqack_num == self.seq_num + data_length')
                    break
        self.seq_num += data_length
        # print('target', self.target_addr)
        return

    def rpl_ack(self, ack_msg):
        self.sendto(ack_msg, self.target_addr)

    def close(self):
        """
        Finish the connection and release resources. For simplicity, assume that
        after a socket is closed, neither further sends nor receives are allowed.
        """
        #############################################################################
        # TODO: YOUR CODE HERE                                                      #
        #############################################################################

        #############################################################################
        #                             END OF YOUR CODE                              #
        #############################################################################
        super().close()

    def set_send_to(self, send_to):
        self._send_to = send_to

    def set_recv_from(self, recv_from):
        self._recv_from = recv_from


"""
You can define additional functions and classes to do thing such as packing/unpacking packets, or threading.

"""
