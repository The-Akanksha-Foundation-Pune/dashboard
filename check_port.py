import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    port = 5000
    if is_port_in_use(port):
        print(f"Port {port} is in use.")
    else:
        print(f"Port {port} is available.")
