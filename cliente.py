import socket

import protocolo
from dados import data_valida

TIMEOUT_DE_CONEXAO = 10


class Cliente:
    def __init__(self, endereco, porta):
        socket_tcp = socket.create_connection((endereco, porta), timeout=TIMEOUT_DE_CONEXAO)
        socket_tcp.settimeout(None)
        self.conexao = protocolo.Conexao(socket_tcp)
        self.token = None
        self.usuario = None

    # monta a requisicao, manda e espera a resposta
    def enviar(self, comando, corpo=None):
        self.conexao.enviar(protocolo.montar_requisicao(comando, corpo, self.token))
        resposta = self.conexao.receber_resposta()
        if resposta is None:
            raise ConnectionError("o servidor fechou a conexao")
        return resposta

    # faz login e guarda o token 
    def entrar(self, usuario, senha):
        resposta = self.enviar(protocolo.AUTENTICAR, {"usuario": usuario, "senha": senha})
        if resposta.deu_certo():
            self.token = resposta.corpo["token"]
            self.usuario = usuario
        return resposta

    def fechar(self):
        self.conexao.fechar()


def pedir_login(cliente):
    while True:
        usuario = input("Usuario: ").strip()
        senha = input("Senha: ").strip()
        resposta = cliente.entrar(usuario, senha)
        if resposta.deu_certo():
            print(f"Bem-vindo, {usuario}.")
            return True
        print("Nao deu certo:", resposta.corpo.get("erro"))
        if input("Tentar de novo? (s/n) ").strip().lower() != "s":
            return False


def mostrar_menu(titulo, opcoes):
    print(f"\n--- {titulo} ---")
    for numero, (rotulo, _funcao) in opcoes.items():
        print(f"{numero}) {rotulo}")
    print("0) Sair")

    escolha = input("Opcao: ").strip()
    if escolha == "0":
        return None
    if escolha not in opcoes:
        print("Opcao invalida.")
        return mostrar_menu(titulo, opcoes)
    return opcoes[escolha][1]


# Usa while ate a data ser valida e no formato cortreto
def pedir_data(pergunta="Data (DD/MM/AAAA): "):
    while True:
        digitado = input(pergunta).strip()
        if data_valida(digitado):
            return digitado
        print("Data invalida. Use DD/MM/AAAA, por exemplo 25/12/2026.")
