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

## From: <sip:linphone@11.0.0.34>;tag=fu-f~cPit
- tag is also randomly generated 9 char string

## To: sip:{src ip addr};tag={tag id}
- tag of the client that you are connecting to
- it will be omitted during an active REQUEST branch

## CSeq: 20 INVITE
- sequence number then SIP command

## Call-ID: TmIkzS6hSB
- rand 10 char int

## Allow: INVITE, ACK, BYE
- removed other requests, only keeping MCO2 specs

## Content-Type: application/sdp
- we use sdp

## Content-Length: {count}
- count of characters in body



# SDP Body

## v=0
- Session Description Protocol Version (v): 0

## 0=linphone 3880 854 IN IP4 11.0.0.34
- originator and session identifier : username, session id, version number, network address
- session id is a 64 NTP timestamp, version number increments by 1 for each hold

## s=Talk
- session name mandatory with at least one UTF-8-encoded character

## t=0 0
- {start time} {end time}

## All other session descriptions were ommitted