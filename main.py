import socket
import threading
import os
from sip import build_invite, parse_sdp
from rtp import build_rtp_packet

#  Config
LOCAL_IP = "127.0.0.1"
SIP_PORT = 5060
RTP_PORT = 8000
SSRC = 12345

call_active = False
remote_rtp_addr = None

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

#  Signaling Listener

def sip_listener():
    """Handles incoming SIP signaling over UDP[cite: 187, 242]."""
    global call_active, remote_rtp_addr
    
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((LOCAL_IP, SIP_PORT))
        print(f"[*] SIP Listener active on {LOCAL_IP}:{SIP_PORT}")
        
        while True:
            data, addr = s.recvfrom(2048)
            msg = data.decode()
            
            # Handle INVITE [cite: 224]
            if msg.startswith("INVITE"):
                print(f"[RECV] INVITE from {addr}")
                remote_rtp_port = parse_sdp(data)
                remote_rtp_addr = (addr[0], remote_rtp_port)
                
                # In a real project, you'd send 100 Trying and 180 Ringing here [cite: 206, 209]
                # For now, we go straight to 200 OK [cite: 211]
                # (You'll need a build_200_ok function in sip.py)
                print("[*] Automatic 200 OK sent (Call Accepted)")
                
            # Handle 200 OK (If we were the ones who called) [cite: 212]
            elif msg.startswith("SIP/2.0 200 OK"):
                print("[RECV] 200 OK - Call Established!")
                remote_rtp_port = parse_sdp(data)
                remote_rtp_addr = (addr[0], remote_rtp_port)
                call_active = True
                
                # Start the Media thread [cite: 228]
                media_thread = threading.Thread(
                    target=rtp_file_sender, 
                    args=(remote_rtp_addr[0], remote_rtp_addr[1], "sample.wav")
                )
                media_thread.start()

            # Handle BYE [cite: 217, 226]
            elif msg.startswith("BYE"):
                print("[RECV] BYE - Terminating call.")
                call_active = False

#  Main Loop

def main():
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
                invite_msg, _ = build_invite(LOCAL_IP, target_ip, SIP_PORT, RTP_PORT)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.sendto(invite_msg, (target_ip, SIP_PORT))
                print(f"[*] Calling {target_ip}...")
                
            elif cmd[0] == "hangup":
                # Logic to send BYE [cite: 226]
                print("[*] Hanging up...")
                call_active = False
                
            elif cmd[0] == "exit":
                break
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()