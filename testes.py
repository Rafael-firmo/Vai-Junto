import os
import socket
import struct
import threading
import time

import protocolo
from cliente import Cliente
from servidor import Servidor

SERVIDOR_EXTERNO = os.environ.get("SERVIDOR")
ENDERECO = SERVIDOR_EXTERNO or "127.0.0.1"
PORTA = int(os.environ.get("PORTA", "6100" if not SERVIDOR_EXTERNO else "6000"))


def subir_servidor():
    if SERVIDOR_EXTERNO:
        print(f"testando contra o servidor em {ENDERECO}:{PORTA}")
        return None

    servidor = Servidor()
    thread = threading.Thread(target=servidor.rodar, args=(ENDERECO, PORTA), daemon=True)
    thread.start()
    time.sleep(0.3)
    return servidor


def novo_cliente(usuario):
    cliente = Cliente(ENDERECO, PORTA)
    cliente.entrar(usuario, "senha123")
    return cliente


def publicar(cliente, rota, assentos, precos, data="10/09/2026", horario="07:00"):
    resposta = cliente.enviar(protocolo.PUBLICAR, {
        "rota": rota, "data": data, "horario": horario,
        "assentos": assentos, "precos": precos,
    })
    assert resposta.codigo == 201, resposta.corpo
    return resposta.corpo["id_carona"]


# O caso do enunciado: ninguem faz o trajeto inteiro, mas a combinacao existe.
def teste_itinerario_com_dois_motoristas():
    motorista_a = novo_cliente("motorista_a")
    motorista_b = novo_cliente("motorista_b")

    publicar(motorista_a, ["Salvador", "Feira de Santana"], 2, [20.0])
    publicar(motorista_b, ["Feira de Santana", "Vitoria da Conquista"], 2, [35.0])

    passageiro = novo_cliente("passageiro_1")
    resposta = passageiro.enviar(protocolo.BUSCAR, {
        "origem": "Salvador",
        "destino": "Vitoria da Conquista",
        "data": "10/09/2026",
    })

    itinerarios = resposta.corpo["itinerarios"]
    assert len(itinerarios) == 1, itinerarios
    assert itinerarios[0]["conexoes"] == 2
    assert itinerarios[0]["preco_total"] == 55.0

    trechos = [
        {"id_carona": t["id_carona"], "posicao": t["posicao"]}
        for t in itinerarios[0]["trechos"]
    ]
    reserva = passageiro.enviar(protocolo.RESERVAR, {"trechos": trechos})
    assert reserva.codigo == 201, reserva.corpo

    print("ok - itinerario combinando dois motoristas")


# 20 passageiros brigando por 3 assentos do mesmo trecho.
def teste_nenhum_assento_vendido_duas_vezes():
    total_de_assentos = 3
    total_de_passageiros = 20

    motorista = novo_cliente("motorista_disputa")
    id_carona = publicar(motorista, ["Ilheus", "Itabuna"], total_de_assentos, [15.0])

    resultados = {}

    def tentar_reservar(numero):
        passageiro = novo_cliente(f"disputa_{numero}")
        resposta = passageiro.enviar(protocolo.RESERVAR, {
            "trechos": [{"id_carona": id_carona, "posicao": 0}],
        })
        resultados[numero] = resposta.codigo
        passageiro.fechar()

    threads = [threading.Thread(target=tentar_reservar, args=(i,))
               for i in range(total_de_passageiros)]

    inicio = time.time()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    duracao = time.time() - inicio

    confirmadas = sum(1 for codigo in resultados.values() if codigo == 201)
    recusadas = sum(1 for codigo in resultados.values() if codigo == 409)

    assert len(resultados) == total_de_passageiros, "faltou resposta para alguem"
    assert confirmadas == total_de_assentos, f"esperava {total_de_assentos}, deu {confirmadas}"
    assert confirmadas + recusadas == total_de_passageiros, "apareceu resposta inesperada"

    print(f"ok - {confirmadas} confirmadas e {recusadas} recusadas "
          f"em {duracao:.3f}s (nenhum assento vendido duas vezes)")


