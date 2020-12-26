from USocket import UnreliableSocket
import utils
import USocket
import math
import threading
from queue import Queue
import time


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

        # This parameter is necessary.
        self.target_addr = None

        self.seq_num = 0
        self.seqack_num = 0
        self.max_segment_size = 2048 - 15
        self.timeout_length = 0.5
        self.send_buffer: Queue = Queue()
        self.recv_buffer: Queue = Queue()
        self.max_ack_num = 0
        self.sending_zone = b''

        self.sender_work = False
        self.acker_work = False

        # Start the sender.
        self.sender = threading.Thread(target=self.send_from_buffer)
        # self.sender.start()

        self.acker = threading.Thread(target=self.ack)
        # self.acker.start()

    def print_debug(self, msg: str, caller) -> None:
        if False:
            print(msg, caller)

    def connect(self, address: (str, int)) -> None:
        """
        According to the professor, I was completely wrong.
        3-way handshake is not necessary.
        Connect to a remote socket at address.
        Corresponds to the process of establishing a connection on the client side.
        """
        self.settimeout(self.timeout_length)
        self.print_debug('before sending handshake 1', self.connect)
        self.handshake_1(address)
        self.print_debug('after sending handshake 1', self.connect)
        data = utils.get_handshake_3_packet()
        self.print_debug('before sending handshake 3', self.connect)
        self.sendto(data, address)
        self.print_debug('after sending handshake 3', self.connect)
        # Handshake 3 is sent. A connection is assumed to be established for the sender.
        self.target_addr = address
        self._recv_from = self.recvfrom
        self.sender.start()
        self.acker.start()
        self.sender_work = True
        self.acker_work = True
        self.setblocking(True)
        return

    def accept(self) -> ('RDTSocket', (str, int)):
        """
        Accept a connection. The socket must be bound to an address and listening for 
        connections. The return value is a pair (conn, address) where conn is a new 
        socket object usable to send and receive data on the connection, and address 
        is the address bound to the socket on the other end of the connection.

        This function should be blocking. 
        """
        conn, addr = RDTSocket(self._rate, debug=False), None
        data, addr = self.recvfrom(2048)
        self.print_debug('before receiving handshake 1', self.accept)
        if data != utils.get_handshake_1_packet():
            # The received packet is not handshake 1. Connection is not established.
            # Therefore, None for socket and None for addr is returned.
            self.print_debug(f'msg {data} != handshake1 {utils.get_handshake_1_packet()}',
                             self.accept)
            return None, None
        self.print_debug('after receiving handshake 1', self.accept)
        self.print_debug('before sending handshake 2', self.accept)
        rpl = utils.get_handshake_2_packet()
        conn.sendto(rpl, addr)
        self.print_debug('after sending handshake 2', self.accept)
        self.print_debug('before receiving handshake 3', self.accept)
        while True:
            try:
                data, addr = self.recvfrom(2048)
            # Timeout.
            except Exception as e:
                self.print_debug(str(e), self.accept)
                continue
            # Send handshake 2 if handshake 3 is not received.
            if data != utils.get_handshake_3_packet():
                conn.sendto(rpl, addr)
            break
        self.print_debug('after receiving handshake 3', self.accept)
        conn._recv_from = self.recvfrom
        conn.target_addr = addr
        conn.is_receiving = False
        conn.sender.start()
        conn.acker.start()
        conn.sender_work = True
        conn.acker_work = True
        conn.print_debug('accept end', self.accept)
        return conn, addr

    def handshake_1(self, addr: (str, int)) -> None:
        while True:
            data = utils.get_handshake_1_packet()
            self.sendto(data, addr)
            try:
                rpl, frm = self.recvfrom(2048)
            except Exception as e:
                # Timeout.
                print(e)
                continue
            if rpl == utils.get_handshake_2_packet():
                # The received packet is not handshake 2.
                break

    def recv(self, buff_size: int):
        """
        Receive data from the socket. 
        The return value is a bytes object representing the data received. 
        The maximum amount of data to be received at once is specified by bufsize. 
        
        Note that ONLY data send by the peer should be accepted.
        In other words, if someone else sends data to you from another address,
        it MUST NOT affect the data returned by this function.
        """
        t1 = time.time_ns()
        assert self._recv_from, "Connection not established yet. Use recvfrom instead."
        data = b''

        while True:
            # if self.recv_buffer.empty():
            #     continue
            msg = self.recv_buffer.get()
            segment, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
            sfa = msg[0:1]
            if sfa == utils.ACK and self.seq_num + data_length == new_seqack_num:
                self.seq_num += len(self.sending_zone)
                self.sending_zone = b''
            elif sfa == utils.DATA or sfa == utils.SEGMENT:
                data = segment
                break
                # if new_seq_num == self.seqack_num:
                #     print(f'ack {new_seq_num}')
                #     ack_msg = utils.generate_ack_msg(self.seq_num, self.seqack_num)
                #     self.seqack_num += data_length
                #     self.rpl_ack(ack_msg)
                #     data = segment
                #     break
            elif sfa == utils.SEGMENT_END:
                break
            else:
                data += segment

        if data:
            print('data is returned!')
        t2 = time.time_ns()
        print('recv time', (t2 - t1) // 1000, '1E-3 milliseconds')
        return data

    # def recv_segment(self, buff_size: int) -> (bytes, bytes):
    #     assert self._recv_from
    #     msg, addr = self._recv_from(buff_size)
    #     data, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
    #     sfa = utils.get_sfa_from_msg(msg)
    #     if new_seq_num != self.seqack_num:
    #         raise Exception(f'new_seq_num: {new_seqack_num} != seqack_num: {self.seqack_num}')
    #     self.ack_buffer.put(new_seq_num + data_length)
    #
    #     # self.seqack_num += data_length
    #     # ack_msg: bytes = utils.generate_ack_msg(self.seq_num, self.seqack_num)
    #     # self.rpl_ack(ack_msg)
    #
    #     return data, sfa

    def send(self, data: bytes):
        """
        Send data to the socket.
        The socket must be connected to a remote socket, i.e. self._send_to must not be none.
        """
        t1 = time.time_ns()
        self.print_debug(str(self.send_buffer), None)
        if not self._send_to:
            self.set_send_to(USocket.get_sendto(id(self)))
        assert self._send_to, "Connection not established yet. Use sendto instead."
        assert self.target_addr, 'You did not specify where to send.'
        data_length = len(data)
        if data_length <= self.max_segment_size:
            self.print_debug(f'put data len({len(data)}) into send_buffer', self.send)
            self.send_buffer.put(data)
        else:
            # Cut the data to send into segments.
            segment_num = math.ceil(data_length / (self.max_segment_size - 15))
            segment_size = math.ceil(data_length / segment_num)
            index_0 = 0
            index_1 = segment_size
            while index_1 < data_length:
                self.print_debug(f'{index_0}, {index_1}, {data_length}', self.send)
                segment = data[index_0:index_1]
                self.send_buffer.put(segment)
                index_0 += segment_size
                index_1 += segment_size
            if index_0 < data_length:
                self.print_debug(f'{index_0}, {index_1}, {data_length}', self.send)
                self.send_buffer.put(data[index_0:])
        t2 = time.time_ns()
        # print('send time', (t2 - t1) // 1000, '1E-3 milliseconds')
        return

    def send_from_buffer(self):
        while True:
            if self.sender_work:
                if self.sending_zone != b'':
                    print(f'send {self.seq_num} data len {len(self.sending_zone)} at {time.time()}')
                    self.send_data(self.sending_zone)
                    time.sleep(0.3)
                else:
                    self.sending_zone = self.send_buffer.get()

    def ack(self):
        while True:
            if self._recv_from and self.acker_work:
                try:
                    msg, frm = self._recv_from(2048)
                except Exception as e:
                    print(e)
                    continue
                if not utils.checksum(msg):
                    continue
                sfa = utils.get_sfa_from_msg(msg)

                if sfa != utils.ACK:
                    segment, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(
                        msg)
                    print(f'data received {new_seq_num}')
                    if new_seq_num == self.seqack_num:
                        print(f'receive {self.seqack_num} len {data_length} at {time.time()}')
                        if data_length == 0:
                            print(msg[0])
                        ack_msg = utils.generate_ack_msg(self.seq_num, self.seqack_num)
                        self.seqack_num += data_length
                        self.rpl_ack(ack_msg)
                        self.recv_buffer.put(msg)
                    continue

                print('ack msg received')
                data, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
                if self.seq_num == new_seqack_num:
                    print(f'rdt from {self.seq_num} len {len(self.sending_zone)} at {time.time()}')
                    self.seq_num += len(self.sending_zone)
                    self.sending_zone = b''

    def send_msg(self, msg: bytes) -> None:
        self.sendto(msg, self.target_addr)
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
        assert len(data) <= self.max_segment_size
        msg = utils.generate_data_msg(self.seq_num, self.seqack_num, data)
        self.send_msg(msg)

    def rpl_ack(self, ack_msg) -> None:
        """
        Use unreliable sendto to send the ack message.
        :param ack_msg: The ack message to send.
        :return: None
        """
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
        # super().close()

    def set_send_to(self, send_to):
        self._send_to = send_to

    def set_recv_from(self, recv_from):
        self._recv_from = recv_from


"""
You can define additional functions and classes to do thing such as packing/unpacking packets, or threading.

"""
