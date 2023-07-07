# Name: Luong Nguyen/ vv2796uo
# This is a chat server program, it can send messages publicly or privately, as well as, login credentials.
# The login credentials are saved and won't be gone after the server reset.

import os.path
import threading
import time
from socket import *

port = 5555

# create tcp socket
serverSocket = socket(AF_INET, SOCK_STREAM)
udpSocket = socket(AF_INET, SOCK_DGRAM)

# get local hostname
host = gethostbyname(gethostname())

# attempts to bind sockets to host/port, waiting until able
connected = False
print("Attempting to bind host/port to sockets", end="", flush=True)
while not connected:
    # bind host/port to sockets
    try:
        connected = True
        serverSocket.bind((host, port))
        udpSocket.bind((host, port))
    except OSError:
        connected = False
        print(".", end="", flush=True)
        time.sleep(3)

print("\nServer is listening at", host, "on port", port)
serverSocket.listen(5)

# max client connections at one time
maxConnections = 5

# list of dispatched threads for handling messages
connectionList = list()  # [thread1, thread2, thread3...]

# list of currently active users, along with their assigned socket and address for sending udp messages
activeUsers = list()

# for clearing /copying lists
tempList = list()

# list of saved username/password pairs
credentialList = list()

# mutexes (mutual exclusion locks) for accessing relevant lists without threading issues
userListMutex = threading.Lock()
credentialListMutex = threading.Lock()
fileMutex = threading.Lock()

# attempt to read in credentials from file credentials.txt
try:
    credentialFile = open('credentials.txt', 'r')
    lines = credentialFile.readlines()
    for line in lines:
        line = line.strip()  # line = user pass
        credentialList.append((line.split()[0], line.split()[1]))  # add (user, pass) to credential list
    credentialFile.close()
except IOError:
    # File not found handler:
    try:
        credentialFile = open('credentials.txt', 'w')
    except IOError:
        # can't create file, possible permissions error
        print("Error occured while creating file!")


