import sys
import os
import glob
import paramiko

four_nine_host = "10.1.18.76"
four_eight_host = "10.1.19.166"
port = 22
username = "root"
password = "phantom"

four_nine_client = paramiko.SSHClient()
four_nine_client.load_system_host_keys()
#four_nine_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
four_nine_client.connect(hostname=four_nine_host, username=username, password=password)

four_eight_client = paramiko.SSHClient()
four_eight_client.load_system_host_keys()
#four_eight_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
four_eight_client.connect(hostname=four_eight_host, username=username, password=password)

app_name = ""


def run_four_nine_test():
    print("running 4.9 test")
    #commands = "cd /mnt/" + app_name + "; phenv python /opt/phantom/bin/compile_app.pyc -id; pwd"
    commands = "cd /mnt/" + app_name + "; phenv python2.7 /opt/phantom/bin/py2/compile_app.pyc -id; pwd"

    stdin, stdout, stderr = four_nine_client.exec_command(commands)

    lines = stdout.readlines()
    print("4.9 output: ")

    for line in lines:
        print(line)

def run_four_eight_test():
    print("running 4.8 test")
    #commands = "cd /mnt/" + app_name + "; phenv python /opt/phantom/bin/compile_app.pyc -id; pwd"
    commands = "cd /mnt/" + app_name + "; phenv python2.7 /opt/phantom/bin/compile_app.pyc -id; pwd"

    stdin, stdout, stderr = four_eight_client.exec_command(commands)

    lines = stdout.readlines()
    print("4.8 output: ")

    for line in lines:
        print(line)


def makeFolder():
    print("no app folder found, creating folder for " + app_name)
    commands = "cd /mnt; mkdir " + app_name
    four_nine_client.exec_command(commands)
    four_eight_client.exec_command(commands)


def install_four_eight(locFilePath):
    print("installing on 4.8")
    app_files = glob.glob(locFilePath + "/*")

    for file in app_files:
        try:
            ftp_client = four_eight_client.open_sftp()
            ftp_client.put(file, '/mnt/' + file[3:])
            ftp_client.close()
        except IOError as e:
            print("Error, this is what happened", str(e))


def install_four_nine(locFilePath):
    print("installing on 4.9")
    app_files = glob.glob(locFilePath + "/*")
    for file in app_files:
        try:
            ftp_client = four_nine_client.open_sftp()
            ftp_client.put(file, '/mnt/' + file[3:])
            ftp_client.close()
        except IOError as e:
            print("Error, this is what happened", str(e))


def install_app( newApp = True ):
    locFilePath = "../" + app_name

    if newApp:
        makeFolder()

    print(locFilePath)
    install_four_nine(locFilePath)
    install_four_eight(locFilePath)



if __name__ == '__main__':
    args = sys.argv
    app_name = args[1]

    print(args)
    install_app()
    run_four_nine_test()
    run_four_eight_test()