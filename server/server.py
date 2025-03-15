import grpc
import sys
from concurrent import futures
import socket
import json
import os
import threading
import time

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2

"""

ACCOUNT_DETAILS = {emailID : [password, balance]}
REQUESTS_PROCESSED = {clientPort : [reqID1, reqID2, ...]}

"""


# GLOBALS
MY_PORT = 0
BANK_NAME = None
ACCOUNT_DETAILS = {}
REQUESTS_PROCESSED = {}
RUN_PING = threading.Event()
SENDER_STATUS = False
RECEIVER_STATUS = False

TRANSACT_LOCK = threading.Lock()
SHARE_LOCK = threading.Lock()


# INTERCEPTORS


# SERVICERS


# GatewayToServerServicer class
class GatewayToServerServicer(services1.GatewayToServerServicer):
    # defining signUp service
    def signUp(self, request, context):
        # globals
        global ACCOUNT_DETAILS, REQUESTS_PROCESSED

        # checking if the request is already processed
        if (
            str(request.clientPort) in REQUESTS_PROCESSED
            and str(request.reqID) in REQUESTS_PROCESSED[str(request.clientPort)]
        ):
            return services2.RegResp(successAck=1, message="Request already processed!")

        # storing details of the new signee
        ACCOUNT_DETAILS[request.email] = [request.password, 0]

        # updating in the requests processed
        if str(request.clientPort) not in REQUESTS_PROCESSED:
            REQUESTS_PROCESSED[str(request.clientPort)] = [str(request.reqID)]
        else:
            REQUESTS_PROCESSED[str(request.clientPort)].append(str(request.reqID))

        return services2.RegResp(successAck=1, message="SignUp Successful!")

    # defining transaction service
    def transact(self, request, context):
        # globals
        global ACCOUNT_DETAILS, REQUESTS_PROCESSED, TRANSACT_LOCK

        # checking if the request is already processed
        if (
            str(request.clientPort) in REQUESTS_PROCESSED
            and str(request.reqID) in REQUESTS_PROCESSED[str(request.clientPort)]
        ):
            return services2.TransactResp(
                successAck=1,
                message="Request already processed!",
                balanceLeft=ACCOUNT_DETAILS[request.email][1],
            )

        # making transaction after taking Lock (CS ahead)
        with TRANSACT_LOCK:
            if request.transactionType == "debit":
                # if not enough balance then return
                if ACCOUNT_DETAILS[request.email][1] < request.amount:
                    return services2.TransactResp(
                        successAck=1,
                        message="Insufficient Balance!",
                        balanceLeft=ACCOUNT_DETAILS[request.email][1],
                    )

                # otherwise, make the transaction
                ACCOUNT_DETAILS[request.email][1] -= request.amount

            elif request.transactionType == "credit":
                ACCOUNT_DETAILS[request.email][1] += request.amount
            else:
                pass

        # updating in the requests processed
        if str(request.clientPort) not in REQUESTS_PROCESSED:
            REQUESTS_PROCESSED[str(request.clientPort)] = [str(request.reqID)]
        else:
            REQUESTS_PROCESSED[str(request.clientPort)].append(str(request.reqID))

        return services2.TransactResp(
            successAck=1,
            message="Transaction Successful!",
            balanceLeft=ACCOUNT_DETAILS[request.email][1],
        )

    # defining failover service
    def failover(self, request, context):
        # checking if the request is already processed
        if (
            str(request.clientPort) in REQUESTS_PROCESSED
            and str(request.reqID) in REQUESTS_PROCESSED[str(request.clientPort)]
        ):
            return services2.FailoverResp(ack=1, message="Request already processed!")

        # waiting for 14 seconds (total, 7 + 7)
        time.sleep(7)

        # updating in the requests processed
        if str(request.clientPort) not in REQUESTS_PROCESSED:
            REQUESTS_PROCESSED[str(request.clientPort)] = [str(request.reqID)]
        else:
            REQUESTS_PROCESSED[str(request.clientPort)].append(str(request.reqID))

        # printing message on Bank server to show task completion
        print("Failover Completed Successfully!")

        # sleeping for the rest of 7 seconds
        time.sleep(7)

        # returning success
        return services2.FailoverResp(ack=1, message="Failover Completed Successfully!")

    # defining commit check service
    def commitCheck(self, request, context):
        global SHARE_LOCK, SENDER_STATUS, RECEIVER_STATUS

        # changing status based on request received
        if request.shareStatus == "sender":
            SENDER_STATUS = True
        elif request.shareStatus == "receiver":
            RECEIVER_STATUS = True

        # returning READY to commit
        return services2.CommitResp(message="Ready!")

    # defining share service
    def share(self, request, context):
        global SHARE_LOCK, ACCOUNT_DETAILS, REQUESTS_PROCESSED, SENDER_STATUS, RECEIVER_STATUS

        # checking if request is already processed
        if (
            str(request.clientPort) in REQUESTS_PROCESSED
            and str(request.reqID) in REQUESTS_PROCESSED[str(request.clientPort)]
        ):
            return services2.ShareResp(
                successAck=1,
                message="Request already processed!",
                balanceLeft=ACCOUNT_DETAILS[request.senderEmail][1],
            )

        # based on SHARE_STATUS
        if SENDER_STATUS:
            # accquiring lock
            with SHARE_LOCK:
                # checking if enough balance
                if ACCOUNT_DETAILS[request.senderEmail][1] < request.amount:
                    return services2.ShareResp(
                        successAck=1, message="Insufficient Balance!"
                    )

                # otherwise, making the deduction
                ACCOUNT_DETAILS[request.senderEmail][1] -= request.amount

                # done with Sender status
                SENDER_STATUS = False

        elif RECEIVER_STATUS:
            # accquiring lock
            with SHARE_LOCK:
                # adding the amount
                ACCOUNT_DETAILS[request.receiverEmail][1] += request.amount

                # done with Receiver status
                RECEIVER_STATUS = False

        # updating in the requests processed
        if str(request.clientPort) not in REQUESTS_PROCESSED:
            REQUESTS_PROCESSED[str(request.clientPort)] = [str(request.reqID)]
        else:
            REQUESTS_PROCESSED[str(request.clientPort)].append(str(request.reqID))

        return services2.ShareResp(
            successAck=1,
            message="Transaction Successful!",
            balanceLeft=ACCOUNT_DETAILS[request.senderEmail][1],
        )

    # defining revert request
    def revert(self, request, context):
        global SHARE_LOCK, ACCOUNT_DETAILS, REQUESTS_PROCESSED

        # reverting back changes in PROCESSED REQUESTS & ACCOUNT DETAILS
        if str(request.clientPort) in REQUESTS_PROCESSED:
            if str(request.reqID) in REQUESTS_PROCESSED[str(request.clientPort)]:
                REQUESTS_PROCESSED[str(request.clientPort)].remove(str(request.reqID))
        ACCOUNT_DETAILS[request.senderEmail][1] += request.amount

        # returning success
        return services2.RevertResp(
            successkAck=1, balanceLeft=ACCOUNT_DETAILS[request.senderEmail][1]
        )