# Se o segundo trecho nao tem vaga, o primeiro nao pode ser descontado.
def teste_reserva_e_tudo_ou_nada():
    motorista = novo_cliente("motorista_atomico")
    carona_cheia = publicar(motorista, ["Recife", "Caruaru"], 1, [30.0])
    carona_livre = publicar(motorista, ["Maceio", "Recife"], 5, [40.0])

    # ocupa a unica vaga do trecho Recife -> Caruaru
    primeiro = novo_cliente("chegou_antes")
    resposta = primeiro.enviar(protocolo.RESERVAR, {
        "trechos": [{"id_carona": carona_cheia, "posicao": 0}],
    })
    assert resposta.codigo == 201

    # agora alguem tenta Maceio -> Recife -> Caruaru; a segunda perna esta cheia
    segundo = novo_cliente("chegou_depois")
    resposta = segundo.enviar(protocolo.RESERVAR, {
        "trechos": [
            {"id_carona": carona_livre, "posicao": 0},
            {"id_carona": carona_cheia, "posicao": 0},
        ],
    })
    assert resposta.codigo == 409, resposta.corpo

    # a vaga do trecho que TINHA lugar precisa continuar intacta
    consulta = segundo.enviar(protocolo.LISTAR_CARONAS, {})
    for carona in consulta.corpo["caronas"]:
        if carona["id"] == carona_livre:
            assert carona["trechos"][0]["assentos_livres"] == 5, carona["trechos"][0]

    print("ok - reserva parcial nao consome assento do trecho disponivel")


def teste_mensagem_malformada_nao_derruba_o_servidor():
    cliente = novo_cliente("bagunceiro")

    cliente.conexao.enviar(b"isso nao e valido\r\n\r\n")
    resposta = cliente.conexao.receber_resposta()
    assert resposta.codigo == 400, resposta.corpo

    # a mesma conexao precisa continuar utilizavel depois do erro
    resposta = cliente.enviar(protocolo.LISTAR_RESERVAS)
    assert resposta.codigo == 200

    print("ok - mensagem malformada recebe 400 e a conexao sobrevive")


def teste_precisa_estar_autenticado():
    cliente = Cliente(ENDERECO, PORTA)
    resposta = cliente.enviar(protocolo.LISTAR_CARONAS, {})
    assert resposta.codigo == 401, resposta.corpo
    cliente.fechar()
    print("ok - sem token o servidor responde 401")


