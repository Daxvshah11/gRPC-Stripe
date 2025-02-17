import grpc
import sys
from concurrent import futures
import socket

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS
MY_PORT = 0


# INTERCEPTOR
class AuthInterceptor(grpc.ServerInterceptor):
    def interceptService(self, continuation, handler_call_details):
        # metadata = dict(handler_call_details.invocation_metadata)
        # username = metadata.get("username")
        # password = metadata.get("password")

        # if not username or not password or users.get(username) != password:

        #     def abort(request, context):
        #         context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid credentials")

        #     return grpc.unary_unary_rpc_method_handler(abort)

        # return continuation(handler_call_details)
        return


# SERVICERS


# function to get a random available port
def findFreePort():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# the Server function
def server():
    # re defining the globals
    global MY_PORT

    # declaring certificate variables
    privateKey = None
    certificate = None
    CACert = None

    # loading SSL certificates
    with open("../certificate/server.key", "rb") as f:
        privateKey = f.read()
    with open("../certificate/server.crt", "rb") as f:
        certificate = f.read()
    with open("../certificate/ca.cert", "rb") as f:
        CACert = f.read()

    # starting a channel for the server with interpceptors
    thisServer = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10), interceptors=[AuthInterceptor()]
    )
    creds = grpc.ssl_server_credentials(
        [(privateKey, certificate)], root_certificates=CACert, require_client_auth=True
    )
    MY_PORT = findFreePort()
    thisServer.add_secure_port(
        f"[::]:{MY_PORT}", creds
    )  # this one is different from what we tried in previous 2 tasks, because we are using SSL security channel na so.....

    # adding all the servicers to server

    # starting the server
    thisServer.start()
    print(f"Server started at {MY_PORT}.....")

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
