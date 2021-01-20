import subprocess, sys


def run(cmd):
    ## run it ##
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    ## inspired by https://www.cyberciti.biz/faq/python-run-external-command-and-get-output/
    # ## do not wait until p's termination
    # ## start displaying output immediately
    # while True:
    #     line = p.stdout.readline(1)
    #     if line == '' and p.poll() != None:
    #         break
    #     if line != '':
    #         sys.stdout.write(line)
    #         sys.stdout.flush()

    while True:
        line = proc.stdout.readline()
        if not line: break
        print(line.decode('utf-8').rstrip('\r\n'))

    # for line in iter(p.stdout.readline,''):
    #     print(line.rstrip())
