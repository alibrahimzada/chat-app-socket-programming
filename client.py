import socket
import os
import errno
import time
import threading
import random
import string
import select
import logging

# constants
IP = '127.0.0.1'
TCP_PORT = 6234
UDP_PORT = 6235
HEADER_LENGTH = 5
STATUS_PERIOD = 6
MAX_CONNECTIONS = 5

# this infinite loop makes sure that an appropriate server port is assigned to a client
while True:
    try:
        TCP_SERVER_PORT = int(''.join(random.choices(string.digits, k = 4)))
        tcp_server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_server_socket.bind((IP, TCP_SERVER_PORT))
        break
    except PermissionError:
        continue

client_username = input("enter your username: ")
client_password = input("enter your password: ")

log_file = f'client_{client_username}.log' # log filename
handlers = [logging.FileHandler(log_file, 'w'), logging.StreamHandler()]   # write to log file and stdout
logging.basicConfig(level=logging.NOTSET,  # set root logger to NOSET 
					handlers = handlers, # set handlers for the logger
					format="%(asctime)s;%(levelname)s;%(message)s",  # log format
					datefmt='%Y-%m-%d %H:%M:%S')  # date format
logger = logging.getLogger()

# AF_INET corresponds to address family IPv4
# SOCK_STREAM corresponds to TCP
tcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
tcp_client_socket.connect(((IP, TCP_PORT)))
tcp_client_socket.setblocking(False)

# start listening from the tcp server of client
tcp_server_socket.listen(MAX_CONNECTIONS)

logger.info(f'TCP server of client {client_username} is running at {IP}:{TCP_SERVER_PORT} and it is listening for connections!')

# a lock and data structures for handling client data
lock = threading.Lock()
peers = []
sockets = [tcp_server_socket]

# SOCK_DGRAM corresponds to UDP
udp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
udp_client_socket.connect(((IP, UDP_PORT)))
udp_client_socket.setblocking(False)

encoded_client_data = ('&&REGISTER&&|' + client_username + '|' + str(TCP_SERVER_PORT)).encode('utf-8')
header = f"{len(encoded_client_data):<{HEADER_LENGTH}}".encode('utf-8')
tcp_client_socket.send(header + encoded_client_data)

logger.info(f'{client_username} has been successfully added in the server\'s database')

def send_status():
    """
    this function is executed by a specific thread. the purpose of this function is to send
    a HELLO message every 6 seconds to the UDP socket of the main server.
    """
    start_time = time.time()

    while True:

        end_time = time.time()

        if end_time - start_time >= STATUS_PERIOD: # check if 6 secs have passed
            # send a HELLO message and reset the timer
            client_message = f'&&HELLO&&|{client_username}'.encode('utf-8')
            message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')
            udp_client_socket.sendto(message_header + client_message, (IP, UDP_PORT))
            start_time = time.time()
            logger.info(f'sending HELLO message to UDP socket of server for user with id - {client_username}')

def send_message():
    """
    this function is executed by a specific thread. the purpose of this function is to take
    users input at each iteration and take some necessary actions. by default, the user's 
    message is considered a normal text message. however, if the function finds out some
    specific words in a user message (i.e., SEARCH, CHAT REQUEST, etc.), then it will change
    the receiver of the message.
    """
    while True:
        server_message = False
        ok_group = False
        reject_group = False

        client_message = f"{client_username}: {input()}"
        client_message = '&&MESSAGE&&|' + client_message
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

        if message_content == 'EXIT GROUP':
            client_message = f'&&EXITGROUP&&|{client_username}'
            server_message = True

        client_message = client_message.encode('utf-8')
        message_header = f"{len(client_message) :< {HEADER_LENGTH}}".encode('utf-8')

        if server_message:
            tcp_client_socket.send(message_header + client_message)
        
        lock.acquire()
        if peers == [] and '&&MESSAGE&&' in client_message.decode('utf-8'):
            tcp_client_socket.send(message_header + client_message)
        lock.release()

        lock.acquire()
        if not server_message and peers != []:
            print(' '.join(client_message.decode('utf-8').split('|')[1:]).strip())
            for socket_ in peers:
                socket_.send(message_header + client_message)
        lock.release()

