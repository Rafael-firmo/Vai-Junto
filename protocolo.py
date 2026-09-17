import json

VERSAO = "CCP/1.0"
CODIFICACAO = "utf-8"
FIM_DOS_CABECALHOS = b"\r\n\r\n"

AUTENTICAR = "AUTENTICAR"
PUBLICAR = "PUBLICAR"
LISTAR_CARONAS = "LISTAR_CARONAS"
LISTAR_PASSAGEIROS = "LISTAR_PASSAGEIROS"
CANCELAR_CARONA = "CANCELAR_CARONA"
BUSCAR = "BUSCAR"
RESERVAR = "RESERVAR"
LISTAR_RESERVAS = "LISTAR_RESERVAS"
CANCELAR_RESERVA = "CANCELAR_RESERVA"

MOTIVOS = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    500: "Internal Server Error",
}



class ErroDeProtocolo(Exception):
    pass


# guarda uma requisicao ja decodificada
class Requisicao:
    def __init__(self, comando, cabecalhos, corpo):
        self.comando = comando
        self.cabecalhos = cabecalhos
        self.corpo = corpo

    def token(self):
        return self.cabecalhos.get("Auth-Token")


# guarda uma resposta ja decodificada
class Resposta:
    def __init__(self, codigo, corpo):
        self.codigo = codigo
        self.motivo = MOTIVOS.get(codigo, "Desconhecido")
        self.corpo = corpo

    def deu_certo(self):
        return 200 <= self.codigo < 300


# junta linha inicial + cabecalhos + corpo numa sequencia de bytes.
def montar_mensagem(primeira_linha, corpo, token=None):
    corpo_em_bytes = json.dumps(corpo or {}, ensure_ascii=False).encode(CODIFICACAO)
    linhas = [
        primeira_linha,
        f"Content-Length: {len(corpo_em_bytes)}",
    ]
    if token:
        linhas.append(f"Auth-Token: {token}")
    return ("\r\n".join(linhas) + "\r\n\r\n").encode(CODIFICACAO) + corpo_em_bytes


# monta uma requisicao do cliente
def montar_requisicao(comando, corpo=None, token=None):
    return montar_mensagem(f"{comando} {VERSAO}", corpo, token)


# monta uma resposta do servidor
def montar_resposta(codigo, corpo=None):
    motivo = MOTIVOS.get(codigo, "Desconhecido")
    return montar_mensagem(f"{VERSAO} {codigo} {motivo}", corpo)


# quebra o bloco de cabecalhos em primeira linha + dicionario 
def separar_cabecalhos(texto):
    linhas = texto.split("\r\n")
    primeira_linha = linhas[0]
    cabecalhos = {}
    for linha in linhas[1:]:
        if not linha:
            continue
        if ":" not in linha:
            raise ErroDeProtocolo(f"cabecalho sem dois-pontos: {linha!r}")
        nome, valor = linha.split(":", 1)
        cabecalhos[nome.strip()] = valor.strip()
    return primeira_linha, cabecalhos

class Conexao:
    def __init__(self, socket_tcp, timeout=None):
        self.socket = socket_tcp
        self.buffer = bytearray()
        if timeout is not None:
            self.socket.settimeout(timeout)

    # manda bytes 
    def enviar(self, bytes_da_mensagem):
        self.socket.sendall(bytes_da_mensagem)

    # le do socket ate achar o marcador; devolve o que veio antes dele (None = o outro lado fechou a conexa)
    def ler_ate_marcador(self, marcador):
        while marcador not in self.buffer:
            pedaco = self.socket.recv(4096)
            if not pedaco:
                if self.buffer:
                    raise ErroDeProtocolo("conexao caiu no meio de uma mensagem")
                return None
            self.buffer.extend(pedaco)
        corte = self.buffer.find(marcador)
        lido = bytes(self.buffer[:corte])
        del self.buffer[: corte + len(marcador)]
        return lido

    # le exatamente a quantidade pedida de bytes, usada para o corpo
    def ler_bytes(self, quantidade):
        while len(self.buffer) < quantidade:
            pedaco = self.socket.recv(4096)
            if not pedaco:
                raise ErroDeProtocolo("conexao caiu antes de terminar o corpo")
            self.buffer.extend(pedaco)
        lido = bytes(self.buffer[:quantidade])
        del self.buffer[:quantidade]
        return lido

    # le uma mensagem inteira: cabecalhos ate o marcador, corpo por tamanho
    def ler_mensagem(self):
        cabecalho_bruto = self.ler_ate_marcador(FIM_DOS_CABECALHOS)
        if cabecalho_bruto is None:
            return None

        texto = cabecalho_bruto.decode(CODIFICACAO, errors="replace")
        primeira_linha, cabecalhos = separar_cabecalhos(texto)

        try:
            tamanho = int(cabecalhos.get("Content-Length", "0"))
        except ValueError:
            raise ErroDeProtocolo("Content-Length nao e um numero")

        corpo = {}
        if tamanho > 0:
            corpo_bruto = self.ler_bytes(tamanho)
            try:
                corpo = json.loads(corpo_bruto.decode(CODIFICACAO))
            except json.JSONDecodeError:
                raise ErroDeProtocolo("corpo nao e um JSON valido")

        return primeira_linha, cabecalhos, corpo

    # le uma mensagem e interpreta a primeira linha como requisicao
    def receber_requisicao(self):
        lido = self.ler_mensagem()
        if lido is None:
            return None
        primeira_linha, cabecalhos, corpo = lido

        partes = primeira_linha.split(" ")
        if len(partes) != 2:
            raise ErroDeProtocolo(f"linha inicial invalida: {primeira_linha!r}")
        comando, versao = partes
        if versao != VERSAO:
            raise ErroDeProtocolo(f"versao nao suportada: {versao!r}")

        return Requisicao(comando, cabecalhos, corpo)

    # le uma mensagem e interpreta a primeira linha como resposta
    def receber_resposta(self):
        lido = self.ler_mensagem()
        if lido is None:
            return None
        primeira_linha, _cabecalhos, corpo = lido

        partes = primeira_linha.split(" ", 2)
        if len(partes) != 3:
            raise ErroDeProtocolo(f"linha inicial invalida: {primeira_linha!r}")
        versao, codigo, _motivo = partes
        if versao != VERSAO:
            raise ErroDeProtocolo(f"versao nao suportada: {versao!r}")
        try:
            codigo = int(codigo)
        except ValueError:
            raise ErroDeProtocolo(f"codigo de status invalido: {codigo!r}")

        return Resposta(codigo, corpo)

    def fechar(self):
        self.socket.close()
