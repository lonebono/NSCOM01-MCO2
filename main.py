import socket, threading, os, time, random, sys
import sounddevice as sd
from typing import Dict, Any, Optional
from sip import SIP, SDP, parse_sip
from rtp import build_rtp_packet, build_rtcp_report, encode_audio, decode_audio

# Config
LOCAL_IP = "127.0.0.1"
REMOTE_IP = "127.0.0.1"
try:
    SIP_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5060
    RTP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
except ValueError:
    SIP_PORT, RTP_PORT = 5060, 8000
SSRC = 12345
FROM_USER, TO_USER = "vaughn", "andre"

call_active = False
current_session: Dict[str, Any] = {'obj': None, 'remote_rtp_port': 8000}

def bind_udp_socket(host: str, port: int, name: str):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
        return sock, port
    except OSError:
        sock.close()
        fallback = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        fallback.bind((host, 0))
        actual_port = fallback.getsockname()[1]
        print(f"[!] {name} port {port} unavailable; bound to available port {actual_port} instead.")
        return fallback, actual_port


def bind_sip_socket(host: str, port: int):
    return bind_udp_socket(host, port, "SIP")

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
    global call_active, RTP_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind((LOCAL_IP, RTP_PORT))
        except OSError:
            s.close()
            s, actual_rtp_port = bind_udp_socket(LOCAL_IP, RTP_PORT, "RTP")
            RTP_PORT = actual_rtp_port
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
                             from_user=TO_USER, to_user=FROM_USER,
                             local_port=SIP_PORT, remote_port=addr[1],
                             sdp=resp_sdp, cseq=sip_obj.cseq, call_id=sip_obj.call_id)
                sock.sendto(ok_sip.build_message().encode(), addr)

            elif "200 OK" in msg:
                print(f"[SIP] 200 OK received")
                current_session['remote_rtp_port'] = sdp_obj.rtp_port
                ack = SIP(request="ACK", local_ip=LOCAL_IP, remote_ip=addr[0],
                          from_user=FROM_USER, to_user=TO_USER,
                          local_port=SIP_PORT, remote_port=addr[1],
                          cseq=sip_obj.cseq,
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
        except Exception as e:
            print(f"Error: {e}")
            
            remote_call_id = "unknown"
            msg = data.decode('utf-8', errors='ignore')
            for line in msg.split("\n"):
                if line.lower().startswith("call-id:"):
                    remote_call_id = line.split(":", 1)[1].strip()
                    break
            
            error_sip = SIP(
                request="SIP/2.0 500 Internal Server Error",
                local_ip=LOCAL_IP, remote_ip=addr[0],
                from_user=TO_USER, to_user=FROM_USER,
                local_port=SIP_PORT, remote_port=addr[1],
                call_id=remote_call_id
            )
            sock.sendto(error_sip.build_message().encode(), addr)

def main():
    global SIP_PORT, RTP_PORT
    sip_sock, actual_sip_port = bind_sip_socket(LOCAL_IP, SIP_PORT)
    SIP_PORT = actual_sip_port
    rtp_sock, actual_rtp_port = bind_udp_socket(LOCAL_IP, RTP_PORT, "RTP")
    RTP_PORT = actual_rtp_port
    rtp_sock.close()
    threading.Thread(target=sip_listener, args=(sip_sock,), daemon=True).start()
    print(f"--- VoIP Client  ---")
    print(f"[+] SIP listening on {LOCAL_IP}:{SIP_PORT}")
    print(f"[+] RTP listening on {LOCAL_IP}:{RTP_PORT}")
    while True:
        cmd = input("> ").strip().split()
        if not cmd: continue
        if cmd[0] == "call":
            target = cmd[1] if len(cmd) > 1 else REMOTE_IP
            target_host = target
            target_port = SIP_PORT
            if ":" in target:
                host, port_str = target.rsplit(":", 1)
                if host:
                    target_host = host
                try:
                    target_port = int(port_str)
                except ValueError:
                    print(f"[!] Invalid target port: {port_str}")
                    continue
            sdp = SDP(local_ip=LOCAL_IP, rtp_port=RTP_PORT, username=FROM_USER)
            invite = SIP(request="INVITE", local_ip=LOCAL_IP, remote_ip=target_host,
                         from_user=FROM_USER, to_user=TO_USER,
                         local_port=SIP_PORT, remote_port=target_port,
                         sdp=sdp)
            current_session['obj'] = invite
            sip_sock.sendto(invite.build_message().encode(), (target_host, target_port))
        elif cmd[0] == "endcall":
            global call_active
            call_active = False
        elif cmd[0] == "exit": break

if __name__ == "__main__":
    main()