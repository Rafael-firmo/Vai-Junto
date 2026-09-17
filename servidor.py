# Servidor central: guarda o estado e responde as requisicoes dos clientes

import socket
import threading
import traceback
import uuid

import protocolo
from dados import Carona, Reserva, data_valida
from grafo import GrafoDeRotas

ENDERECO_PADRAO = "0.0.0.0"
PORTA_PADRAO = 6000

# tempo maximo que o servidor espera por uma requisicao numa conexao parada.
TIMEOUT_DE_CONEXAO = 600


class Servidor:
    def __init__(self):
        self.grafo = GrafoDeRotas()
        self.caronas = {}
        self.reservas = {}
        self.usuarios = {}
        self.sessoes = {}

        # Evita que duas reservas aconteçam ao mesmo tempo.
        # Como cada cliente roda em uma thread, sem a trava
        # os dois poderiam reservar o mesmo assento.
        self.trava = threading.Lock()

        self.operacoes = {
            protocolo.AUTENTICAR: self.autenticar,
            protocolo.PUBLICAR: self.publicar_carona,
            protocolo.LISTAR_CARONAS: self.listar_caronas,
            protocolo.LISTAR_PASSAGEIROS: self.listar_passageiros,
            protocolo.CANCELAR_CARONA: self.cancelar_carona,
            protocolo.BUSCAR: self.buscar_itinerarios,
            protocolo.RESERVAR: self.reservar,
            protocolo.LISTAR_RESERVAS: self.listar_reservas,
            protocolo.CANCELAR_RESERVA: self.cancelar_reserva,
        }

    # ---------------- sessao ----------------

    # traduz o token de sessao no nome do usuario
    def usuario_do_token(self, token):
        if not token:
            return None
        return self.sessoes.get(token)

    # entra no sistema e devolve um token. cadastra no primeiro login
    def autenticar(self, requisicao, _usuario):
        nome = requisicao.corpo.get("usuario")
        senha = requisicao.corpo.get("senha")
        if not nome or not senha:
            return 400, {"erro": "informe usuario e senha"}

        with self.trava:
            senha_salva = self.usuarios.get(nome)
            if senha_salva is None:
                self.usuarios[nome] = senha
            elif senha_salva != senha:
                return 401, {"erro": "senha incorreta"}

            token = str(uuid.uuid4())
            self.sessoes[token] = nome

        return 200, {"token": token, "usuario": nome}

    # ---------------- motorista ----------------

    # valida os campos, cria a carona e insere nos dois lugares: no dicionario
    # de caronas (busca por id) e no grafo (busca por cidade)
    def publicar_carona(self, requisicao, usuario):
        rota = requisicao.corpo.get("rota")
        data = requisicao.corpo.get("data")
        horario = requisicao.corpo.get("horario")
        assentos = requisicao.corpo.get("assentos")
        precos = requisicao.corpo.get("precos")

        if not isinstance(rota, list) or len(rota) < 2:
            return 400, {"erro": "a rota precisa de pelo menos 2 cidades"}
        if not data or not horario:
            return 400, {"erro": "informe data e horario"}
        if not data_valida(data):
            return 400, {"erro": "data invalida, use DD/MM/AAAA"}
        if not isinstance(assentos, int) or assentos < 1:
            return 400, {"erro": "assentos deve ser um numero maior que zero"}
        if not isinstance(precos, list) or len(precos) != len(rota) - 1:
            return 400, {"erro": "precos precisa ter um valor para cada trecho"}

        carona = Carona(
            id_carona=str(uuid.uuid4()),
            motorista=usuario,
            rota=rota,
            data=data,
            horario=horario,
            assentos=assentos,
            precos=precos,
        )

        with self.trava:
            self.caronas[carona.id] = carona
            self.grafo.adicionar_carona(carona)

        return 201, {"id_carona": carona.id}

    # lista as caronas, todas ou so as do motorista autenticado
    def listar_caronas(self, requisicao, usuario):
        minhas_caronas = requisicao.corpo.get("minhas_caronas", False)
        with self.trava:
            lista = [
                c.como_dicionario()
                for c in self.caronas.values()
                if not minhas_caronas or c.motorista == usuario
            ]
        return 200, {"caronas": lista}

    # quem embarcou em cada trecho de uma carona. so o dono pode consultar
    def listar_passageiros(self, requisicao, usuario):
        id_carona = requisicao.corpo.get("id_carona")

        with self.trava:
            carona = self.caronas.get(id_carona)
            if carona is None:
                return 404, {"erro": "carona nao encontrada"}
            if carona.motorista != usuario:
                return 403, {"erro": "essa carona nao e sua"}

            por_trecho = {}
            for posicao in range(len(carona.trechos)):
                por_trecho[posicao] = []

            for reserva in self.reservas.values():
                if reserva.cancelada:
                    continue
                for trecho in reserva.trechos:
                    if trecho["id_carona"] == id_carona:
                        por_trecho[trecho["posicao"]].append(reserva.passageiro)

        return 200, {"passageiros_por_trecho": por_trecho}

    # marca a carona como cancelada e tira ela do grafo
    def cancelar_carona(self, requisicao, usuario):
        id_carona = requisicao.corpo.get("id_carona")

        with self.trava:
            carona = self.caronas.get(id_carona)
            if carona is None:
                return 404, {"erro": "carona nao encontrada"}
            if carona.motorista != usuario:
                return 403, {"erro": "essa carona nao e sua"}
            if carona.cancelada:
                return 200, {"situacao": "ja estava cancelada"}

            carona.cancelada = True
            self.grafo.remover_carona(carona)

        return 200, {"situacao": "cancelada"}

    # ---------------- passageiro ----------------

    # procura no grafo os caminhos possiveis entre duas cidades
    def buscar_itinerarios(self, requisicao, _usuario):
        origem = requisicao.corpo.get("origem")
        destino = requisicao.corpo.get("destino")
        data = requisicao.corpo.get("data")

        if not origem or not destino or not data:
            return 400, {"erro": "informe origem, destino e data"}
        if not data_valida(data):
            return 400, {"erro": "data invalida, use DD/MM/AAAA"}

        with self.trava:
            caminhos = self.grafo.buscar_itinerarios(origem, destino, data)

        itinerarios = []
        for trechos in caminhos:
            itinerarios.append({
                "trechos": [t.como_dicionario() for t in trechos],
                "preco_total": sum(t.preco for t in trechos),
                "conexoes": len(trechos),
            })

        return 200, {"itinerarios": itinerarios}

    # reserva todos os trechos do itinerario, ou nenhum.
    # obs : tudo dentro da trava: confere que todos tem vaga e so entao desconta,
 
    def reservar(self, requisicao, usuario):
        pedidos = requisicao.corpo.get("trechos")
        if not pedidos:
            return 400, {"erro": "nenhum trecho informado"}

        with self.trava:
            trechos = []
            for pedido in pedidos:
                carona = self.caronas.get(pedido.get("id_carona"))
                if carona is None or carona.cancelada:
                    return 409, {"erro": "essa carona nao esta mais disponivel"}

                posicao = pedido.get("posicao")
                if not isinstance(posicao, int) or posicao < 0 or posicao >= len(carona.trechos):
                    return 400, {"erro": f"posicao de trecho invalida: {posicao}"}

                trecho = carona.trechos[posicao]
                if not trecho.tem_vaga():
                    return 409, {"erro": f"sem vaga no trecho {trecho.origem} -> {trecho.destino}"}
                trechos.append(trecho)

            for trecho in trechos:
                trecho.assentos_livres -= 1

            reserva = Reserva(str(uuid.uuid4()), usuario, trechos)
            self.reservas[reserva.id] = reserva

        return 201, reserva.como_dicionario()

    # lista as reservas do passageiro autenticado
    def listar_reservas(self, _requisicao, usuario):
        with self.trava:
            minhas = [
                r.como_dicionario()
                for r in self.reservas.values()
                if r.passageiro == usuario
            ]
        return 200, {"reservas": minhas}

    # cancela a reserva e devolve os assentos a todos os trechos dela
    def cancelar_reserva(self, requisicao, usuario):
        id_reserva = requisicao.corpo.get("id_reserva")

        with self.trava:
            reserva = self.reservas.get(id_reserva)
            if reserva is None:
                return 404, {"erro": "reserva nao encontrada"}
            if reserva.passageiro != usuario:
                return 403, {"erro": "essa reserva nao e sua"}
            if reserva.cancelada:
                return 200, {"situacao": "ja estava cancelada"}

            reserva.cancelada = True
            for item in reserva.trechos:
                carona = self.caronas.get(item["id_carona"])
                if carona is not None:
                    carona.trechos[item["posicao"]].assentos_livres += 1

        return 200, {"situacao": "cancelada"}

    # ---------------- rede ----------------

    # escolhe a operacao pelo comando e confere a autenticacao
    def responder(self, requisicao):
        operacao = self.operacoes.get(requisicao.comando)
        if operacao is None:
            return 404, {"erro": f"comando desconhecido: {requisicao.comando}"}

        if requisicao.comando == protocolo.AUTENTICAR:
            return operacao(requisicao, None)

        usuario = self.usuario_do_token(requisicao.token())
        if usuario is None:
            return 401, {"erro": "autentique-se antes"}

        return operacao(requisicao, usuario)

    # laco de uma conexao: le uma requisicao, responde, repete
    def atender(self, conexao):
        try:
            while True:
                try:
                    requisicao = conexao.receber_requisicao()
                except protocolo.ErroDeProtocolo as erro:
                    conexao.enviar(protocolo.montar_resposta(400, {"erro": str(erro)}))
                    continue

                if requisicao is None:
                    break

                try:
                    codigo, corpo = self.responder(requisicao)
                except Exception as erro:
                    traceback.print_exc()
                    codigo, corpo = 500, {"erro": str(erro)}

                conexao.enviar(protocolo.montar_resposta(codigo, corpo))

        except socket.timeout:
            pass
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            conexao.fechar()

    # abre a porta e cria uma thread para cada cliente que conecta
    def rodar(self, endereco=ENDERECO_PADRAO, porta=PORTA_PADRAO):
        escuta = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        escuta.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        escuta.bind((endereco, porta))
        escuta.listen(64)
        print(f"servidor ouvindo em {endereco}:{porta}")

        try:
            while True:
                socket_do_cliente, _ = escuta.accept()
                conexao = protocolo.Conexao(socket_do_cliente, timeout=TIMEOUT_DE_CONEXAO)
                thread = threading.Thread(target=self.atender, args=(conexao,), daemon=True)
                thread.start()
        except KeyboardInterrupt:
            print("\nservidor encerrado")
        finally:
            escuta.close()


if __name__ == "__main__":
    Servidor().rodar()
