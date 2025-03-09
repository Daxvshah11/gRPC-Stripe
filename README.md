# `P1 - Strife`

## Assumptions

### Payment Gateway Server

* Only ONE, always! It can also go offline

* To handle offline case, assuming that there is a Stable storage on Disk locally. Further, to simulate failure, assuming that only *Ctrl+C* is used

* Thus, whenever failure happens, the locally stored memory about everything that has been updated, and is required by the Gateway is immediately stored locally on Disk

* Similarly, whenever the storage comes back up Online, it retrieves all the data from the local Disk storage into its Memory for `faster access`

* Gateway server has the `Interceptors`, namely Auth & Logging. Thus, assuming that both the functionalities are performed at Gateway itself and so, Bank servers dont have to do it



### Bank Servers
* Per Bank, there would be ONLY one Port assigned at a time. Same goes for vice-versa ie. Per Server instance, there would be only ONE Bank assigned to it

* Whenever there is a Server inititated, it will ask for the Bank details that will be based out of that Server. Assuming that at any given point of time, there are ONLY UNIQUE Bank names entered

* All the Bank's storages are stored locally in a folder called `./storage/`, where each Bank's exactly 1 unique file is kept. In case there is a new Bank joining then a new file is created. If an older Bank re-joins then it simply opens its own storage file



### Client

* For a given bank, a Client will always have `ONLY ONE` Bank account. For a new bank account, he/she has to register with some other Bank

* Can only perform 2 types of **transactions** :
    - Deposit (in one of his logged in Bank Accounts)
    - Withdrawal (from one of his logged in Bank Accounts)



## I/O Format


### Sign Up

* Whenever a new client joins in, by default, its assumed that they can only perform 2 initial actions, namely:
    - Sign Up (create new Bank Account, if not already existing)
    - Log In (log into the existing Bank Account, if any)

* Signing up requires letting the gateway know about the Bank name where you want your new Bank Account, your registration emailID & password for the same

* Logging into a Bank Account also requires the same details as those for Signing Up