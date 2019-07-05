#!/usr/bin/python
# install via pip: web3, jsonschema
#
# ethInterface.py
# python script that listens for json requests, parses them and interacts with the ethereum blockchain 
# to store the delivered via smart contract. Needs contract address, abi and an ethereum (light) node including account with some eth
# works asynchronousm all incoming requests are dumped into a queue beforehand and processed afterwards
import sys
import web3
from web3 import Web3, HTTPProvider
from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3.contract import ConciseContract

import queue
import fnmatch

import json
from jsonschema import validate
import time
import datetime
import http.server
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from socketserver import ThreadingMixIn
import threading

debug = False #for extensive logging
mainnet = True  # if not True: use ropsten test net

# if a trade should be logged onto the block chain
# has the timestamp of order and direction as in "Up" or "down"
class tradeobject:
    def __init__(self, year,month,day,hour,minute,second,direction):
      self.year=year
      self.month=month
      self.day=day
      self.hour=hour
      self.minute=minute
      self.second=second
      self.direction=direction
      self.purpose="addtrade"

# if a trade is closed this will be stored onto the block chain
# has the exact closing time and the result as in pips
class resultobject:
    def __init__(self, year,month,day,hour,minute,second,netpips):
      self.year=year
      self.month=month
      self.day=day
      self.hour=hour
      self.minute=minute
      self.second=second
      self.netpips=netpips
      self.purpose="addresult"
      
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

# requesthandler parses the http request and creates an object that is dropped into the main loop
# as of now, all http requests with proper data fields here will go into the blockchain function
class RequestHandler(BaseHTTPRequestHandler):
      def log_message(self, format, *args):
        return
      def do_POST(self):
        
        request_path = self.path
        
        if debug:
          print("\n----- Request Start ----->\n")
          print("Request path:", request_path)
        
        request_headers = self.headers
        content_length = request_headers.get('Content-Length')
        length = int(content_length) if content_length else 0
        
        if debug:
          print("Content Length:", length)
          print("Request headers:", request_headers)
          print("Request payload:", self.rfile.read(length))
          print("<----- Request End -----\n")
        
        obj = json.loads(self.rfile.read(length))
        if debug:
          print("Request payload:", obj)
          print(datetime.datetime.now())
        doQuery="false"
        doFunction=""

        for x in obj:
          print("RECEIVED: ",x, " ", obj[x])
          if(x=="do"):
            if(obj[x]=="query"):
              doQuery="true"
          if(x=="function"):
            if(obj[x]=="getTrade"):    
              doFunction="getTrade"
        
        if(doQuery=="true"):
          if(doFunction!=""):
            print("put/exec function: ", doFunction ," use main net: ", mainnet)
            q.put(doFunction)
        
        if("hour" in obj and "minute" in obj and "second" in obj and "direction" in obj and "year" in obj and "month" in obj and "day" in obj):
          if("TEST" not in obj["direction"]):
            print("found addTrade - ", obj["direction"])
            q.put(tradeobject(obj["year"],obj["month"],obj["day"],obj["hour"],obj["minute"],obj["second"],obj["direction"]))
            
            
        if("hour" in obj and "minute" in obj and "second" in obj and "netpips" in obj and "year" in obj and "month" in obj and "day" in obj):
          if("TEST" not in obj["netpips"]):  
            print("found addResult - ", obj["netpips"])
            q.put(resultobject(obj["year"],obj["month"],obj["day"],obj["hour"],obj["minute"],obj["second"],obj["netpips"]))
    
        self.send_response(200)
        self.end_headers()     
        #possible to give a return message to the post request
        responsetext="this is a sample return message."
        self.wfile.write(responsetext.encode("utf-8"))
        