# function to get a random available port
def findFreePort():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def runPing(gatewayStub, gatewayChannel):
    global RUN_PING

    while not RUN_PING.is_set():
        pingReq = services2.PingReq(bankName=BANK_NAME)
        try:
            grpc.channel_ready_future(gatewayChannel).result(timeout=0.1)
        except grpc.FutureTimeoutError:
            print("Gateway Offline!")
            time.sleep(0.9)
            continue

        try:
            gatewayStub.ping(pingReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print("Gateway Offline!")
            else:
                print(f"gRPC error: {e}")
        time.sleep(0.9)


# the Server function
def server():
    # re defining the globals
    global MY_PORT, BANK_NAME, ACCOUNT_DETAILS, REQUESTS_PROCESSED, RUN_PING

    # getting the bank name
    bankName = input("Enter the Bank Name : ")
    BANK_NAME = bankName

    # getting a random free port
    MY_PORT = findFreePort()
    MY_PORT = int(MY_PORT)

    # declaring certificate variables
    privateKey = None
    certificate = None
    CACert = None

    # loading SSL certificates
    with open("../certificate/server.key", "rb") as f:
        privateKey = f.read()
    with open("../certificate/server.crt", "rb") as f:
        certificate = f.read()
    with open("../certificate/ca.crt", "rb") as f:
        CACert = f.read()

    # connecting to Gateway Server with SSL credentials
    creds = grpc.ssl_channel_credentials(
        root_certificates=CACert, private_key=privateKey, certificate_chain=certificate
    )
    gatewayChannel = grpc.secure_channel(
        "localhost:50000",
        creds,
        options=(("grpc.ssl_target_name_override", "gateway"),),
    )
    gatewayStub = services1.ServerToGatewayStub(gatewayChannel)

    # registering itself with the gateway server
    request = services2.RegBankReq(bankName=BANK_NAME, bankPort=MY_PORT)
    try:
        response = gatewayStub.register(request)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            print("Gateway server unavailable!")
        else:
            print(f"gRPC error: {e}")
        return

    # checking if failed
    if response.successAck == 0:
        print(response.message)
        return

    # starting pinging thread
    pingThread = threading.Thread(target=runPing, args=(gatewayStub, gatewayChannel))
    pingThread.start()

    # otherwise, checking if file exists or not
    if os.path.exists(f"./data/{BANK_NAME}.json"):
        with open(f"./data/{BANK_NAME}.json", "r") as f:
            data = json.load(f)
            ACCOUNT_DETAILS = data["ACCOUNT_DETAILS"]
            REQUESTS_PROCESSED = data["REQUESTS_PROCESSED"]
    else:
        # creating a new file
        with open(f"./data/{BANK_NAME}.json", "w") as f:
            json.dump(
                {
                    "ACCOUNT_DETAILS": ACCOUNT_DETAILS,
                    "REQUESTS_PROCESSED": REQUESTS_PROCESSED,
                },
                f,
            )

    # printing loaded data, if any
    print(f"Loaded data for {BANK_NAME} : {ACCOUNT_DETAILS}")
    print(REQUESTS_PROCESSED)

    # starting a channel for the server with interpceptors
    thisServer = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # adding all the servicers to server
    services1.add_GatewayToServerServicer_to_server(
        GatewayToServerServicer(), thisServer
    )

    # storing all the creds
    creds = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(privateKey, certificate)],
        root_certificates=CACert,
        require_client_auth=True,
    )

    # adding a SECURE PORT here based on the credentials (different from what we had done previosuly)
    thisServer.add_secure_port(f"[::]:{MY_PORT}", creds)
    thisServer.start()
    print(f"{BANK_NAME} Server started at {MY_PORT}.....")

    # keeping the server alive, awaiting requests
    try:
        thisServer.wait_for_termination()
    except KeyboardInterrupt:
        # joining pinging thread
        RUN_PING.set()
        pingThread.join()

        # dumping data to storage
        with open(f"./data/{BANK_NAME}.json", "w") as f:
            json.dump(
                {
                    "ACCOUNT_DETAILS": ACCOUNT_DETAILS,
                    "REQUESTS_PROCESSED": REQUESTS_PROCESSED,
                },
                f,
            )

        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    server()
