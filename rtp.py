import struct
import time
import sounddevice as sd
import numpy as np
try:
    import audioop
except ImportError:
    import audioop_lts as audioop

def build_rtp_packet(seq, ts, ssrc, payload):
    header = struct.pack('!BBHII', 0x80, 0x00, seq, ts, ssrc)
    return header + payload

def build_rtcp_report(ssrc, p_count):
    # Header: V=2, P=0, RC=0, PT=200 (SR), length=6 (28 bytes total / 4 - 1).
    ntp_time = time.time() + 2208988800.0  # convert unix epoch to NTP epoch
    ntp_sec = int(ntp_time)
    ntp_frac = int((ntp_time - ntp_sec) * (1 << 32))
    rtp_ts = int((time.time() % 1) * 8000)
    octet_count = p_count * 160
    return struct.pack('!BBHIIIIII', 0x80, 200, 6, ssrc, ntp_sec, ntp_frac, rtp_ts, p_count, octet_count)


def encode_audio(indata):
    """Converts float32 mic input to G.711 u-law."""
    audio_int16 = (indata * 32767).astype(np.int16).tobytes()
    return audioop.lin2ulaw(audio_int16, 2)

def decode_audio(payload):
    """Converts G.711 u-law to int16 for playback."""
    audio_data = audioop.ulaw2lin(payload, 2)
    return np.frombuffer(audio_data, dtype=np.int16)