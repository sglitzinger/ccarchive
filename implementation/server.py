'''
Implements receiver for experimental evaluation of archive-based covert channel.
'''


import socketserver
import struct
import binascii


# Match entries in client.py
#HOST = "192.168.137.31"
HOST = "132.176.77.133"
PORT = 44544


class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.data = self.request.recv(4)

        print(self.data)
        print(binascii.hexlify(self.data))
        print(struct.unpack('!f', self.data))


if __name__ == "__main__":
    with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
        # Interrupt with Ctrl-C
        server.serve_forever()
