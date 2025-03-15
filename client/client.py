import grpc
import sys
from concurrent import futures
import time
import socket
import threading

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS
MY_PORT = None
REQUEST_ID = 0
REQUEST_QUEUE = []
REQUEST_DONE = []
MAX_RETRIES = 5
RUN_QUEUE_RETRY = threading.Event()


# fucntion for requests queued thread
def queuedReqRetry(gatewayChannel, gatewayStub):
    global REQUEST_QUEUE, REQUEST_DONE

    # getting into loop
    while not RUN_QUEUE_RETRY.is_set():
        # iterating over the Queue
        if len(REQUEST_QUEUE) > 0:
            # checking the connection or its presence (online)
            try:
                grpc.channel_ready_future(gatewayChannel).result(timeout=2)
            except grpc.FutureTimeoutError:
                continue

            # getting first element & removing it
            req = REQUEST_QUEUE[0][0]
            triesDone = REQUEST_QUEUE[0][1]
            REQUEST_QUEUE = REQUEST_QUEUE[1:]

            if req.__class__ == services2.RegReq:
                try:
                    response = gatewayStub.signUp(req)

                    # checking if error occurred then queue it up at the back
                    if response.successAck == 0:
                        # checking if ran out of retries
                        if (triesDone + 1) == MAX_RETRIES:
                            REQUEST_DONE.append([req.reqID, "Request Aborted!"])
                        else:
                            REQUEST_QUEUE.append([req, triesDone + 1])
                    elif response.successAck == 1:
                        REQUEST_DONE.append([req.reqID, response.message])

                except grpc.RpcError as e:
                    if e.code() == grpc.StatusCode.UNAVAILABLE:
                        print("Gateway server unavailable!")
                    else:
                        print(f"gRPC error: {e}")
                    continue

            elif req.__class__ == services2.TransactReq:
                try:
                    response = gatewayStub.transact(req)

                    # checking if error occurred then queue it up at the back
                    if response.successAck == 0:
                        # checking if ran out of retries
                        if (triesDone + 1) == MAX_RETRIES:
                            REQUEST_DONE.append([req.reqID, "Request Aborted!"])
                        else:
                            REQUEST_QUEUE.append([req, triesDone + 1])
                    elif response.successAck == 1:
                        REQUEST_DONE.append(
                            [req.reqID, response.message, response.balanceLeft]
                        )

                except grpc.RpcError as e:
                    if e.code() == grpc.StatusCode.UNAVAILABLE:
                        print("Gateway server unavailable!")
                    else:
                        print(f"gRPC error: {e}")
                    continue

            elif req.__class__ == services2.FailoverReq:
                try:
                    response = gatewayStub.failover(req)

                    # checking if failed then adding to the queue
                    if response.successAck == 0:
                        # checking if ran out of retries
                        if (triesDone + 1) == MAX_RETRIES:
                            REQUEST_DONE.append([req.reqID, "Request Aborted!"])
                        else:
                            REQUEST_QUEUE.append([req, triesDone + 1])
                    elif response.ack == 1:
                        REQUEST_DONE.append([req.reqID, response.message])

                except grpc.RpcError as e:
                    if e.code() == grpc.StatusCode.UNAVAILABLE:
                        print("Gateway server unavailable!")
                    else:
                        print(f"gRPC error: {e}")
                    continue

            elif req.__class__ == services2.ShareReq:
                try:
                    response = gatewayStub.share(req)

                    # checking if error occurred then queue it up at the back
                    if response.successAck == 0:
                        # checking if ran out of retries
                        if (triesDone + 1) == MAX_RETRIES:
                            REQUEST_DONE.append([req.reqID, "Request Aborted!"])
                        else:
                            REQUEST_QUEUE.append([req, triesDone + 1])
                    elif response.successAck == 1:
                        REQUEST_DONE.append(
                            [req.reqID, response.message, response.balanceLeft]
                        )

                except grpc.RpcError as e:
                    if e.code() == grpc.StatusCode.UNAVAILABLE:
                        print("Gateway server unavailable!")
                    else:
                        print(f"gRPC error: {e}")
                    continue

            else:
                pass

        time.sleep(1)

    return


