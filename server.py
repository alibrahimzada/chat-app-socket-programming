import socket # socket library for creating sockets
import select # OS level IO capability
import time # time library for handling time related tasks
import threading # threading library for multithreading
import logging # logging library to perform logging

log_file = 'server.log' # filename of server logs
handlers = [logging.FileHandler(log_file, 'w'), logging.StreamHandler()] # write to log file and stdout
logging.basicConfig(level=logging.NOTSET, # set root logger to NOSET 
					handlers = handlers, # set handlers for the logging
					format="%(asctime)s;%(levelname)s;%(message)s", # log format
					datefmt='%Y-%m-%d %H:%M:%S') # date format
logger = logging.getLogger()

# constants
IP = '127.0.0.1'
TCP_PORT = 6234
UDP_PORT = 6235
MAX_CONNECTIONS = 5
HEADER_LENGTH = 5
ACTIVITY_LIMIT = 20

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

logger.info(f'TCP server is running at {IP}:{TCP_PORT} and it is listening for connections!')
logger.info(f'UDP server is running at {IP}:{UDP_PORT} and it is listening for connections!')

# data structures for handling client and socket instances
sockets = [tcp_socket, udp_socket]
clients = {}
private_chat_rooms = {}
group_chat_rooms = {}


def recieve_message(client_socket):
    """
    this function gets a notified client (a client socket which has something to be read)
    as input. First, it extracts the header section of the message and then use it as buffer
    size to extract the rest of the message (data). the function then returns a dictionary
    which contains some message attributes.
    """
    try:
        message_header = client_socket.recv(HEADER_LENGTH)

        if not len(message_header):
            return False

        message_length = int(message_header.decode('utf-8'))
        data = client_socket.recv(message_length).decode('utf-8')
        server_port = -1
        if '&&REGISTER&&' in data:
            server_port = int(data.split('|')[2].strip())
            data = data.split('|')[1].strip()
            message_header = f"{len(data) :< {HEADER_LENGTH}}".encode('utf-8')

        return {'header': message_header, 'data': data.encode('utf-8'), 'server_port': server_port, 'activity': ACTIVITY_LIMIT, 'start_time': time.time(), 'in_session': False}

    except Exception:
        return False


def search_peer(peer_username):
    """
    this function gets a client's username as string and searches the clients dictionary
    in order to find a match for that given username. If a match is found, the function
    returns the address (IP, PORT) of that client, else it returns None.
    """
    address = None
    for client in clients:
        if clients[client]['data'].decode('utf-8') == peer_username:
            address = client.getpeername()

    return address


def get_peer_socket(peer_ip_addr, peer_port):
    """
    this function gets the IP and PORT as input, and uses them to query the clients dictionary.
    If a match is found, the function returns the socket instance for that match, else it returns
    None.
    """
    for client in clients:
        address = client.getpeername()
        if address == (peer_ip_addr, peer_port):
            return client

    return None


def get_socket(username):
    """
    this function gets the username of a client as a string and uses it to query the clients dictionary.
    If a match is found, it returns the client's socket instance, else it returns None.
    """
    ip, port = search_peer(username)
    user_socket = get_peer_socket(ip, port)
    return user_socket


def process_text_message(notified_socket, message):
    """
    this function gets a notified socket and a message as input. First, it checks all available
    global chat rooms to check if the notified socket is in one of them. If it exists, the message
    is forwarded to all members of that specific room.
    """
    for chat_room in group_chat_rooms:
        if notified_socket in group_chat_rooms[chat_room]:
            user = clients[notified_socket]
            for client_socket in group_chat_rooms[chat_room]:
                client_socket.send(user['header'] + user['data'] + message['header'] + message['data'])


def is_busy(peer_socket):
    """
    this function gets a client socket as input and checks both group and private chat rooms.
    If the given client socket exists in any of them, the function returns True, else it returns
    False.
    """
    for chat_room in group_chat_rooms:
        if peer_socket in group_chat_rooms[chat_room]:
            return True

    for chat_room in private_chat_rooms:
        if peer_socket in private_chat_rooms[chat_room]:
            return True

    return False


def remove_participant(chat_rooms, peer_socket):
    """
    this function gets a chat room (private/global) and a peer socket as input. Then it
    checks all available chat rooms for the existance of the given peer socket. If it exists,
    the function removes that socket from the room.
    """
    room = None
    for chat_room in chat_rooms:
        if peer_socket in chat_rooms[chat_room]:
            chat_rooms[chat_room].remove(peer_socket)
            room = chat_room

    if room is None:
        return room, None
    return room, chat_rooms[room]


