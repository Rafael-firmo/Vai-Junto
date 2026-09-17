# Sistema de Caronas Compartilhadas

## Arquivos

```
protocolo.py    protocolo CCP: formato das mensagens e leitura pelo socket
dados.py        Trecho, Carona, Reserva e validação de data
grafo.py        grafo de rotas e busca de itinerários
servidor.py     servidor central
cliente.py      base compartilhada pelos clientes
motorista.py    cliente do motorista
passageiro.py   cliente do passageiro
testes.py       testes automatizados
meu_ip.py       descobre o IP da máquina na rede local
Dockerfile      imagem única para servidor e clientes
Makefile        atalhos para os comandos abaixo (opcional)
```

## Requisitos

- Docker
- Ou, sem Docker: Python 3

## Numa máquina só

Sem Docker:

```bash
python servidor.py
python motorista.py
python passageiro.py
```

Com Docker:

```bash
docker build -t caronas .
docker run --rm -p 6000:6000 caronas
```

```bash
docker run -it --rm -e SERVIDOR=host.docker.internal caronas python motorista.py
docker run -it --rm -e SERVIDOR=host.docker.internal caronas python passageiro.py
```

Testes:

```bash
python testes.py
```

ou

```bash
docker run --rm caronas python testes.py
```

## Em mais de uma máquina

Em cada máquina:

```bash
cd caronas
docker build -t caronas .
```

Na máquina do servidor:

```bash
python meu_ip.py
docker run --rm -p 6000:6000 caronas
```

Teste de conexão (opcional, nas outras máquinas):

```bash
python -c "import socket; socket.create_connection(('IP_DO_SERVIDOR', 6000), timeout=3); print('conectou')"
```

Clientes:

```bash
docker run -it --rm -e SERVIDOR=IP_DO_SERVIDOR caronas python motorista.py
docker run -it --rm -e SERVIDOR=IP_DO_SERVIDOR caronas python passageiro.py
```

Testes contra o servidor remoto:

```bash
docker run --rm -e SERVIDOR=IP_DO_SERVIDOR -e PORTA=6000 caronas python testes.py
```

## Erros comuns

| Erro                                          | Solução                                       |
| --------------------------------------------- | --------------------------------------------- |
| `Connection refused`, numa máquina só         | Use `-e SERVIDOR=host.docker.internal`        |
| `Connection refused` ou trava, entre máquinas | Firewall ou IP errado — teste a conexão antes |
| Menu não recebe o que foi digitado            | Falta `-it` no comando                        |
| `docker: command not found`                   | Tente com `sudo`                              |

## Makefile (opcional)

```bash
make build
make servidor
make motorista SERVIDOR=IP_DO_SERVIDOR
make passageiro SERVIDOR=IP_DO_SERVIDOR
make testes-remoto SERVIDOR=IP_DO_SERVIDOR
```

## Variáveis de ambiente

| Variável   | Padrão       | Uso               |
| ---------- | ------------ | ----------------- |
| `SERVIDOR` | esta máquina | IP do servidor    |
| `PORTA`    | `6000`       | Porta do servidor |
