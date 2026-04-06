import socket, threading, os, time, random, sys
import sounddevice as sd
from typing import Dict, Any, Optional
from sip import SIP, SDP, parse_sip
from rtp import build_rtp_packet, build_rtcp_report, encode_audio, decode_audio

# Config
LOCAL_IP = "192.168.1.23"
REMOTE_IP = "192.168.1.22"
try:
    SIP_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5060
    RTP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
except ValueError:
    SIP_PORT, RTP_PORT = 5060, 8000
SSRC = 12345
FROM_USER, TO_USER = "vaughn", "andre"
RECV_FILENAME = "received_output.g711"

call_active = False
sender_mode = "mic"
current_send_file = ""
current_record_file = "received_output.g711"
current_session: Dict[str, Any] = {'obj': None, 'remote_rtp_port': 8000, 'remote_ip': None, 'remote_port': None, 'call_id': None, 'cseq': None, 'tag': None}

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
        print(f"[!] {name} port {port} unavailable; using {actual_port}")
        return fallback, actual_port

def bind_sip_socket(host: str, port: int):
    return bind_udp_socket(host, port, "SIP")

def rtp_file_sender(target_ip, target_port, filename):
    global call_active
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq, ts = 0, 0
    try:
        with open(filename, "rb") as f:
            print(f"[*] Sending file: {filename}")
            chunk = f.read(160)
            while chunk and call_active:
                sock.sendto(build_rtp_packet(seq, ts, SSRC, chunk), (target_ip, target_port))
                seq = (seq + 1) % 65536
                ts += 160
                time.sleep(0.02) # Real-time 8kHz pacing
                chunk = f.read(160)
    except FileNotFoundError:
        print(f"[!] Error: {filename} not found.")
    finally:
        sock.close()

def rtp_sender(target_ip, target_port):
    global call_active, sender_mode, current_send_file
    if sender_mode == "file":
        rtp_file_sender(target_ip, target_port, current_send_file)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        seq, ts, pkts = 0, 0, 0
        def callback(indata, frames, time_info, status):
            nonlocal seq, ts, pkts
            if not call_active: raise sd.CallbackStop()
            payload = encode_audio(indata)
            sock.sendto(build_rtp_packet(seq, ts, SSRC, payload), (target_ip, target_port))
            seq, ts = (seq + 1) % 65536, ts + frames
        with sd.InputStream(samplerate=8000, channels=1, callback=callback, blocksize=160):
            while call_active: time.sleep(0.1)
        sock.close()

def rtp_receiver():
    global call_active, RTP_PORT, current_record_file
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((LOCAL_IP, RTP_PORT))
        s.settimeout(1.0)
        out_stream = sd.OutputStream(samplerate=8000, channels=1, dtype='int16')
        out_stream.start()
        
        with open(current_record_file, "wb") as f:
            print(f"[*] Storing and Playing audio to: {current_record_file}")
            while call_active:
                try:
                    data, _ = s.recvfrom(2048)
                    payload = data[12:]
                    f.write(payload) # Store
                    out_stream.write(decode_audio(payload)) # Play
                except socket.timeout: continue
        out_stream.stop()

