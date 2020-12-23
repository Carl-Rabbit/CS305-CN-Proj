# Big-endian is used for all bytes.

# SYN, FIN and ACK bits of a message. I do not want to manipulate bits
# directly, so I used bytes as the minimum unit.
SYN = (128).to_bytes(length=1, byteorder='big', signed=False)
FIN = (64).to_bytes(length=1, byteorder='big', signed=False)
ACK = (32).to_bytes(length=1, byteorder='big', signed=False)

DATA = (0).to_bytes(length=1, byteorder='big', signed=False)

# Bytes of SEQ=0 and SEQACK=0.
SEQ_0 = (0).to_bytes(length=4, byteorder='big', signed=False)
SEQACK_0 = (0).to_bytes(length=4, byteorder='big', signed=False)

# Length of the payload of handshakes is 0 in bytes.
LEN_HANDSHAKE_PACKET = (0).to_bytes(length=4, byteorder='big', signed=False)


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
    even_chksm = ((256 - even_sum) % 256).to_bytes(length=1, byteorder='big', signed=False)
    odd_chksm = ((256 - odd_sum) % 256).to_bytes(length=1, byteorder='big', signed=False)
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
    for b in msg[1::2]:
        odd_chksm += b
        odd_chksm %= 256
    return even_chksm == 0 and odd_chksm == 0


def get_handshake_1_packet() -> bytes:
    """
    Return the packet of handshake 1.
    :return: The packet of handshake 1.
    """
    packet_without_chksm = SYN + SEQ_0 + SEQACK_0 + LEN_HANDSHAKE_PACKET
    return packet_without_chksm + generate_chksm(packet_without_chksm)


def get_handshake_2_packet() -> bytes:
    """
    Return the packet of handshake 2.
    :return: The packet of handshake 2.
    """
    handshake_1_seqack = (15).to_bytes(length=4, byteorder='big', signed=False)
    packet_without_chksm = FIN + SEQ_0 + handshake_1_seqack + LEN_HANDSHAKE_PACKET
    return packet_without_chksm + generate_chksm(packet_without_chksm)


def get_handshake_3_packet() -> bytes:
    """
    Return the packet of handshake 3.
    :return: The packet of handshake 3.
    """
    handshake_2_seq = (15).to_bytes(length=4, byteorder='big', signed=False)
    handshake_2_seqack = (15).to_bytes(length=4, byteorder='big', signed=False)
    packet_without_chksm = ACK + handshake_2_seq + handshake_2_seqack + LEN_HANDSHAKE_PACKET
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
    Extract data from message. It is assumed that chksm is correct.
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
    sfa = DATA
    seq = seq_num.to_bytes(length=4, byteorder='big', signed=False)
    seqack = seqack_num.to_bytes(length=4, byteorder='big', signed=False)
    data_length = len(data).to_bytes(length=4, byteorder='big', signed=False)
    chksm = generate_chksm(sfa + seq + seqack + data_length + data)
    return sfa + seq + seqack + data_length + chksm + data


if __name__ == '__main__':
    print('Testing constants.')
    print(SYN.hex())
    print(FIN.hex())
    print(ACK.hex())
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
