import struct
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
    return struct.pack('!BBHII', 0x80, 200, 6, ssrc, p_count)

def encode_audio(indata):
    """Converts float32 mic input to G.711 u-law."""
    audio_int16 = (indata * 32767).astype(np.int16).tobytes()
    return audioop.lin2ulaw(audio_int16, 2)

def decode_audio(payload):
    """Converts G.711 u-law to int16 for playback."""
    audio_data = audioop.ulaw2lin(payload, 2)
    return np.frombuffer(audio_data, dtype=np.int16)