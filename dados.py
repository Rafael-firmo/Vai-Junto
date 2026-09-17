# Estruturas de dados do sistema e validacao de data

from datetime import datetime

FORMATO_DATA = "%d/%m/%Y"

def data_valida(texto):
    if not isinstance(texto, str):
        return False
    try:
        datetime.strptime(texto, FORMATO_DATA)
        return True
    except ValueError:
        return False


class Trecho:
    def __init__(self, id_carona, posicao, origem, destino, data, preco, assentos):
        self.id_carona = id_carona
        self.posicao = posicao
        self.origem = origem
        self.destino = destino
        self.data = data
        self.preco = preco
        self.assentos_livres = assentos

    def tem_vaga(self):
        return self.assentos_livres > 0

    # converte para dicionario, formato que o JSON aceita mandar pela rede
    def como_dicionario(self):
        return {
            "id_carona": self.id_carona,
            "posicao": self.posicao,
            "origem": self.origem,
            "destino": self.destino,
            "preco": self.preco,
            "assentos_livres": self.assentos_livres,
        }


# uma viagem publicada por um motorista, dividida em trechos
class Carona:
    def __init__(self, id_carona, motorista, rota, data, horario, assentos, precos):
        self.id = id_carona
        self.motorista = motorista
        self.rota = rota
        self.data = data
        self.horario = horario
        self.assentos = assentos
        self.cancelada = False

        # uma rota de N cidades vira N-1 trechos, pegando duas cidades vizinhas por vez
        self.trechos = []
        for posicao in range(len(rota) - 1):
            self.trechos.append(Trecho(
                id_carona=id_carona,
                posicao=posicao,
                origem=rota[posicao],
                destino=rota[posicao + 1],
                data=data,
                preco=float(precos[posicao]),
                assentos=assentos,
            ))

    def como_dicionario(self):
        return {
            "id": self.id,
            "motorista": self.motorista,
            "rota": self.rota,
            "data": self.data,
            "horario": self.horario,
            "assentos": self.assentos,
            "cancelada": self.cancelada,
            "trechos": [t.como_dicionario() for t in self.trechos],
        }


# o que um passageiro reservou. pode juntar trechos de caronas diferentes
class Reserva:
    def __init__(self, id_reserva, passageiro, trechos):
        self.id = id_reserva
        self.passageiro = passageiro
        self.cancelada = False
        self.trechos = [
            {
                "id_carona": t.id_carona,
                "posicao": t.posicao,
                "origem": t.origem,
                "destino": t.destino,
                "preco": t.preco,
            }
            for t in trechos
        ]

    def preco_total(self):
        return sum(t["preco"] for t in self.trechos)

    def como_dicionario(self):
        return {
            "id": self.id,
            "passageiro": self.passageiro,
            "trechos": self.trechos,
            "preco_total": self.preco_total(),
            "cancelada": self.cancelada,
        }