def end_session(peer_socket):
    """
    this function receives a peer socket as input and removes it from all rooms (private/group),
    if available using the remove_participant function.
    """
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
    """
    this function is executed by a specific thread. the purpose of this function is to keep
    checking the tcp socket of the server if it has anything to be read. If so, the program
    is sure that a new user has registered in the chatting application, hence the message
    is read from the socket and necessary actions are taken.
    """
    while True:
        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

        if tcp_socket not in read_sockets:
            continue

        client_socket, client_address = tcp_socket.accept()

        client_data = recieve_message(client_socket)

        if not client_data:
            logger.warning(f'registering the new user with address {client_address} failed')
            continue

        sockets.append(client_socket)
        clients[client_socket] = client_data
        logger.info(f"accepted/registered new connection from {client_address}:{client_address[1]} username: {client_data['data'].decode('utf-8')}")


def update_activity():
    """
    this function is executed by a specific thread. the purpose of this function is to keep
    listening the udp socket of the server. if it has anything to be read, the program is sure
    that it has received a HELLO message from a client, hence it will reset the activity time
    for that specific client. if the udp socket has received nothing, then the program will decrease
    the activity times of each client by a specific number of seconds.
    """
    while True:
        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

        if udp_socket not in read_sockets:
            for client_socket in clients.copy():

                try:
                    client_address = client_socket.getpeername()
                    waited_duration = time.time() - clients[client_socket]['start_time']
                    clients[client_socket]['activity'] -= waited_duration
                    clients[client_socket]['start_time'] = time.time()

                    if clients[client_socket]['activity'] <= 0:
                        logger.info(f'terminating {client_address}:{client_address[1]} username: {clients[client_socket]["data"].decode("utf-8")}')
                        clients.pop(client_socket)
                        sockets.remove(client_socket)

                except KeyError:
                    continue

        else:
            message = udp_socket.recvfrom(256)
            decoded_message = message[0].decode('utf-8')
            client_username = (decoded_message.split('|')[-1]).strip()
            client_socket = get_socket(client_username)
            client_address = client_socket.getpeername()
            clients[client_socket]['activity'] = ACTIVITY_LIMIT
            logger.info(f'resetting activity time from {client_address}:{client_address[1]} username: {clients[client_socket]["data"].decode("utf-8")}')


