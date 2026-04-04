import random, time
from dataclasses import dataclass, field

@dataclass
class SDPSession:
    local_ip: str
    rtp_port: int
    username: str = "-"
    session_name: str = "Talk"
    # Using timestamps for ID and Version as per RFC 4566
    session_id: int = field(default_factory=lambda: int(time.time()))
    version: int = field(default_factory=lambda: int(time.time()))

    def build(self) -> str:
        """Constructs the raw SDP string."""
        lines = [
            "v=0",
            f"o={self.username} {self.session_id} {self.version} IN IP4 {self.local_ip}",
            f"s={self.session_name}",
            f"c=IN IP4 {self.local_ip}",
            "t=0 0",
            f"m=audio {self.rtp_port} RTP/AVP 0",
            "a=rtpmap:0 PCMU/8000",
            "" # Trailing newline
        ]
        return "\r\n".join(lines)

@dataclass
class SIPInvite:
    local_ip: str
    remote_ip: str
    from_user: str
    to_user: str
    sdp: SDPSession
    cseq: int = 1
    tag: int = field(default_factory=lambda: random.randint(100, 999))
    call_id: str = field(init=False)

    def __post_init__(self):
        # Automatically generate Call-ID if not provided
        self.call_id = f"{random.randint(1000, 9999)}@{self.local_ip}"

    def build_message(self) -> str:
        """Combines header and SDP into a full SIP INVITE packet."""
        sdp_body = self.sdp.build()
        header = (
            f"INVITE sip:{self.to_user}@{self.remote_ip} SIP/2.0\r\n"
            f"From: <sip:{self.from_user}@{self.local_ip}>;tag={self.tag}\r\n"
            f"To: <sip:{self.to_user}@{self.remote_ip}>\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self.cseq} INVITE\r\n"
            f"Allow: INVITE, ACK, BYE\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp_body)}\r\n"
            "\r\n"
            f"{sdp_body}"
        )
        return header
    


def parse_sdp(data):
    """Extracts remote RTP port and IP from SDP."""
    lines = data.decode().split('\r\n')
    port = 0
    for line in lines:
        if line.startswith('m=audio'):
            port = int(line.split()[1])
    return port

