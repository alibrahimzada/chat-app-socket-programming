import socket
import os
import errno
import time
import threading

IP = '127.0.0.1'
TCP_PORT = 6234
UDP_PORT = 6235
HEADER_LENGTH = 5
STATUS_PERIOD = 60

client_username = input("enter your username: ")
client_password = input("enter your password: ")

# AF_INET corresponds to address family IPv4
# SOCK_STREAM corresponds to TCP
tcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
tcp_client_socket.connect(((IP, TCP_PORT)))
tcp_client_socket.setblocking(False)
# SOCK_DGRAM corresponds to UDP
# udp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
# udp_client_socket.connect(((IP, UDP_PORT)))
# udp_client_socket.setblocking(False)

encoded_client_username = client_username.encode('utf-8')
header = f"{len(encoded_client_username):<{HEADER_LENGTH}}".encode('utf-8')
tcp_client_socket.send(header + encoded_client_username)

# def send_status():
#     start_time = time.time()

#     while True:

#         end_time = time.time()

#         if end_time - start_time >= STATUS_PERIOD:
#             client_message = '&&HELLO&&'.encode('utf-8')
#             message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
#             udp_client_socket.sendto(message_header + client_message, (IP, UDP_PORT))
#             start_time = time.time()

def send_message():
    logout = False
    while True:

        client_message = f"{client_username}: {input()}"
        message_content = ' '.join(client_message.split(':')[1:]).strip()

        if message_content == 'LOGOUT':
            client_message = '&&LOGOUT&&'
            logout = True

        if 'SEARCH' in message_content:
            searched_peer = client_message.split(' ')[-1].strip()
            client_message = f'&&SEARCH&&|{searched_peer}|{client_username}'

        if 'CHAT REQUEST' in message_content:
            peer_ip_addr = client_message.split(' ')[-2]
            peer_port = client_message.split(' ')[-1]
            client_message = f'&&CHATREQUEST&&|{peer_ip_addr}|{peer_port}|{client_username}'

        if 'REJECT' in message_content:
            sender_username = client_message.split(' ')[-1]
            client_message = f'&&REJECT&&|{client_username}|{sender_username}'

        if 'OK' in message_content:
            sender_username = client_message.split(' ')[-1]
            client_message = f'&&OK&&|{client_username}|{sender_username}'
        
        if message_content == 'EXIT':
            client_message = f'&&EXIT&&|{client_username}'

        if 'GROUP CHAT' in message_content:
            tokens = message_content.split()
            client_message = f'&&GROUPCHAT&&|{client_username}|'
            for i in range(2, len(tokens)):
                client_message += tokens[i] + '|'

        if 'REJECT GROUP' in message_content:
            group_number = client_message.split(' ')[-1]
            client_message = f'&&REJECTGROUP&&|{client_username}|{group_number}'

        if 'OK GROUP' in message_content:
            group_number = client_message.split(' ')[-1]
            client_message = f'&&OKGROUP&&|{client_username}|{group_number}'


        client_message = client_message.encode('utf-8')
        message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
        tcp_client_socket.send(message_header + client_message)

        if logout:
            print(f'loggin out from session. goodbye {client_username}')
            os.kill(os.getpid(), 9)

def receive_message():

    while True:
        try:
            while True:
                username_header = tcp_client_socket.recv(HEADER_LENGTH)
                username_length = int(username_header.decode('utf-8'))
                username = tcp_client_socket.recv(username_length).decode('utf-8')

                message_header = tcp_client_socket.recv(HEADER_LENGTH)
                message_length = int(message_header.decode('utf-8'))
                message = tcp_client_socket.recv(message_length).decode('utf-8')
                
                if ':' in message:
                    message = ' '.join(message.split(':')[1:]).strip()
                else:
                    username = 'server'

                print(f'{username}: {message}')

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

# status_thread = threading.Thread(target=send_status)
# status_thread.start()