# O enunciado exige que o servidor sobreviva a um cliente que morre.
# Simulamos tres tipos de morte feia: fechar no meio de uma mensagem,
# dar reset na conexao (RST em vez de FIN), e sumir logo apos publicar.
def teste_queda_de_cliente_nao_derruba_o_servidor():
    motorista = novo_cliente("motorista_sobrevivente")
    id_carona = publicar(motorista, ["Natal", "Joao Pessoa"], 4, [30.0])

    # 1. some no meio de uma mensagem: manda cabecalho prometendo corpo e fecha
    meio_da_mensagem = Cliente(ENDERECO, PORTA)
    meio_da_mensagem.conexao.socket.sendall(
        b"LISTAR_CARONAS CCP/1.0\r\nContent-Length: 500\r\n\r\n{")
    meio_da_mensagem.conexao.socket.close()

    # 2. reset abrupto da conexao, sem fechamento educado
    reset = Cliente(ENDERECO, PORTA)
    reset.conexao.socket.setsockopt(
        socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    reset.conexao.socket.close()

    # 3. autentica, publica e desaparece sem fechar direito
    fantasma = novo_cliente("fantasma")
    publicar(fantasma, ["Aracaju", "Maceio"], 2, [45.0])
    fantasma.conexao.socket.close()

    time.sleep(0.2)

    # o servidor tem que continuar atendendo normalmente
    sobrevivente = novo_cliente("chegou_depois_do_caos")
    resposta = sobrevivente.enviar(protocolo.BUSCAR, {
        "origem": "Natal", "destino": "Joao Pessoa", "data": "10/09/2026"})
    assert resposta.codigo == 200, resposta.corpo
    assert len(resposta.corpo["itinerarios"]) == 1

    # e o estado deixado pelos clientes mortos tem que estar intacto
    reserva = sobrevivente.enviar(protocolo.RESERVAR, {
        "trechos": [{"id_carona": id_carona, "posicao": 0}]})
    assert reserva.codigo == 201, reserva.corpo

    print("ok - servidor sobrevive a quedas abruptas de clientes")


# O enunciado pede que o tempo de resposta continue adequado sob carga.
def teste_tempo_de_resposta_sob_carga():
    quantidade_de_clientes = 30
    buscas_por_cliente = 10
    limite_de_segundos = 1.0

    motorista = novo_cliente("motorista_carga")
    publicar(motorista, ["Petrolina", "Juazeiro", "Senhor do Bonfim"], 50, [10.0, 12.0])

    tempos = []
    trava_da_lista = threading.Lock()

    def carga(numero):
        passageiro = novo_cliente(f"carga_{numero}")
        for _ in range(buscas_por_cliente):
            inicio = time.time()
            resposta = passageiro.enviar(protocolo.BUSCAR, {
                "origem": "Petrolina",
                "destino": "Senhor do Bonfim",
                "data": "10/09/2026",
            })
            duracao = time.time() - inicio
            assert resposta.codigo == 200
            with trava_da_lista:
                tempos.append(duracao)
        passageiro.fechar()

    threads = [threading.Thread(target=carga, args=(i,))
               for i in range(quantidade_de_clientes)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    total = len(tempos)
    esperado = quantidade_de_clientes * buscas_por_cliente
    assert total == esperado, f"esperava {esperado} respostas, vieram {total}"

    media = sum(tempos) / total
    pior = max(tempos)
    assert pior < limite_de_segundos, f"resposta mais lenta levou {pior:.3f}s"

    print(f"ok - {total} buscas de {quantidade_de_clientes} clientes simultaneos "
          f"(media {media * 1000:.1f}ms, pior {pior * 1000:.1f}ms)")


# o servidor recusa data que nao existe, mesmo que o cliente nao valide
def teste_servidor_recusa_data_invalida():
    motorista = novo_cliente("motorista_datas")

    for data_ruim in ["90/255/245215", "31/02/2026", "2026-09-10", "amanha", ""]:
        resposta = motorista.enviar(protocolo.PUBLICAR, {
            "rota": ["Bahia", "Sergipe"], "data": data_ruim, "horario": "08:00",
            "assentos": 2, "precos": [10.0],
        })
        assert resposta.codigo == 400, f"aceitou a data {data_ruim!r}: {resposta.corpo}"

    # e continua aceitando data valida
    resposta = motorista.enviar(protocolo.PUBLICAR, {
        "rota": ["Bahia", "Sergipe"], "data": "29/02/2028", "horario": "08:00",
        "assentos": 2, "precos": [10.0],
    })
    assert resposta.codigo == 201, resposta.corpo

    print("ok - servidor recusa datas invalidas e aceita 29/02 em ano bissexto")


# cliente apontado para um endereco inalcancavel desiste em vez de travar
def teste_cliente_desiste_de_servidor_inalcancavel():
    from cliente import TIMEOUT_DE_CONEXAO

    inicio = time.time()
    try:
        # 203.0.113.0/24 e uma faixa reservada para documentacao: nunca responde
        Cliente("203.0.113.1", 6000)
        assert False, "deveria ter falhado ao conectar"
    except OSError:
        pass
    duracao = time.time() - inicio

    assert duracao < TIMEOUT_DE_CONEXAO + 2, f"demorou {duracao:.1f}s para desistir"
    print(f"ok - cliente desiste de servidor inalcancavel em {duracao:.1f}s")


if __name__ == "__main__":
    subir_servidor()
    teste_itinerario_com_dois_motoristas()
    teste_nenhum_assento_vendido_duas_vezes()
    teste_reserva_e_tudo_ou_nada()
    teste_mensagem_malformada_nao_derruba_o_servidor()
    teste_precisa_estar_autenticado()
    teste_queda_de_cliente_nao_derruba_o_servidor()
    teste_tempo_de_resposta_sob_carga()
    teste_servidor_recusa_data_invalida()
    teste_cliente_desiste_de_servidor_inalcancavel()
    print("\ntodos os testes passaram")
