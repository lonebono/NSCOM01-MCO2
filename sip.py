import random, time

# make a sip/sdp struct so we can pass that object instead of one by one

def build_invite(local_ip, remote_ip, sip_port, rtp_port):
    """Creates INVITE with SDP body."""
    call_id = f"{random.randint(10,999)}@{local_ip}"
    sdp = (f"v=0\r\no=- {int(time.time())} {int(time.time())} IN IP4 {local_ip}\r\n"
           f"s=Talk\r\nc=IN IP4 {local_ip}\r\nt=0 0\r\n"
           f"m=audio {rtp_port} RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n")
    
    header = (f"INVITE sip:user@{remote_ip} SIP/2.0\r\n"
              f"From: <sip:vaughn@{local_ip}>;tag={random.randint(9,99)}\r\n"
              f"To: <sip:user@{remote_ip}>\r\n"
              f"Call-ID: {call_id}\r\n"
              f"CSeq: 1 INVITE\r\n"
              f"Allow: 1 INVITE, ACK, BYE\r\n"
              f"Content-Type: application/sdp\r\n"
              f"Content-Length: {len(sdp)}\r\n\r\n")
    return (header + sdp).encode(), call_id

def parse_sdp(data):
    """Extracts remote RTP port and IP from SDP."""
    lines = data.decode().split('\r\n')
    port = 0
    for line in lines:
        if line.startswith('m=audio'):
            port = int(line.split()[1])
    return port

def build_200_ok():
