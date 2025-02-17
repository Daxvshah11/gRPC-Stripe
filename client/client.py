import grpc
import sys
from concurrent import futures
import time

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# the Client function
def client():
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
    gateway_channel = grpc.secure_channel("localhost:50000", creds)
    gateway_stub = services1.GatewayStub(gateway_channel)

    # getting into loop
    while True:
        # taking input from user
        command = input("Enter the command : ")

        # splitting the command
        command = command.split(" ")
        cmd = command[0]
        if cmd == "exit":
            break

        elif cmd == "work":
            pass
            # preparing a new request
            # sending it & getting response

        else:
            # printing for error
            print("Command incorrect!")
            continue

    return


# MAIN
if __name__ == "__main__":
    client()
