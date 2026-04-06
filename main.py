import socket
import threading
import os, time, random
from sip import build_invite, parse_sdp
from rtp import build_rtp_packet
from dataclasses import dataclass, field

@dataclass
class SDP:
    local_ip: str
    rtp_port: int
    username: str = "-"
    session_name: str = "Talk"
    # Using timestamps for ID and Version as per RFC 4566
    session_id: int
    version: int

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
    sdp: SDP
    cseq: int = 1
    tag: int
    call_id: str

    def build_message(self) -> str:
        """Combines header and SDP into a full SIP INVITE packet."""
        sdp_body = self.sdp.build()
        header = (
            f"{self.request}\r\n"
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

#  Config
LOCAL_IP = "127.0.0.1"
REMOTE_IP = "1.1.1.1"
SIP_PORT = 5060
RTP_PORT = 8000
SSRC = 12345
FROM_USER ="vaughn"
TO_USER ="andre"

call_active = False
remote_rtp_addr = None
current_session = {'obj': None}

def rtp_sender(target_ip, target_port):
    # RTP Audio send in realtime
    pass

def sip_listener(sock):
    global call_active, current_session
    
    while True:
        try:
            data, addr = sock.recvfrom(2048)
            msg = data.decode('utf-8', errors='ignore')

            # Scenario 1: Receive an INVITE
            if msg.startswith("INVITE"):
                print(f"\n[RECV] Incoming call from {addr[0]}")

                ok_resp = "SIP/2.0 200 OK\r\nContent-Length: 0\r\n\r\n"
                sock.sendto(ok_resp.encode(), addr)
                print("[*] Sent 200 OK. Waiting for ACK...")

            # Scenario 2: Receive a 200 OK
            elif "SIP/2.0 200 OK" in msg:
                print(f"\n[RECV] 200 OK from {addr[0]}")
                if current_session['obj']:
                    ack = current_session['obj'].build_ack()
                    sock.sendto(ack.encode(), addr)
                    print("[*] Sent ACK. Call Established!")
                    
                    call_active = True
                    threading.Thread(target=rtp_sender, args=(addr[0], RTP_PORT), daemon=True).start()

            # Scenario 3: Receive an ACK
            elif msg.startswith("ACK"):
                print("[RECV] ACK Received. Starting Media...")
                call_active = True
                threading.Thread(target=rtp_sender, args=(addr[0], RTP_PORT), daemon=True).start()

            elif "BYE" in msg:
                print("[RECV] BYE Received. Call ended.")
                call_active = False

        except Exception as e:
            print(f"Listener Error: {e}")

            remote_call_id = "unknown"

            # get most recent call_id from incoming packet
            for line in msg.split("\n"):
                if line.lower().startswith("call-id:"):
                    remote_call_id = line.split(":", 1)[1].strip()

            # obj is the initial invite_sip, or whenever it gets updated in main 
            obj = current_session.get("obj")

            error_sip = SIP(
                request="SIP/2.0 400 Bad Request",
                local_ip=LOCAL_IP, remote_ip=REMOTE_IP,
                from_user=FROM_USER, to_user=TO_USER,
                tag = obj.tag if obj else 0,
                call_id=remote_call_id
            )
            sock.sendto(error_sip.build_message().encode(), (REMOTE_IP, SIP_PORT))
            break

#  Media Logic 

def rtp_file_sender(target_ip, target_port, filename):
    """Reads a file and sends it via RTP segments[cite: 228, 232]."""
    global call_active
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq, ts = 0, 0
    
    if not os.path.exists(filename):
        print(f"[!] File {filename} not found.")
        return

    with open(filename, "rb") as f:
        print(f"[*] Starting RTP stream to {target_ip}:{target_port}...")
        while call_active:
            payload = f.read(160)  # Standard 20ms chunk 
            if not payload:
                print("[*] End of file reached.")
                break
            
            packet = build_rtp_packet(seq, ts, SSRC, payload)
            sock.sendto(packet, (target_ip, target_port))
            
            seq = (seq + 1) % 65536
            ts += 160
            import time
            time.sleep(0.02) 



#  Main Loop

def main():
    global call_active
    
    sip_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sip_sock.bind((LOCAL_IP, SIP_PORT))
    except OSError:
        print(f"[!] Could not bind to port {SIP_PORT}.")
        return
    
    listener = threading.Thread(target=sip_listener, daemon=True)
    listener.start()

    print("\n--- NSCOM01 MCO2 VoIP Client ---")
    print("Commands: 'call <ip>', 'hangup', 'exit'")
    
    try:
        while True:
            cmd = input("> ").strip().split()
            if not cmd: continue
            
            if cmd[0] == "call":
                target_ip = cmd[1]

                invite_sdp = SDP(
                    local_ip = LOCAL_IP,
                    rtp_port = RTP_PORT,
                    username = FROM_USER,
                    session_name = "Talk",
                    session_id = int(time.time()),
                    version = int(time.time())
                )

                invite_sip = SIP(
                    request="INVITE",
                    local_ip=LOCAL_IP,
                    remote_ip=REMOTE_IP,
                    from_user=FROM_USER,
                    to_user=TO_USER,
                    sdp=invite_sdp,
                    cseq = 1,
                    tag = random.randint(1000, 9999),
                    call_id = random.randint(10000, 99999)
                )

                current_session['obj'] = invite_sip
                # invite_sip is a dataclass object, while build_message() turns it into a string

                sip_sock.sendto(invite_sip.build_message().encode(), (REMOTE_IP, SIP_PORT))
                print(f"[*] INVITE sent to {REMOTE_IP}...")

                # the rest is handled by the listener thread...

                
            elif cmd[0] == "hangup":
                obj = current_session.get("obj")

                if obj and call_active:
                    obj.request = "BYE"
                    obj.cseq += 1
                    obj.sdp = None
                    
                    bye_packet = obj.build_message()
                    sip_sock.sendto(bye_packet.encode(), (REMOTE_IP, SIP_PORT))
                    
                    call_active = False
                    print("[*] BYE sent. Call ended.")
                else:
                    print("[!] No active call.")
                
            elif cmd[0] == "exit":
                break
    except KeyboardInterrupt:
        pass
    sip_sock.close()

if __name__ == "__main__":
    main()