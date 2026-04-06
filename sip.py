import random, time


def parse_sdp(data):
    """Extracts remote RTP port and IP from SDP."""
    lines = data.decode('utf-8', errors='ignore').split('\r\n')
    port = 0
    ip = None
    for line in lines:
        if line.startswith('c=IN IP4 '):
            ip = line.split()[-1]
        if line.startswith('m=audio'):
            port = int(line.split()[1])
    return ip, port
