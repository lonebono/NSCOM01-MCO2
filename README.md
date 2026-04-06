# NSCOM01 MCO2 - Implementation of Real-Time Audio Streaming over IP

## How to Run

1. Install Python and configure paths

- **Recommended:** Python 3.10 - 3.12
- **Note for Python 3.13+:** This project requires `audioop-lts` as the standard `audioop` library was deprecated in Python 3.13.

2. Install dependenies on the terminal **pip install sounddevice numpy audioop-lts**
3. Open two terminals

- Terminal 1: **python main.py 5060 8000**
- Terminal 2: python main.py 5061 8002

4. Start the program on both terminals 'main.py'
5. Start a call from one client by typing 'call (target ip)'
6. End call by typing 'endcall'

## Documentation

### SIP Signaling (RFC 3261)

Handshake: Full INVITE -> 200 OK -> ACK flow\
Mandatory Headers: Includes Via, From, To, Call-ID, CSeq, Contact, and Content-Length\
Teardown: Uses BYE to gracefully terminate sessions

### SDP Negotiation (RFC 4566)

Dynamic Exchange: SDP is embedded in INVITE and 200 OK to negotiate media endpoints\
Required Fields:

- v=0 (Version)
- o= (Origin) - Fixes the username and session ID
- c=IN IP4 (Connection) - Defines the target IP for audio
- m=audio (Media) - Defines the RTP port and PCMU/8000 codec

### RTP & RTCP (RFC 3550)

RTP Header: 12-byte header with Sequence Number, Timestamp, and SSRC\
RTCP: Sends periodic Sender Reports (SR) with packet/octet counts every 5 seconds

## Test Cases

1. Calling Setup
2. Real Time Audio
3. End Call
