import grpc
import sys
from concurrent import futures
import socket
import threading

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS
MY_PORT = 0
BANK_NAME = None


# INTERCEPTORS


# SERVICERS


# function to get a random available port
def findFreePort():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# the Server function
def server():
    # re defining the globals
    global MY_PORT, BANK_NAME

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
    response = gatewayStub.register(request)

    # checking if failed
    if response.successAck == 0:
        print(response.message)
        return

    # otherwise, starting a channel for the server with interpceptors
    thisServer = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10)
        # futures.ThreadPoolExecutor(max_workers=10), interceptors=[AuthInterceptor()]
    )
    creds = grpc.ssl_server_credentials(
        [(privateKey, certificate)], root_certificates=CACert, require_client_auth=True
    )

    # adding a SECURE PORT here based on the credentials (different from what we had done previosuly)
    thisServer.add_secure_port(f"[::]:{MY_PORT}", creds)

    # adding all the servicers to server

    # starting the server
    thisServer.start()
    print(f"{BANK_NAME} Server started at {MY_PORT}.....")

    # keeping the server alive, awaiting requests
    try:
        thisServer.wait_for_termination()
    except KeyboardInterrupt:
        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    server()