def process_message():
    """
    this function is executed by a specific thread. the purpose of this function is to receive
    client messages sent to the server and take specific actions. for instance, if the server
    receives a SEARCH message, it performs some specific actions and returns a response to the
    client making the SEARCH. please refer to the project report for a complete detail on such
    messages.
    """
    total_private_rooms = 0
    total_global_rooms = 0

    while True:

        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets, 0)

        for notified_socket in read_sockets:

            if notified_socket == tcp_socket or notified_socket == udp_socket:
                continue
            
            try:
                in_session = clients[notified_socket]['in_session']
            except KeyError:
                continue

            message = recieve_message(notified_socket)

            if not message:
                # remove the socket here
                continue
            
            decoded_message = message['data'].decode('utf-8')

            if decoded_message == '&&LOGOUT&&' and not in_session:
                # we do not remove the client socket immediately in here as it will be removed
                # by udp socket anyways
                message['data'] = '&&LOGOUTSUCCESS&&'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                notified_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])
            
            elif '&&SEARCH&&' in decoded_message and not in_session:
                searched_peer = (decoded_message.split('|')[-2]).strip()
                sender_username = (decoded_message.split('|')[-1]).strip()
            
                response = search_peer(searched_peer)
            
                if response == None: # if search result is None
                    response = '&&NOTFOUND&&|user not found'
                elif searched_peer == sender_username: # if user have searched him/herself
                    response = '&&INVALIDSEARCH&&|you can\'t search yourself. search for other users'
                else: # a match has been found for the search
                    response = f'&&FOUND&&|{searched_peer} found. its address is ' + str(response)

                # send search results back to the user making the search
                sender_socket = get_socket(sender_username)
                message['data'] = response.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                sender_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&CHATREQUEST&&' in decoded_message and not in_session:
                searched_peer = (decoded_message.split('|')[-2]).strip()
                sender_username = (decoded_message.split('|')[-1]).strip()

                client_socket = get_socket(searched_peer)
                sender_socket = get_socket(sender_username)

                if client_socket is None:
                    continue

                if is_busy(client_socket): # check if the searched peer is busy
                    message['data'] = f'&&BUSY&&|the user is busy. try again later.'.encode('utf-8')
                    message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                    sender_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                else: # if not busy, send a message and inform them about the chat request
                    message['data'] = f'{sender_username} would like to chat with you? (OK/REJECT)'.encode('utf-8')
                    message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])
            
            elif '&&REJECT&&' in decoded_message and not in_session:
                sender_username = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()

                sender_socket = get_socket(sender_username)
                peer_socket = get_socket(peer_username)

                # send message to both sender and receiver about the rejection of chat request
                message['data'] = f'you have rejected the chat request!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                peer_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                message['data'] = f'{peer_username} rejected the chat request!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                sender_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&OK&&' in decoded_message and not in_session:
                peer_server_port = (decoded_message.split('|')[-1]).strip()
                sender_username = (decoded_message.split('|')[-2]).strip()
                peer_username =  (decoded_message.split('|')[-3]).strip()

                peer1_socket = get_socket(sender_username)
                peer2_socket = get_socket(peer_username)

                sender_server_port = clients[peer1_socket]['server_port']

                # update attributes of users and create a private room
                total_private_rooms += 1
                private_chat_rooms[str(total_private_rooms)] = [peer1_socket, peer2_socket]
                clients[peer1_socket]['in_session'] = True
                clients[peer2_socket]['in_session'] = True

                # send a message to both sender and receiver about the start of the chat session
                message['data'] = f'&&CLIENTOK&&|{peer_username} accepted the chat request. you can send your message now!|{peer_server_port}'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                peer1_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                message['data'] = f'&&CLIENTOK&&|you have entered into a private chat with {sender_username}. you can send your message now!|{sender_server_port}'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                peer2_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&EXIT&&' in decoded_message and in_session:
                peer_username = (decoded_message.split('|')[-1]).strip()
                peer_socket = get_socket(peer_username)

                participant_sockets = end_session(peer_socket)
                # send a message to both sender and receiver about the end of the chat session
                message['data'] = f'&&CLIENTEXIT&&|you left the chat room.'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                peer_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                message['data'] = f'&&CLIENTEXIT&&|{peer_username} left the chat room. the chat room has been closed'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                participant_sockets[0].send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                # update user attributes
                clients[peer_socket]['in_session'] = False
                clients[participant_sockets[0]]['in_session'] = False

                res = end_session(participant_sockets[0])

            elif '&&GROUPCHAT&&' in decoded_message and not in_session:
                tokens = decoded_message.split('|')
                peers = tokens[2:-1]
                sender_username = tokens[1]
                total_global_rooms += 1

                # add the group admin to the group chat and let him/her know
                message['data'] = f'you have added yourself to group chat {total_global_rooms}. a request has been sent to your added friends. type EXIT GROUP to leave.'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                admin_socket = get_socket(sender_username)
                group_chat_rooms[str(total_global_rooms)] = [admin_socket]
                clients[admin_socket]['in_session'] = True
                admin_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                # send an exclusive message to each invited client and ask for their response
                message['data'] = f'{sender_username} would like to add you to group chat room {total_global_rooms}? (OK/REJECT GROUP <room_number>)'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                for peer in peers:
                    peer_socket = get_socket(peer)

                    if peer_socket is None:
                        continue
                    
                    elif is_busy(peer_socket):
                        message['data'] = f'&&BUSY&&|{peer} is busy. try again later.'.encode('utf-8')
                        message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                        admin_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                    else:
                        peer_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&REJECTGROUP&&' in decoded_message and not in_session:
                group_number = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()
                peer_socket = get_socket(peer_username)

                # send a message to the rejector and group admin about the invitation rejection
                message['data'] = f'you have rejected the group chat request!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                peer_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                message['data'] = f'{peer_username} rejected the group chat request!'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                group_chat_rooms[group_number][0].send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&OKGROUP&&' in decoded_message and not in_session:
                group_number = (decoded_message.split('|')[-1]).strip()
                peer_username =  (decoded_message.split('|')[-2]).strip()

                peer_socket = get_socket(peer_username)

                # update attributes of the acceptor
                group_chat_rooms[group_number].append(peer_socket)
                clients[peer_socket]['in_session'] = True

                # send a message to all members of a group chat in the room
                message['data'] = f'{peer_username} joined the group chat'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')

                for client_socket in group_chat_rooms[group_number]:
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&EXITGROUP&&' in decoded_message and in_session:
                peer_username = (decoded_message.split('|')[-1]).strip()
                peer_socket = get_socket(peer_username)

                participant_sockets = end_session(peer_socket)

                # send a message to both leaver and all other members about the leaving of the client
                message['data'] = f'you left the chat room.'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                peer_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

                message['data'] = f'{peer_username} left the chat room.'.encode('utf-8')
                message['header'] = f"{len(message['data']) :< {HEADER_LENGTH}}".encode('utf-8')
                clients[peer_socket]['in_session'] = False

                for client_socket in participant_sockets:
                    client_socket.send(clients[notified_socket]['header'] + clients[notified_socket]['data'] + message['header'] + message['data'])

            elif '&&MESSAGE&&' in decoded_message and in_session:
                # send group message to all clients in a specific group chat room
                process_text_message(notified_socket, message)


register_user_thread = threading.Thread(target=register_new_users)
register_user_thread.start()
logger.info('successfully started register user thread')

update_activity_thread = threading.Thread(target=update_activity)
update_activity_thread.start()
logger.info('successfully started update activity thread')

process_message_thread = threading.Thread(target=process_message)
process_message_thread.start()
logger.info('successfully started process message thread')
