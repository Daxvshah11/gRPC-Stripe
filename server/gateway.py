import grpc
import sys
from concurrent import futures
import time
import threading
import json

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS
ONLINE_BANKS = {}
ACCOUNT_DETAILS = {}


# INTERCEPTORS


# interceptor for logging details of requests & other info
class LogInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        # globals
        global ACCOUNT_DETAILS, ONLINE_BANKS

        # storing the og handler
        handlerOG = continuation(handler_call_details)
        if handlerOG is None:
            return None

        # creating a wrapper for all, if needed
        if handlerOG.unary_unary:
            # defining a new unary_unary function
            def new_unary_unary(request, context):
                # calling the original handler to get the response (moves ahead in the Chain)
                response = handlerOG.unary_unary(request, context)

                # logging the details along with the response
                with open("log.txt", "a") as f:
                    log_line = (
                        f"{time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}\t\t"
                        f"{handler_call_details.method} : "
                        f"{response.message}\n"
                    )
                    f.write(log_line)

                return response

            # returning a new handler that uses our wrapped function
            return grpc.unary_unary_rpc_method_handler(
                new_unary_unary,
                request_deserializer=handlerOG.request_deserializer,
                response_serializer=handlerOG.response_serializer,
            )

        # for all other cases, returning the original handler
        return handlerOG


class AuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        # globals
        global ACCOUNT_DETAILS, ONLINE_BANKS

        # storing the OG handler
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        # only wrapping if its unary-unary RPC
        if handler.unary_unary:
            # defining a new unary_unary function
            def new_unary_unary(request, context):
                # checking if the request is from a Bank server or Client
                if "/ClientToGateway/" in handler_call_details.method:
                    # checking if Bank is registered and online
                    if request.bank not in ONLINE_BANKS:
                        return services2.RegResp(
                            successAck=0, message="Bank Offline or Not Registered!"
                        )

                    # method-specific checks here
                    if handler_call_details.method == "/ClientToGateway/signUp":
                        # checking if account already exists
                        if (
                            ACCOUNT_DETAILS.get(request.bank) is not None
                            and ACCOUNT_DETAILS[request.bank].get(request.email)
                            is not None
                        ):
                            return services2.RegResp(
                                successAck=0, message="Account already exists!"
                            )

                        # adding account if it doesnt exist
                        elif ACCOUNT_DETAILS.get(request.bank) is not None:
                            ACCOUNT_DETAILS[request.bank][
                                request.email
                            ] = request.password
                        else:
                            ACCOUNT_DETAILS[request.bank] = {
                                request.email: request.password
                            }

                        # calling the og handler for further processsing
                        return handler.unary_unary(request, context)

                    elif handler_call_details.method == "/ClientToGateway/signIn":
                        # checking if the account even exists
                        if (
                            ACCOUNT_DETAILS.get(request.bank) is None
                            or ACCOUNT_DETAILS[request.bank].get(request.email) is None
                        ):
                            return services2.RegResp(
                                successAck=0, message="Account does not exist!"
                            )

                        # checking for the correct password
                        if (
                            ACCOUNT_DETAILS[request.bank][request.email]
                            != request.password
                        ):
                            return services2.RegResp(
                                successAck=0, message="Incorrect Password!"
                            )

                        # otherwise, normal futher proceedings
                        return handler.unary_unary(request, context)

                    else:
                        # for other methods, simply calling the og handler
                        return handler.unary_unary(request, context)

                elif "/ServerToGateway/" in handler_call_details.method:
                    # method based checks here
                    if (
                        handler_call_details.method == "/ServerToGateway/register"
                    ) and (request.bankName in ONLINE_BANKS):
                        return services2.RegBankResp(
                            successAck=0, message="Bank already Online!"
                        )

                    # for other cases, simply calling the og handler
                    return handler.unary_unary(request, context)

            # returning a new handler that uses our wrapper function
            return grpc.unary_unary_rpc_method_handler(
                new_unary_unary,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        else:
            # for all non-unary RPCs, returning og handler
            return handler


# SERVICERS


# ClientToGatewayServicer class
class ClientToGatewayServicer(services1.ClientToGatewayServicer):
    # defining signUp service
    def signUp(self, request, context):
        return services2.RegResp(successAck=1, message="SignUp Successful!")

    # defining signIn service
    def signIn(self, request, context):
        return services2.RegResp(successAck=1, message="SignIn Successful!")


# ServerToGatewayServicer class
class ServerToGatewayServicer(services1.ServerToGatewayServicer):
    # defining register service for a Bank
    def register(self, request, context):
        # globals
        global ONLINE_BANKS

        # registering & adding the bank to ONLINE_BANKS with port & current time stamp
        ONLINE_BANKS[request.bankName] = [request.bankPort, time.time()]

        return services2.RegBankResp(successAck=1, message="Bank Registered & Online!")


# the Server function
def gateway():
    global ACCOUNT_DETAILS, ONLINE_BANKS

    # loading the data from the JSON (single JSON object in the file to multiple globals here)
    with open("./data/gateway.json", "r") as f:
        data = json.load(f)
        ACCOUNT_DETAILS = data["ACCOUNT_DETAILS"]
        ONLINE_BANKS = data["ONLINE_BANKS"]

    print(ONLINE_BANKS)

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

    # starting a channel for the server with SSL credentials (first LOG, then AUTH, because one way flow only possible!!)
    thisServer = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[LogInterceptor(), AuthInterceptor()],
    )

    # adding all the servicers to server
    services1.add_ClientToGatewayServicer_to_server(
        ClientToGatewayServicer(), thisServer
    )
    services1.add_ServerToGatewayServicer_to_server(
        ServerToGatewayServicer(), thisServer
    )

    # storing all the creds
    creds = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(privateKey, certificate)],
        root_certificates=CACert,
        require_client_auth=True,
    )

    # starting the server
    thisServer.add_secure_port(f"[::]:{50000}", creds)
    thisServer.start()
    print(f"Gateway Server started.....")

    # keeping the server alive, awaiting requests
    try:
        thisServer.wait_for_termination()
    except KeyboardInterrupt:
        # storing all the local memory Data into a JSON file (all the Globals basically!)
        with open("./data/gateway.json", "w") as f:
            json.dump(
                {"ACCOUNT_DETAILS": ACCOUNT_DETAILS, "ONLINE_BANKS": ONLINE_BANKS}, f
            )

        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    gateway()
