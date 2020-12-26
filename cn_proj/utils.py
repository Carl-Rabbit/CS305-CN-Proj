# Big-endian is used for all bytes.

# SYN, FIN and ACK bits of a message. I do not want to manipulate bits
# directly, so I used bytes as the minimum unit.
HANDSHAKE_1 = (255).to_bytes(length=1, byteorder='big', signed=False)
HANDSHAKE_2 = (254).to_bytes(length=1, byteorder='big', signed=False)
HANDSHAKE_3 = (253).to_bytes(length=1, byteorder='big', signed=False)
HANDSHAKE_4 = (252).to_bytes(length=1, byteorder='big', signed=False)
ACK = (251).to_bytes(length=1, byteorder='big', signed=False)
PACKET_TOO_LONG = (250).to_bytes(length=1, byteorder='big', signed=False)
PROBE = (249).to_bytes(length=1, byteorder='big', signed=False)
PROBE_RPL = (248).to_bytes(length=1, byteorder='big', signed=False)

DATA = (0).to_bytes(length=1, byteorder='big', signed=False)
SEGMENT = (1).to_bytes(length=1, byteorder='big', signed=False)
SEGMENT_END = (2).to_bytes(length=1, byteorder='big', signed=False)

# Bytes of SEQ=0 and SEQACK=0.
SEQ_0 = (0).to_bytes(length=4, byteorder='big', signed=False)
SEQACK_0 = (0).to_bytes(length=4, byteorder='big', signed=False)

# Length of the payload of handshakes is 0 in bytes.
LEN_HANDSHAKE_PACKET = (0).to_bytes(length=4, byteorder='big', signed=False)


def int_to_bu_bytes(i: int, bytes_length: int) -> bytes:
    """
    Convert an non-negative int to big-endian unsigned bytes.
    :param i: The non-negative int.
    :param bytes_length:
    :return: The bytes.
    """
    return i.to_bytes(length=bytes_length, byteorder='big', signed=False)


def bytes_to_bu_int(b: bytes) -> int:
    """
    Convert bytes to a big-endian unsigned int.
    :param b: The bytes.
    :return: The big-endian unsigned int.
    """
    return int.from_bytes(bytes=b, byteorder='big', signed=False)


def generate_chksm(packet: bytes) -> bytes:
    """
    generate checksum for a packet.
    :param packet: The packet to generate checksum.
    :return: The checksum. The length of checksum is 2 bytes.
    """
    even_sum = 0x0
    odd_sum = 0x0
    for b in packet[0::2]:
        even_sum += b
        even_sum %= 256
    for b in packet[1::2]:
        odd_sum += b
        odd_sum %= 256
    even_chksm = int_to_bu_bytes(((256 - even_sum) % 256), 1)
    odd_chksm = int_to_bu_bytes(((256 - odd_sum) % 256), 1)
    # The order is reverted here because checksum bytes are in 13 and 14. 13 is odd.
    chksm = odd_chksm + even_chksm
    return chksm


def checksum(msg: bytes) -> bool:
    """
    Check the checksum.
    :param msg: The packet to check.
    :return: Correctness of checksum.
    """
    even_chksm = 0x0
    odd_chksm = 0x0
    for b in msg[0::2]:
        even_chksm += b
        even_chksm %= 256
        # print(even_chksm)
    for b in msg[1::2]:
        odd_chksm += b
        odd_chksm %= 256
        # print(odd_chksm)
    return even_chksm == 0 and odd_chksm == 0


def get_handshake_1_packet() -> bytes:
    """
    Return the packet of handshake 1.
    :return: The packet of handshake 1.
    """
    packet_without_chksm = HANDSHAKE_1 + SEQ_0 + SEQACK_0 + LEN_HANDSHAKE_PACKET
    return packet_without_chksm + generate_chksm(packet_without_chksm)


def get_handshake_2_packet() -> bytes:
    """
    Return the packet of handshake 2.
    :return: The packet of handshake 2.
    """
    packet_without_chksm = HANDSHAKE_2 + SEQ_0 + SEQACK_0 + LEN_HANDSHAKE_PACKET
    return packet_without_chksm + generate_chksm(packet_without_chksm)


def get_handshake_3_packet() -> bytes:
    """
    Return the packet of handshake 3.
    :return: The packet of handshake 3.
    """
    packet_without_chksm = HANDSHAKE_3 + SEQ_0 + SEQACK_0 + LEN_HANDSHAKE_PACKET
    return packet_without_chksm + generate_chksm(packet_without_chksm)


def assemble(info: bytes, data: bytes) -> bytes:
    """
    Receive the bytes before chksm and bytes after chksm, generate chksm and concat them
    together.
    :param info: Bytes before chksm. Named by ArslanaWu.
    :param data: Bytes after chksm.
    :return: msg in bytes.
    """
    chksm: bytes = generate_chksm(info + data)
    return info + chksm + data


