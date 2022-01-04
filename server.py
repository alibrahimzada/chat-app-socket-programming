import socket
import select # OS level IO capability
import time

import threading

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
udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# reconnect to server if address is in use
tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# bind the IP and PORT to the sockets
tcp_socket.bind((IP, TCP_PORT))
udp_socket.bind((IP, UDP_PORT))

# the queue will take at most MAX_CONNECTIONS
tcp_socket.listen(MAX_CONNECTIONS)

print(f'TCP server is running at {IP}:{TCP_PORT} and it is waiting to receive connections!')
print(f'UDP server is running at {IP}:{UDP_PORT} and it is waiting to receive connections!')

sockets = [tcp_socket, udp_socket]
clients = {}
private_chat_rooms = {}
group_chat_rooms = {}


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
        if address == (peer_ip_addr, peer_port):
            return client

    return None


def get_socket(username):
    ip, port = search_peer(username)
    user_socket = get_peer_socket(ip, port)
    return user_socket


def forward_message(chat_rooms, notified_socket, message):
    for chat_room in chat_rooms:
        if notified_socket in chat_rooms[chat_room]:
        # peer1 is receiver, peer2 is sender or peer 2 is receiver, peer1 is send
            user = clients[notified_socket]
            for client_socket in chat_rooms[chat_room]:
                client_socket.send(user['header'] + user['data'] + message['header'] + message['data'])


def process_text_message(notified_socket, message):
    forward_message(private_chat_rooms, notified_socket, message)
    forward_message(group_chat_rooms, notified_socket, message)


def is_busy(peer_socket):
    for chat_room in private_chat_rooms:
        if peer_socket in private_chat_rooms[chat_room]:
            return True

    return False


def remove_participant(chat_rooms, peer_socket):
    room = None
    for chat_room in chat_rooms:
        if peer_socket in chat_rooms[chat_room]:
            chat_rooms[chat_room].remove(peer_socket)
            room = chat_room

    if room is None:
        return room, None
    return room, chat_rooms[room]


def end_session(peer_socket):
    room, participant_sockets = remove_participant(private_chat_rooms, peer_socket)

    if participant_sockets is None:
        room, participant_sockets = remove_participant(group_chat_rooms, peer_socket)
        if len(participant_sockets) == 0:
            group_chat_rooms.pop(room)

    else:
        if len(participant_sockets) == 0:
            private_chat_rooms.pop(room)

    return participant_sockets


def register_new_users():

    while True:
        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

        if tcp_socket not in read_sockets:
            continue

        client_socket, client_address = tcp_socket.accept()

        client_data = recieve_message(client_socket)

        if not client_data:
            continue

        sockets.append(client_socket)
        clients[client_socket] = client_data
        print(f"accepted new connection from {client_address}:{client_address[1]} username: {client_data['data'].decode('utf-8')}")


def update_activity():

    while True:
        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

        if udp_socket not in read_sockets:
            for client_socket in clients.copy():
                client_address = client_socket.getpeername()
                waited_duration = time.time() - clients[client_socket]['start_time']
                clients[client_socket]['activity'] -= waited_duration
                clients[client_socket]['start_time'] = time.time()

                if clients[client_socket]['activity'] <= 0:
                    print(f'terminating {client_address}:{client_address[1]} username: {clients[client_socket]["data"].decode("utf-8")}')
                    clients.pop(client_socket)
                    sockets.remove(client_socket)

        else:

            message = udp_socket.recvfrom(256)
            clients[client_socket]['activity'] = ACTIVITY_LIMIT
            print(f'resetting activity time from {client_address}:{client_address[1]} username: {clients[client_socket]["data"].decode("utf-8")}')


def process_message():
    total_private_rooms = 0
    total_global_rooms = 0

    while True:

        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

        for notified_socket in read_sockets:

            if notified_socket == tcp_socket or notified_socket == udp_socket:
                continue
                
            message = recieve_message(notified_socket)

            if not message:
                # remove the socket here
                continue
            
            decoded_message = message['data'].decode('utf-8')

            if decoded_message == '&&LOGOUT&&':
                clients.pop(notified_socket)
                sockets.remove(notified_socket)
                continue
            
            elif '&&SEARCH&&' in decoded_message:
                searched_peer = (decoded_message.split('|')[-2]).strip()
                sender_username = (decoded_message.split('|')[-1]).strip()
            
                response = search_peer(searched_peer)
            
                if response == None:
                    response = 'user not found'
                else:
                    response = f'{searched_peer} found. its address is ' + str(response)

                sender_socket = get_socket(sender_username)

                message['data'] = response.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                sender_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])
                continue

            elif '&&CHATREQUEST&&' in decoded_message:
                searched_peer = (decoded_message.split('|')[-2]).strip()
                sender_username = (decoded_message.split('|')[-1]).strip()

                client_socket = get_socket(searched_peer)
                sender_socket = get_socket(sender_username)

                if client_socket is None:
                    continue

                if is_busy(client_socket):
                    message['data'] = f'the user is busy. try again later.'.encode('utf-8')
                    message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                    sender_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                else:
                    message['data'] = f'{sender_username} would like to chat with you? (OK/REJECT)'.encode('utf-8')
                    message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue
            
            elif '&&REJECT&&' in decoded_message:
                sender_username = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()
                sender_socket = get_socket(sender_username)

                message['data'] = f'{peer_username} rejected the chat request!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                sender_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue

            elif '&&OK&&' in decoded_message:
                sender_username = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()

                peer1_socket = get_socket(sender_username)
                peer2_socket = get_socket(peer_username)

                total_private_rooms += 1
                private_chat_rooms[str(total_private_rooms)] = [peer1_socket, peer2_socket]

                message['data'] = f'{peer_username} accepted the chat request. you can send your message now!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                peer1_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue

            elif '&&EXIT&&' in decoded_message:
                peer_username = (decoded_message.split('|')[-1]).strip()
                peer_socket = get_socket(peer_username)

                participant_sockets = end_session(peer_socket)

                message['data'] = f'{peer_username} left the chat room.'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                for client_socket in participant_sockets:
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue

            elif '&&GROUPCHAT&&' in decoded_message:
                tokens = decoded_message.split('|')
                peers = tokens[2:-1]
                sender_username = tokens[1]
                total_global_rooms += 1

                message['data'] = f'{sender_username} would like to add you to group chat room {total_global_rooms}? (OK/REJECT GROUP <room_number>)'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                group_chat_rooms[str(total_global_rooms)] = [get_socket(sender_username)]

                for peer in peers:
                    peer_socket = get_socket(peer)

                    if peer_socket is None:
                        continue
                    
                    peer_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue

            elif '&&REJECTGROUP&&' in decoded_message:
                group_number = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()

                message['data'] = f'{peer_username} rejected the group chat request!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                for client_socket in group_chat_rooms[group_number]:
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue

            elif '&&OKGROUP&&' in decoded_message:
                group_number = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()

                peer_socket = get_socket(peer_username)

                group_chat_rooms[group_number].append(peer_socket)

                message['data'] = f'{peer_username} joined the group chat'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                for client_socket in group_chat_rooms[group_number]:
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                continue

            process_text_message(notified_socket, message)


register_user_thread = threading.Thread(target=register_new_users)
register_user_thread.start()
print('successfully started register user thread')

update_activity_thread = threading.Thread(target=update_activity)
update_activity_thread.start()
print('successfully started update activity thread')

process_message_thread = threading.Thread(target=process_message)
process_message_thread.start()
print('successfully started process message thread')
