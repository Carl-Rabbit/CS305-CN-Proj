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

    ALPHA = 0.125
    BETA = 0.25

    S_WAIT = 0
    S_CHECK = 1
    S_SD_DATA = 2
    S_SD_ACK = 3

    def __init__(self, rate=None, debug=True):
        super().__init__(rate=rate)
        self._rate = rate
        self._send_to = None
        self._recv_from = None
        self.debug = debug

        self.set_send_to(USocket.get_sendto(id(self), rate))

        # This parameter is necessary.
        self.target_addr = None

        self.seq_num = 0
        self.seqack_num = 0
        self.buff_size = 2048

        self.target_buff_size: int = 2048
        self.max_segment_size = self.target_buff_size - 15

        self.rtt_unit: float = 0.0
        self.rtt_multiplicand: float = self.max_segment_size / 15
        self.estimated_rtt = 1
        self.dev_rtt = 1

        self.send_buffer: Queue = Queue()
        self.recv_buffer: Queue = Queue()
        self.sending_zone = b''
        self.immediate = b''

        self.sender_work = threading.Lock()
        self.acker_work = False
        self.sender = threading.Thread(target=self.send_from_buffer)
        self.acker = threading.Thread(target=self.ack)

        self.probed = False

        self.closed = False
        self.target_closed = False

        # control
        self._last_package = None
        self._send_time = 0
        self._ack_time = 0

    def print_debug(self, msg: str, caller) -> None:
        if self.debug:
            print(msg, caller)

    def connect(self, address: (str, int)) -> None:
        """
        According to the professor, I was completely wrong.
        3-way handshake is not necessary.
        Connect to a remote socket at address.
        Corresponds to the process of establishing a connection on the client side.
        """
        start: float = time.time_ns()
        self.handshake_1(address)
        end: float = time.time_ns()
        self.rtt_unit = (end - start) * 1.2 / 1E9
        print('estimated rtt unit', self.rtt_unit)

        data = utils.get_handshake_3_packet()
        while True:
            assert self._send_to is not None, 'problem in _send_to'
            self._send_to(data, address)
            self.settimeout(2)
            try:
                rpl, addr = self._recv_from(self.buff_size)
                if rpl == utils.get_handshake_2_packet():
                    continue
            except Exception as e:
                print('it is assumed that connection is established.', e, self.connect)
                break

        self.target_addr = address
        self._recv_from = self.recvfrom
        self.setblocking(True)
        self.acker_work = True
        self.sender.start()
        self.acker.start()

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
        conn.set_send_to(USocket.get_sendto(id(conn), conn._rate))
        while True:
            data, addr = self.recvfrom(self.buff_size)
            if data == utils.get_handshake_1_packet():
                break

        start: float = time.time_ns()
        rpl = utils.get_handshake_2_packet()
        self._send_to(rpl, addr)
        while True:
            self.settimeout(2)
            try:
                data, addr = self.recvfrom(self.buff_size)
                if data == utils.get_handshake_1_packet():
                    self._send_to(rpl, addr)
                elif data == utils.get_handshake_3_packet():
                    break
            except Exception as e:
                # timeout
                print(e, self.accept)
                self._send_to(rpl, addr)
                continue

        end: float = time.time_ns()
        self.rtt_unit = (end - start) * 1.2 / 1E9
        print('estimated rtt', self.rtt_unit * self.rtt_multiplicand)

        self.setblocking(True)
        conn._recv_from = self.recvfrom
        conn.target_addr = addr
        conn.rtt_unit = self.rtt_unit
        conn.is_receiving = False
        conn.setblocking(True)
        conn.sender.start()
        conn.acker.start()
        conn.sender_work = True
        conn.acker_work = True
        conn.rtt_unit = (end - start) * 1.2 / 1E9
        return conn, addr

    def handshake_1(self, addr: (str, int)) -> None:
        data = utils.get_handshake_1_packet()
        while True:
            self._send_to(data, addr)
            self.settimeout(2)
            try:
                rpl, frm = self.recvfrom(self.buff_size)
                if rpl == utils.get_handshake_2_packet():
                    print('handshake 2 received')
                    self.setblocking(True)
                    break
            except Exception as e:
                print(e, self.handshake_1)
                continue

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
        self.buff_size = buff_size
        while True:
            if self.recv_buffer.empty():
                continue
            # print('recv_buffer not empty')
            msg = self.recv_buffer.get()
            # print('get!!!')
            if not utils.generate_chksm(msg):
                continue
            segment, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
            sfa = msg[0:1]
            if sfa == utils.DATA:
                data = segment
                break
            elif sfa == utils.CLOSE:
                assert segment == b''
                self.close()
                data = segment
                break
            else:
                print('what did you put in buffer?', sfa)

        if data:
            print('data is returned!')
        t2 = time.time_ns()
        # print('recv time', (t2 - t1) // 1000, '1E-3 milliseconds')
        return data

    def probe(self):
        msg = utils.generate_probe_msg(self.seq_num, self.seqack_num)
        with self.sender_work:
            self.acker_work = False
            self.settimeout(2)
            while True:
                self._send_to(msg, self.target_addr)
                try:
                    rpl, frm = self._recv_from(self.buff_size)
                    sfa = utils.get_sfa_from_msg(rpl)
                    if sfa != utils.PROBE_RPL:
                        continue
                    data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(rpl)
                    self.target_buff_size = utils.bytes_to_bu_int(data)
                    self.max_segment_size = self.target_buff_size - 15
                    break
                except Exception as e:
                    print(e, self.probe)
                    continue
            self.probed = True
        self.acker_work = True
        self.setblocking(True)

    def fsm(self):
        pass

    def send(self, data: bytes):
        """
        Send data to the socket.
        The socket must be connected to a remote socket, i.e. self._send_to must not be none.
        """
        if not self._send_to:
            self.set_send_to(USocket.get_sendto(id(self), self._rate))
        assert self._send_to, "Connection not established yet. Use sendto instead."
        assert self.target_addr, 'You did not specify where to send.'

        if not self.probed:
            self.probe()

        data_length = len(data)
        if data_length <= self.max_segment_size:
            self.send_buffer.put(data)
        else:
            # Cut the data to send into segments.
            segment_num = math.ceil(data_length / (self.max_segment_size - 15))
            segment_size = math.ceil(data_length / segment_num)
            index_0 = 0
            index_1 = segment_size
            while index_1 < data_length:
                print(f'{index_0}, {index_1}, {data_length}')
                segment = data[index_0:index_1]
                self.send_buffer.put(segment)
                index_0 += segment_size
                index_1 += segment_size
            if index_0 < data_length:
                print(f'{index_0}, {data_length}, {data_length}')
                self.send_buffer.put(data[index_0:])
        return

    def send_from_buffer(self):
        while True:

            if self.sending_zone != b'':
                with self.sender_work:
                    if self._last_package != self.seq_num:
                        # send success
                        sample_rtt = self._ack_time - self._send_time
                        self.estimated_rtt = (1 - self.ALPHA) * self.estimated_rtt + self.ALPHA * sample_rtt
                        self.dev_rtt = (1 - self.BETA) * self.dev_rtt + self.BETA * abs(sample_rtt - self.estimated_rtt)

                        self._send_time = time.time()
                        self._last_package = self.seq_num

                    else:
                        # time out
                        self.estimated_rtt *= 1.2
                        self.dev_rtt *= 1.2

                    print(f'send {self.seq_num} data len {len(self.sending_zone)} at {time.time()}. '
                          f'dev_rtt={self.dev_rtt}')
                    self.send_data(self.sending_zone)

                # TODO: Congestion control.
                time.sleep(self.dev_rtt)
            else:
                with self.sender_work:
                    self.sending_zone = self.send_buffer.get()

    def probe_rpl(self):
        with self.sender_work:
            self.acker_work = False

            buff_size: int = self.buff_size
            data_length: int = math.ceil(math.log(buff_size + 1, 256))
            data = utils.int_to_bu_bytes(buff_size, data_length)
            msg = utils.generate_probe_rpl_msg(self.seq_num, self.seqack_num, data)
            self._send_to(msg, self.target_addr)

            self.acker_work = True

    def ack(self):
        while True:
            if self._recv_from and self.acker_work:
                try:
                    msg, frm = self._recv_from(self.buff_size)
                except Exception as e:
                    print(e, self.ack)
                    continue
                if not utils.checksum(msg):
                    print('The packet is corrupted!')
                    continue
                sfa = utils.get_sfa_from_msg(msg)
                if sfa == utils.PROBE:
                    print('probe msg received')
                    self.probe_rpl()
                    continue
                elif sfa == utils.PROBE_RPL:
                    continue
                elif sfa == utils.DATA:
                    segment, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
                    print(f'receive {self.seqack_num} len {data_length} at {time.time()}')
                    if new_seq_num == self.seqack_num:
                        print(f'put {self.seqack_num} len {data_length} at {time.time()}')
                        # receive 0, ack 0, then self.seqack += len(segment)
                        ack_msg = utils.generate_ack_msg(self.seq_num, self.seqack_num)
                        self.seqack_num += data_length
                        with self.sender_work:
                            self.rpl_ack(ack_msg)
                        self.recv_buffer.put(msg)
                        continue
                    elif new_seq_num < self.seqack_num:
                        print('smaller')
                        ack_msg = utils.generate_ack_msg(self.seq_num, self.seqack_num)
                        with self.sender_work:
                            self.rpl_ack(ack_msg)
                        continue
                elif sfa == utils.ACK:
                    data, new_seq_num, new_seqack_num, data_length = utils.extract_data_from_msg(msg)
                    print('ack msg received', new_seqack_num)
                    if self.seq_num == new_seqack_num:
                        print(f'rdt {self.seq_num} len {len(self.sending_zone)}')

                        self._ack_time = time.time()

                        with self.sender_work:
                            self.seq_num += len(self.sending_zone)
                            self.sending_zone = b''
                    elif self.seq_num < new_seqack_num:
                        with self.sender_work:
                            self.seq_num += len(self.sending_zone)
                            self.sending_zone = b''
                elif sfa == utils.CLOSE:
                    try:
                        data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(msg)
                    except Exception as e:
                        print(e, self.ack)
                        continue
                    if seq_num == self.seqack_num:
                        with self.sender_work:
                            self.close_rpl()
                            self.recv_buffer.put(msg)
                else:
                    print('what did you receive?', sfa)

    def send_msg(self, msg: bytes) -> None:
        self._send_to(msg, self.target_addr)
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

    def close_rpl(self) -> None:
        msg = utils.generate_close_rpl_msg(self.seq_num, self.seqack_num)
        self._send_to(msg, self.target_addr)

        # This is the only place self.target_closed is assigned True.
        self.target_closed = True

    def close(self):
        """
        Finish the connection and release resources. For simplicity, assume that
        after a socket is closed, neither further sends nor receives are allowed.
        """
        while not self.send_buffer.empty() or self.sending_zone:
            continue

        with self.sender_work:
            self.closed = True

            self.acker_work = False
            msg = utils.generate_close_msg(self.seq_num, self.seqack_num)
            self.settimeout(1)
            while True:
                self._send_to(msg, self.target_addr)
                try:
                    rpl, frm = self._recv_from(self.buff_size)
                except Exception as e:
                    print(e, self.close)
                    continue
                if not utils.checksum(rpl):
                    continue
                sfa = utils.get_sfa_from_msg(rpl)
                try:
                    data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(msg)
                except Exception as e:
                    print(e, self.close)
                    continue
                if sfa != utils.CLOSE_RPL:
                    continue
                if seq_num != self.seqack_num:
                    print('wrong order in close')
                    continue
                break

            if not self.target_closed:
                self.acker_work = True
                while not self.target_closed:
                    continue
                self.acker_work = False
                self.settimeout(2)
                while True:
                    try:
                        self._recv_from(self.buff_size)
                        self.close_rpl()
                    except Exception as e:
                        print('target is really closed', e)
                        break

        self.acker_work = False
        super().close()

    def set_send_to(self, send_to):
        self._send_to = send_to

    def set_recv_from(self, recv_from):
        self._recv_from = recv_from