# interface to Ethereum blockchain. Has the ABI of the contract, and interacts with the blockchain through the functions addTradeNow()
# and addResultNow()
# Needs a ethereum node reachable via http and an account with some eth to pay for gas in it
# Light Node is enough, no need to sync the whole chain
class EthInterface:
    def __init__(self):
      if(mainnet):
        self.web3Interface = Web3(HTTPProvider('http://localhost:8545')) #real net
      else:
        self.web3Interface = Web3(HTTPProvider('http://localhost:8546')) #test net
      self.web3Interface.eth.setGasPriceStrategy(medium_gas_price_strategy)
      for account in self.web3Interface.eth.accounts:
        print("account: ", account, " - balance: ", self.web3Interface.eth.getBalance(account))
      
      #implicit: first account used
      if(self.web3Interface.eth.accounts):
        self.useAccount = self.web3Interface.eth.accounts[0]
        print("using account ", self.useAccount)
      
      jforexabiJSON = open('/path/to/Contract.json', 'r').read() #read the ABI for the contract
      self.jforexabi = json.loads(jforexabiJSON)
      if(mainnet):
        self.adr = self.web3Interface.toChecksumAddress("0xffffffffffffffffffffffffffffffffffffffff") #address of main net contract
      else:  
        self.adr = self.web3Interface.toChecksumAddress("0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee") #address of test net contract
      self.myContract = self.web3Interface.eth.contract(address=self.adr, abi=self.jforexabi) 
      
      if debug:                                                           
        print("self my contract set to ", self.myContract)

    def callback_newblock(self,block_hash): #may be useful later for monitoring of blockchain related events
      pass
      
    def addTradeNow(self,tradeObjectdata):
      print("called addTradeNow")
      dateData=int(tradeObjectdata.year+tradeObjectdata.month+tradeObjectdata.day)
      timeData=int(tradeObjectdata.hour+tradeObjectdata.minute+tradeObjectdata.second)
      fulltime=int(tradeObjectdata.year+tradeObjectdata.month+tradeObjectdata.day+tradeObjectdata.hour+tradeObjectdata.minute+tradeObjectdata.second)
      buyBool=False
      if tradeObjectdata.direction is "up":
        buyBool=True
      print("tradeObjectdata: ", fulltime, " buy ",buyBool, " use account: ", self.useAccount)
      
      tx_hash = self.myContract.functions.addTrade(fulltime,buyBool).transact({'from': self.useAccount,'gas': 160000})
      try:
        txn_receipt = self.web3Interface.eth.waitForTransactionReceipt(tx_hash, timeout=360)                                                 
      except:
        print("exception at waitForTransactionReceipt addTradeNow")
        
      print("txn_receipt addTradeNow: ", txn_receipt)


    def addResultNow(self,resultData):
      print("called addResultNow")
      resultpips=int(float(resultData.netpips))
      print("will add result of ",resultpips, " to blockchain . main net?: ", mainnet)
      
      uid = int(self.myContract.functions.getId().call())
    
      print("received UID from blockchain: ", uid)      
      if(uid > -1):
        tx_hash = self.myContract.functions.addProfit(uid,resultpips).transact({'from': self.useAccount,'gas': 160000}) 
        try:
          txn_receipt = self.web3Interface.eth.waitForTransactionReceipt(tx_hash, timeout=360)
        except:
          print("exception at waitfortransactionreceipt addProfit")
        print("txn_receipt addResultNow: ", txn_receipt)
  
      else:
        print("invalid uid: ",uid)
      
# main loop iterates over its queue and assigns each item to
# the proper function...if applicable
def mainLoop(ethInterfaceObject):
    while True:
        qitem = q.get()
        if(qitem.purpose is "addtrade"):
          print("addtrade found in queue for ",qitem)
          ethInterfaceObject.addTradeNow(qitem)
        if(qitem.purpose is "addresult"):
          print("addresult found in queue for ",qitem)
          ethInterfaceObject.addResultNow(qitem)  
        time.sleep(10)

# main functions opens the webserver and starts the main loop with the Ethereum interface class
def main():
  HOST, PORT = "localhost", 8080
  
  server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
  ip, port = server.server_address
  server_thread = threading.Thread(target=server.serve_forever)
  server_thread.daemon = True
  server_thread.start()
  
  print("Server loop running in thread:", server_thread.name, ip, port)
  ethClient = EthInterface()
  mainLoop(ethClient)


# start here
if __name__ == "__main__":
  q = queue.Queue()
  main()