def dissemble(msg: bytes) -> (bytes, bytes):
    """
    Dissemble the msg into info and data. Checksum is checked.
    :param msg: The message.
    :return: info and data in bytes.
    """
    if not checksum(msg):
        raise Exception('Wrong chksm')
    info = msg[0:13]
    data = msg[15:]
    return info, data


def extract_data_from_msg(msg: bytes) -> (bytes, int, int, int):
    """
    Extract data from message.
    :param msg: The message bytes received.
    :return: data bytes, seq_num int, seqack_num int, length of data int.
    """
    if not checksum(msg):
        raise Exception('Wrong chksm')
    data_length = bytes_to_bu_int(msg[9:13])
    if data_length != len(msg) - 15:
        raise Exception(f'Wrong msg length: {data_length}, {len(msg) - 15}')
    data = msg[15:]
    seq_num = bytes_to_bu_int(msg[1:5])
    seqack_num = bytes_to_bu_int(msg[5:9])
    return data, seq_num, seqack_num, data_length


def generate_data_msg(seq_num: int, seqack_num: int, data: bytes) -> bytes:
    """
    Given SEQ, SEQACK and the data bytes, generate the message bytes.
    :param seq_num: SEQ
    :param seqack_num: SEQACK
    :param data: The data bytes.
    :return: The message bytes.
    """
    return generate_msg_with_sfa(DATA, seq_num, seqack_num, data)


def generate_segment_msg(seq_num: int, seqack_num: int, segment: bytes) -> bytes:
    """
    Given SEQ, SEQACK and the segment bytes, generate the message bytes.
    :param seq_num: SEQ
    :param seqack_num: SEQACK
    :param segment: The segment bytes.
    :return: The message bytes.
    """
    return generate_msg_with_sfa(SEGMENT, seq_num, seqack_num, segment)


def generate_segment_end_msg(seq_num: int, seqack_num: int) -> bytes:
    return generate_msg_with_sfa(SEGMENT_END, seq_num, seqack_num, b'')


def generate_msg_with_sfa(sfa: bytes, seq_num: int, seqack_num: int, data: bytes) -> bytes:
    seq = int_to_bu_bytes(seq_num, 4)
    seqack = int_to_bu_bytes(seqack_num, 4)
    data_length_bytes = int_to_bu_bytes(len(data), 4)
    chksm = generate_chksm(sfa + seq + seqack + data_length_bytes + data)
    return sfa + seq + seqack + data_length_bytes + chksm + data


def generate_ack_msg(seq_num: int, seqack_num: int) -> bytes:
    """
    Generate an ack message from seq and seqack of the receiver.
    :param seq_num: seq of the receiver.
    :param seqack_num: seqack of the receiver.
    :return: The ack message the receiver uses.
    """
    sfa: bytes = ACK
    seq = int_to_bu_bytes(seq_num, 4)
    seqack = int_to_bu_bytes(seqack_num, 4)
    data_length_bytes = int_to_bu_bytes(0, 4)
    chksm: bytes = generate_chksm(sfa + seq + seqack + data_length_bytes)
    return sfa + seq + seqack + data_length_bytes + chksm


def generate_probe_msg(seq_num: int, seqack_num: int) -> bytes:
    sfa: bytes = PROBE
    seq = int_to_bu_bytes(seq_num, 4)
    seqack = int_to_bu_bytes(seqack_num, 4)
    data_length_bytes = int_to_bu_bytes(0, 4)
    chksm: bytes = generate_chksm(sfa + seq + seqack + data_length_bytes)
    return sfa + seq + seqack + data_length_bytes + chksm


def generate_probe_rpl_msg(seq_num: int, seqack_num: int, buff_size: bytes) -> bytes:
    sfa: bytes = PROBE_RPL
    seq = int_to_bu_bytes(seq_num, 4)
    seqack = int_to_bu_bytes(seqack_num, 4)
    data_length_bytes = int_to_bu_bytes(len(buff_size), 4)
    chksm: bytes = generate_chksm(sfa + seq + seqack + data_length_bytes + buff_size)
    return sfa + seq + seqack + data_length_bytes + chksm + buff_size


def get_seq_num(msg: bytes):
    """
    Get the seq field from a message.
    :param msg: The message.
    :return: The seq field.
    """
    return bytes_to_bu_int(msg[1:5])


def get_seqack_num(msg: bytes):
    """
    Get the seqack field from a message.
    :param msg: The message.
    :return: The seq field.
    """
    return bytes_to_bu_int(msg[5:9])


def get_sfa_from_msg(msg: bytes) -> bytes:
    return msg[0:1]


if __name__ == '__main__':
    print('Testing constants.')
    print(HANDSHAKE_1.hex())
    print(HANDSHAKE_2.hex())
    print(HANDSHAKE_3.hex())
    print(SEQ_0.hex())
    print(SEQACK_0.hex())
    print(get_handshake_1_packet().hex())
    print(get_handshake_2_packet().hex())
    print(get_handshake_3_packet().hex())
    try:
        dissemble(get_handshake_1_packet())
        dissemble(get_handshake_2_packet())
        dissemble(get_handshake_3_packet())
    except Exception as e:
        print(e)
    print('Testing constants ended.')
