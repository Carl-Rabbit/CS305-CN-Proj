from USocket import UnreliableSocket
import utils
import USocket
import math


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
        self.max_segment_size = 2048
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
        # print('before sending handshake 2')
        rpl = utils.get_handshake_2_packet()
        conn.sendto(rpl, addr)
        # print('after sending handshake 2')
        # print('before receiving handshake 3')
        data, addr = self.recvfrom(2048)
        if data != utils.get_handshake_3_packet():
            raise Exception(f'msg {data} != handshake3 {utils.get_handshake_3_packet()}')
        # print('after receiving handshake 3')
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
        # print('before sending handshake 1')
        data = utils.get_handshake_1_packet()
        self.sendto(data, address)
        # print('after sending handshake 1')
        # print('before receiving handshake 2')
        while True:
            rpl, frm = self.recvfrom(2048)
            if rpl != utils.get_handshake_2_packet():
                raise Exception(f'rpl {rpl} != handshake2 {utils.get_handshake_2_packet()}')
            # print('after receiving handshake 2')
            # print('before sending handshake 3')
            data = utils.get_handshake_3_packet()
            self.sendto(data, address)
            self.target_addr = address
            self._recv_from = self.recvfrom
            # print('after sending handshake 3')
            break
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
        # print('before self._recv_from in recv')
        data = b''
        while True:
            segment, sfa = self.recv_segment(buff_size)
            if sfa == utils.DATA:
                data = segment
                break
            elif sfa == utils.SEGMENT_END:
                break
            else:
                data += segment
        #############################################################################
        #                             END OF YOUR CODE                              #
        #############################################################################
        return data

    def recv_segment(self, buff_size: int) -> (bytes, bytes):
        assert self._recv_from
        msg, addr = self._recv_from(buff_size)
        data, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
        sfa = utils.get_sfa_from_msg(msg)
        if new_seq_num != self.seqack_num:
            raise Exception(f'new_seq_num: {new_seqack_num} != seqack_num: {self.seqack_num}')
        self.seqack_num += data_length
        ack_msg: bytes = utils.generate_ack_msg(self.seq_num, self.seqack_num)
        self.rpl_ack(ack_msg)
        return data, sfa

    def send(self, data: bytes):
        """
        Send data to the socket.
        The socket must be connected to a remote socket, i.e. self._send_to must not be none.
        """
        if not self._send_to:
            self.set_send_to(USocket.get_sendto(id(self)))
        # print('send', data)
        assert self._send_to, "Connection not established yet. Use sendto instead."
        assert self.target_addr, 'You did not specify where to send.'
        data_length = len(data)
        if data_length <= self.max_segment_size:
            self.send_data(data)
        else:
            segment_num = math.ceil(data_length / (self.max_segment_size - 15))
            segment_size = math.ceil(data_length / segment_num)
            index_0 = 0
            index_1 = segment_size
            while index_1 < data_length:
                # TODO: Delete this.
                print(index_0, data_length)
                segment = data[index_0:index_1]
                self.send_segment(segment)
                index_0 += segment_size
                index_1 += segment_size
            if index_0 < data_length:
                # TODO: Delete this.
                print(index_0, data_length)
                self.send_segment(data[index_0:])
            self.send_segment_end()
        return

    def send_msg(self, msg: bytes) -> None:
        data_length = len(msg) - 15
        while True:
            self.sendto(msg, self.target_addr)
            # TODO: WHY self._recv_from(2048) is right but self.recvfrom(2048) is wrong?
            ack_msg, frm = self._recv_from(2048)
            if utils.checksum(ack_msg):
                seqack_num = utils.get_seqack_num(ack_msg)
                if seqack_num == self.seq_num + data_length:
                    break
            else:
                print(f'ack_msg {ack_msg} Wrong chksm')
        self.seq_num += data_length
        return

    def send_segment(self, segment: bytes) -> None:
        """
        Send segments of data. This is called by send.
        :param segment: The segment of data to send.
        :return: None
        """
        assert len(segment) < 2048 - 15
        msg = utils.generate_segment_msg(self.seq_num, self.seqack_num, segment)
        self.send_msg(msg)
        return

    def send_segment_end(self) -> None:
        msg = utils.generate_segment_end_msg(self.seq_num, self.seqack_num)
        self.send_msg(msg)
        return

    def send_data(self, data: bytes) -> None:
        """
        Send unsegmented data.
        """
        assert len(data) < 2048 - 15
        msg = utils.generate_data_msg(self.seq_num, self.seqack_num, data)
        self.send_msg(msg)

    def rpl_ack(self, ack_msg) -> None:
        """
        Use unreliable sendto to send the ack message.
        :param ack_msg: The ack message to send.
        :return: None
        """
        # print('before sendto int rpl_ack', ack_msg, self.target_addr)
        self.sendto(ack_msg, self.target_addr)
        # print('after sendto int rpl_ack', ack_msg, self.target_addr)

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