# the Client function
def client():
    global MY_PORT, REQUEST_ID, REQUEST_QUEUE

    # asking for the Client ID (PORT ID)
    MY_PORT = int(input("Enter the Client (PORT) ID : "))

    # printing port
    print(f"Client running with {MY_PORT} ID ....")

    # loading SSL certificates
    privateKey = None
    certificate = None
    CACert = None

    with open("../certificate/client.key", "rb") as f:
        privateKey = f.read()
    with open("../certificate/client.crt", "rb") as f:
        certificate = f.read()
    with open("../certificate/ca.crt", "rb") as f:
        CACert = f.read()

    # connecting to Gateway Server with SSL credentials
    creds = grpc.ssl_channel_credentials(
        root_certificates=CACert, private_key=privateKey, certificate_chain=certificate
    )
    # updated secure_channel call with target name override for matching the certificate CN
    gatewayChannel = grpc.secure_channel(
        "localhost:50000",
        creds,
        options=(("grpc.ssl_target_name_override", "gateway"),),
    )
    gatewayStub = services1.ClientToGatewayStub(gatewayChannel)

    # creating thread for queued requests
    queueRetryThread = threading.Thread(
        target=queuedReqRetry, args=(gatewayChannel, gatewayStub)
    )
    queueRetryThread.start()

    # getting into loop
    while True:
        # printing everything in the REQUEST_DONE queue & clearing it
        if len(REQUEST_DONE) > 0:
            print("\n---------------- RE-TRIED REQUESTS ----------------")
            for req in REQUEST_DONE:
                if len(req) == 3:
                    print(
                        f"Request ID : {req[0]} -> {req[1]} -> Account balance : {req[2]}"
                    )
                else:
                    print(f"Request ID : {req[0]} -> {req[1]}")

            REQUEST_DONE.clear()

        # taking input from user
        command = input("\nEnter the command : ")

        # splitting the command
        command = command.split(" ")
        cmd = command[0]
        if cmd == "exit":
            # joining thread
            RUN_QUEUE_RETRY.set()

            break

        # checking & waiting if the channel is ready or not (UNAVAILABLE)
        try:
            grpc.channel_ready_future(gatewayChannel).result(timeout=5)
        except grpc.FutureTimeoutError:
            print("Sorry! Gateway server Down!")
            continue

        if cmd == "signup":
            # getting all the inputs
            bankName = input("Enter the Bank Name : ")
            emailID = input("Enter the Email ID : ")
            pswd = input("Enter the Password : ")

            # preparing a new request & sending
            REQUEST_ID += 1
            request = services2.RegReq(
                bank=bankName,
                email=emailID,
                password=pswd,
                clientPort=MY_PORT,
                reqID=REQUEST_ID,
            )
            try:
                response = gatewayStub.signUp(request)
                print(f"Request ID : {REQUEST_ID} -> {response.message}")

                # checking if error occurred then queue it up at the back
                if response.successAck == 0:
                    REQUEST_QUEUE.append([request, 0])

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print("Gateway server unavailable!")
                else:
                    print(f"gRPC error: {e}")
                continue

        elif cmd == "transact":
            # getting all the inputs
            bankName = input("Enter the Bank Name : ")
            emailID = input("Enter the Email ID : ")
            pswd = input("Enter the Password : ")
            transactionType = input("Enter the Transaction Type (credit/debit/view) : ")
            amount = 0
            if transactionType == "view":
                amount = -1
            elif (transactionType == "credit") or (transactionType == "debit"):
                amount = input("Enter the Amount : ")
                amount = int(amount)
            else:
                print("Transaction type Invalid!")
                continue

            # preparing a new request & sending
            REQUEST_ID += 1
            request = services2.TransactReq(
                bank=bankName,
                email=emailID,
                password=pswd,
                transactionType=transactionType,
                amount=amount,
                clientPort=MY_PORT,
                reqID=REQUEST_ID,
            )
            try:
                response = gatewayStub.transact(request)
                print(f"Request ID : {REQUEST_ID} -> {response.message}")

                # checking if error occurred then queue it up at the back
                if response.successAck == 0:
                    REQUEST_QUEUE.append([request, 0])

                # checking if failed or success
                if response.successAck == 1:
                    print(f"Account balance : {response.balanceLeft}")

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print("Gateway server unavailable!")
                else:
                    print(f"gRPC error: {e}")
                continue

        elif cmd == "share":
            # getting all the inputs
            senderBank = input("Enter the Sender Bank Name : ")
            senderEmail = input("Enter the Sender Email ID : ")
            senderPassword = input("Enter the Sender Password : ")
            receiverBank = input("Enter the Receiver Bank Name : ")
            receiverEmail = input("Enter the Receiver Email ID : ")
            amount = int(input("Enter the Amount : "))

            # checking if SAME sender and receiver
            if senderBank == receiverBank and senderEmail == receiverEmail:
                print("Sender and Receiver cannot be the same accounts!")
                continue

            # preparing a new request & sending
            REQUEST_ID += 1
            request = services2.ShareReq(
                senderBank=senderBank,
                senderEmail=senderEmail,
                senderPassword=senderPassword,
                receiverBank=receiverBank,
                receiverEmail=receiverEmail,
                amount=amount,
                clientPort=MY_PORT,
                reqID=REQUEST_ID,
            )
            try:
                response = gatewayStub.share(request)
                print(f"Request ID : {REQUEST_ID} -> {response.message}")

                # checking if error occurred then queue it up at the back
                if response.successAck == 0:
                    REQUEST_QUEUE.append([request, 0])

                # checking if failed or success
                if response.successAck == 1:
                    print(f"Account balance : {response.balanceLeft}")

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print("Gateway server unavailable!")
                else:
                    print(f"gRPC error: {e}")
                continue

        elif cmd == "failover":
            # getting all the inputs
            bankName = input("Enter the Bank Name : ")

            # preparing a new request & sending
            REQUEST_ID += 1
            request = services2.FailoverReq(
                bank=bankName,
                clientPort=MY_PORT,
                reqID=REQUEST_ID,
            )
            try:
                response = gatewayStub.failover(request)
                print(f"Request ID : {REQUEST_ID} -> {response.message}")

                # checking if failed then adding to the queue
                if response.ack == 0:
                    REQUEST_QUEUE.append([request, 0])

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print("Gateway server unavailable!")
                else:
                    print(f"gRPC error: {e}")

        else:
            # printing for error
            print("Command incorrect!")
            continue

    return


# MAIN
if __name__ == "__main__":
    client()
