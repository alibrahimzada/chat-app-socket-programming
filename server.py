import socket
import select # OS level IO capability
import time

IP = '127.0.0.1'
TCP_PORT = 6234
UDP_PORT = 6235
MAX_CONNECTIONS = 5
HEADER_LENGTH = 5
ACTIVITY_LIMIT = 200

# AF_INET corresponds to address family IPv4
# SOCK_STREAM corresponds to TCP
# SOCK_DGRAM corresponds to UDP
tcp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
# udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# reconnect to server if address is in use
tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# bind the IP and PORT to the sockets
tcp_socket.bind((IP, TCP_PORT))
# udp_socket.bind((IP, UDP_PORT))

# the queue will take at most MAX_CONNECTIONS
tcp_socket.listen(MAX_CONNECTIONS)

print(f'TCP server is running at {IP}:{TCP_PORT} and it is waiting to receive connections!')
print(f'UDP server is running at {IP}:{UDP_PORT} and it is waiting to receive connections!')

sockets = [tcp_socket]
clients = {}

def recieve_message(client_socket):
    try:
        message_header = client_socket.recv(HEADER_LENGTH)

        if not len(message_header):
            return False

        message_length = int(message_header.decode('utf-8'))
        return {'header': message_header, 'data': client_socket.recv(message_length), 'activity': ACTIVITY_LIMIT, 'start_time': time.time()}

    except Exception:
        False


def search_peer(peer_username):
    address = None
    for client in clients:
        if clients[client]['data'].decode('utf-8') == peer_username:
            address = client.getpeername()

    return address


def get_peer_socket(peer_ip_addr, peer_port):
    for client in clients:
        address = client.getpeername()
        print(type(address[0]), type(address[1]))

        if address == (peer_ip_addr, peer_port):
            return client

    return None


while True:

    # select.select will make use of OS and it will wait until a file descriptor is ready for IO
    read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

    # if udp_socket not in read_sockets:
    #     for client_socket in clients.copy():
    #         waited_duration = time.time() - clients[client_socket]['start_time']
    #         clients[client_socket]['activity'] -= waited_duration
    #         clients[client_socket]['start_time'] = time.time()

    #         if clients[client_socket]['activity'] <= 0:
    #             print(f'terminating {client_address}:{client_address[1]} username: {clients[client_socket]["data"].decode("utf-8")}')
    #             clients.pop(client_socket)
    #             sockets.remove(client_socket)


    for notified_socket in read_sockets:

        if notified_socket == tcp_socket:

            client_socket, client_address = tcp_socket.accept()

            client_data = recieve_message(client_socket)

            if not client_data:
                continue

            sockets.append(client_socket)
            clients[client_socket] = client_data
            print(f"accepted new connection from {client_address}:{client_address[1]} username: {client_data['data'].decode('utf-8')}")

        # if notified_socket == udp_socket:
        #     message = udp_socket.recvfrom(256)
        #     clients[client_socket]['activity'] = ACTIVITY_LIMIT
        #     print(f'resetting activity time from {client_address}:{client_address[1]} username: {clients[client_socket]["data"].decode("utf-8")}')

        else: 
            
            message = recieve_message(notified_socket)

            if not message:
                # remove the socket here
                continue
            
            decoded_message = message['data'].decode('utf-8')

            if decoded_message == '&&LOGOUT&&':
                clients.pop(notified_socket)
                sockets.remove(notified_socket)
                continue
            
            if '&&SEARCH&&' in decoded_message:
                searched_peer = (decoded_message.split('|')[-1]).strip()
          
                response = search_peer(searched_peer)
          
                if response == None:
                    response = 'user not found'
                else:
                    response = 'user found. its address is' + str(response)

                message['data'] = response.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

            if '&&CHATREQUEST&&' in decoded_message:
                peer_ip_addr = (decoded_message.split('|')[-2]).strip()
                peer_port = int((decoded_message.split('|')[-1]).strip())

                client_socket = get_peer_socket(peer_ip_addr, peer_port)

                client_socket.send(message['header'] + message['data'])
                continue

            user = clients[notified_socket]

            for client_socket in clients:
                client_socket.send(user['header'] + user['data'] + message['header'] + message['data'])
