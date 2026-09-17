MAX_CONEXOES = 4


class GrafoDeRotas:
    def __init__(self):
        self.saidas = {}

    # insere cada trecho da carona como aresta 
    def adicionar_carona(self, carona):
        for trecho in carona.trechos:
            if trecho.origem not in self.saidas:
                self.saidas[trecho.origem] = []
            self.saidas[trecho.origem].append(trecho)

    # tira do grafo os trechos de uma carona cancelada
    def remover_carona(self, carona):
        for trecho in carona.trechos:
            lista = self.saidas.get(trecho.origem, [])
            if trecho in lista:
                lista.remove(trecho)

    def trechos_saindo_de(self, cidade):
        return self.saidas.get(cidade, [])


    def buscar_itinerarios(self, origem, destino, data):
        encontrados = []
        self.explorar_caminhos(
            cidade_atual=origem,
            destino=destino,
            data=data,
            caminho=[],
            cidades_visitadas={origem},
            encontrados=encontrados,
        )
        encontrados.sort(key=ordem_do_itinerario)
        return encontrados

    def explorar_caminhos(self, cidade_atual, destino, data, caminho, cidades_visitadas, encontrados):
        if cidade_atual == destino and caminho:
            encontrados.append(list(caminho))
            return

        if len(caminho) >= MAX_CONEXOES:
            return

        for trecho in self.trechos_saindo_de(cidade_atual):
            if trecho.data != data:
                continue
            if not trecho.tem_vaga():
                continue
            if trecho.destino in cidades_visitadas:
                continue

            caminho.append(trecho)
            cidades_visitadas.add(trecho.destino)

            self.explorar_caminhos(trecho.destino, destino, data, caminho, cidades_visitadas, encontrados)

            cidades_visitadas.remove(trecho.destino)
            caminho.pop()

def ordem_do_itinerario(trechos):
    quantidade = len(trechos)
    preco = sum(t.preco for t in trechos)
    return (quantidade, preco)
