import sys

from USocket import UnreliableSocket
import utils
import USocket
import math
import threading
from queue import Queue
from queue import Empty
import time
import random


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

    S_STOP = 1
    S_START = 2
    S_WAIT = 3
    S_SD_DATA = 4
    S_SD_ACK = 5
    S_SD_RE = 6
    # S_SD_PROBE = 7
    S_SD_CLOSE_1_RPL = 8
    S_SD_CLOSE_2_RPL = 9

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
        self.estimated_rtt = 10 ** 9
        self.dev_rtt = 10 ** 9

        self.data_queue: Queue = Queue()
        self.msg_queue: Queue = Queue()
        self.recv_queue: Queue = Queue()
        self.ret_queue: Queue = Queue()
        self.sending_zone = b''
        self.immediate = b''

        self.controller_work = False
        self.sender_work = False
        self.receiver_work = False

        self.controller = threading.Thread(target=self.control_thread)
        self.sender = threading.Thread(target=self.send_thread)
        self.receiver = threading.Thread(target=self.receive_thread)

        self.probed = False

        self.closed = False
        self.target_closed = False

        # control
        self.status = self.S_START
        self.nxt_status = self.S_START

        self.send_new = True
        self.check_time = -1

        self.msg_to_ack = None
        self.cur_msg = None

        self.to_probe = False

        self.send_time = 0
        self.recv_time = 0

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
        if self.debug:
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
                if self.debug:
                    print('it is assumed that connection is established.', e, self.connect)
                break

        self.target_addr = address
        self._recv_from = self.recvfrom
        self.setblocking(True)

        self.controller.start()
        self.sender.start()
        self.receiver.start()

        self.sender_work = True
        self.receiver_work = True
        self.controller_work = True
        self.nxt_status = self.S_WAIT  # open controller

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
                if self.debug:
                    print(e, self.accept)
                self._send_to(rpl, addr)
                continue

        end: float = time.time_ns()
        self.rtt_unit = (end - start) * 1.2 / 1E9
        if self.debug:
            print('estimated rtt', self.rtt_unit * self.rtt_multiplicand)

        self.setblocking(True)
        conn._recv_from = self.recvfrom
        conn.target_addr = addr
        conn.rtt_unit = self.rtt_unit
        conn.is_receiving = False
        conn.setblocking(True)

        conn.controller.start()
        conn.sender.start()
        conn.receiver.start()

        conn.sender_work = True
        conn.receiver_work = True
        conn.controller_work = True
        conn.nxt_status = self.S_WAIT  # open controller

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
                    if self.debug:
                        print('handshake 2 received')
                    self.setblocking(True)
                    break
            except Exception as e:
                if self.debug:
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
        assert self._recv_from, "Connection not established yet. Use recvfrom instead."
        self.buff_size = buff_size
        return self.ret_queue.get(block=True)

    def send(self, data: bytes):
        """
        Send data to the socket.
        The socket must be connected to a remote socket, i.e. self._send_to must not be none.
        """
        if not self._send_to:
            self.set_send_to(USocket.get_sendto(id(self), self._rate))
        assert self._send_to, "Connection not established yet. Use sendto instead."
        assert self.target_addr, 'You did not specify where to send.'
        assert not self.closed, 'The man closed is the man who does not send.'

        data_length = len(data)
        if data_length <= self.max_segment_size:
            self.data_queue.put(data)
        else:
            # Cut the data to send into segments.
            segment_num = math.ceil(data_length / (self.max_segment_size - 15))
            segment_size = math.ceil(data_length / segment_num)
            index_0 = 0
            index_1 = segment_size
            while index_1 < data_length:
                if self.debug:
                    print(f'{index_0}, {index_1}, {data_length}')
                segment = data[index_0:index_1]
                self.data_queue.put(segment)
                index_0 += segment_size
                index_1 += segment_size
            if index_0 < data_length:
                if self.debug:
                    print(f'{index_0}, {data_length}, {data_length}')
                self.data_queue.put(data[index_0:])
        return

    def update_dev_rtt(self):
        """
        Compute a new dev rtt and save to self.dev_rtt
        """
        sample_rtt = self.recv_time - self.send_time
        self.estimated_rtt = (1 - self.ALPHA) * self.estimated_rtt + self.ALPHA * sample_rtt
        self.dev_rtt = (1 - self.BETA) * self.dev_rtt + self.BETA * abs(sample_rtt - self.estimated_rtt)

    def control_thread(self):
        while self.nxt_status == self.S_START:
            pass
        if self.debug:
            print('Controller thread start')

        while True:
            # update status
            if self.nxt_status != self.status:
                if self.debug:
                    print('goto status : ', self.nxt_status)
            self.status = self.nxt_status

            if self.status == self.S_WAIT:
                if not self.recv_queue.empty():
                    msg = self.recv_queue.get()
                    sfa = utils.get_sfa_from_msg(msg)
                    if sfa == utils.DATA:
                        # parse data
                        try:
                            data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(msg)
                            if self.debug:
                                print(f'received {seq_num}')
                            if seq_num <= self.seqack_num:
                                if seq_num == self.seqack_num:
                                    self.ret_queue.put(data)
                                    self.msg_to_ack = msg
                                else:
                                    # not to update msg_to_ack
                                    pass

                                # ready to send ack
                                self.nxt_status = self.S_SD_ACK
                            else:
                                raise Exception(f'seq_num > : {utils.extract_data_from_msg(msg)}, {self.seqack_num}')
                        except Exception as e:
                            if self.debug:
                                print(e)

                    elif sfa == utils.ACK:
                        # update send info
                        try:
                            data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(msg)
                            if self.debug:
                                print(f'rdt {seqack_num} len {data_length} self:{self.seq_num}')
                            if seqack_num == self.seq_num + len(self.cur_msg) - 15:
                                if self.debug:
                                    print('correct condition')
                                self.recv_time = time.time_ns()
                                self.update_dev_rtt()
                                self.seq_num += len(self.cur_msg) - 15

                                if not self.data_queue.empty():
                                    self.nxt_status = self.S_SD_DATA
                                else:
                                    self.check_time = -1
                                    self.nxt_status = self.S_WAIT
                            # elif seqack_num == self.seq_num:

                            elif seqack_num < self.seq_num + len(self.cur_msg) - 15:
                                self.nxt_status = self.S_WAIT
                            else:
                                if self.debug:
                                    print(utils.extract_data_from_msg(msg))
                                if self.debug:
                                    print(utils.extract_data_from_msg(self.cur_msg))
                                raise Exception(f'Seq ack error: seqack_num={seqack_num}, self.seq_num={self.seq_num}')
                        except Exception as e:
                            if self.debug:
                                print(e)
                    elif sfa == utils.CLOSE_1:
                        try:
                            data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(msg)
                            assert data == b''
                            if self.debug:
                                print(f'rdt {seqack_num} len {data_length} self:{self.seq_num}')
                            if seq_num != self.seqack_num:
                                sys.stderr.write('This is not supposed to happen. ORZ')
                            self.ret_queue.put(data)
                            self.nxt_status = self.S_SD_CLOSE_1_RPL
                        except Exception as e:
                            if self.debug:
                                print(e)
                    elif sfa == utils.CLOSE_2:
                        try:
                            data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(msg)
                            assert data == b''
                            if self.debug:
                                print(f'rdt {seqack_num} len {data_length} self:{self.seq_num}')
                            if seq_num != self.seqack_num:
                                sys.stderr.write('This is not supposed to happen. ORZ')
                            self.ret_queue.put(data)
                            self.nxt_status = self.S_SD_CLOSE_2_RPL
                        except Exception as e:
                            if self.debug:
                                print(e)
                    elif sfa == utils.CLOSE_1_RPL:
                        self.nxt_status = self.S_WAIT
                    elif sfa == utils.CLOSE_2_RPL:
                        self.nxt_status = self.S_STOP
                    else:
                        raise Exception(f'Unknown sfa: {sfa}')
                elif self.check_time == -1 and not self.data_queue.empty():
                    self.nxt_status = self.S_SD_DATA
                elif self.check_time != -1 and time.time_ns() >= self.check_time:
                    self.nxt_status = self.S_SD_RE
                elif not self.data_queue.empty() and not self.controller_work:
                    self.nxt_status = self.S_STOP
                else:
                    self.nxt_status = self.S_WAIT

            elif self.status == self.S_SD_DATA:
                data = self.data_queue.get()
                if data:
                    # data != b''
                    self.cur_msg = utils.generate_data_msg(self.seq_num, self.seqack_num, data)
                    self.msg_queue.put(self.cur_msg)

                    self.send_time = time.time_ns()
                    self.check_time = time.time_ns() + self.dev_rtt
                    if self.debug:
                        print(f'send {self.seq_num} data len {len(self.cur_msg) - 15} at {time.time()}. '
                          f'dev_rtt={self.dev_rtt / 10 ** 9}')

                    self.nxt_status = self.S_WAIT

                elif self.target_closed:
                    self.cur_msg = utils.generate_close_1_msg(self.seq_num, self.seqack_num)
                    self.send_time = time.time_ns()
                    self.check_time = time.time_ns() + self.dev_rtt
                    if self.debug:
                        print(f'send {self.seq_num} close 1 len {len(self.cur_msg) - 15} at {time.time()}. '
                          f'dev_rtt={self.dev_rtt / 10 ** 9}')

                    self.nxt_status = self.S_WAIT
                else:
                    # send CLOSE
                    self.cur_msg = utils.generate_close_2_msg(self.seq_num, self.seqack_num)
                    self.send_time = time.time_ns()
                    self.check_time = time.time_ns() + self.dev_rtt
                    if self.debug:
                        print(f'send {self.seq_num} close 2 len {len(self.cur_msg) - 15} at {time.time()}. '
                          f'dev_rtt={self.dev_rtt / 10 ** 9}')

                    self.nxt_status = self.S_WAIT

            elif self.status == self.S_SD_ACK:
                # send ack
                data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(self.msg_to_ack)
                assert seq_num <= self.seqack_num, '!<='
                if self.debug:
                    print(f'send ack, seq_num={seq_num}, data_length={data_length}, self.seqack_num={self.seqack_num}')
                # assert seq_num == self.seqack_num
                # print(utils.extract_data_from_msg(self.msg_to_ack))
                if seq_num == self.seqack_num:
                    self.seqack_num += data_length
                msg = utils.generate_ack_msg(self.seq_num, self.seqack_num)
                # print(utils.extract_data_from_msg(msg))
                self.msg_queue.put(msg)
                if self.debug:
                    print(f'ack {self.seqack_num} {seq_num} len {data_length}')
                self.nxt_status = self.S_WAIT

            elif self.status == self.S_SD_RE:
                if self.debug:
                    print('Time exceeded')
                self.msg_queue.put(self.cur_msg)
                self.estimated_rtt *= 1.2
                self.dev_rtt *= 1.2
                self.check_time = time.time_ns() + self.dev_rtt

                if self.debug:
                    print(f'send {self.seq_num} data len {len(self.cur_msg) - 15} at {time.time()}. '
                      f'dev_rtt={self.dev_rtt / 10 ** 9}')

                self.nxt_status = self.S_WAIT

            # elif self.status == self.S_SD_PROBE:
            #     pass
            elif self.status == self.S_SD_CLOSE_1_RPL:
                if self.debug:
                    print('received not processed', self.recv_queue.qsize())
                if self.debug:
                    print('yet to send 1', self.msg_queue.qsize())
                data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(self.msg_to_ack)
                assert seq_num <= self.seqack_num, '!<='
                if self.debug:
                    print(
                    f'send ack 1 close, seq_num={seq_num}, data_length={data_length}, self.seqack_num={self.seqack_num}')
                # assert seq_num == self.seqack_num
                # print(utils.extract_data_from_msg(self.msg_to_ack))
                if seq_num == self.seqack_num:
                    self.seqack_num += data_length
                msg = utils.generate_close_1_rpl_msg(self.seq_num, self.seqack_num)
                self.target_closed = True
                # print(utils.extract_data_from_msg(msg))
                self.msg_queue.put(msg)
                if self.debug:
                    print(f'ack close {self.seqack_num} {seq_num} len {data_length}')
                self.nxt_status = self.S_WAIT
            elif self.status == self.S_SD_CLOSE_2_RPL:
                if self.debug:
                    print('received not processed', self.recv_queue.qsize())
                if self.debug:
                    print('yet to send 2', self.msg_queue.qsize())
                data, seq_num, seqack_num, data_length = utils.extract_data_from_msg(self.msg_to_ack)
                assert seq_num <= self.seqack_num, '!<='
                if self.debug:
                    print(
                    f'send ack 2 close, seq_num={seq_num}, data_length={data_length}, self.seqack_num={self.seqack_num}')
                # assert seq_num == self.seqack_num
                # print(utils.extract_data_from_msg(self.msg_to_ack))
                if seq_num == self.seqack_num:
                    self.seqack_num += data_length
                msg = utils.generate_close_2_rpl_msg(self.seq_num, self.seqack_num)
                self.target_closed = True
                # print(utils.extract_data_from_msg(msg))
                self.msg_queue.put(msg)
                if self.debug:
                    print(f'ack close {self.seqack_num} {seq_num} len {data_length}')
                try:
                    rpl = self.recv_queue.get(timeout=self.dev_rtt / 1E9 * 3)
                    self.nxt_status = self.S_SD_CLOSE_2_RPL
                except TimeoutError:
                    if self.debug:
                        print('entering timeout err')
                    self.nxt_status = self.S_STOP
                except Empty:
                    if self.debug:
                        print('empty exception?')
                    self.nxt_status = self.S_STOP
                except Exception as e:
                    if self.debug:
                        print('some other exception')
                    if self.debug:
                        print(e)
                    self.nxt_status = self.S_SD_CLOSE_2_RPL

            elif self.status == self.S_STOP:
                self.sender_work = False
                self.receiver_work = False
                super().close()
                if self.debug:
                    print('Stop')
                break

            else:
                raise Exception('Status Error')

    def send_thread(self):

        while not self.sender_work:
            pass
        if self.debug:
            print('send_thread start')

        while self.sender_work and not self.target_closed:
            # if random.random() < 0.1:
            #     print(self.msg_queue.qsize())
            try:
                msg = self.msg_queue.get(timeout=0.1)
                self._send_to(msg, self.target_addr)
            except Exception as e:
                if self.debug:
                    print(e)
                continue

    def receive_thread(self):
        while not self.receiver_work:
            pass
        if self.debug:
            print('receive_thread start')

        try:
            while self.receiver_work:
                msg, addr = self._recv_from(self.buff_size)
                self.recv_queue.put(msg)
        except Exception as e:
            if self.debug:
                print(e)

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

    def close(self):
        """
        TODO
        Finish the connection and release resources. For simplicity, assume that
        after a socket is closed, neither further sends nor receives are allowed.
        """
        self.closed = True
        self.data_queue.put(b'')

    def set_send_to(self, send_to):
        self._send_to = send_to

    def set_recv_from(self, recv_from):
        self._recv_from = recv_from
