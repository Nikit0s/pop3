import socket
import argparse
import ssl
import re
import quopri
import base64
import getpass
import traceback

_MAXLINE = 2048
CR = '\r'
LF = '\n'
CRLF = CR+LF

def getResponse(sfile):
	line = sfile.readline(_MAXLINE + 1)
	if len(line) > _MAXLINE:
		print('line too long')
		sys.exit()
	if not line:
		print("EOF")
		sys.exit()
	if line[-2:] == CRLF:
		resp = line[:-2]
	if line[0] == CR:
		resp = line[1:-1]
	resp = line[:-1]
	return resp

def getLongResponse(sfile):
	resp = getResponse(sfile)
	if not resp.startswith(b"+"):
		return resp, []
	mylist = []
	line = getResponse(sfile)
	while line != b".\r":
		if line.startswith(b".."):
			line = line[1:]
		mylist.append(line)
		line = getResponse(sfile)
	return resp, mylist

def auth(sock, sfile, login, password):
	for command in ["USER {0}\r\n".format(login).encode("utf-8"), "PASS {0}\r\n".format(password).encode("utf-8")]:
		sock.sendall(command)
		resp = getResponse(sfile)
		if not resp.startswith(b"+"):
			return False
	return True

def getQuantity(sock, sfile):
	sock.sendall(b"LIST\r\n")
	resp, mails = getLongResponse(sfile)
	if resp.startswith(b"+"):
		strData = resp.decode("utf-8")
		strQuantity = ""
		cur = 4
		while (strData[cur] in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]):
			strQuantity += strData[cur]
			cur += 1
		quantity = int(strQuantity)
		return quantity
	return 0

def getMessage(number, sock, sfile):
	sock.send("retr {0}\r\n".format(number).encode("utf-8"))
	resp, content = getLongResponse(sfile)
	return resp, content

def decodeHeader(inputStr):
	encoding = re.compile("=\?(.+?)\?(.)\?(.+?)\?=")
	res = re.findall(encoding, inputStr)
	if len(res) == 0:
		return ""
	else:
		res = res[0]
		if ((res[1] == "q") or (res[1] == "Q")):
			return quopri.decodestring(res[2]).decode(res[0])
		elif((res[1] == "b") or (res[1] == "B")):
			return base64.b64decode(res[2]).decode(res[0])
	return ""

def showMessages(left, right, sock, sfile):
	regQuo = re.compile("([^@|\s]+@[^@]+\.[^@|\s]+)")
	for i in range(left, right + 1):
		res = {"From" : "?!", "To" : "?!", "Date" : "?!", "Subject" : "?!", "Size" : "?!"}
		curResp, curContent = getMessage(i, sock, sfile)
		if not curResp.startswith(b"+"):
			print("No such e-mail in your box")
			print()
			continue
		emailList = []
		for s in curContent:
			try:
				emailList.append(s.decode("utf-8"))
			except UnicodeDecodeError:
				pass
		for s in emailList:
			if s.startswith("From: "):
				standartname = re.findall(regQuo, s)
				if len(standartname) == 0:
					standartname = [""]
				name = decodeHeader(s)
				if len(name) > 0:
					res["From"] = name + " " + standartname[0]
				else:
					res["From"] = standartname[0]
			if s.startswith("To: "):
				name = decodeHeader(s)
				standartname = re.findall(regQuo, s)
				if len(standartname) == 0:
					standartname = [""]
				if len(name) > 0:
					res["To"] = name + " " + standartname[0]
				else:
					res["To"] = standartname[0]
			if s.startswith("Date: "):
				res["Date"] = s[6:-1]
			if s.startswith("Subject: "):
				subj = s[9:-1]
				res["Subject"] = decodeHeader(subj)
		sock.sendall("LIST {0}\r\n".format(i).encode("utf-8"))
		resp = getResponse(sfile)
		res["Size"] = resp.decode("utf-8")[5 + len(str(i)):-1]
		try:
			print("От ", res["From"])
			print("Кому ", res["To"])
			print("Тема: ", res["Subject"])
			print("Дата: ", res["Date"])
			print("Размер: ", res["Size"])
			print()
		except UnicodeEncodeError:
			pass


def main(args):
	server = args.server
	port = args.port
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.settimeout(30)
	try:
		sock.connect((server, port))
		sock = ssl.wrap_socket(sock, None, None)
		sfile = sock.makefile("rb")
		resp = getResponse(sfile)
		if (resp.startswith(b"+")):
			succesAuth = False
			print("We need your login")
			login = str(input())
			print("Enter your password")
			password = str(getpass.getpass())
			while not succesAuth:
				succesAuth = auth(sock, sfile, login, password)
				if not succesAuth:
					print("Cant auth, repeat please")
					print("We need your login")
					login = str(input())
					print("Enter your password")
					password = str(getpass.getpass())
			quantity = getQuantity(sock, sfile)
			print("You have ", quantity, " e-mails")
			print()
			print("Input which one you want to explore, or input left and right limits to explore several e-mails")
			inp = input().split(" ")
			if (len(inp) > 1):
				left = int(inp[0])
				right = int(inp[1])
			if (len(inp) == 1):
				left = right = inp[0]
		else:
			print("Cant auth")
			sys.exit()
		showMessages(left, right, sock, sfile)
	except socket.timeout:
		print("Sock timeout")
	finally:
		sock.close()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="POP Client")
	parser.add_argument("server", help="Server's address")
	parser.add_argument("port", help="Server's pop3 port", nargs="?", default=995)
	args = parser.parse_args()
	main(args)