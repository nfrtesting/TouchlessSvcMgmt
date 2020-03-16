from flask import Flask, Response, request
from prometheus_client import generate_latest, Gauge, Histogram, Counter, Summary, CONTENT_TYPE_LATEST
from prometheus_flask_exporter import PrometheusMetrics
from jenkins import Jenkins as JenkinsServer
import requests, jenkins, os, time, sys, json, requests
VERSION="0.0.3"
app = Flask(__name__)
m = PrometheusMetrics(app=app)
if False:
    #========================================================================================
    #========================================================================================
    def JenkinsBuild(token, plan, label):
        #app.logger.debug('Jenkins build using [%s] with testplan [%s]', token, plan)
        jobid = -1
        JS_URL = app.config["JENKINS_URL"]
        app.logger.debug('Connecting to Jenkins %s as %s', JS_URL, app.config["UID"])
        js = JenkinsServer(JS_URL, username=app.config["UID"], password=app.config["PWD"])
        app.logger.debug('Connected')
        app.logger.info('Hello from Jenkins %s', js.get_version())
        p = {'TEST_LABEL': label,
             'TEST_PLAN': plan}
        jobid = js.build_job(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"], parameters=p)
        return jobid
    #========================================================================================
    #========================================================================================
    def addJob():
        startingUp = True
        JS_URL = app.config["JENKINS_URL"]
        while startingUp:
            try:
                app.logger.debug('Connecting to Jenkins %s as %s', JS_URL, app.config["UID"])
                js = JenkinsServer(JS_URL, username=app.config["UID"], password=app.config["PWD"])
                if (js.wait_for_normal_op(30)):
                    app.logger.debug('Connected')
                    app.logger.info('Hello from Jenkins %s', js.get_version())
                    startingUp = False
            except:
                app.logger.debug('%s caught during Jenkins connect', sys.exc_info()[0])
                app.logger.debug('Waiting for startup, sleeping')
                time.sleep(5)
        try:
            app.logger.debug('Creating folder %s', app.config["FOLDER_NAME"])
            js.create_job(app.config["FOLDER_NAME"], jenkins.EMPTY_FOLDER_XML)
        except:
            app.logger.debug('%s caught during folder create.', sys.exc_info()[0])
            pass
        if app.config["GIT_UID"] != "":
            cj = credentialXML()
            try:
                app.logger.debug('Credential check.')
                try:
                    app.logger.debug('Prophylactic delete of credential.')
                    js.delete_credential(app.config["GIT_UID"], app.config["FOLDER_NAME"])
                except:
                    pass
                app.logger.debug('Creating credential.')
                js.create_credential(app.config["FOLDER_NAME"], cj)
            except:
                app.logger.debug('%s caught during config', sys.exc_info()[0])
        else:
            app.logger.debug("Anonymous GIT access")
        app.logger.debug('Generating Job XML.')
        nj = jobXML()
        app.logger.debug('Creating job.')
        try:
            app.logger.debug('Does job exist?.')
            if js.job_exists(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"]):
                exists = True
                app.logger.debug('Yep!')
                #app.logger.debug('Reconfiguring job %s using [%s]', app.config["PIPELINE_NAME"], nj)
                js.reconfig_job(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"], nj)
                exists = True
            else:
                app.logger.debug('Nope!')
                #app.logger.debug('Trying to create job %s using [%s].', app.config["PIPELINE_NAME"], nj)
                js.create_job(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"], nj)
                app.logger.debug('Attempting initial build to allow Jenkinsfile based configuration.')
                rid = js.build_job(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"])
                app.logger.debug('Started %d', rid)
            app.logger.debug('Initial build to set parameters (jobid=%d)', JenkinsBuild('', ''))
        except:
            app.logger.debug('%s caught during job config', sys.exc_info()[0])
    #========================================================================================
    #========================================================================================
    def credentialXML():
        ret = ''
        ret += '<com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl plugin="credentials@2.1.18">'
        ret += '<scope>GLOBAL</scope>'
        ret += '<id>' + app.config["GIT_UID"] + '</id>'
        ret += '<description/>'
        ret += '<username>' + app.config["GIT_UID"] + '</username>'
        ret += '<password>' + app.config["GIT_PWD"] + '</password>'
        ret += '</com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>'
        return ret
    #========================================================================================
    @app.route('/runTest', methods=['POST'])
    # Debug method allowing interactive execution of a test.
    #========================================================================================
    def runTest():
        app.logger.debug("Plan contents:")
        request.get_data(parse_form_data=True)
        ct = request.form['cloud_token']
        app.logger.debug('got cloud_token')
        tl = request.form['test_label']
        app.logger.debug('got label')
        tp = request.files['test_plan'].read()
        app.logger.debug('read testplan')
        rid = JenkinsBuild(ct, tp, tl)
        if (rid > 0):
            ret = tl
        else:
            ret = "An Error Has Occurred"
        return ret
    #========================================================================================
    @app.route('/getStatus', methods=['GET'])
    # Debug method allowing interactive query of status
    #========================================================================================
    def getStatus():
        rid = request.args.get("rid")
        JS_URL = app.config["JENKINS_URL"]
        app.logger.debug('Connecting to Jenkins %s as %s', JS_URL, app.config["UID"])
        js = JenkinsServer(JS_URL, username=app.config["UID"], password=app.config["PWD"])
        app.logger.debug('Connected')
        app.logger.info('Hello from Jenkins %s', js.get_version())
        allBuilds = js.get_job_info(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"], fetch_all_builds=True)
        ret = "{"
        for build in allBuilds['builds']:
            bi = js.get_build_info(app.config["FOLDER_NAME"] + '/' + app.config["PIPELINE_NAME"], build['number'])
            if (bi['displayName'] == rid):
                ret += " \"displayName\": \"" + str(bi['displayName']) + "\", "
                ret += " \"buildNumber\": \"" + str(build['number']) + "\", "
                ret += " \"building\": \"" + str(bi['building']) + "\", "
                ret += " \"result\": \"" + str(bi['result']) + "\""
                continue
        ret += "}"
        return ret
    #========================================================================================
    @app.route('/getResult', methods=['GET'])
    # Debug method which returns a file.
    #========================================================================================
    def getResult():
        rid = request.args.get("rid")
        JS_URL = app.config["JUPYTER_URL"]
        resp = requests.get(JS_URL + "/api/contents/" + rid)
        dfile = ""
        for item in resp.json()['content']:
            if item['mimetype'] == 'text/html':
                dfile = item['name']
        dload = requests.get(JS_URL + "/api/contents/" + rid + "/" + dfile)
        pagetitle = '{} - {}'.format(rid, dfile)
        return '<html><title>{}</title><body>{}</body></html>'.format(pagetitle, dload.json()['content'])
    #========================================================================================
    @app.route('/ui', methods=['GET'])
    # A debug method presenting a webform and some links.  The webform allows for interactive
    # tests of functions.
    #========================================================================================
    def ui():
        uiForm = "<HTML><HEADER><TITLE>Test UI</TITLE></HEADER><BODY>"
        uiForm += "Use this UI to test the REST interfaces and submit jobs<hr>"
        uiForm += "<H2>Submit a Test Request</H2><HR><FORM action=\"/runTest\" method=\"POST\" enctype=\"multipart/form-data\">Cloud Token:<input name=\"cloud_token\" \><p>Test Label:<input name=\"test_label\" \><p>TestPlan File:<input type=\"file\" id=\"test_plan\" name=\"test_plan\" acceot=\"text/yaml\"\><p><button name=\"SUBMIT\">Submit</button></FORM>"
        uiForm += "<H2>Status of Test</H2><HR><FORM action=\"/getStatus\">Test Label: <input name=\"rid\" \><button name=\"SUBMIT\">Submit</button></FORM>"
        uiForm += "<H2>Retrieve Test Result</H2><HR><FORM action=\"/getResult\">Test Label: <input name=\"rid\" \><button name=\"SUBMIT\">Submit</button></FORM>"
        uiForm += "</BODY></HTML>"
        return uiForm
#========================================================================================
#========================================================================================
def pushStatusValues(labels):
    url = app.config["PROMETHEUS_PUSH_URL"] + '/metrics/job/readiness_check'
    for l in labels:
        if l != 'severity' and l != 'alertname':
            url = url + '/{0}/{1}'.format(l, labels[l])
    metric = "readiness_test"
    return url, metric
#========================================================================================
# common method to set the metric alert manager uses
#========================================================================================
def setVerifiedStatus(labels, value):
    app.logger.debug('Setting Verified Status to {0}'.format(value))
    url, metric = pushStatusValues(labels)
    response = requests.post(url, data='{0} {1}\n'.format(metric, value))
#    app.logger.debug('\tURL: {0} '.format(url))
#    app.logger.debug('\tResponse: [{0}]: {1}'.format(response.status_code, response.text))
    return
#========================================================================================
# connectJenkins loops, in case Jenkins isn't available yet.
#========================================================================================
def connectJenkins():
    startingUp = True
    js = None
    while startingUp:
        try:
#            app.logger.debug('Connecting to Jenkins %s as %s', app.config["JENKINS_URL"], app.config["UID"])
            js = JenkinsServer(app.config["JENKINS_URL"], username=app.config["UID"], password=app.config["PWD"])
            if (js.wait_for_normal_op(30)):
#                app.logger.debug('Connected')
#                app.logger.info('Hello from Jenkins %s', js.get_version())
                startingUp = False
        except:
            app.logger.debug('%s caught during Jenkins connect', sys.exc_info()[0])
            app.logger.debug('Waiting for startup, sleeping')
            time.sleep(5)
    return js
#========================================================================================
#========================================================================================
def createFolder(js, fn):
    try:
#        app.logger.debug('Creating folder %s', fn)
        js.create_job(fn, jenkins.EMPTY_FOLDER_XML)
    except:
        app.logger.debug('%s caught during folder create.', sys.exc_info()[0])
        pass
    return
# ========================================================================================
# ========================================================================================
def jobXML(jobname):
    ret = ''
    ret += '<?xml version=\'1.1\' encoding=\'UTF-8\'?> '
    ret += '<flow-definition plugin="workflow-job@2.32"> '
    ret += '  <description>' + jobname + '</description> '
    ret += '  <keepDependencies>false</keepDependencies> '
    ret += '  <properties/> '
    ret += '  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps@2.67"> '
    ret += '    <scm class="hudson.plugins.git.GitSCM" plugin="git@3.9.4"> '
    ret += '      <configVersion>2</configVersion> '
    ret += '      <userRemoteConfigs> '
    ret += '        <hudson.plugins.git.UserRemoteConfig> '
    ret += '          <url>' + app.config["GIT_REPO"] + '</url> '
    if app.config["GIT_UID"] != "":
        ret += '          <credentialsId>' + app.config["GIT_UID"] + '</credentialsId> '
    ret += '        </hudson.plugins.git.UserRemoteConfig> '
    ret += '      </userRemoteConfigs> '
    ret += '      <branches> '
    ret += '        <hudson.plugins.git.BranchSpec> '
    ret += '          <name>*/' + app.config["GIT_BRANCH"] + '</name> '
    ret += '        </hudson.plugins.git.BranchSpec> '
    ret += '      </branches> '
    ret += '      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations> '
    ret += '      <submoduleCfg class="list"/> '
    ret += '      <extensions/> '
    ret += '    </scm> '
    ret += '    <scriptPath>Jenkinsfile</scriptPath> '
    ret += '    <lightweight>true</lightweight> '
    ret += '  </definition> '
    ret += '  <triggers/> '
    ret += '  <disabled>false</disabled> '
    ret += '</flow-definition> '
    return ret
#========================================================================================
#========================================================================================
def createJob(js, folder, job):
    if js.job_exists(folder + '/' + job):
        app.logger.debug('Job exists, nothing to see here.')
    else:
        app.logger.debug('Creating Test.')
        js.create_job(folder + '/' + job, jobXML(job))
        app.logger.debug('Attempting initial build to allow Jenkinsfile based configuration.')
        rid = js.build_job(folder + '/' + job)
        app.logger.debug('Started %d, sleeping momentarily', rid)
        time.sleep(5)
    return
#========================================================================================
#========================================================================================
def execJob(js, labels):
#    app.config["PROMETHEUS_PUSH_URL"] = 'http://tsm-prometheus-push:9091'
    url, metric = pushStatusValues(labels)
#    app.config["PROMETHEUS_PUSH_URL"] = 'http://prometheus-push.tsm'
    p = {'RESULT_URL': url,
         'RESULT_METRIC': metric}
    jobid = js.build_job(labels['app'] + '/' + labels['env'], parameters=p)
    return jobid
#========================================================================================
#========================================================================================
def runTest(labels):
    js = connectJenkins()
    createFolder(js, labels['app'])
    createJob(js, labels['app'], labels['env']) #does nothing if job already exists
    rid = execJob(js, labels)
    app.logger.debug('Started RID: {0}'.format(rid))
    #setVerifiedStatus(labels, 1)
    return
#========================================================================================
@app.route('/', methods=['GET'])
# Debug method, presents version information
#========================================================================================
def index():
    config = '<html><header><title>Webhook</title></header>'
    config += '<body><h1 align="center">TSM Robotics [' + VERSION + ']</h1><hr>'
    config += '<H2>Usage Links</H2><HR>'
    config += "<p><a href=\"ui\">Interactive UI</a>"
    config += "<p><a href=\"metrics\">Exposed Prometheus Metrics</a>"
    config += "<H2>Internal Links</H2><HR>"
    config += "<p><a href=\"" + app.config["PROMETHEUS_URL"] + "\">Prometheus</a>"
    config += "<p><a href=\"" + app.config["JENKINS_URL"] + "\">Jenkins</a>"
    config += "<p><a href=\"" + app.config["JUPYTER_URL"] + "\">Jupyter</a>"
    config += "<p><a href=\"" + app.config["JUPYTER_HELPER_URL"] + "\">Jupyter Helper</a>"
    config += '</body></html>'
    return config
#========================================================================================
@app.route('/metrics', methods=['GET'])
# Method called by Prometheus to scrape metrics.
#========================================================================================
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
#========================================================================================
@app.route('/alert/<string:room>', methods=['POST'])
# Alert, something is wrong.  This method is only here for demonstration.  It is where
# you might relay the message to a chatroom or something.  Notice there are "FIRING"
# and "RESOLVED" messages and multiple alerts come in together.
#========================================================================================
def alert(room):
    alertinfo = request.json
    for alert in alertinfo['alerts']:
        json_data = {}
        json_data['to'] = room
        json_data['displayfromname'] = 'AlertManager Bot'
        json_data['from'] = app.config["BOTID"]
        json_data['password'] = app.config["BOTPWD"]
        json_data['type'] = 'meeting'
        if alert['status'] == "firing":
            json_data['html'] = str('<span style="color: #ff0000;">ROBOT WARNING</span>: ' + alert['annotations']['description'])
        else:
            json_data['html'] = str('<span style="color: #008000;">ROBOT RESOLVED:</span> ' + alert['annotations']['description'])
        response = requests.post(app.config["OUTPUT_URL"], data=json.dumps(json_data))
    return "Ok."
#========================================================================================
@app.route('/notify/<string:room>', methods=['POST'])
# Notifying the robot something is ready for a state transition.  This demonstrates
# how an alert path, through a different webhook, can trigger state transition behavior.
# For this demonstration, this message triggers a test to run.
#========================================================================================
def notify(room):
    alertinfo = request.json
    for alert in alertinfo['alerts']:
        json_data = {}
        json_data['to'] = room
        json_data['displayfromname'] = 'AlertManager Bot'
        json_data['from'] = app.config["BOTID"]
        json_data['password'] = app.config["BOTPWD"]
        json_data['type'] = 'meeting'
        if alert['status'] == "firing":
            json_data['html'] = str('<span style="color: #0000ff;">ROBOT NOTIFICATION</span>: ' + alert['annotations']['description'])
            response = requests.post(app.config["OUTPUT_URL"], data=json.dumps(json_data))
    return "Ok."
#========================================================================================
@app.route('/robotics', methods=['POST'])
# Notifying the robot something is ready for a state transition.  This demonstrates
# how an alert path, through a different webhook, can trigger state transition behavior.
# For this demonstration, this message triggers a test to run.
#========================================================================================
def robotics():
    alertinfo = request.json
    for alert in alertinfo['alerts']:
        if alert['status'] == "firing":
            app.logger.debug('({0}, {1}): {2}'.format(alert['labels']['app'], alert['labels']['env'], alert['labels']['severity']))
            if alert['labels']['severity'] == 'not_ready':
                setVerifiedStatus(alert['labels'], -1)
            elif alert['labels']['severity'] == 'ready_to_test':
                runTest(alert['labels'])
            elif alert['labels']['severity'] == 'ready_to_use':
                app.logger.debug('\tSetting READY_TO_USE')
            else:
                app.logger.debug('\tWTF is this?')
    return "Ok."

#========================================================================================
@app.before_first_request
#========================================================================================
def onStartup():
    m.info('webhook_app_info', 'Application Info',
            version=VERSION,
            )
    app.config.update(
        JENKINS_URL='http://tsm-jenkins-web:8080',
        JUPYTER_URL='http://tsm-jupyter-web:8888',
        JUPYTER_HELPER_URL='http://tsm-jupyter-helper:9999',
        PROMETHEUS_URL='http://tsm-prometheus-web:9090',
        PROMETHEUS_PUSH_URL='http://tsm-prometheus-push:9091',
        UID='admin',
        PWD='admin',
        GIT_REPO='https://github.com/wroney688/SimplePipeline',
        GIT_BRANCH='master',
        GIT_UID='',
        GIT_PWD='',
#        FOLDER_NAME='xyx',
#        PIPELINE_NAME='TestingPipeline',
#        OUTPUT_URL='http://alertmonitor.tsm/alert',
        OUTPUT_URL='http://alertmonitor-web:5000',
        BOTID = 'Robotics',
        BOTPWD = 'na'
    )
    app.logger.debug('onStartup')
    #addJob()
#========================================================================================
#========================================================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
