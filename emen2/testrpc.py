import emen2.clients.emen2client
db = emen2.clients.emen2client.opendb(username=None)

print db.getrecord(0)
