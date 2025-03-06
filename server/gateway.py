import grpc
import sys
from concurrent import futures
import time

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS
REGISTERED_BANKS = ["ICICI", "SBI"]
ACCOUNT_DETAILS = {}


# INTERCEPTORS


# interceptor for auth check
class AuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        # globals
        global REGISTERED_BANKS, ACCOUNT_DETAILS

        # storing the og handler
        handlerOG = continuation(handler_call_details)
        if handlerOG is None:
            return None

        # wrapping only the signUp method
        if handler_call_details.method == "/ClientToGateway/signUp":
            # wrapping the unary method
            def new_unary_unary(request, context):
                # checking if the Bank is registered or not
                if request.bank not in REGISTERED_BANKS:
                    # here, instead of raising an error, I am returning a RegResp msg with failure msg
                    return services2.RegResp(
                        successAck=0, message="Bank not registered!"
                    )

                # adding new account details to global
                if (ACCOUNT_DETAILS.get(request.bank) is not None) and (
                    ACCOUNT_DETAILS[request.bank].get(request.email) is not None
                ):
                    return services2.RegResp(
                        successAck=0, message="Account already exists!"
                    )
                elif (
                    ACCOUNT_DETAILS.get(request.bank) is not None
                ) and ACCOUNT_DETAILS[request.bank].get(request.email) is None:
                    ACCOUNT_DETAILS[request.bank][request.email] = request.password
                elif ACCOUNT_DETAILS.get(request.bank) is None:
                    ACCOUNT_DETAILS[request.bank] = {}
                    ACCOUNT_DETAILS[request.bank][request.email] = request.password
                else:
                    pass

                # otherwise calling og handler
                return handlerOG.unary_unary(request, context)

            # return new handler that wraps our new_unary_unary function
            return grpc.unary_unary_rpc_method_handler(
                new_unary_unary,
                request_deserializer=handlerOG.request_deserializer,
                response_serializer=handlerOG.response_serializer,
            )

        elif handler_call_details.method == "/ClientToGateway/signIn":
            # wrapping the unary method
            def new_unary_unary(request, context):
                # checking if the Bank is registered or not
                if request.bank not in REGISTERED_BANKS:
                    # here, instead of raising an error, I am returning a RegResp msg with failure msg
                    return services2.RegResp(
                        successAck=0, message="Bank not registered!"
                    )

                # checking if the given account exists or not
                if ACCOUNT_DETAILS[request.bank].get(request.email) is None:
                    return services2.RegResp(
                        successAck=0, message="Account does not exist!"
                    )
                elif (
                    ACCOUNT_DETAILS[request.bank].get(request.email) != request.password
                ):
                    return services2.RegResp(
                        successAck=0, message="Incorrect Password!"
                    )
                else:
                    pass

                # otherwise calling og handler
                return handlerOG.unary_unary(request, context)

            # return new handler that wraps our new_unary_unary function
            return grpc.unary_unary_rpc_method_handler(
                new_unary_unary,
                request_deserializer=handlerOG.request_deserializer,
                response_serializer=handlerOG.response_serializer,
            )

        # for all other cases, returning the original handler
        return handlerOG


# interceptor for logging details of requests & other info
class LogInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        # logging the request into the file (create file if not exists)
        with open("gatewayLog.txt", "a") as f:
            # appending current date & time & method in one line, tab separated
            f.write(
                f"{time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}\t{handler_call_details.method}\n"
            )

        return continuation(handler_call_details)


# SERVICERS


# ClientToGatewayServicer class
class ClientToGatewayServicer(services1.ClientToGatewayServicer):
    # defining signUp service
    def signUp(self, request, context):
        return services2.RegResp(successAck=1, message="SignUp Successful!")

    # defining signIn service
    def signIn(self, request, context):
        return services2.RegResp(successAck=1, message="SignIn Successful!")


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
    thisServer = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor(), LogInterceptor()],
    )

    # adding all the servicers to server
    services1.add_ClientToGatewayServicer_to_server(
        ClientToGatewayServicer(), thisServer
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
        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    gateway()
