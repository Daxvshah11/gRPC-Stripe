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
    # updated secure_channel call with target name override for matching the certificate CN
    gatewayChannel = grpc.secure_channel(
        "localhost:50000",
        creds,
        options=(("grpc.ssl_target_name_override", "gateway"),),
    )
    gatewayStub = services1.ClientToGatewayStub(gatewayChannel)

    # getting into loop
    while True:
        # taking input from user
        command = input("Enter the command : ")

        # splitting the command
        command = command.split(" ")
        cmd = command[0]
        if cmd == "exit":
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
            request = services2.RegReq(bank=bankName, email=emailID, password=pswd)
            try:
                response = gatewayStub.signUp(request)
                print(response.message)
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
            request = services2.TransactReq(
                bank=bankName,
                email=emailID,
                password=pswd,
                transactionType=transactionType,
                amount=amount,
            )
            try:
                response = gatewayStub.transact(request)
                print(response.message)

                # printing current balance
                print(f"Current Balance : {response.balanceLeft}")

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print("Gateway server unavailable!")
                else:
                    print(f"gRPC error: {e}")
                continue

        else:
            # printing for error
            print("Command incorrect!")
            continue

    return


# MAIN
if __name__ == "__main__":
    client()
