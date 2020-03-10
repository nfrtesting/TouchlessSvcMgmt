from flask import Flask, Response, request
from prometheus_client import generate_latest, Info, Gauge, Histogram, Counter, Summary, CONTENT_TYPE_LATEST, start_http_server
from prometheus_flask_exporter import PrometheusMetrics
import re, glob, getopt, sys, yaml, subprocess
import xml.etree.ElementTree as etree

METRIC_PREFIX = 'configcheck'
PORT=9270


app = Flask(__name__)
m = PrometheusMetrics(app=app)
configCheck = Gauge('{0}'.format(METRIC_PREFIX), 'Config Match==1, Mismatch==0', ['configfile', 'path'])

def readModel(modelFile):
    fd = open(modelFile, "r")
    targetline = fd.readline()
    target = re.match("compareTo\((XML|OS)\):\W*(.*)", targetline)
    if target is not None:
        if target.groups()[0] == 'XML': spec = etree.XML(fd.read())
        if target.groups()[0] == 'OS': spec = yaml.load(fd.read(), Loader=yaml.FullLoader)
        else: spec = None
        return target.groups()[0], target.groups()[1], spec
    else:
        return None, None, None

def removeNamespace(txt):
    return re.match('({.+})*(.+)',txt).groups()[1]

def formattedAttributes(myAttr):
    fStr = ''
    if len(myAttr) > 0:
        fStr = '[{0}]'.format(', '.join(myAttr))
    return fStr

def formattedValue(myVal):
    fStr = ''
    if myVal is not None and myVal.strip() != "":
        fStr = '{0}'.format(myVal.strip())
    return fStr

def hasDupNodes(xml):
    retval = False
    dupCounts = {}
    children = [removeNamespace(i.tag) for i in list(xml)]
    distinctChildren = [*set(children),]
    countChildren = len(children)
    countDistinctChildren = len(distinctChildren)
    if(countChildren != countDistinctChildren):
        retval = True
    dupList = [len([x for x in children if x == i]) for i in distinctChildren]
    if len(children) > 0:
        for i in range(0,countDistinctChildren):
            if dupList[i] > 1:
                dupCounts[distinctChildren[i]] = dupList[i]
    return retval, dupCounts

def recursiveFlatten(xml, duparent = False, depth=0):
    children = list(xml)
    leaves = []
    subleaves = []
    myVal = xml.text
    myAttribs = []

    tabs = ''
    for x in range(0, depth): tabs = tabs + '\t'

    hasDups, dupTags = hasDupNodes(xml)

    if xml.text is not None: #clean up whitespace
        myVal = xml.text.strip()
    for n, v in xml.attrib.items():
        cleanname = removeNamespace(n)
        if cleanname != 'schemaLocation': # intentionally omit this tag
            myAttribs.append('{0}={1}'.format(cleanname, v))

    prefix = '{0}{1}.'.format(removeNamespace(xml.tag), formattedValue(myVal))

    if len(children) == 0:
        leaves.append('{0}{1}={2}'.format(removeNamespace(xml.tag), formattedAttributes(myAttribs), formattedValue(myVal)))
    else:
        for child in children:
            inDups = False
            if removeNamespace(child.tag) in dupTags:
                inDups = True
            sl = recursiveFlatten(child, inDups, depth+1)
            if inDups == False:
                for l in sl:
                    subleaves.append(l)
            else:
                subleaves.append(formattedAttributes(sl))
        if len(subleaves) == 0:
            leaves.append('{0}{1}'.format(prefix, formattedAttributes(myAttribs)))
        else:
            for leaf in subleaves: #prepend my prefix
                leaves.append('{0}{1}{2}'.format(prefix, formattedAttributes(myAttribs), leaf))
    return leaves

def compareXML(configName, model, actual):
    flatModel = recursiveFlatten(model)
    flatActual  = recursiveFlatten(actual)
    for entry in flatModel:
        if entry in flatActual:
            configCheck.labels(configName, '{0}'.format(entry)).set(1)
        else:
            configCheck.labels(configName, '{0}'.format(entry)).set(0)
    return

userID = None
osMetrics = {}

def compareOS(configName, spec):
    for checkItem in spec['OS_Values']:
        print('\tChecking: {0}'.format(checkItem))
        actualValue = re.search(str(checkItem['regex']), subprocess.run(checkItem['command'], stdout=subprocess.PIPE).stdout.decode('utf-8'))
        if actualValue is None:
            configCheck.labels(configName, '{0}'.format(checkItem['name'])).set(0)
        else:
            configCheck.labels(configName, '{0}'.format(checkItem['name'])).set(1)
    return

def updateConfigReport():
    for model in [file for file in glob.glob('./*.model')]:
        print('\tChecking [{0}]'.format(model))
        type, target, spec = readModel(model)
        if type == 'XML': compareXML(target, spec, etree.XML(open(target, "r").read()))
        if type == 'OS': compareOS(target, spec)
        else: print('{0} is invalid.'.format(model))

@app.route('/metrics', methods=['GET'])
def metrics():
    updateConfigReport()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, 'u:')
    for opt in opts:
        if opt[0] == '-u': userID = opt[1]

    print('OS UID: {0}'.format(userID))
    app.run(debug=True, host='0.0.0.0', port=PORT)

