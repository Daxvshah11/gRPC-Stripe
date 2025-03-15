# `P1 - Strife`

## Assumptions

### Payment Gateway Server

* Only ONE, always! It can also go offline

* To handle offline case, assuming that there is a Stable storage on Disk locally. Further, to simulate failure, assuming that only *Ctrl+C* is used

* Thus, whenever failure happens, the locally stored memory about everything that has been updated, and is required by the Gateway is immediately stored locally on Disk

* Similarly, whenever the storage comes back up Online, it retrieves all the data from the local Disk storage into its Memory for `faster access`

* Gateway server has the `Interceptors`, namely Auth & Logging. Thus, assuming that both the functionalities are performed at Gateway itself and so, Bank servers dont have to do it

* Declares Bank server as offline if Ping not received for more than 4 seconds

* Assuming that the Gateway server has its own THREADING LOCKS to prevent entering into CS of different auth checks altogether for different client requests of the **same thing**. This is ensure that Gateway server is indeed acting like a middle point for all the auth checks and preventing those checks from happening redundantly at the Servers as well

* Therefore, based on the above assumption, the locking for safety happens at an earlier stage (*for some of the actions*) at the Gateway rather than at the later stage at the Bank servers (*safer option*)

* Assuming that a `Revert Request` *NEVER FAILS*, based on the implementation. This is done in order to prevent to have to maintain a new separate failed requests queue at the Gateway server as well. Again, as mentioned, this is only as per the current implementation, can be changed as per requirements



### Bank Servers
* Per Bank, there would be ONLY one Port assigned at a time. Same goes for vice-versa ie. Per Server instance, there would be only ONE Bank assigned to it

* Whenever there is a Server inititated, it will ask for the Bank details that will be based out of that Server. Assuming that at any given point of time, there are ONLY UNIQUE Bank names entered

* All the Bank's storages are stored locally in a folder called `./storage/`, where each Bank's exactly 1 unique file is kept. In case there is a new Bank joining then a new file is created. If an older Bank re-joins then it simply opens its own storage file

* Sending a ping after every 1 second to the Gateway server



### Client

* For a given bank, a Client will always have `ONLY ONE` Bank account. For a new bank account, he/she has to register with some other Bank

* For every client, there is a unique Client ID or also called as the `PORT ID` in this case

* Clients can perform 2 Main types of actions with their accounts:
    1) Transact money (*ie. debit/credit some amount from/into account respectively*)
    2) Send money to some other account (*even in some other Bank's server*)

* Can only perform 2 types of **transactions** :
    - Deposit (in one of his logged in Bank Accounts)
    - Withdrawal (from one of his logged in Bank Accounts)

* Clients ofcourse cant decide to *"receive"* money from some Bank account without their perms. But, as per regular world transaction possibilities, the vice-versa is possible. This means that someone can send money to someone else's account without explicit permission

* Assuming that sending money to `YOUR OWN ACCOUNT` is forbidden

* Assuming that for every transaction, the Client has to login every time. This can easily be changed based on requirements for ease of use or something similar

* Thus, based on the above, the client has to provide Bank name, account ID & password for every transaction along with the transaction details

* Only integer transactions are allowed. Although, this can easily be changed as per requirements

* For implementation of Idempotency, usage of Port ID is done even on the Client side. So, assuming that the PORT ADDRESS of any new client is always unique and not same as any previously opened Port addresses

* Idempotent messaging can be tested using `failover` command testing method. Basically, failover command makes that Bank server sleep for a total of 14 seconds (7 + 7). But in between, after first 7 seconds, Bank server prints a message of Failover command and then sleeps again. Thus:
    - we can check in 2 cases
    - fail the Bank server using Ctrl+C *before* the Failover message is printed
    - fail the Bank server using Ctrl+C *after* the Failover message in printed
    - in the second case, the request has been processed so it should not print failover second time at the Bank server

* Assuming that once a request is made by the Client, it wants it to be finished. But, for any request, we can only have a `LIMITED RE-TRIES (3 Retries in this case)` ie. even if it fails at the moment, the Client will be shown the error message and it will move on to the next requests to be made. But, eventually, beacuse of retrying, there will be a success message shown with that Request ID to show that the request was completed, ***if it was indeed completed***

* Otherwise, based on above assumption, if it failed even after 3 retries then that request would be `Dropped / Aborted`. In continuation to that, the abortion message will be printed to show the same

* For every Client that is running, there is assumed to be a Request Queue. Once Client is running, a separate thread is made which keeps on doing only one thing, iterate over the queued up requests after every 1 second gap, and retry those requests until not satisfied

* 1 second gap is assumed between every retry made for consecutive requests. As for the case of *numerous* queued up requests, we would not want the requests towards the end to wait for too long. Rather, its better to have more chances faster, though some of them would be wasted. Worth trying and failing than not trying for too long & waiting doing nothing!

* Assuming, irrespective of the success or failure of the request, the RequestID always increments by 1

* For the particular case of sharing/sending of Money to other accounts, it has been assumed that implementation of `Notifications for the Credited money` is NOT to be done. This is based on the assumption from above that there is, as such, no *"logging In"* for particular clients. Also, a Client is not necessarily always ONLINE so there is ambiguity of WHERE to display the notification and WHEN?



## I/O Format


### Sign Up

* Whenever a new client joins in, by default, its assumed that they can only perform 2 initial actions, namely:
    - Sign Up (create new Bank Account, if not already existing)
    - Log In (log into the existing Bank Account, if any)

* Signing up requires letting the gateway know about the Bank name where you want your new Bank Account, your registration emailID & password for the same

* Logging into a Bank Account also requires the same details as those for Signing Up