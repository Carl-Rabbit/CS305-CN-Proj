# Big-endian is used for all bytes.

# SYN, FIN and ACK bits of a message. I do not want to manipulate bits
# directly, so I used bytes as the minimum unit.
SYN = (128).to_bytes(length=1, byteorder='big', signed=False)
FIN = (64).to_bytes(length=1, byteorder='big', signed=False)
ACK = (32).to_bytes(length=1, byteorder='big', signed=False)

# Bytes of SEQ=0 and SEQACK=0.
SEQ_0 = (0).to_bytes(length=4, byteorder='big', signed=False)
SEQACK_0 = (0).to_bytes(length=4, byteorder='big', signed=False)

# Fixme: Should you use the length of payload, or the length of the whole packet?
# Length of the payload of handshakes is 0 in bytes.
# However, the length of the whole packet is 15 in bytes.
# Here, we use the length of the whole packet as the length, which is 15.
LEN_HANDSHAKE_PACKET = (15).to_bytes(length=4, byteorder='big', signed=False)


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
    return even_chksm + odd_chksm


def get_handshake_1_packet() -> bytes:
    """
    Return the packet of handshake 1.
    :return: The packet of handshake 1.
    """
    packet_without_chksm = SYN + SEQ_0 + SEQACK_0 + LEN_HANDSHAKE_PACKET
    return SYN + SEQ_0 + SEQACK_0 + LEN_HANDSHAKE_PACKET + generate_chksm(packet_without_chksm)


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
    print('Testing constants ended.')
