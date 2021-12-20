import socket
import select
import errno

IP = '127.0.0.1'
TCP_PORT = 1234
HEADER_LENGTH = 10

client_username = input()
client_password = input()

# AF_INET corresponds to address family IPv4
# SOCK_STREAM corresponds to TCP
client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
client_socket.connect(((IP, TCP_PORT)))
client_socket.setblocking(False)

client_username = client_username.encode('utf-8')
header = f"{len(client_username):<{HEADER_LENGTH}}".encode('utf-8')
client_socket.send(header + client_username)

while True:

    client_message = input(f"{client_username}: ")

    if client_message:
        client_message = client_message.encode('utf-8')
        message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
        client_socket.send(message_header + client_message)

    try:
        while True:
            username_header = client_socket.recv(HEADER_LENGTH)
            username_length = int(username_header.decode('utf-8'))
            username = client_socket.recv(username_length).decode('utf-8')

            message_header = client_socket.recv(HEADER_LENGTH)
            message_length = int(message_header.decode('utf-8'))
            message = client_socket.recv(message_length).decode('utf-8')

            print(f'{username}: {message}')

    except IOError as e:
        if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
            exit()
        continue

    except Exception:
        exit()
