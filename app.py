'''
@Author: BoYanZh
@Date: 2020-05-12 11:29:02
LastEditors: BoYanZh
LastEditTime: 2020-08-08 21:34:38
'''
# -*- coding: utf-8 -*-
from flask import Flask, Response, request, send_from_directory, jsonify, escape, redirect, session, abort
from functools import wraps
from threading import Thread
import subprocess
import glob
import os
import re as regex
import time
import random
import json
import logging
import datetime
import shutil
from argparse import ArgumentParser
logging.basicConfig(
    handlers=[logging.FileHandler("differ.log"),
              logging.StreamHandler()],
    format=
    '%(asctime)s %(levelname)-8s: %(filename)s %(funcName)s %(lineno)s %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=logging.DEBUG)

root = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = 'dijkstrawillnotdie'

STATUS = dict()


def getStatus(problemName):
    if STATUS.get(problemName) is None:
        STATUS[problemName] = {
            "testSize": 1000,
            "caseCount": 0,
            "time": 0,
            "isRunning": False,
            "errorRe": '',
            "lastRun": 'Unknown'
        }
    return STATUS[problemName]


def now():
    return time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(time.time()))


def logSubprocess(commands, **kwargs):
    logCommand = "$ "
    if isinstance(commands, list):
        logCommand += ' '.join(commands)
    else:
        logCommand += str(commands)
    logging.debug(logCommand)
    try:
        outBytes = subprocess.check_output(commands, **kwargs)
        code = 0
    except subprocess.CalledProcessError as e:
        outBytes = e.output
        code = e.returncode
        logging.debug('CalledProcessError')
    except subprocess.TimeoutExpired as e:
        outBytes = e.output
        code = -1
        logging.debug('TimeoutExpired')
    outText = outBytes.decode('utf-8')
    return code, outText


def getFolderHtml(problemName, fileType):
    templateWLink = """<li><code><a href="/problems/{problemName}/{fileType}/{file_}">{file_}</a><span style="float: right">{ctime}</span></code></li>"""
    templateWOLink = """<li><code>{file_}<span style="float: right">{ctime}</span></code></li>"""
    files = glob.glob(f"./problems/{problemName}/{fileType}/*")
    files = [f for f in files if os.path.isfile(f)]
    files = list(filter(lambda n: not n.endswith(".html"), files))
    if fileType == "generators":
        files = list(filter(lambda n: not n.endswith(".exe"), files))
    ctimes = [os.path.getctime(fn) for fn in files]
    files = [file_.split("\\")[-1].split("/")[-1] for file_ in files]
    files = zip(files, ctimes)
    files = sorted(files, key=lambda item: item[1])
    files = [(f, time.strftime("%m-%d %H:%M", time.localtime(ctime)))
             for (f, ctime) in files]
    re = f"<h3>{fileType.capitalize()}</h3>"
    re += "<ol>"
    for file_, ctime in files:
        if fileType != "solvers":
            template = templateWLink
        else:
            template = templateWOLink
        re += template.format_map(vars())
    re += "</ol>"
    return re


def compileGCC(fileDir, fileName, companyFiles):
    prefix = fileName.split(".")[-1]
    filePath = f"{fileDir}{fileName}"
    commands = [
        'g++', filePath, *[f"{fileDir}{fn}" for fn in companyFiles], '-o',
        f"{filePath[:-len(prefix)-1]}.exe", '-Wall', '-pedantic', '-O2',
        '-std=c++17'
    ]
    code, outText = logSubprocess(commands, stderr=subprocess.STDOUT)
    return code, outText, ' '.join(commands)


