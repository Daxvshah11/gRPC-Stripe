# `P1 - Strife`

## Assumptions

### Payment Gateway Server

* Only ONE, always. Assuming that it NEVER goes Offline

* Only Gateway server has the `Interceptors`, and Bank servers dont have it



### Bank Servers
* Per Bank, there would be ONLY one Port assigned at a time. Same goes for vice-versa ie. Per Server instance, there would be only ONE Bank assigned to it

* Whenever there is a Server inititated, it will ask for the Bank details that will be based out of that Server. Assuming that at any given point of time, there are ONLY UNIQUE Bank names entered

* All the Bank's storages are stored locally in a folder called `./storage/`, where each Bank's exactly 1 unique file is kept. In case there is a new Bank joining then a new file is created. If an older Bank re-joins then it simply opens its own storage file



### Client

* 



## I/O Format