
import socket

def ip_na_rede_local():
    tentativa = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        tentativa.connect(("8.8.8.8", 80))
        return tentativa.getsockname()[0]
    except OSError:
        return None
    finally:
        tentativa.close()


if __name__ == "__main__":
    endereco = ip_na_rede_local()

    if endereco is None:
        print("Nao consegui descobrir o IP. Use 'ip addr' ou 'ipconfig'.")
    else:
        print(f"IP desta maquina: {endereco}")
