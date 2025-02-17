import grpc
import sys
from concurrent import futures

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS


# SERVICERS


# the Server function
def gateway():
    # re defining the globals

    # getting server certificate & key
    privateKey = None
    certificate = None
    CACert = None

    with open("../certificate/gateway.key", "rb") as f:
        privateKey = f.read()
    with open("../certificate/gateway.crt", "rb") as f:
        certificate = f.read()
    with open("../certificate/ca.crt", "rb") as f:
        CACert = f.read()

    # starting a channel for the server with SSL credentials
    thisServer = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    creds = grpc.ssl_server_credentials(
        [(privateKey, certificate)], root_certificates=CACert, require_client_auth=True
    )
    thisServer.add_secure_port(f"[::]:{50000}", creds)

    # adding all the servicers to server

    # connecting to LB server for registering with SSL credentials
    creds = grpc.ssl_channel_credentials(
        root_certificates=CACert,
        private_key=privateKey,
        certificate_chain=certificate
    )
    channel = grpc.secure_channel("localhost:50000", creds)

    # starting the server
    thisServer.start()
    print(f"Gateway Server started.....")

    # keeping the server alive, awaiting requests
    try:
        thisServer.wait_for_termination()
    except KeyboardInterrupt:
        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    gateway()
