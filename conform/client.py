#!/usr/bin/env python

import sys
import barrister
import codecs
try:
    import json
except:
    import simplejson as json

trans    = barrister.HttpTransport("http://localhost:9233/")
client   = barrister.Client(trans, validate_request=False)
batch    = None

f   = open(sys.argv[1])
out = codecs.open(sys.argv[2], "w", "utf-8")

def get_and_log_result(iface, func, params, c):
    status = "ok"

    try:
        resp = c()
    except barrister.RpcException as e:
        status = "rpcerr"
        resp = e.code
    except:
        print "ERR: %s" % str(sys.exc_info())
        status = "err"
        resp = ""

    out.write("%s|%s|%s|%s|%s\n" % (iface, func, params, status, json.dumps(resp)))

########################################

lines = f.read().split("\n")
for line in lines:
    line = line.strip()
    if line == '' or line.find("#") == 0:
        continue

    if line == 'start_batch':
        batch = client.start_batch()
        continue
    elif line == 'end_batch':
        results = batch.send()
        for i in range(results.count):
            c = lambda: results.get(i)
            req = batch.req_list[i]
            pos = req["method"].find(".")
            iface = req["method"][:pos]
            func  = req["method"][pos+1:]
            get_and_log_result(iface, func, json.dumps(req["params"]), c)
        batch = None
        continue

    cur_client = client
    if batch:
        cur_client = batch

    iface, func, params, exp_status, exp_resp = line.split("|")
    p = json.loads(params)

    svc = getattr(cur_client, iface)
    fn  = getattr(svc, func)
    c   = lambda: fn(*p)

    if batch:
        c()
    else:
        get_and_log_result(iface, func, params, c)

    line = f.readline()

f.close()
out.close()
