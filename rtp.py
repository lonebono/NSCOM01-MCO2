import struct

def build_rtp_packet(seq, ts, ssrc, payload):
    """Standard 12-byte RTP Header + Payload."""
    # V=2, P=0, X=0, CC=0 (0x80) | PT=0 (PCMU)
    header = struct.pack('!BBHII', 0x80, 0x00, seq, ts, ssrc)
    return header + payload

def build_rtcp_report(ssrc, p_count):
    """Basic RTCP Sender Report for stats."""
    return struct.pack('!BBHII', 0x80, 200, 6, ssrc, p_count)