# Name: Luong Nguyen/ vv279uo
# Chat client program, multithreading with login credentials.
import queue

import sys
import threading
from socket import *


# data message receiving thread
# receives data messages via the udpSocket
# adds them to the queue of messages to be printed out at the proper time
def message_receiving_thread(udpSocket):
    global messageQueue

    # listen for messages forever and save them to the messageQueue
    # this thread should only be run as a daemon, so it will end when its parent does
    while True:
        message, address = udpSocket.recvfrom(4096)
        userFrom, address = udpSocket.recvfrom(4096)
        messageType, address = udpSocket.recvfrom(4096)
        messageQueue.put((message.decode(), userFrom.decode(), messageType.decode()))


# this function is to be used by a thread that waits for input and prompts its parent that the input is ready
def input_listener_thread(prompt):
    global inputCommand
    global inputReadyFlag

    inputCommand = input(prompt)
    inputReadyFlag = True


# starts an input_listener_thread and waits for input to be received, continually check messageQueue for data
# messages to print if data messages are printed the prompt that is given for input is reprinted returns the string
# that was input
def get_input(prompt):
    global inputReadyFlag
    global inputCommand
    inputReadyFlag = False
    inputCommand = ""

    inputListenerThread = threading.Thread(target=input_listener_thread, args=(prompt,), daemon=True)
    inputListenerThread.start()

    while not inputReadyFlag:
        print_messages(prompt)
    inputReadyFlag = False
    return inputCommand


# prints all the messages in the message queue
# reprints a given prompt. If no prompt is needed simply supply the function with an empty string
def print_messages(prompt):
    global messageQueue
    while not messageQueue.empty():
        messageTuple = messageQueue.get()
        print("\n*** New Message ***")
        print("Message type: " + messageTuple[2])
        print("From: " + messageTuple[1] + "\n")
        print(messageTuple[0] + "\n")
        print(prompt)


# starts a thread to listen for a socket response, to be used for getting operation responses over the tcp socket
# prints out messages from the queue while waiting for the response
# returns the string sent by the server
def get_response(socket, prompt):
    global responseReadyFlag
    global socketResponse
    responseReadyFlag = False
    socketResponse = ""

    socketResponseListener = threading.Thread(target=response_listener_thread, args=(serverSocket,), daemon=True)
    socketResponseListener.start()

    while not responseReadyFlag:
        print_messages(prompt)
    responseReadyFlag = False
    return socketResponse


# receives a response from the server and saves it, flags the parent thread that the response is ready
def response_listener_thread(socket):
    global responseReadyFlag
    global socketResponse
    socketResponse = socket.recv(4096).decode()
    responseReadyFlag = True


hostname = gethostbyname(gethostname())
port = 5555
username = sys.argv[1]

# queue for storing/printing DM/PM messages received
messageQueue = queue.Queue()

# attempt to begin and bind tcp socket and begin udp socket
try:
    serverSocket = socket(AF_INET, SOCK_STREAM)

    serverSocket.connect((hostname, port))
    udpSocket = socket(AF_INET, SOCK_DGRAM)
except ConnectionRefusedError:
    print("TCP Connection was refused at host:", hostname, "on port:", port)
    print("Please check your hostname and port again!")
    sys.exit()

# send username to server
serverSocket.send(username.encode())
response = serverSocket.recv(4096).decode()

# handle authentication of existing user
if response == "existing":
    approved = False
    password = input("Existing user. Please enter password:\n")

    while not approved:
        serverSocket.send(password.encode())
        response = serverSocket.recv(4096).decode()
        if response == "refused":
            password = input("Incorrect password, please try again:\n")
        elif response == "final refuse":
            print("Password refused too many times. exiting program")
            serverSocket.close()
            sys.exit()
        else:
            approved = True

# handle creation of new user
elif response == "new":
    password = input("Welcome new user: " + username + " please enter a new password:\n")

    while " " in password:
        password = input(
            "Password cannot contain \' \' character. Please re-enter a new password that does not contain a space:\n")

    serverSocket.send(password.encode())
    response = serverSocket.recv(4096).decode()
    print(response)

# username is already active
elif response == "inuse":
    print("That user is already actively logged in. Please restart the program as a different user")
    serverSocket.close()
    sys.exit()
else:
    print("Server error!")
    serverSocket.close()
    sys.exit()

# send the address of the udp socket to the server
# dispatch a thread that handles receiving messages
# something like handle_messages(udp_socket)
udpSocket.sendto("udp begin".encode(), (hostname, port))

# wait for server to send over tcp socket that it has received the udp message.
response = serverSocket.recv(4096).decode()
if response != "udp receive":
    print("Error receiving udp?")
    print(response)

# begin messageListening thread
messageListenerThread = threading.Thread(target=message_receiving_thread, args=(udpSocket,), daemon=True)
messageListenerThread.start()

responseReadyFlag = False
socketResponse = ""

inputReadyFlag = False
inputCommand = ""

# ready to send/receive operation messages with server
operating = True
while operating:
    # get command
    command = get_input(
        "Please enter a command:\n\tPM - public message to all active users.\n\tDM - direct message to a  single "
        "user\n\tEX - exit program and logout of account\n")

    # handle sending a public message
    if command == "PM":
        serverSocket.send(command.encode())
        response = get_response(serverSocket, "")
        if response != "PM":
            print("Did not recognize PM request?")

        # ask for message
        message = get_input("Message:\n")
        serverSocket.send(message.encode())
        response = get_response(serverSocket, "")
        if response != "complete":
            print("message wasn't sent?")
        else:
            print("Message sent")

    # handle sending a direct message
    elif command == "DM":
        serverSocket.send(command.encode())
        response = get_response(serverSocket, "")
        if response != "DM":
            print("Server did not receive DM request properly?")

        serverSocket.send("received".encode())

        gettingUser = True
        while gettingUser:

            print("Select a user to send a message to:")
            response = get_response(serverSocket, "")
            # receive list of active users
            while response != "END":
                print("\t" + response)
                serverSocket.send("received".encode())
                response = get_response(serverSocket, "")

            # prompt user to select recipient of DM
            sendTo = get_input("To:\n")
            serverSocket.send(sendTo.encode())
            response = get_response(serverSocket, "")

            # handle user Does Not Exist
            if response == "DNE":
                print("User does not exist.")
                serverSocket.send("received".encode())

            # user exists, prompt user for message to send
            elif response == "message":
                gettingUser = False
                # get message input, send it etc.
                message = get_input("\nEnter message:\n")
                serverSocket.send(message.encode())
                response = get_response(serverSocket, "")
                # message was not sent
                if response != "complete":
                    print("Something went wrong")
                # message sent
                else:
                    print("Message sent")
            else:
                print("Invalid response?")
    # log user out
    elif command == "EX":
        # print and pending messages
        print_messages("")

        # log user out of server
        operating = False
        print("Sending logout command to server")
        serverSocket.send(command.encode())
        response = get_response(serverSocket, "")

        if response == "logout":
            print("Successfully logged out. Closing client side socket and ending program.")
        else:
            print("Error logging out??? closing socket anyways")

        # close sockets and exit
        serverSocket.close()
        udpSocket.close()
        sys.exit()
    else:
        print("Unknown command.")
