import socket
import select
import errno
import time
import threading

IP = '127.0.0.1'
TCP_PORT = 1234
UDP_PORT = 1235
HEADER_LENGTH = 5
STATUS_PERIOD = 10

client_username = input("enter your username: ")
client_password = input("enter your password: ")

# AF_INET corresponds to address family IPv4
# SOCK_STREAM corresponds to TCP
tcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
tcp_client_socket.connect(((IP, TCP_PORT)))
tcp_client_socket.setblocking(False)
# SOCK_DGRAM corresponds to UDP
udp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
udp_client_socket.connect(((IP, UDP_PORT)))
udp_client_socket.setblocking(False)

encoded_client_username = client_username.encode('utf-8')
header = f"{len(encoded_client_username):<{HEADER_LENGTH}}".encode('utf-8')
tcp_client_socket.send(header + encoded_client_username)

def send_status():
    start_time = time.time()

    while True:

        end_time = time.time()

        if end_time - start_time >= STATUS_PERIOD:
            client_message = '&&HELLO&&'.encode('utf-8')
            message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
            udp_client_socket.sendto(message_header + client_message, (IP, UDP_PORT))
            start_time = time.time()

def send_message():
    while True:

        client_message = f"{client_username}: {input()}"

        if client_message:
            client_message = client_message.encode('utf-8')
            message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
            tcp_client_socket.send(message_header + client_message)

def receive_message():

    while True:
        try:
            while True:
                message_header = tcp_client_socket.recv(HEADER_LENGTH)
                message_length = int(message_header.decode('utf-8'))
                message = tcp_client_socket.recv(message_length).decode('utf-8')

                print(f'{message}')

        except IOError as e:
            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                exit()
            continue

        except Exception:
            exit()

send_thread = threading.Thread(target=send_message)
send_thread.start()

recieve_thread = threading.Thread(target=receive_message)
recieve_thread.start()

status_thread = threading.Thread(target=send_status)
status_thread.start()