def receive_server_message():
    """
    this function is executed by a thread. the purpose of this function is to receive
    server messages, extract message body and show them to client.
    """
    while True:
        try:
            while True:
                username_header = tcp_client_socket.recv(HEADER_LENGTH)
                username_length = int(username_header.decode('utf-8'))
                username = tcp_client_socket.recv(username_length).decode('utf-8')

                message_header = tcp_client_socket.recv(HEADER_LENGTH)
                message_length = int(message_header.decode('utf-8'))
                message = tcp_client_socket.recv(message_length).decode('utf-8')

                if '&&LOGOUTSUCCESS&&' in message: # if logout is successful, kill the process using SIGKILL
                    logger.info(f'loggin out from session. goodbye {client_username}')
                    os.kill(os.getpid(), 9)

                elif '&&CLIENTOK&&' in message: # if a chat session is starting, connect user's socket to each other's tcp server
                    receiver_port = int(message.split('|')[-1].strip())
                    message = message.split('|')[1].strip()
                    tcp_client_peer_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
                    tcp_client_peer_socket.connect(((IP, receiver_port)))
                    tcp_client_peer_socket.setblocking(False)

                    # change the list 'peers' in a lock since it is changed in more than one thread
                    lock.acquire()
                    peers.append(tcp_client_peer_socket)
                    lock.release()

                elif '&&CLIENTEXIT' in message: # if a client is exiting, clear out the peers dict
                    # change the list 'peers' in a lock since it is changed in more than one thread
                    lock.acquire()
                    peers.clear()
                    lock.release()
                    message = message.split('|')[1].strip()

                elif '&&NOTFOUND&&' in message or '&&INVALIDSEARCH&&' in message or '&&FOUND&&' in message or '&&BUSY&&' in message:
                    message = message.split('|')[1].strip()

                if ':' in message:
                    message = ' '.join(message.split(':')[1:]).strip()
                else:
                    username = 'server'

                print(f'{username}: {message}')

        except IOError as e:
            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                logger.error('the process committed an unexpected exception. exiting!!!')
                exit()
            continue

        except Exception:
            logger.error('the process committed an unexpected exception. exiting!!!')
            exit()

def receive_peer_message():
    """
    this function is executed by a thread. the purpose of this function is to receive messages
    from other peers during P2P messaging. the messages are received by the receiver client's 
    TCP server.
    """
    while True:
        # select.select will make use of OS and it will wait until a file descriptor is ready for IO
        read_sockets, useless, exceptional_sockets = select.select(sockets, [], sockets)

        if tcp_server_socket in read_sockets: # if a new connection is made, add client's socket to a list
            socket_, client_address = tcp_server_socket.accept()
            sockets.append(socket_)
        else: # else retrieve the client's socket
            socket_ = read_sockets[0]

        message_header = socket_.recv(HEADER_LENGTH) # receive the message header

        if not len(message_header):
            return False

        # use the message header to retrieve the message data and print it
        message_length = int(message_header.decode('utf-8'))
        message = socket_.recv(message_length).decode('utf-8')

        logger.info(f'{client_username} received a new message from another peer with address {socket_.getpeername()}')

        if ':' in message:
            message = ' '.join(message.split('|')[1:]).strip()

        print(message)


send_thread = threading.Thread(target=send_message)
send_thread.start()
logger.info('successfully started send message thread')

receive_server_thread = threading.Thread(target=receive_server_message)
receive_server_thread.start()
logger.info('successfully started receive server message thread')

recieve_peer_thread = threading.Thread(target=receive_peer_message)
recieve_peer_thread.start()
logger.info('successfully started receive peer message thread')

status_thread = threading.Thread(target=send_status)
status_thread.start()
logger.info('successfully started send status thread')
