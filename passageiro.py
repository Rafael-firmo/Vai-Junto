import os
import sys

import protocolo
from cliente import Cliente, pedir_login, mostrar_menu, pedir_data

ultima_busca = []


def buscar(cliente):
    global ultima_busca

    origem = input("De onde voce sai: ").strip()
    destino = input("Para onde voce vai: ").strip()
    data = pedir_data()

    resposta = cliente.enviar(protocolo.BUSCAR, {"origem": origem, "destino": destino, "data": data})

    if not resposta.deu_certo():
        print("Erro:", resposta.corpo.get("erro"))
        return

    ultima_busca = resposta.corpo["itinerarios"]
    if not ultima_busca:
        print("Nenhum itinerario encontrado para essa data.")
        return

    for numero, itinerario in enumerate(ultima_busca):
        caminho = " + ".join(
            f"{t['origem']}->{t['destino']}" for t in itinerario["trechos"]
        )
        print(f"  [{numero}] {caminho}"
              f"  R$ {itinerario['preco_total']:.2f}"
              f"  ({itinerario['conexoes']} trecho[s])")


def reservar(cliente):
    if not ultima_busca:
        print("Faca uma busca primeiro.")
        return

    numero = int(input("Numero do itinerario: ").strip())
    if numero < 0 or numero >= len(ultima_busca):
        print("Esse numero nao esta na lista.")
        return

    trechos = [
        {"id_carona": t["id_carona"], "posicao": t["posicao"]}
        for t in ultima_busca[numero]["trechos"]
    ]

    resposta = cliente.enviar(protocolo.RESERVAR, {"trechos": trechos})

    if resposta.deu_certo():
        print(f"Reserva confirmada. Id: {resposta.corpo['id']}"
              f"  Total: R$ {resposta.corpo['preco_total']:.2f}")
    else:
        print("Nao deu:", resposta.corpo.get("erro"))


def listar(cliente):
    resposta = cliente.enviar(protocolo.LISTAR_RESERVAS)
    reservas = resposta.corpo.get("reservas", [])

    if not reservas:
        print("Voce nao tem reservas.")
        return

    for reserva in reservas:
        situacao = "cancelada" if reserva["cancelada"] else "ativa"
        caminho = " + ".join(f"{t['origem']}->{t['destino']}" for t in reserva["trechos"])
        print(f"  [{reserva['id']}] {caminho}  R$ {reserva['preco_total']:.2f}  {situacao}")


def cancelar(cliente):
    id_reserva = input("Id da reserva a cancelar: ").strip()
    resposta = cliente.enviar(protocolo.CANCELAR_RESERVA, {"id_reserva": id_reserva})
    if resposta.deu_certo():
        print("Reserva", resposta.corpo["situacao"])
    else:
        print("Erro:", resposta.corpo.get("erro"))


OPCOES = {
    "1": ("Buscar itinerarios", buscar),
    "2": ("Reservar um itinerario", reservar),
    "3": ("Minhas reservas", listar),
    "4": ("Cancelar uma reserva", cancelar),
}


def main():
    endereco = os.environ.get("SERVIDOR", "127.0.0.1")
    porta = int(os.environ.get("PORTA", "6000"))

    try:
        cliente = Cliente(endereco, porta)
    except OSError as erro:
        print(f"Nao consegui conectar em {endereco}:{porta} -> {erro}")
        sys.exit(1)

    print(f"Conectado em {endereco}:{porta}")
    if not pedir_login(cliente):
        cliente.fechar()
        return

    while True:
        acao = mostrar_menu("Passageiro", OPCOES)
        if acao is None:
            break
        try:
            acao(cliente)
        except ValueError:
            print("Valor invalido, tente de novo.")
        except ConnectionError as erro:
            print("Conexao perdida:", erro)
            break

    cliente.fechar()


if __name__ == "__main__":
    main()
