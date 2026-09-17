# Cliente do motorista: publica caronas e acompanha os passageiros

import os
import sys

import protocolo
from cliente import Cliente, pedir_login, mostrar_menu, pedir_data


def publicar(cliente):
    texto = input("Rota (cidades separadas por virgula): ")
    rota = [cidade.strip() for cidade in texto.split(",") if cidade.strip()]
    if len(rota) < 2:
        print("A rota precisa de pelo menos 2 cidades.")
        return

    data = pedir_data()
    horario = input("Horario de partida (HH:MM): ").strip()
    assentos = int(input("Assentos livres no carro: ").strip())

    precos = []
    for i in range(len(rota) - 1):
        valor = input(f"Preco de {rota[i]} para {rota[i + 1]}: R$ ").strip()
        precos.append(float(valor))

    resposta = cliente.enviar(protocolo.PUBLICAR, {
        "rota": rota,
        "data": data,
        "horario": horario,
        "assentos": assentos,
        "precos": precos,
    })

    if resposta.deu_certo():
        print("Carona publicada. Id:", resposta.corpo["id_carona"])
    else:
        print("Erro:", resposta.corpo.get("erro"))


def listar(cliente):
    resposta = cliente.enviar(protocolo.LISTAR_CARONAS, {"minhas_caronas": True})
    caronas = resposta.corpo.get("caronas", [])

    if not caronas:
        print("Voce ainda nao publicou nenhuma carona.")
        return

    for carona in caronas:
        situacao = "cancelada" if carona["cancelada"] else "ativa"
        print(f"\n[{carona['id']}] {situacao}")
        print(f"  {' -> '.join(carona['rota'])}  em {carona['data']} as {carona['horario']}")
        for trecho in carona["trechos"]:
            print(f"    trecho {trecho['posicao']}: {trecho['origem']} -> {trecho['destino']}"
                  f"  R$ {trecho['preco']:.2f}  ({trecho['assentos_livres']} livre[s])")


def ver_passageiros(cliente):
    id_carona = input("Id da carona: ").strip()
    resposta = cliente.enviar(protocolo.LISTAR_PASSAGEIROS, {"id_carona": id_carona})

    if not resposta.deu_certo():
        print("Erro:", resposta.corpo.get("erro"))
        return

    por_trecho = resposta.corpo["passageiros_por_trecho"]
    for posicao, passageiros in sorted(por_trecho.items(), key=lambda item: int(item[0])):
        nomes = ", ".join(passageiros) if passageiros else "ninguem"
        print(f"  trecho {posicao}: {nomes}")


def cancelar(cliente):
    id_carona = input("Id da carona a cancelar: ").strip()
    resposta = cliente.enviar(protocolo.CANCELAR_CARONA, {"id_carona": id_carona})
    if resposta.deu_certo():
        print("Carona", resposta.corpo["situacao"])
    else:
        print("Erro:", resposta.corpo.get("erro"))


OPCOES = {
    "1": ("Publicar carona", publicar),
    "2": ("Listar minhas caronas", listar),
    "3": ("Ver passageiros por trecho", ver_passageiros),
    "4": ("Cancelar carona", cancelar),
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
        acao = mostrar_menu("Motorista", OPCOES)
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
