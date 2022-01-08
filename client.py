import socket
import os
import errno
import time
import threading
import random
import string
import select

IP = '127.0.0.1'
TCP_PORT = 6234
UDP_PORT = 6235

while True:
    try:
        TCP_SERVER_PORT = int(''.join(random.choices(string.digits, k = 4)))
        tcp_server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_server_socket.bind((IP, TCP_SERVER_PORT))
        break
    except PermissionError:
        continue

HEADER_LENGTH = 5
STATUS_PERIOD = 60
MAX_CONNECTIONS = 5

client_username = input("enter your username: ")
client_password = input("enter your password: ")

# AF_INET corresponds to address family IPv4
# SOCK_STREAM corresponds to TCP
tcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
tcp_client_socket.connect(((IP, TCP_PORT)))
tcp_client_socket.setblocking(False)

tcp_server_socket.listen(MAX_CONNECTIONS)

peers = []
sockets = [tcp_server_socket]

# SOCK_DGRAM corresponds to UDP
udp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
udp_client_socket.connect(((IP, UDP_PORT)))
udp_client_socket.setblocking(False)

encoded_client_data = ('&&REGISTER&&|' + client_username + '|' + str(TCP_SERVER_PORT)).encode('utf-8')
header = f"{len(encoded_client_data):<{HEADER_LENGTH}}".encode('utf-8')
tcp_client_socket.send(header + encoded_client_data)

def send_status():
    start_time = time.time()

    while True:

        end_time = time.time()

        if end_time - start_time >= STATUS_PERIOD:
            client_message = f'&&HELLO&&|{client_username}'.encode('utf-8')
            message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
            udp_client_socket.sendto(message_header + client_message, (IP, UDP_PORT))
            start_time = time.time()

def send_message():

    while True:
        server_message = False
        ok_group = False
        reject_group = False

        client_message = f"{client_username}: {input()}"
        client_message = '&&CLIENTMESSAGE&&|' + client_message
        message_content = ' '.join(client_message.split(':')[1:]).strip()

        if message_content == 'LOGOUT':
            client_message = '&&LOGOUT&&'
            server_message = True

        if 'SEARCH' in message_content:
            searched_peer = client_message.split(' ')[-1].strip()
            client_message = f'&&SEARCH&&|{searched_peer}|{client_username}'
            server_message = True

        if 'GROUP CHAT' in message_content:
            tokens = message_content.split()
            client_message = f'&&GROUPCHAT&&|{client_username}|'
            server_message = True
            for i in range(2, len(tokens)):
                client_message += tokens[i] + '|'

        if 'REJECT GROUP' in message_content:
            group_number = client_message.split(' ')[-1]
            client_message = f'&&REJECTGROUP&&|{client_username}|{group_number}'
            reject_group = True
            server_message = True

        if 'OK GROUP' in message_content:
            group_number = client_message.split(' ')[-1]
            client_message = f'&&OKGROUP&&|{client_username}|{group_number}'
            ok_group = True
            server_message = True

        if 'CHAT REQUEST' in message_content:
            searched_peer = client_message.split(' ')[-1].strip()
            client_message = f'&&CHATREQUEST&&|{searched_peer}|{client_username}'
            server_message = True

        if 'REJECT' in message_content and not reject_group:
            sender_username = client_message.split(' ')[-1]
            client_message = f'&&REJECT&&|{client_username}|{sender_username}'
            server_message = True

        if 'OK' in message_content and not ok_group:
            sender_username = client_message.split(' ')[-1]
            client_message = f'&&OK&&|{client_username}|{sender_username}|{TCP_SERVER_PORT}'
            server_message = True
        
        if message_content == 'EXIT':
            client_message = f'&&EXIT&&|{client_username}'
            server_message = True

        client_message = client_message.encode('utf-8')
        message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')

        if server_message:
            tcp_client_socket.send(message_header + client_message)
        elif not server_message and peers != []:
            print(' '.join(client_message.decode('utf-8').split('|')[1:]).strip())
            for socket_ in peers:
                socket_.send(message_header + client_message)


def receive_server_message():

    while True:
        try:
            while True:
                username_header = tcp_client_socket.recv(HEADER_LENGTH)
                username_length = int(username_header.decode('utf-8'))
                username = tcp_client_socket.recv(username_length).decode('utf-8')

                message_header = tcp_client_socket.recv(HEADER_LENGTH)
                message_length = int(message_header.decode('utf-8'))
                message = tcp_client_socket.recv(message_length).decode('utf-8')
                
                if '&&LOGOUTSUCCESS&&' in message:
                    print(f'loggin out from session. goodbye {client_username}')
                    os.kill(os.getpid(), 9)

                elif '&&CLIENTOK&&' in message:
                    receiver_port = int(message.split('|')[-1].strip())
                    message = message.split('|')[1].strip()
                    tcp_client_peer_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
                    tcp_client_peer_socket.connect(((IP, receiver_port)))
                    tcp_client_peer_socket.setblocking(False)
                    peers.append(tcp_client_peer_socket)

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

def receive_peer_message():

    while True:
        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets)

        if tcp_server_socket in read_sockets:
            socket_, client_address = tcp_server_socket.accept()
            sockets.append(socket_)
        else:
            socket_ = read_sockets[0]

        message_header = socket_.recv(HEADER_LENGTH)

        if not len(message_header):
            return False

        message_length = int(message_header.decode('utf-8'))
        message = socket_.recv(message_length).decode('utf-8')

        if ':' in message:
            message = ' '.join(message.split('|')[1:]).strip()

        print(message)


send_thread = threading.Thread(target=send_message)
send_thread.start()

receive_server_thread = threading.Thread(target=receive_server_message)
receive_server_thread.start()

recieve_peer_thread = threading.Thread(target=receive_peer_message)
recieve_peer_thread.start()

status_thread = threading.Thread(target=send_status)
status_thread.start()
