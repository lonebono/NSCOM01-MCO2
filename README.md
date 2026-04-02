# NSCOM01 MCO2

insert description here

### How to Run


# Documentation

# SIP Request


## INVITE sip:{src ip addr} SIP/2.0
- kept SIP/2.0 so wireshark can detect it hopefully
- purposeky does not include the username

## ACK sip:linphone@11.0.0.40;transport=udp SIP/2.0

## BYE sip:linphone@11.0.0.40;transport=udp SIP/2.0


# SIP Header

## Via: SIP/2.0/UDP {src ip addr}:{src port};branch=z9hG4bK.{transaction id}
- branch will start with the "z9hG4bK" flag then proceeded with a randomly generated 9 character string

- rport is omitted since NAT traversal is not implemented

## From: <sip:linphone@11.0.0.34>;tag=fu-f~cPit
- tag is also randomly generated 9 char string

## To: sip:{src ip addr};tag={tag id}
- tag of the client that you are connecting to
- it will be omitted during an active REQUEST branch

## CSeq: 20 INVITE
- sequence number then SIP command

## Call-ID: TmIkzS6hSB
- rand 10 char int

## Max-Forwards omitted
- no proxy implementation to be of use

## Supported omitted

## Allow: INVITE, ACK, BYE
- removed other requests, only keeping MCO2 specs

## Content-Type: application/sdp
- we use sdp

## Content-Length: {count}
- count of characters in body

## Contact: <sip:linphone@11.0.0.34;transport=udp>
- removed sip instance since we dont have other devices



# SDP Body

## v=0
- Session Description Protocol Version (v): 0

## 0=linphone 3880 854 IN IP4 11.0.0.34
- originator and session identifier : username, id, version number, network address

## s=Talk
- session name mandatory with at least one UTF-8-encoded character

## t=0 0
- {start time} {end time}

## All other session descriptions were ommitted