# function used by client threads
def client_connection_thread(clientSocket):
    global userListMutex
    global credentialListMutex
    global fileMutex
    global credentialList
    global activeUsers

    # wait for username
    username = clientSocket.recv(4096).decode()

    # check if existing or new (store credentials in file)
    credentialListMutex.acquire()
    existingUser = False

    for userTuple in credentialList:
        if userTuple[0] == username:
            existingUser = True
            break

    credentialListMutex.release()

    # check if the user is already logged in
    userListMutex.acquire()
    for userTuple in activeUsers:
        if userTuple[0] == username:
            # already logged in!
            clientSocket.send("in use".encode())
            clientSocket.close()
            userListMutex.release()
            return
    userListMutex.release()

    # handle login for existing user
    if existingUser:
        # acknowledge client is existing
        clientSocket.send("existing".encode())
        accepted = False
        attemptCount = 0

        # allow user to attempt to log in, 3 false passwords gives error and ends thread
        while not accepted:
            # wait for password
            password = clientSocket.recv(4096).decode()

            credentialListMutex.acquire()
            # check password
            for userTuple in credentialList:
                if userTuple[0] == username:
                    if userTuple[1] == password:
                        accepted = True
                    break
            credentialListMutex.release()

            if not accepted:
                # looping to ask for password
                # allowed 3 attempts
                attemptCount += 1
                if attemptCount >= 3:
                    # tell client password was refused for third time, end thread
                    clientSocket.send("final refuse".encode())
                    clientSocket.close()
                    return
                else:
                    # tell client password is incorrect, allow to try again
                    clientSocket.send("refused".encode())
            else:
                clientSocket.send("accepted".encode())
    else:
        # acknowledge client is new
        clientSocket.send("new".encode())

        # wait for password
        password = clientSocket.recv(4096).decode()

        # acknowledge new registration
        message = "News User: " + username + " Password: " + password
        clientSocket.send(message.encode())

        fileExists = os.path.isfile('credentials.txt')
        fileEmpty = (os.path.getsize('credentials.txt') == 0)  # number of bytes?
        # register - add to file AND update credentialList
        fileMutex.acquire()
        file = open('credentials.txt', 'a')
        if fileExists and not fileEmpty:
            file.write("\n")
        file.write(username + " " + password)
        file.close()
        fileMutex.release()
        credentialList.append((username, password))
    # proceed to handling block

    # handling block
    # user is logged in / registered

    # receive message from the udp socket
    # save in the active userList the udp address for sending messages to
    messageType, address = udpSocket.recvfrom(4096)

    # append them to active user list
    userListMutex.acquire()
    activeUsers.append((username, clientSocket, address))
    userListMutex.release()
    running = True

    # tell client that it has received the udp address and is ready to receive commands.
    clientSocket.send("udp receive".encode())

    while running:
        # wait for command
        operation = clientSocket.recv(4096).decode()

        if operation == "PM":
            # PM - broadcast to all active () logged in and not yet exited
            # send acknowledgement of PM request
            clientSocket.send("PM".encode())
            # wait for message
            message = clientSocket.recv(4096).decode()

            # check active user list for any users that aren't the sender, and send them the message
            userListMutex.acquire()
            for userTuple in activeUsers:
                if userTuple[0] != username:
                    udpSocket.sendto(message.encode(), userTuple[2])
                    udpSocket.sendto(username.encode(), userTuple[2])
                    udpSocket.sendto("Public Message (PM)".encode(), userTuple[2])
            userListMutex.release()

            # notify user that message was sent
            clientSocket.send("complete".encode())
        # return to wait for command

        elif operation == "DM":
            # acknowledge DM request
            clientSocket.send("DM".encode())
            message = clientSocket.recv(4096).decode()
            if message != "received":
                print("Error handshaking?")
                print(message)

            # send user a list of all active users
            gettingUser = True
            while gettingUser:
                userListMutex.acquire()
                for userTuple in activeUsers:
                    clientSocket.send(userTuple[0].encode())
                    message = clientSocket.recv(4096).decode()
                    if message != "received":
                        print("client did not receive username properly")
                userListMutex.release()

                clientSocket.send("END".encode())

                # get recipient from client
                receiver = clientSocket.recv(4096).decode()

                # search list of active users for recipent
                found = False
                userListMutex.acquire()
                for userTuple in activeUsers:
                    if userTuple[0] == receiver:
                        found = True
                        receiverAddress = userTuple[2]
                        break
                userListMutex.release()

                # notify user that recipient does not exist or is not logged in
                if not found:
                    clientSocket.send("DNE".encode())
                    message = clientSocket.recv(4096).decode()
                    if message != "received":
                        print("Error receiving DNE?")
                # send message to recipient
                else:
                    gettingUser = False
                    clientSocket.send("message".encode())
                    message = clientSocket.recv(4096).decode()
                    udpSocket.sendto(message.encode(), receiverAddress)
                    udpSocket.sendto(username.encode(), receiverAddress)
                    udpSocket.sendto("Direct Message (DM)".encode(), receiverAddress)
                    clientSocket.send("complete".encode())
        # return to wait for command

        elif operation == "EX":
            running = False
            # update list of logged in threads
            userListMutex.acquire()
            for userTuple in activeUsers:
                if userTuple[0] == username:
                    activeUsers.remove(userTuple)
                    break
            userListMutex.release()
            # notify client that it was logged out, then close socket
            clientSocket.send("logout".encode())
            clientSocket.close()
        # allow this thread to end by exiting while loop and reaching end of the function

        else:
            clientSocket.send("unknown".encode())
        # unknown


# main thread for handling receiving new connections
print("Server ready to receive connections")
while True:
    # blocks if there are more than the max collections allowed
    while len(connectionList) >= maxConnections:
        tempList.clear()
        for thread in connectionList:
            if thread.is_alive():
                tempList.append(thread)
        connectionList.clear()
        connectionList = tempList.copy()

    # wait for new connection
    newConnection, addr = serverSocket.accept()

    # create thread, add to list of threads, start new thread
    newThread = threading.Thread(target=client_connection_thread, args=(newConnection,))

    # cleanup any finished threads by removing from list
    tempList.clear()
    for thread in connectionList:
        if thread.is_alive():
            tempList.append(thread)
    connectionList.clear()
    connectionList = tempList.copy()

    # add newly created thread to list, then start it!
    connectionList.append(newThread)
    newThread.start()
