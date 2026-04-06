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

    def build_message(self) -> str:
        """Combines header and SDP into a full SIP packet."""
        # Extract method name from request (e.g., "INVITE" from "INVITE sip:..." or "ACK")
        method = self.request.split()[0] if " " in self.request else self.request
        header = (
            f"{self.request}\r\n"
            f"From: <sip:{self.from_user}@{self.local_ip}>;tag={self.tag}\r\n"
            f"To: <sip:{self.to_user}@{self.remote_ip}>\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self.cseq} {method}\r\n"
            f"Allow: INVITE, ACK, BYE\r\n"
        )
        if self.sdp:
            sdp_body = self.sdp.build()
            header += f"Content-Type: application/sdp\r\nContent-Length: {len(sdp_body)}\r\n\r\n{sdp_body}"
        else:
            header += "Content-Length: 0\r\n\r\n"
        return header


def parse_sip(packet):
    """Extracts remote RTP port and IP from SDP."""
    lines = packet.decode('utf-8', errors='ignore').split('\r\n')
    
    # Parse request line (first line)
    request = lines[0] if lines else ""
    
    # Parse headers and find SDP start
    sip_headers = {}
    sdp_start = 0
    
    for i, line in enumerate(lines[1:], 1):
        if line == "":  # Empty line separates headers from SDP body
            sdp_start = i + 1
            break
        
        if ":" in line:
            key, value = line.split(":", 1)
            sip_headers[key.strip().lower()] = value.strip()
    
    # Extract SIP fields
    from_header = sip_headers.get('from', '')
    to_header = sip_headers.get('to', '')
    call_id = sip_headers.get('call-id', '')
    cseq_line = sip_headers.get('cseq', '1')
    
    # Parse From header: <sip:user@ip>;tag=value
    from_user = ""
    local_ip = ""
    tag = 0
    
    if "sip:" in from_header:
        from_user = from_header.split("sip:")[1].split("@")[0]
        local_ip = from_header.split("@")[1].split(">")[0]
    
    if "tag=" in from_header:
        tag = int(from_header.split("tag=")[1])
    
    # Parse To header: <sip:user@ip>
    to_user = ""
    remote_ip = ""
    
    if "sip:" in to_header:
        to_user = to_header.split("sip:")[1].split("@")[0]
        remote_ip = to_header.split("@")[1].split(">")[0]
    
    # Parse SDP section
    rtp_port = 8000
    session_id = 0
    version = 0
    username = "-"
    
    for line in lines[sdp_start:]:
        if line.startswith("m=audio"):
            # Format: m=audio 8000 RTP/AVP 0
            rtp_port = int(line.split()[1])
        elif line.startswith("o="):
            # Format: o=username session_id version IN IP4 ip
            parts = line.split()
            username = parts[0][2:]
            session_id = int(parts[1])
            version = int(parts[2])
    
    # Create SDP object
    sdp_obj = SDP(
        local_ip=local_ip,
        rtp_port=rtp_port,
        username=username,
        session_id=session_id,
        version=version
    )
    
    # Create SIP object
    sip_obj = SIP(
        request=request,
        local_ip=local_ip,
        remote_ip=remote_ip,
        from_user=from_user,
        to_user=to_user,
        sdp=sdp_obj,
        cseq=int(cseq_line.split()[0]),
        tag=tag,
        call_id=call_id
    )
    
    return sip_obj, sdp_obj