def play_local_file(filename):
    print(f"[*] Playing: {filename}")
    out_stream = sd.OutputStream(samplerate=8000, channels=1, dtype='int16')
    out_stream.start()
    try:
        with open(filename, "rb") as f:
            chunk = f.read(160)
            while chunk:
                out_stream.write(decode_audio(chunk))
                chunk = f.read(160)
                time.sleep(0.02)
    except FileNotFoundError:
        print("[!] File not found.")
    finally:
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
                current_session['remote_ip'] = addr[0]
                current_session['remote_port'] = addr[1]
                current_session['call_id'] = sip_obj.call_id
                current_session['cseq'] = sip_obj.cseq
                current_session['tag'] = sip_obj.tag
                
                resp_sdp = SDP(local_ip=LOCAL_IP, rtp_port=RTP_PORT, username=FROM_USER)
                ok_sip = SIP(request="SIP/2.0 200 OK", local_ip=LOCAL_IP, remote_ip=addr[0],
                             from_user=TO_USER, to_user=FROM_USER,
                             local_port=SIP_PORT, remote_port=addr[1],
                             sdp=resp_sdp, cseq=sip_obj.cseq, call_id=sip_obj.call_id)
                sock.sendto(ok_sip.build_message().encode(), addr)

            elif "200 OK" in msg:
                print(f"[SIP] 200 OK received")
                current_session['remote_rtp_port'] = sdp_obj.rtp_port
                current_session['remote_ip'] = addr[0]
                current_session['remote_port'] = addr[1]
                current_session['cseq'] = sip_obj.cseq
                current_session['tag'] = sip_obj.tag
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
                current_session['remote_ip'] = addr[0]
                current_session['remote_port'] = addr[1]
                current_session['cseq'] = sip_obj.cseq
                call_active = True
                threading.Thread(target=rtp_sender, args=(addr[0], current_session['remote_rtp_port']), daemon=True).start()
                threading.Thread(target=rtp_receiver, daemon=True).start()

            elif msg.startswith("BYE"):
                call_active = False
                bye_response = SIP(request="SIP/2.0 200 OK", local_ip=LOCAL_IP, remote_ip=addr[0],
                                   from_user=TO_USER, to_user=FROM_USER,
                                   local_port=SIP_PORT, remote_port=addr[1],
                                   cseq=sip_obj.cseq, call_id=sip_obj.call_id)
                sock.sendto(bye_response.build_message().encode(), addr)
                print(f"[SIP] BYE received from {addr[0]}, sent 200 OK")
                # Reset session
                current_session['remote_ip'] = None
                current_session['remote_port'] = None
                current_session['call_id'] = None
                current_session['cseq'] = None
                current_session['tag'] = None
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
    global SIP_PORT, RTP_PORT, sender_mode, current_send_file, current_record_file
    sip_sock, actual_sip_port = bind_sip_socket(LOCAL_IP, SIP_PORT)
    SIP_PORT = actual_sip_port
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
            current_session['remote_ip'] = target_host
            current_session['remote_port'] = target_port
            current_session['call_id'] = invite.call_id
            current_session['cseq'] = invite.cseq
            sip_sock.sendto(invite.build_message().encode(), (target_host, target_port))
        elif cmd == "transfer":
            sender_mode = "file"
            target = cmd[1] if len(cmd) > 1 else REMOTE_IP
            current_send_file = cmd[2] if len(cmd) > 2 else "input.g711"
            sdp = SDP(local_ip=LOCAL_IP, rtp_port=RTP_PORT, username=FROM_USER)
            invite = SIP("INVITE", LOCAL_IP, target, FROM_USER, TO_USER, local_port=SIP_PORT, sdp=sdp)
            sip_sock.sendto(invite.build_message().encode(), (target, 5060))
        elif cmd == "record":
            current_record_file = cmd[1] if len(cmd) > 1 else "received_output.g711"
            print(f"[*] Next call will save to: {current_record_file}")
        elif cmd == "play":
            f_name = cmd[1] if len(cmd) > 1 else "received_output.g711"
            play_local_file(f_name)
        elif cmd[0] == "endcall":
            call_active = False
            if current_session['remote_ip']:
                bye = SIP(request="BYE", local_ip=LOCAL_IP, remote_ip=current_session['remote_ip'],
                          from_user=FROM_USER, to_user=TO_USER,
                          local_port=SIP_PORT, remote_port=current_session['remote_port'],
                          cseq=current_session['cseq'] + 1 if current_session['cseq'] else 1,
                          call_id=current_session['call_id'])
                sip_sock.sendto(bye.build_message().encode(), (current_session['remote_ip'], current_session['remote_port']))
                print(f"[SIP] BYE sent to {current_session['remote_ip']}:{current_session['remote_port']}")
                # Reset session
                current_session['remote_ip'] = None
                current_session['remote_port'] = None
                current_session['call_id'] = None
                current_session['cseq'] = None
                current_session['tag'] = None
            else:
                print("[!] No active call to end")
        elif cmd[0] == "exit": break

if __name__ == "__main__":
    main()