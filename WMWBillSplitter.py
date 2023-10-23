#!/usr/bin/env python3

import sys
import re
from typing import List
from enum import Enum

# pip install money-lib
from money import Money, xrates
from decimal import Decimal

indent = '  '
WildMan = Enum('WildMan', ['Nishant','Steve','Joe','Elton','John','Dim'])
xrates.backend = 'money.exchange.SimpleBackend'
xrates.base = 'USD'

# transactions in input files must be specified as follows, one transaction per line with white space separating each argument
# [transaction amount (REQUIRED)] [transaction currency (REQUIRED)] [WildMan payer (REQUIRED)] [Double-quote enclosed description of transaction (REQUIRED)] [Comma-separated list of WildMan beneficiaries (OPTIONAL, defaults to all wild men)] [Comma-separated list of proportions of the expense each beneficiary owes (OPTIONAL, defaults to an even split among beneficiaries)]
transaction_rgx = re.compile('([0-9\.]+)\s+(\S+)\s+(\S+)\s+\"(.*)\"\s+([a-zA-Z]+(?:,\s*[a-zA-Z]+)*)*(\s+[0-9/\.]+(?:,\s*[0-9/\.]+)*)*')

class Transaction:
	''' Models a payment made by a creditor for the benefit of a list of recipients
	'''
	def __init__(self, amt:Money, creditor:WildMan, recipients:List[WildMan]=list(WildMan.__members__.keys()), split:List[Decimal]|None=None, desc:str=str()):
		''' Initializes a transaction.
			amt = the currency value of the transaction
			creditor = the individual who originally paid the transaction
			recipients = the list of individuals benefitting from the transaction (defaults to all Wild Men)
			split = the share of the transaction owed, respectively, by each recipient (defaults to None for the case where the transaction is to be evenly split)
			desc = a string description of the transaction (defaults to an empty string)
		'''
		self.amt = round(amt, ndigits=2)
		self.creditor = creditor
		self.recipients = recipients 
		self.split = split if split!=None else [1/len(self.recipients) for _ in self.recipients]
		self.desc = desc

	def obligation(self, wm:WildMan) -> Money:
		'''Describes the Wildman's role in the transaction
		Returns the (positive) amount of USD wm is owed or the (negative) amount of USD wm owes in the transaction, whichever is applicable, or 0 if wm is not involved
		'''
		if self.creditor==wm:
			return self.amt
		elif wm in self.recipients:
			return -Decimal(self.split[self.recipients.index(wm)])*self.amt
		else:
			return Money('0','USD')

	def __str__(self) -> str:
		# splice out the creditor from the list of recipients, if necessary
		# to avoid 'person (and others) owes person $$$' outputs
		strrecipients = [r for r in self.recipients if r!=self.creditor]
		idx = self.recipients.index(self.creditor) if self.creditor in self.recipients else -1
		stramt = self.amt if idx==-1 else round(self.amt-(Decimal(self.split[idx])*self.amt), ndigits=2)

		return '{} {} {} ${} {}'.format(' and '.join(strrecipients), 'owe' if len(strrecipients)>1 else 'owes', self.creditor, stramt, 'for '+self.desc if self.desc!='' else '')

	def __lt__(self, other) -> bool:
		return self.amt < other.amt

	def __gt__(self, other) -> bool:
		return self.amt > other.amt

	def __le__(self, other) -> bool:
		return self.amt <= other.amt

	def __ge__(self, other) -> bool:
		return self.amt >= other.amt

	def __add__(self, other) -> Money:
		return self.amt + other.amt

	def __iadd__(self, other):
		self.amt += other

	def __mul__(self, other:float) -> Money:
		return Decimal(other) * self.amt

def error(msg:str) -> None:
	'''Prints an error.
	'''
	print('ERROR: {}'.format(msg))
	print('     : The transaction could not be added; please try again.')

def readExpenseFiles(files:list) -> list:
	'''Inputs transaction data from a list of input files and returns a list of Transaction objects'''
	transactions = []
	for file in files:
		for line in open(file,'r').readlines():
			mch = transaction_rgx.match(line)
			if mch==None or len(mch.groups()) != 6:
				print('Line\n{}\nin file {} could not be parsed; quitting.'.format(line,file))
			try:
				amt = float(mch.groups()[0])
				currency = mch.groups()[1]
				creditor = mch.groups()[2].capitalize()
				desc = mch.groups()[3]
				recipients = list(WildMan.__members__.keys()) if mch.groups()[4]==None else [a.strip() for a in mch.groups()[4].split(',')]
				split = None if mch.groups()[5]==None else [a.strip() for a in mch.groups()[5].split(',')]
			except Exception as e:
				raise e
			transactions.append(Transaction(amt=Money(amt,currency), creditor=creditor, recipients=recipients, split=split, desc=desc))
	return transactions

def main():
	if len(sys.argv)>1:
		transactions = readExpenseFiles(sys.argv[1:])
	else:
		transactions = queryUser()

	# compute initial balance (net amount owed to/by others) for each WildMan
	moneyOwed = dict.fromkeys(WildMan.__members__.keys(), Money('0','USD'))
	for t in transactions:
		# the creditor is owed the full amount
		moneyOwed[t.creditor] += t.amt
		# the recipients each owe their share of the full amount
		for (r,p) in zip(t.recipients, t.split):
			moneyOwed[r] -= t*p;

	# compute payments to make to settle everything up
	paymentsToMake = list()
	ct = 0
	while not all([round(v, ndigits=2).is_zero() for v in moneyOwed.values()]): 
		# make the biggest debtor pay the biggest creditor
		biggestDebtor = min(moneyOwed.items(), key=lambda i: i[1])
		biggestCreditor = max(moneyOwed.items(), key=lambda i: i[1])
		assert biggestCreditor[0] != biggestDebtor[0]
		amt = min(biggestCreditor[1], abs(biggestDebtor[1]))
		# adjust each person's balance
		moneyOwed[biggestDebtor[0]] = biggestDebtor[1]+amt
		moneyOwed[biggestCreditor[0]] = biggestCreditor[1]-amt
		# record the transaction
		paymentsToMake.append(Transaction(amt=amt, creditor=biggestCreditor[0], recipients=[biggestDebtor[0]]))
	
	# print summary and quit
	print('\nTO SETTLE THESE TRANSACTIONS...')
	for t in transactions:
		print(t)
	print('...MAKE THESE PAYMENTS:')
	for p in paymentsToMake:
		print(p)

	# check results: make sure each person is receiving (roughly) what they are owed
	for (wm,b) in moneyOwed.items():
		obal = round(b, ndigits=2)
		if obal != Money('0','USD'):
			print('SOMETHING\'S WRONG: {} has outstanding balance {}'.format(wm,obal))

if __name__ == '__main__':
	sys.exit(main())
