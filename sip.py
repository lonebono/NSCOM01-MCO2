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
    local_port: Optional[int] = None
    remote_port: Optional[int] = None

    def _format_sip_uri(self, user: str, host: str, port: Optional[int]) -> str:
        return f"sip:{user}@{host}:{port}" if port else f"sip:{user}@{host}"

    def build_message(self) -> str:
        """Combines header and SDP into a full SIP packet."""
        if self.request.startswith("SIP/2.0"):
            start_line = self.request
            method = self.request.split()[2] if len(self.request.split()) >= 3 else ""
        else:
            uri = self._format_sip_uri(self.to_user, self.remote_ip, self.remote_port)
            start_line = f"{self.request} {uri} SIP/2.0"
            method = self.request

        header = (
            f"{start_line}\r\n"
            f"From: <{self._format_sip_uri(self.from_user, self.local_ip, self.local_port)}>;tag={self.tag}\r\n"
            f"To: <{self._format_sip_uri(self.to_user, self.remote_ip, self.remote_port)}>\r\n"
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
    
    # Parse From header: <sip:user@host[:port]>;tag=value
    from_user = ""
    local_ip = ""
    local_port = None
    tag = 0
    
    if "sip:" in from_header:
        uri = from_header.split("sip:", 1)[1].split(">", 1)[0].split(";", 1)[0]
        from_user, host_port = uri.split("@", 1)
        if ":" in host_port:
            local_ip, port_str = host_port.rsplit(":", 1)
            try:
                local_port = int(port_str)
            except ValueError:
                local_ip = host_port
        else:
            local_ip = host_port
    
    if "tag=" in from_header:
        tag = int(from_header.split("tag=", 1)[1])
    
    # Parse To header: <sip:user@host[:port]>
    to_user = ""
    remote_ip = ""
    remote_port = None
    
    if "sip:" in to_header:
        uri = to_header.split("sip:", 1)[1].split(">", 1)[0].split(";", 1)[0]
        to_user, host_port = uri.split("@", 1)
        if ":" in host_port:
            remote_ip, port_str = host_port.rsplit(":", 1)
            try:
                remote_port = int(port_str)
            except ValueError:
                remote_ip = host_port
        else:
            remote_ip = host_port
    
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
        local_port=local_port,
        remote_port=remote_port,
        sdp=sdp_obj,
        cseq=int(cseq_line.split()[0]),
        tag=tag,
        call_id=call_id
    )
    
    return sip_obj, sdp_obj
