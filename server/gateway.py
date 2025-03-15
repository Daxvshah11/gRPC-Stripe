import grpc
import sys
from concurrent import futures
import time
import json
import threading
import os

# changing path for importing rest of the files
sys.path.append("../protofiles")
import services_pb2_grpc as services1
import services_pb2 as services2


# GLOBALS
ONLINE_BANKS = {}
ACCOUNT_DETAILS = {}
privateKey = None
certificate = None
CACert = None
RUN_PING_CHECK = threading.Event()

CG_SIGNUP_LOCK = threading.Lock()
CG_SHARE_LOCK = threading.Lock()
SG_REGISTER_LOCK = threading.Lock()


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

                # checking if PING message
                if "ping" not in handler_call_details.method:
                    # logging the details along with the response
                    with open("log.txt", "a") as f:
                        if "ServerToGateway" in handler_call_details.method:
                            log_line = (
                                f"{time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}, "
                                f"{handler_call_details.method}, "
                                f"{request.bankName}, "
                                f"Port {request.bankPort}, "
                                f"{response.message}\n"
                            )
                        elif "ClientToGateway" in handler_call_details.method:
                            if "share" in handler_call_details.method:
                                log_line = (
                                    f"{time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}, "
                                    f"{handler_call_details.method}, "
                                    f"{request.senderBank} -> {request.receiverBank}, "
                                    f"Port {request.clientPort}, "
                                    f"Request ID {request.reqID}, "
                                    f"{response.message}\n"
                                )
                            else:
                                log_line = (
                                    f"{time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}, "
                                    f"{handler_call_details.method}, "
                                    f"{request.bank}, "
                                    f"Port {request.clientPort}, "
                                    f"Request ID {request.reqID}, "
                                    f"{response.message}\n"
                                )
                        f.write(log_line)

                    # printing
                    print(f"ACCOUNT DETAILS : {ACCOUNT_DETAILS}")
                    print(f"ONLINE BANKS : {ONLINE_BANKS}")
                    print()

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
        global ACCOUNT_DETAILS, ONLINE_BANKS, CG_SIGNUP_LOCK, SG_REGISTER_LOCK

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
                    if (
                        "share" not in handler_call_details.method
                        and request.bank not in ONLINE_BANKS
                    ):
                        return services2.RegResp(
                            successAck=0, message="Bank Offline or Not Registered!"
                        )

                    # method-specific checks here
                    if handler_call_details.method == "/ClientToGateway/signUp":
                        # accquiring the lock (CS ahead)
                        with CG_SIGNUP_LOCK:
                            # checking if account already exists
                            if (
                                request.bank in ACCOUNT_DETAILS
                                and request.email in ACCOUNT_DETAILS[request.bank]
                            ):
                                return services2.RegResp(
                                    successAck=1, message="Account already exists!"
                                )

                            # calling og handler for further processing
                            ogResp = handler.unary_unary(request, context)

                            # checking response
                            if ogResp.successAck == 0:
                                return ogResp

                            # adding account if it doesnt exist
                            if request.bank in ACCOUNT_DETAILS:
                                ACCOUNT_DETAILS[request.bank][
                                    request.email
                                ] = request.password
                            else:
                                ACCOUNT_DETAILS[request.bank] = {
                                    request.email: request.password
                                }

                        # calling the og handler for further processsing
                        return ogResp

                    elif handler_call_details.method == "/ClientToGateway/transact":
                        # checking if the account even exists
                        if request.email not in ACCOUNT_DETAILS[request.bank]:
                            return services2.RegResp(
                                successAck=1, message="Account does not exist!"
                            )

                        # checking for the correct password
                        if (
                            ACCOUNT_DETAILS[request.bank][request.email]
                            != request.password
                        ):
                            return services2.RegResp(
                                successAck=1, message="Incorrect Password!"
                            )

                        # otherwise, normal futher proceedings
                        return handler.unary_unary(request, context)

                    elif handler_call_details.method == "/ClientToGateway/share":
                        # checking if both the banks are online or not
                        if request.senderBank not in ONLINE_BANKS:
                            return services2.ShareResp(
                                successAck=0, message="Sender Bank Offline!"
                            )
                        if request.receiverBank not in ONLINE_BANKS:
                            return services2.ShareResp(
                                successAck=0, message="Receiver Bank Offline!"
                            )

                        # checking if both accounts exist in respective Banks & authorized
                        if (
                            request.senderEmail
                            not in ACCOUNT_DETAILS[request.senderBank]
                        ):
                            return services2.ShareResp(
                                successAck=0, message="Sender Account does not exist!"
                            )
                        elif request.senderEmail in ACCOUNT_DETAILS[
                            request.senderBank
                        ] and (
                            ACCOUNT_DETAILS[request.senderBank][request.senderEmail]
                            != request.senderPassword
                        ):
                            return services2.ShareResp(
                                successAck=0, message="Incorrect Sender Password!"
                            )

                        if (
                            request.receiverEmail
                            not in ACCOUNT_DETAILS[request.receiverBank]
                        ):
                            return services2.ShareResp(
                                successAck=0, message="Receiver Account does not exist!"
                            )

                        # normal futher proceedings
                        return handler.unary_unary(request, context)

                    else:
                        # for other methods, simply calling the og handler
                        return handler.unary_unary(request, context)

                elif "/ServerToGateway/" in handler_call_details.method:
                    # getting the lock (CS ahead)
                    with SG_REGISTER_LOCK:
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
        # connecting to the Bank server
        newCreds = grpc.ssl_channel_credentials(
            root_certificates=CACert,
            private_key=privateKey,
            certificate_chain=certificate,
        )
        bankServerChannel = grpc.secure_channel(
            f"localhost:{ONLINE_BANKS[request.bank][0]}",
            newCreds,
            options=(("grpc.ssl_target_name_override", "server"),),
        )
        bankServerStub = services1.GatewayToServerStub(bankServerChannel)

        # checking & waiting if the channel is ready or not (UNAVAILABLE)
        try:
            grpc.channel_ready_future(bankServerChannel).result(timeout=3)
        except grpc.FutureTimeoutError:
            # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
            return services2.TransactResp(
                successAck=0, message="Bank Server Offline!", balanceLeft=-1
            )

        # performing signup
        newReq = request
        try:
            response = bankServerStub.signUp(newReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
                return services2.RegResp(successAck=0, message="Bank Server Offline!")
            else:
                print(f"gRPC error: {e}")

        return services2.RegResp(successAck=1, message="SignUp Successful!")

    # defining transaction service
    def transact(self, request, context):
        # connecting to the Bank server
        newCreds = grpc.ssl_channel_credentials(
            root_certificates=CACert,
            private_key=privateKey,
            certificate_chain=certificate,
        )
        bankServerChannel = grpc.secure_channel(
            f"localhost:{ONLINE_BANKS[request.bank][0]}",
            newCreds,
            options=(("grpc.ssl_target_name_override", "server"),),
        )
        bankServerStub = services1.GatewayToServerStub(bankServerChannel)

        # checking & waiting if the channel is ready or not (UNAVAILABLE)
        try:
            grpc.channel_ready_future(bankServerChannel).result(timeout=3)
        except grpc.FutureTimeoutError:
            # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
            return services2.TransactResp(
                successAck=0, message="Bank Server Offline!", balanceLeft=-1
            )

        # performing transaction
        newReq = request
        try:
            response = bankServerStub.transact(newReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
                return services2.TransactResp(
                    successAck=0,
                    message="Bank Server Offline!",
                    balanceLeft=-1,
                )
            else:
                print(f"gRPC error: {e}")

        return response

    # defining failover service
    def failover(self, request, context):
        # connecting to the Bank server
        newCreds = grpc.ssl_channel_credentials(
            root_certificates=CACert,
            private_key=privateKey,
            certificate_chain=certificate,
        )
        bankServerChannel = grpc.secure_channel(
            f"localhost:{ONLINE_BANKS[request.bank][0]}",
            newCreds,
            options=(("grpc.ssl_target_name_override", "server"),),
        )
        bankServerStub = services1.GatewayToServerStub(bankServerChannel)

        # checking & waiting if the channel is ready or not (UNAVAILABLE)
        try:
            grpc.channel_ready_future(bankServerChannel).result(timeout=3)
        except grpc.FutureTimeoutError:
            # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
            return services2.FailoverResp(ack=0, message="Bank Server not yet Online!")

        # performing transaction
        newReq = request
        try:
            response = bankServerStub.failover(newReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
                return services2.FailoverResp(ack=0, message="Bank Server Offline!")
            else:
                print(f"gRPC error: {e}")

        return response

    # defining share service
    def share(self, request, context):
        # connecting to the sender Bank server
        newCreds = grpc.ssl_channel_credentials(
            root_certificates=CACert,
            private_key=privateKey,
            certificate_chain=certificate,
        )
        senderBankServerChannel = grpc.secure_channel(
            f"localhost:{ONLINE_BANKS[request.senderBank][0]}",
            newCreds,
            options=(("grpc.ssl_target_name_override", "server"),),
        )
        senderBankServerStub = services1.GatewayToServerStub(senderBankServerChannel)

        # also connecting to the receiver Bank server
        receiverBankServerChannel = grpc.secure_channel(
            f"localhost:{ONLINE_BANKS[request.receiverBank][0]}",
            newCreds,
            options=(("grpc.ssl_target_name_override", "server"),),
        )
        receiverBankServerStub = services1.GatewayToServerStub(
            receiverBankServerChannel
        )

        # # checking & waiting if the channels are ready or not (UNAVAILABLE case handling)
        # try:
        #     grpc.channel_ready_future(senderBankServerChannel).result(timeout=3)
        #     grpc.channel_ready_future(receiverBankServerChannel).result(timeout=3)
        # except grpc.FutureTimeoutError:
        #     # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
        #     return services2.FailoverResp(
        #         ack=0, message="Bank Server(s) not yet Online!"
        #     )

        # otherwise, asking for commitment from both the Banks (with a timeout of 5 seconds)
        commReqSender = services2.CommitReq(message="Ready?", shareStatus="sender")
        commReqReceiver = services2.CommitReq(message="Ready?", shareStatus="receiver")
        try:
            commRespSender = senderBankServerStub.commitCheck(commReqSender, timeout=5)
        except grpc.RpcError as e:
            if e.code() in (
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.UNKNOWN,
            ):
                return services2.ShareResp(
                    successAck=0,
                    message="Sender's Bank Server Offline or response timed out!",
                    balanceLeft=-1,
                )
            else:
                print(f"gRPC error: {e}")
                return services2.ShareResp(
                    successAck=0,
                    message="Unexpected error in sender commit check",
                    balanceLeft=-1,
                )

        try:
            commRespReceiver = receiverBankServerStub.commitCheck(
                commReqReceiver, timeout=5
            )
        except grpc.RpcError as e:
            if e.code() in (
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.UNKNOWN,
            ):
                return services2.ShareResp(
                    successAck=0,
                    message="Receiver's Bank Server Offline or response timed out!",
                    balanceLeft=-1,
                )
            else:
                print(f"gRPC error: {e}")

        # otherwise, both Banks are ready. Forwarding share request to sender first
        newReq = request
        balanceLeftVal = -1
        try:
            response = senderBankServerStub.share(newReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
                return services2.ShareResp(
                    successAck=0, message="Sender Bank Offline!", balanceLeft=-1
                )
            else:
                print(f"gRPC error: {e}")
        balanceLeftVal = response.balanceLeft

        # checking if sender was successful
        if response.successAck == 0 or response.message == "Insufficient Balance!":
            return response

        # otherwise, forwarding to receiver as well
        try:
            response = receiverBankServerStub.share(newReq)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                # reverting transaction at Sender
                revertReq = services2.RevertReq(
                    senderBank=newReq.senderBank,
                    senderEmail=newReq.senderEmail,
                    amount=newReq.amount,
                )
                # assuming that it will never fail here!!!!!!
                revertResp = senderBankServerStub.revert(revertReq)
                balanceLeftVal = revertResp.balanceLeft

                # simply returning here, not manually removing from Online Banks. Trusting the Ping checker
                return services2.ShareResp(
                    successAck=0,
                    message="Receiver Bank Offline!",
                    balanceLeft=balanceLeftVal,
                )
            else:
                print(f"gRPC error: {e}")

        # if reached here, receiver was also successful
        finalResp = services2.ShareResp(
            successAck=1,
            message="Transaction Successful!",
            balanceLeft=balanceLeftVal,
        )
        return finalResp


# ServerToGatewayServicer class
class ServerToGatewayServicer(services1.ServerToGatewayServicer):
    # defining register service for a Bank
    def register(self, request, context):
        # globals
        global ONLINE_BANKS

        # registering & adding the bank to ONLINE_BANKS with port
        ONLINE_BANKS[request.bankName] = [request.bankPort, time.time()]

        return services2.RegBankResp(successAck=1, message="Bank Registered & Online!")

    def ping(self, request, context):
        global ONLINE_BANKS

        if request.bankName in ONLINE_BANKS:
            # update last ping time (keeping the port unchanged)
            ONLINE_BANKS[request.bankName][1] = time.time()

        return services2.PingResp(message="PONG")


# HELPERS


# ping checker thread
def pingChecker():
    global ONLINE_BANKS, RUN_PING_CHECK

    # sleep for some time, just for the case when Gateway goes down & comes back up'
    time.sleep(5)

    while not RUN_PING_CHECK.is_set():
        current = time.time()
        for bank in list(ONLINE_BANKS.keys()):
            last_ping = ONLINE_BANKS[bank][1]
            if current - last_ping > 2:
                # add to logs
                with open("log.txt", "a") as f:
                    log_line = (
                        f"{time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}, "
                        f"{bank} Bank Offline!\n"
                    )
                    f.write(log_line)

                print(f"{bank} Bank Offline!")
                del ONLINE_BANKS[bank]


# the Server function
def gateway():
    global ACCOUNT_DETAILS, ONLINE_BANKS, privateKey, certificate, CACert, RUN_PING_CHECK

    # loading the data from the JSON (single JSON object in the file to multiple globals here)\
    if os.path.exists(f"./data/GATEWAY.json"):
        with open(f"./data/GATEWAY.json", "r") as f:
            data = json.load(f)
            ACCOUNT_DETAILS = data["ACCOUNT_DETAILS"]
            ONLINE_BANKS = data["ONLINE_BANKS"]
    else:
        # creating a new file
        with open(f"./data/GATEWAY.json", "w") as f:
            json.dump(
                {"ACCOUNT_DETAILS": ACCOUNT_DETAILS, "ONLINE_BANKS": ONLINE_BANKS}, f
            )

    # printing loaded data
    print(f"Loaded Data : {ACCOUNT_DETAILS}, {ONLINE_BANKS}")

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

    # starting ping checker thread
    checkerThread = threading.Thread(target=pingChecker, daemon=True)
    checkerThread.start()

    # keeping the server alive, awaiting requests
    try:
        thisServer.wait_for_termination()
    except KeyboardInterrupt:
        # joining ping check thread
        RUN_PING_CHECK.set()
        checkerThread.join()

        # storing all the local memory Data into a JSON file (all the Globals basically!)
        with open("./data/GATEWAY.json", "w") as f:
            json.dump(
                {"ACCOUNT_DETAILS": ACCOUNT_DETAILS, "ONLINE_BANKS": ONLINE_BANKS}, f
            )

        print("Server terminating gracefully!")
        thisServer.stop(0)

    return


# MAIN
if __name__ == "__main__":
    gateway()
