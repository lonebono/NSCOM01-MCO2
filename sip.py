import random, time


def parse_sdp(data):
    """Extracts remote RTP port and IP from SDP."""
    lines = data.decode().split('\r\n')
    port = 0
    for line in lines:
        if line.startswith('m=audio'):
            port = int(line.split()[1])
    return port

