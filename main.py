import socket
import threading
import os, time, random
from sip import build_invite, parse_sdp, SIP, SDP, parse_sip
from rtp import build_rtp_packet

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

            # Parse incoming SIP packet
            sip_obj, sdp_obj = parse_sip(data)
            msg = sip_obj.request

            # Scenario 1: Receive an INVITE
            if msg.startswith("INVITE"):
                print(f"\n[RECV] Incoming call from {addr[0]}")
                current_session['obj'] = sip_obj
                
                # Build 200 OK response with SDP from local
                response_sdp = SDP(
                    local_ip=LOCAL_IP,
                    rtp_port=RTP_PORT,
                    username=FROM_USER,
                    session_id=int(time.time()),
                    version=int(time.time())
                ) # just add the rtp media details like encoding, buffer here later
                
                response_tag = random.randint(1000, 9999)
                ok_sip = SIP(
                    request="SIP/2.0 200 OK",
                    local_ip=LOCAL_IP,
                    remote_ip=sip_obj.local_ip,
                    from_user=sip_obj.to_user,
                    to_user=sip_obj.from_user,
                    sdp=response_sdp,
                    cseq=sip_obj.cseq,
                    tag=response_tag,
                    call_id=sip_obj.call_id
                )
                
                sock.sendto(ok_sip.build_message().encode(), addr)
                print("[*] Sent 200 OK with SDP. Waiting for ACK...")

            # Scenario 2: Receive a 200 OK
            elif "SIP/2.0 200 OK" in msg:
                print(f"\n[RECV] 200 OK from {addr[0]}")
                
                # Extract remote RTP details from the 200 OK response
                if sdp_obj:
                    remote_rtp_port = sdp_obj.rtp_port
                    print(f"[*] Remote RTP port: {remote_rtp_port}")
                
                # Build and send ACK
                ack_sip = SIP(
                    request="ACK",
                    local_ip=sip_obj.local_ip,
                    remote_ip=sip_obj.remote_ip,
                    from_user=sip_obj.to_user,
                    to_user=sip_obj.from_user,
                    sdp=None,
                    cseq=sip_obj.cseq,
                    tag=sip_obj.tag,
                    call_id=sip_obj.call_id
                )
                
                sock.sendto(ack_sip.build_message().encode(), addr)
                print("[*] Sent ACK. Waiting for call to establish...")

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
                    # Create a new BYE SIP message
                    bye_sip = SIP(
                        request="BYE",
                        local_ip=obj.local_ip,
                        remote_ip=obj.remote_ip,
                        from_user=obj.from_user,
                        to_user=obj.to_user,
                        sdp=None,
                        cseq=obj.cseq + 1,
                        tag=obj.tag,
                        call_id=obj.call_id
                    )
                    
                    sip_sock.sendto(bye_sip.build_message().encode(), (REMOTE_IP, SIP_PORT))
                    
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