def getProblemHtml(problemName):
    testSize = getStatus(problemName)['testSize']
    generatorTemplate = """
    <h3>Submit New {capFileType}</h3>
    <form action="?type={fileType}" method="post">
    <p>File Name: <input type="text" name="filename" placeholder="xxx.cpp" /></p>
    <p>Compile With: <input type="text" name="companyfiles" placeholder="xxxTester.cpp yyy.cpp" /></p>
    <p>Code: <br><textarea type="text" name="code" rows="10" cols="30"></textarea></p>
    <p><input type="checkbox" name="static" id="static{fileType}" value="static">
    <label for="static{fileType}"> static file</label></p>
    <input type="submit" value="Submit" />
    </form>
    """
    staticsTemplate = """
    <h3>Submit New {capFileType}</h3>
    <form action="?type={fileType}" method="post" enctype="multipart/form-data">
    <p>Zip: <input type="file" id="zipfilestatic" name="zipfilestatic"  accept=".zip" /></p>
    <input type="submit" value="Submit" />
    </form>
    """
    solverTemplate = """
    <h3>Submit New {capFileType}</h3>
    <form action="?type={fileType}" method="post" enctype="multipart/form-data">
    <p>Solver Name: <input type="text" name="filename" {solverAttr}/></p>
    <p>Zip: <input type="file" id="zipfilesolver" name="zipfilesolver" accept=".zip" /></p>
    <input type="submit" value="Submit" />
    </form>
    """
    solverAttr = f'value="{session.get("solverName")}"' if session.get(
        "solverName") else ""
    status = getStatus(problemName)
    re = f'<title>{problemName}</title>'
    re += '<div style="width: 90%;margin: 0px 5%;padding: 0;position: relative">'
    re += '<a href="/problems">< Problems</a>'
    re += """<h1 style="text-align:center">{problemName}</h1>""".format(
        problemName=escape(problemName))
    re += """<h2 style="text-align:center" id="status">Finished - NaN/NaN - 0s</h2>"""
    re += '<div id="run" style="text-align:center"><br>'
    re += f'<form action="/problems/{problemName}/run" method="post">'
    re += f'<h2><label for="withval">Run With Valgrind</label><input type="checkbox" id="withval" name="withval" value="withval"><br>Test Size: <input type="text" name="size" size="4" value="{testSize}" />&nbsp;<input type="submit" style="font-size : 20px;" value="Run"></h2>'
    re += '</form>'
    re += '</div>'
    re += '<div id="stop" style="text-align:center; display:none">'
    re += f'<form action="/problems/{problemName}/stop" method="post">'
    re += f'<input type="submit" style="font-size : 24px;" value="Stop">'
    re += '</form>'
    re += '</div>'
    re += '<hr>'
    # Generators
    re += '<div style="float: left;width: 20%;margin:0px 5%">'
    re += getFolderHtml(problemName, "generators")
    re += "<hr>"
    re += generatorTemplate.format(capFileType="Generators",
                                   fileType="generators")
    re += '<p>First line of stdout treated as arguments.</p>'
    re += '</div>'
    # Statics
    re += '<div style="float: right;width: 20%;margin:0px 5%">'
    re += getFolderHtml(problemName, "statics")
    re += "<hr>"
    re += staticsTemplate.format(capFileType="Statics", fileType="statics")
    re += '</div>'
    # Solvers
    re += '<div style="float: right;width: 30%;margin:0px 5%">'
    re += getFolderHtml(problemName, "solvers")
    re += "<hr>"
    re += solverTemplate.format(capFileType="Solvers",
                                fileType="solvers",
                                solverAttr=solverAttr)
    re += '</div>'
    re += '</div>'
    re += '<div style="clear:both">'
    re += '<div style="width: 90%;margin: 0px 5%;padding: 0;position: relative">'
    re += f'<h1 style="text-align:center">Result - {status["lastRun"]}</h1><hr>'
    re += f'<div>'
    re += f'<code id="result"></pre>'
    re += '</div>'
    re += '<hr>'
    re += f'<pre>{status["errorRe"]}</pre>'
    re += '</div>'
    re += '</div>'
    re += '<script src="https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js"></script>'
    re += '<script>'
    re += 'var lastSwitch = false;'
    re += 'function refreshPage(forced){'
    re += '$.ajax({url: "/problems/' + problemName + '/running", success: function(result){if(result === "1" || forced || !lastSwitch){'
    re += '$.ajax({url: "/problems/' + problemName + '/result", success: function(result){$("#result").html(result);}});'
    re += '$.ajax({url: "/problems/' + problemName + '/status", success: function(result){$("#status").html(result);}});'
    re += '}'
    re += 'if(result === "0"){lastSwitch = true;clearInterval(timer);}'
    re += 'if(result === "1"){$("#run").css("display","none");$("#stop").css("display","");}else{$("#run").css("display","");$("#stop").css("display","none");}'
    re += '}});'
    re += '}'
    re += 'refreshPage(true);var timer = setInterval(refreshPage, 10000);'
    re += '</script>'
    return re


