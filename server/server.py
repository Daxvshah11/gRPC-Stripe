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


# GLOBALS
MY_PORT = 0
BANK_NAME = None
ACCOUNT_DETAILS = {}
RUN_PING = threading.Event()


# INTERCEPTORS


# SERVICERS


# GatewayToServerServicer class
class GatewayToServerServicer(services1.GatewayToServerServicer):
    # defining signUp service
    def signUp(self, request, context):
        # globals
        global ACCOUNT_DETAILS

        # storing details of the new signee
        ACCOUNT_DETAILS[request.email] = [request.password, 0]

        return services2.RegResp(successAck=1, message="SignUp Successful!")

    # defining transaction service
    def transact(self, request, context):
        # globals
        global ACCOUNT_DETAILS

        # making transaction
        if request.transactionType == "debit":
            ACCOUNT_DETAILS[request.email][1] -= request.amount
        elif request.transactionType == "credit":
            ACCOUNT_DETAILS[request.email][1] += request.amount
        elif request.transactionType == "view":
            pass
        else:
            pass

        return services2.TransactResp(
            successAck=1,
            message="Transaction Successful!",
            balanceLeft=ACCOUNT_DETAILS[request.email][1],
        )


# function to get a random available port
def findFreePort():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def runPing(gatewayStub):
    global RUN_PING

    while not RUN_PING.is_set():
        pingReq = services2.PingReq(bankName=BANK_NAME)
        try:
            gatewayStub.ping(pingReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print("Gateway Offline!")
            else:
                print(f"gRPC error: {e}")
        time.sleep(0.5)


# the Server function
def server():
    # re defining the globals
    global MY_PORT, BANK_NAME, ACCOUNT_DETAILS, RUN_PING

    # getting the bank name
    bankName = input("Enter the Bank Name : ")
    BANK_NAME = bankName

    # getting a random free port
    MY_PORT = findFreePort()

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
    request = services2.RegBankReq(bankName=BANK_NAME, bankPort=int(MY_PORT))
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
    pingThread = threading.Thread(target=runPing, args=(gatewayStub,))
    pingThread.start()

    # otherwise, checking if file exists or not
    if os.path.exists(f"./data/{BANK_NAME}.json"):
        with open(f"./data/{BANK_NAME}.json", "r") as f:
            ACCOUNT_DETAILS = json.load(f)["ACCOUNT_DETAILS"]
    else:
        # creating a new file
        with open(f"./data/{BANK_NAME}.json", "w") as f:
            json.dump({"ACCOUNT_DETAILS": ACCOUNT_DETAILS}, f)

    # printing loaded data, if any
    print(f"Loaded data for {BANK_NAME} : {ACCOUNT_DETAILS}")

    # starting a channel for the server with interpceptors
    thisServer = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10)
        # futures.ThreadPoolExecutor(max_workers=10), interceptors=[AuthInterceptor()]
    )

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
            json.dump({"ACCOUNT_DETAILS": ACCOUNT_DETAILS}, f)

        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    server()
