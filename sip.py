import random, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SDP:
    local_ip: str
    rtp_port: int
    username: str = "-"
    session_name: str = "Talk"
    session_id: int = field(default_factory=lambda: int(time.time()))
    version: int = field(default_factory=lambda: int(time.time()))

    def build(self) -> str:
        lines = [
            "v=0",
            f"o={self.username} {self.session_id} {self.version} IN IP4 {self.local_ip}",
            f"s={self.session_name}",
            f"c=IN IP4 {self.local_ip}",
            "t=0 0",
            f"m=audio {self.rtp_port} RTP/AVP 0",
            "a=rtpmap:0 PCMU/8000",
            "" 
        ]
        return "\r\n".join(lines)

@dataclass
class SIP:
    request: str
    local_ip: str
    remote_ip: str
    from_user: str
    to_user: str
    cseq: int = 1
    tag: int = field(default_factory=lambda: random.randint(1000, 9999))
    call_id: str = field(default_factory=lambda: str(random.randint(10000, 99999)))
    sdp: Optional[SDP] = None
    local_port: Optional[int] = None
    remote_port: Optional[int] = None

    def _format_sip_uri(self, user: str, host: str, port: Optional[int]) -> str:
        return f"sip:{user}@{host}:{port}" if port else f"sip:{user}@{host}"

    def build_message(self) -> str:
        if self.request.startswith("SIP/2.0"):
            start_line = self.request
        else:
            uri = self._format_sip_uri(self.to_user, self.remote_ip, self.remote_port)
            start_line = f"{self.request} {uri} SIP/2.0"

        header = (
            f"{start_line}\r\n"
            f"From: <{self._format_sip_uri(self.from_user, self.local_ip, self.local_port)}>;tag={self.tag}\r\n"
            f"To: <{self._format_sip_uri(self.to_user, self.remote_ip, self.remote_port)}>\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self.cseq} {self.request.split()[0]}\r\n"
            f"Allow: INVITE, ACK, BYE\r\n"
        )
        if self.sdp:
            sdp_body = self.sdp.build()
            header += f"Content-Type: application/sdp\r\nContent-Length: {len(sdp_body)}\r\n\r\n{sdp_body}"
        else:
            header += "Content-Length: 0\r\n\r\n"
        return header

def parse_sip(packet):
    lines = packet.decode('utf-8', errors='ignore').split('\r\n')
    request = lines[0]
    sip_headers = {}
    sdp_start = 0
    for i, line in enumerate(lines[1:], 1):
        if line == "":
            sdp_start = i + 1
            break
        if ":" in line:
            k, v = line.split(":", 1)
            sip_headers[k.strip().lower()] = v.strip()
    
    rtp_port = 8000
    for line in lines[sdp_start:]:
        if line.startswith("m=audio"):
            rtp_port = int(line.split()[1])
            
    cseq_val = int(sip_headers.get('cseq', '1').split()[0])
    sdp_obj = SDP(local_ip="", rtp_port=rtp_port)
    sip_obj = SIP(request=request, local_ip="", remote_ip="", from_user="", to_user="", cseq=cseq_val, call_id=sip_headers.get('call-id', ''), sdp=sdp_obj)
    return sip_obj, sdp_obj