def auth(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if session.get("user") == 'he2reisyourreward':
            ret = func(*args, **kwargs)
            return ret
        else:
            return redirect("/login")

    return inner


@app.route('/problems/<problemName>/running')
@auth
def getProblemRunning(problemName):
    return "1" if isProblemRunning(problemName) else "0"


@app.route('/problems/<problemName>/result')
@auth
def getProblemResult(problemName):
    return send_from_directory(
        root,
        filename=f"./problems/{problemName}/re.html",
        mimetype='text/plain; charset=utf-8')


@app.route('/problems/<problemName>/status')
@auth
def getProblemStatus(problemName):
    status = getStatus(problemName)
    if not isProblemRunning(problemName):
        testSize = status['testSize']
        caseCount = status['caseCount']
        elapsedTime = status['time']
        mySize = testSize
        myCaseCount = caseCount
        if elapsedTime == 0:
            mySize = "NaN"
            myCaseCount = "NaN"
        runningStatus = f'Finished - {myCaseCount}/{mySize} - {elapsedTime}s'
    else:
        testSize = status['testSize']
        caseCount = status['caseCount']
        elapsedTime = status['time']
        runningStatus = f"Running - {caseCount}/{testSize} - {elapsedTime}s"
    return runningStatus


@app.route('/problems')
@auth
def getProblems():
    def sort_human(l):
        convert = lambda text: float(text) if text.isdigit() else text
        alphanum = lambda key: [
            convert(c) for c in regex.split('([-+]?[0-9]*\.?[0-9]*)', key)
        ]
        l.sort(key=alphanum)
        return l
    if not os.path.exists("./problems"):
        os.mkdir("./problems")
    dirs = next(os.walk("./problems"))[1]
    dirs = sort_human(dirs)
    template = """<li><a style="float: left;display:block;clear:both;" href="/problems/{folder}">{folder}</a> {status}<span style="float: right;display:block;">{count} solver(s)</span></li>"""
    re = '<title>Problems</title>'
    re += '<div style="width: 90%;margin: 0px 5%;padding: 0;position: relative"><br>'
    if session.get('solverName'):
        re += f'<h1 style="text-align: center">Welcome, {session.get("solverName")}</h1><hr>'
    else:
        re += f'<h1 style="text-align: center">Welcome</h1><hr>'
    re += '<h2 style="text-align: center">Problems</h2>'
    re += '<ol style="text-align: center width: 20%;margin: 0px 40%;padding: 0;position: relative">'
    for problemName in dirs:
        solverDir = f"./problems/{problemName}/solvers/"
        solverCount = len(glob.glob(f"{solverDir}*.exe"))
        status = '*' if isProblemRunning(problemName) else ''
        re += template.format(folder=problemName,
                              count=solverCount,
                              status=status)
    re += "</ol><br>"
    re += "<hr>"
    re += '<h2 style="text-align: center">Msg Board</h2>'
    if os.path.exists("./msg.html"):
        re += open('msg.html').read()
    re += '</div>'

    return re


@app.route('/problems/<problemName>', methods=['GET', 'POST'])
@auth
def getProblem(problemName):
    if request.method == 'POST':
        fileType = request.args['type']
        if fileType == "generators":
            fileName = request.form['filename']
            companyFiles = request.form['companyfiles'].split()
            isStatic = request.form.get('static') is not None
            code = request.form['code'].replace('\r\n', '\n')
            fileDir = f"./problems/{problemName}/{fileType}/"
            filePath = f"{fileDir}{fileName}"
            try:
                if not code:
                    os.remove(filePath)
                    result = f"Remove result:<br>Succeed. {now()}"
                else:
                    with open(filePath, "w") as f:
                        f.write(code)
                    if isStatic:
                        result = f"Upload result:<br>Succeed. {now()}"
                    else:
                        code, outText, command = compileGCC(
                            fileDir, fileName, companyFiles)
                        if code != 0:
                            os.remove(filePath)
                        compileResult = "Succeed" if code == 0 else "Failed"
                        result = f"Compile result:<br>{compileResult}. {now()}<br>{command}<br>Compile with return {code}, with following message:<br><pre>{outText}</pre>"
            except Exception as e:
                logging.error(e)
                result = 'Failed'
        elif fileType == "statics":
            zipFile = request.files['zipfilestatic']
            filePath = f"./problems/{problemName}/{fileType}/"
            try:
                zipFile.save("/tmp/tmpstatic.zip")
                shutil.unpack_archive("/tmp/tmpstatic.zip", filePath)
                result = f"Upload result:<br>Succeed. {now()}"
            except Exception as e:
                logging.error(e)
                result = 'Failed'
        elif fileType == "solvers":
            if isProblemRunning(problemName):
                return 'Failed. The problem is running.'
            fileName = request.form['filename']
            zipFile = request.files['zipfilesolver']
            filePath = f"./problems/{problemName}/{fileType}/"
            if not os.path.exists(
                    f"./problems/{problemName}/statics/Makefile"):
                result = "Compile result: Failed. Makefile not found in statics"
            else:
                try:
                    if os.path.exists("/tmp/solver"):
                        shutil.rmtree("/tmp/solver")
                    os.mkdir("/tmp/solver")
                    zipFile.save("/tmp/solver/solver.zip")
                    shutil.unpack_archive("/tmp/solver/solver.zip",
                                          "/tmp/solver")
                    command = ' && '.join([
                        f"cp ./problems/{problemName}/statics/* /tmp/solver",
                        'cd /tmp/solver', 'make',
                        f"cp /tmp/solver/a.out {root}/problems/{problemName}/solvers/{fileName}.exe"
                    ])
                    code, outText = logSubprocess(command,
                                                  shell=True,
                                                  stderr=subprocess.STDOUT)
                    compileResult = "Succeed" if code == 0 else "Failed"
                    result = f"Compile result:<br>{compileResult}. {now()}<br>Compile with return {code}, with following message:<br><pre>{outText}</pre>"
                    if os.path.exists("/tmp/solver"):
                        shutil.rmtree("/tmp/solver")
                except Exception as e:
                    logging.error(e)
                    result = 'Failed'
        return f'<a href="/problems/{problemName}">< Back</a><br>' + result
    else:
        if not os.path.isdir(f"./problems/{problemName}"):
            os.makedirs(f"./problems/{problemName}/generators/data")
            os.makedirs(f"./problems/{problemName}/solvers/data")
            os.makedirs(f"./problems/{problemName}/statics")
            getStatus(problemName)
        return getProblemHtml(problemName)


def runProblem(problemName, testSize, withVal):
    startTime = time.time()
    status = getStatus(problemName)
    status['testSize'] = testSize
    status['time'] = 0
    status['caseCount'] = 0
    status['isRunning'] = True
    status['lastRun'] = now()
    status['errorRe'] = ''
    errorRe = []
    # Generators
    generatorDir = f"./problems/{problemName}/generators/"
    generatorFileNames = [
        file_.split("\\")[-1].split("/")[-1][:-4]
        for file_ in glob.glob(f"{generatorDir}*.exe")
    ]
    # Solvers
    solverDir = f"./problems/{problemName}/solvers/"
    solverFileNames = [
        file_.split("\\")[-1].split("/")[-1][:-4]
        for file_ in glob.glob(f"{solverDir}*.exe")
    ]
    # Result
    resultFilePath = f"./problems/{problemName}/re.html"
    resultFile = open(resultFilePath, "w")
    if withVal:
        resultFile.write("Run with Valgrind.<hr>")
    else:
        resultFile.write("Run without Valgrind.<hr>")
    inputFiles = []
    caseCount = 0
    if os.path.exists(f"{generatorDir}data"):
        shutil.rmtree(f"{generatorDir}data")
    os.mkdir(f"{generatorDir}data")
    if os.path.exists(f"{solverDir}data"):
        shutil.rmtree(f"{solverDir}data")
    os.mkdir(f"{solverDir}data")
    lastCaseStatus = ''
    for fn in generatorFileNames:
        for i in range(testSize // len(generatorFileNames) + 1):
            argFilePath = f"{generatorDir}data/{fn}.{i}.arg"
            stdinFilePath = f"{generatorDir}data/{fn}.{i}.in"
            generatorFilePath = f"{generatorDir}{fn}.exe"
            command = f'{generatorFilePath} {i} > {stdinFilePath}'
            code, outText = logSubprocess(command,
                                          shell=True,
                                          stderr=subprocess.STDOUT)
            if code != 0:
                errorRe.append('error: ' + command + ' => ' + outText)
                continue
            command = f"""awk 'NR<2' {stdinFilePath} > {argFilePath} && echo "$(tail -n +2 {stdinFilePath})" > {stdinFilePath}"""
            code, outText = logSubprocess(command,
                                          shell=True,
                                          stderr=subprocess.STDOUT)
            stdoutFiles = []
            returnCodes = []
            for solverFileName in solverFileNames:
                args = open(argFilePath).readline().replace(
                    '{PATH}', stdinFilePath).split()
                stdoutFilePath = f"{solverDir}data/{solverFileName}.{fn}.{i}.out"
                stderrFilePath = f"{solverDir}data/{solverFileName}.{fn}.{i}.err"
                returnCodeFilePath = f"{solverDir}data/{solverFileName}.{fn}.{i}.ret"
                stdoutFiles.append(stdoutFilePath)
                if withVal:
                    commands = [
                        "valgrind", "--leak-check=full", "--error-exitcode=1",
                        "-q", f"{solverDir}{solverFileName}.exe", *args, ">",
                        f"{stdoutFilePath}", "<", f"{stdinFilePath}"
                    ]
                else:
                    commands = [
                        f"{solverDir}{solverFileName}.exe", *args, ">",
                        f"{stdoutFilePath}", "<", f"{stdinFilePath}"
                    ]
                command = ' '.join(commands)
                code, outText = logSubprocess(command,
                                              shell=True,
                                              timeout=10,
                                              stderr=subprocess.STDOUT)
                open(returnCodeFilePath, mode='w').write(str(code))
                returnCodes.append(code)
                if code != 0:
                    open(stderrFilePath, mode='w').write(outText)
            parent = list(range(len(solverFileNames)))

            def find(parent, n):
                return n if (n == parent[n]) else find(parent, parent[n])

            def same(parent, a, b):
                return find(parent, a) == find(parent, b)

            for j in range(len(stdoutFiles)):
                for k in range(j + 1, len(stdoutFiles)):
                    if same(parent, j, k):
                        continue
                    if returnCodes[j] == 0 and returnCodes[k] == 0:
                        command = ' '.join([
                            'git', '--no-pager', 'diff', '--quiet',
                            '--ignore-space-at-eol', f"{stdoutFiles[j]}",
                            f"{stdoutFiles[k]}"
                        ])
                        code, outText = logSubprocess(command, shell=True)
                        if code == 0:
                            parent[find(parent, j)] = find(parent, k)
            reDict = {}
            for index, num in enumerate(parent):
                for key, value in reDict.items():
                    if same(parent, key, index):
                        value.append(index)
                        break
                else:
                    reDict[num] = [index]
            tmpRe = []
            if len(reDict.keys()) == 1:
                currentCaseStatus = 'passed'
                currentHtml = f'<span style="color: blue">{fn}.{i}</span>'
            else:
                currentCaseStatus = 'failed'
                currentHtml = f'<a href="/problems/{problemName}/generators/data/{fn}.{i}">{fn}.{i}</a>'
            if currentCaseStatus == 'passed':
                for solverFileName in solverFileNames:
                    stdoutFilePath = f"{solverDir}data/{solverFileName}.{fn}.{i}.out"
                    returnCodeFilePath = f"{solverDir}data/{solverFileName}.{fn}.{i}.ret"
                    os.remove(stdoutFilePath)
                    os.remove(returnCodeFilePath)
                os.remove(stdinFilePath)
                os.remove(argFilePath)
            if lastCaseStatus == '':
                tmpRe.append(f'case {currentHtml}')
            elif lastCaseStatus == 'passed' and currentCaseStatus == 'failed':
                tmpRe.append(f' passed!<hr>case {currentHtml}')
            elif lastCaseStatus == 'passed' and currentCaseStatus == 'passed':
                tmpRe.append(f', case {currentHtml}')
            else:
                tmpRe.append(f'<hr>case {currentHtml}')
            if currentCaseStatus == 'failed':
                tmpRe.append(' failed! ')
                for value in reDict.values():
                    if len(value) == 1:
                        idx = value[0]
                        if returnCodes[idx] == 0:
                            tmpRe.append(
                                f'<a href="/problems/{problemName}/solvers/data/{solverFileNames[idx]}.{fn}.{i}">{solverFileNames[idx]}</a> '
                            )
                        else:
                            tmpRe.append(
                                f'<a style="color: red" href="/problems/{problemName}/solvers/data/{solverFileNames[idx]}.{fn}.{i}">{solverFileNames[idx]}</a> '
                            )
                    else:
                        for idx in value[:-1]:
                            tmpRe.append(
                                f'<a href="/problems/{problemName}/solvers/data/{solverFileNames[idx]}.{fn}.{i}">{solverFileNames[idx]}</a> == '
                            )
                        idx = value[-1]
                        tmpRe.append(
                            f'<a href="/problems/{problemName}/solvers/data/{solverFileNames[idx]}.{fn}.{i}">{solverFileNames[idx]}</a> '
                        )
                    tmpRe.append(", ")
                tmpRe.pop()
            lastCaseStatus = currentCaseStatus
            resultFile.write(''.join(tmpRe))
            resultFile.flush()
            caseCount += 1
            status['caseCount'] = caseCount
            status['time'] = round(time.time() - startTime, 2)
            status['errorRe'] = '<br>\n'.join(errorRe)
            if caseCount >= testSize or not status['isRunning']:
                if lastCaseStatus == "passed":
                    resultFile.write(f' passed!<br>')
                break
        if caseCount >= testSize or not status['isRunning']:
            break
    status['isRunning'] = False
    resultFile.close()


def isProblemRunning(problemName):
    return getStatus(problemName)['isRunning']


@app.route('/problems/<problemName>/run', methods=['POST'])
@auth
def runProblemPage(problemName):
    testSize = request.form.get('size', '200')
    if testSize.isdigit():
        testSize = int(testSize)
    if testSize == 0:
        testSize = 1
    withVal = request.form.get('withval') is not None
    if not isProblemRunning(problemName):
        Thread(target=runProblem,
               args=(problemName, testSize, withVal)).start()
    return redirect(f'/problems/{problemName}')


@app.route('/problems/<problemName>/stop', methods=['POST'])
@auth
def stopProblemPage(problemName):
    if isProblemRunning(problemName):
        getStatus(problemName)['isRunning'] = False
    return redirect(f'/problems/{problemName}')


@app.route('/problems/<problemName>/remove')
@auth
def removeProblem(problemName):
    if os.path.exists(f"./problems/{escape(problemName)}"):
        shutil.rmtree(f"./problems/{escape(problemName)}")
    return redirect(f'/problems')


@app.route('/login/letmelogin')
def getSession():
    session["user"] = 'he2reisyourreward'
    return redirect(f'/problems')


@app.route('/login/letmelogin/<solverName>')
def getSolverName(solverName):
    session["user"] = 'he2reisyourreward'
    session["solverName"] = solverName
    return f'<a href="/problems">< Back</a><br><h1 style="text-align: center">Welcome, {session.get("solverName")}</h1>'


@app.route('/login')
def getRoot():
    return "<h1>Try to Login?</h1>"


@app.route('/')
def hello():
    return "<h1>Hello!</h1>"


@app.route('/problems/<problemName>/statics/<fileName>')
@auth
def getStatics(problemName, fileName):
    fileName = escape(fileName)
    return send_from_directory(
        root,
        filename=f"./problems/{problemName}/statics/{fileName}",
        mimetype='text/plain; charset=utf-8')


@app.route('/problems/<problemName>/generators/<fileName>')
@auth
def getGenerator(problemName, fileName):
    fileName = escape(fileName)
    return send_from_directory(
        root,
        filename=f"./problems/{problemName}/generators/{fileName}",
        mimetype='text/plain; charset=utf-8')


@app.route('/problems/<problemName>/generators/data/<fileName>')
@auth
def getGeneratorData(problemName, fileName):
    fileName = escape(fileName)
    re = "<h3>arg</h3><hr><pre>"
    if not os.path.exists(
            f"./problems/{problemName}/generators/data/{fileName}.arg"):
        abort(404)
    re += open(
        f"./problems/{problemName}/generators/data/{fileName}.arg").read()
    if not os.path.exists(
            f"./problems/{problemName}/generators/data/{fileName}.in"):
        abort(404)
    re += "</pre><h3>stdin</h3><hr><pre>"
    re += open(
        f"./problems/{problemName}/generators/data/{fileName}.in").read()
    re += "</re>"
    return re


@app.route('/problems/<problemName>/solvers/data/<fileName>')
@auth
def getSolverData(problemName, fileName):
    fileName = escape(fileName)
    re = "<h3>return code</h3><hr><pre>"
    if not os.path.exists(
            f"./problems/{problemName}/solvers/data/{fileName}.ret"):
        abort(404)
    re += open(f"./problems/{problemName}/solvers/data/{fileName}.ret").read()
    if not os.path.exists(
            f"./problems/{problemName}/solvers/data/{fileName}.out"):
        abort(404)
    if os.path.exists(f"./problems/{problemName}/solvers/data/{fileName}.err"):
        re += "</pre><h3>stderr</h3><hr><pre>"
        re += open(
            f"./problems/{problemName}/solvers/data/{fileName}.err").read()
        re += "</pre>"
    re += "</pre><h3>stdout</h3><hr><pre>"
    re += open(f"./problems/{problemName}/solvers/data/{fileName}.out").read()
    re += "</pre>"
    return re


@app.route('/index.py')
@auth
def getIndexPy():
    return send_from_directory(root,
                               filename=f"./index.py",
                               mimetype='text/plain; charset=utf-8')


@app.after_request
def add_header(response):
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p',)
    args = parser.parse_args()
    val = args.a
    app.run(host='0.0.0.0', port=2121, threaded=True)
