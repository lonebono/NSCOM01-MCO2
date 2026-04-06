import socket, threading, os, time, random
import sounddevice as sd
from typing import Dict, Any, Optional
from sip import SIP, SDP, parse_sip
from rtp import build_rtp_packet, build_rtcp_report, encode_audio, decode_audio

# Config
LOCAL_IP = "127.0.0.1"
REMOTE_IP = "127.0.0.1"
SIP_PORT, RTP_PORT = 5060, 8000
SSRC = 12345
FROM_USER, TO_USER = "vaughn", "andre"

call_active = False
current_session: Dict[str, Any] = {'obj': None, 'remote_rtp_port': 8000}

def rtp_sender(target_ip, target_port):
    global call_active
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq, ts, pkts = 0, 0, 0
    
    def callback(indata, frames, time_info, status):
        nonlocal seq, ts, pkts
        if not call_active: raise sd.CallbackStop()
        payload = encode_audio(indata)
        sock.sendto(build_rtp_packet(seq, ts, SSRC, payload), (target_ip, target_port))
        pkts += 1
        seq = (seq + 1) % 65536
        ts += frames
        if pkts % 250 == 0:
            sock.sendto(build_rtcp_report(SSRC, pkts), (target_ip, target_port + 1))

    with sd.InputStream(samplerate=8000, channels=1, callback=callback, blocksize=160):
        while call_active: time.sleep(0.1)
    sock.close()

def rtp_receiver():
    global call_active
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((LOCAL_IP, RTP_PORT))
        s.settimeout(1.0)
        out_stream = sd.OutputStream(samplerate=8000, channels=1, dtype='int16')
        out_stream.start()
        while call_active:
            try:
                data, _ = s.recvfrom(2048)
                out_stream.write(decode_audio(data[12:]))
            except socket.timeout: continue
        out_stream.stop()

def sip_listener(sock):
    global call_active, current_session
    while True:
        try:
            data, addr = sock.recvfrom(2048)
            sip_obj, sdp_obj = parse_sip(data)
            msg = sip_obj.request

            if msg.startswith("INVITE"):
                print(f"\n[SIP] INVITE from {addr[0]}")
                current_session['remote_rtp_port'] = sdp_obj.rtp_port
                
                resp_sdp = SDP(local_ip=LOCAL_IP, rtp_port=RTP_PORT, username=FROM_USER)
                ok_sip = SIP(request="SIP/2.0 200 OK", local_ip=LOCAL_IP, remote_ip=addr[0],
                             from_user=TO_USER, to_user=FROM_USER, sdp=resp_sdp, 
                             cseq=sip_obj.cseq, call_id=sip_obj.call_id)
                sock.sendto(ok_sip.build_message().encode(), addr)

            elif "200 OK" in msg:
                print(f"[SIP] 200 OK received")
                current_session['remote_rtp_port'] = sdp_obj.rtp_port
                ack = SIP(request="ACK", local_ip=LOCAL_IP, remote_ip=addr[0],
                          from_user=FROM_USER, to_user=TO_USER, cseq=sip_obj.cseq, 
                          tag=sip_obj.tag, call_id=sip_obj.call_id)
                sock.sendto(ack.build_message().encode(), addr)
                call_active = True
                threading.Thread(target=rtp_sender, args=(addr[0], sdp_obj.rtp_port), daemon=True).start()
                threading.Thread(target=rtp_receiver, daemon=True).start()

            elif msg.startswith("ACK"):
                call_active = True
                threading.Thread(target=rtp_sender, args=(addr[0], current_session['remote_rtp_port']), daemon=True).start()
                threading.Thread(target=rtp_receiver, daemon=True).start()

            elif msg.startswith("BYE"):
                call_active = False
                sock.sendto(b"SIP/2.0 200 OK\r\n\r\n", addr)
        except Exception as e: print(f"Error: {e}")

def main():
    sip_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sip_sock.bind((LOCAL_IP, SIP_PORT))
    threading.Thread(target=sip_listener, args=(sip_sock,), daemon=True).start()
    print(f"--- VoIP Client ({FROM_USER}) ---")
    while True:
        cmd = input("> ").strip().split()
        if not cmd: continue
        if cmd[0] == "call":
            target = cmd[1] if len(cmd) > 1 else REMOTE_IP
            sdp = SDP(local_ip=LOCAL_IP, rtp_port=RTP_PORT, username=FROM_USER)
            invite = SIP(request="INVITE", local_ip=LOCAL_IP, remote_ip=target,
                         from_user=FROM_USER, to_user=TO_USER, sdp=sdp)
            current_session['obj'] = invite
            sip_sock.sendto(invite.build_message().encode(), (target, SIP_PORT))
        elif cmd[0] == "endcall":
            global call_active
            call_active = False
        elif cmd[0] == "exit": break

if __name__ == "__main__":
    main()