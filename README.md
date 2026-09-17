# Sistema de Caronas Compartilhadas

Sistema de caronas de média/longa distância. Motoristas publicam rotas
com assentos por trecho; passageiros buscam e reservam itinerários,
inclusive combinando trechos de motoristas diferentes. Comunicação por
socket TCP puro, com protocolo de aplicação próprio (CCP).

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
- Ou, sem Docker: Python 3 (nenhuma biblioteca externa é usada)

## Rodando numa máquina só

Sem Docker, em três terminais:

```bash
python servidor.py
python motorista.py
python passageiro.py
```

Com Docker, primeiro suba o servidor:

```bash
docker build -t caronas .
docker run --rm -p 6000:6000 caronas
```

Em outros terminais, os clientes. Dentro de um container, `127.0.0.1`
aponta para o próprio container, não para a máquina que o hospeda — por
isso é preciso um endereço especial para alcançar o servidor que está
rodando ao lado, na mesma máquina:

```bash
docker run -it --rm -e SERVIDOR=host.docker.internal caronas python motorista.py
```
```bash
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

## Rodando em mais de uma máquina

Cenário: servidor numa máquina, motorista em outra, passageiro numa
terceira, todas na mesma rede local. Aqui **não se usa**
`host.docker.internal` nem `127.0.0.1` — usa-se o IP real da máquina do
servidor.

### 1. Construir a imagem em cada máquina

Copie a pasta do projeto para as três máquinas e, em cada uma:

```bash
cd caronas
docker build -t caronas .
```

### 2. Subir o servidor

Na máquina do servidor, descubra o IP dela:

```bash
python meu_ip.py
```

Ou, no Linux:

```bash
hostname -I
```

Anote o endereço (por exemplo 192.168.0.15). Suba o servidor:

```bash
docker run --rm -p 6000:6000 caronas
```

O `-p 6000:6000` é obrigatório: publica a porta do container na
máquina, permitindo que as outras máquinas alcancem o servidor.

### 3. Testar a rede antes de abrir os clientes

Nas outras máquinas, antes de rodar o cliente, confirme que a porta
está alcançável (troque o IP pelo anotado no passo 2):

```bash
python -c "import socket; socket.create_connection(('IP_DO_SERVIDOR', 6000), timeout=3); print('conectou')"
```

Se não conectar, o problema é de rede, não do sistema. Verifique:
firewall na máquina do servidor, e se as máquinas estão na mesma
sub-rede.

### 4. Abrir os clientes

Na máquina do motorista:

```bash
docker run -it --rm -e SERVIDOR=IP_DO_SERVIDOR caronas python motorista.py
```

Na máquina do passageiro:

```bash
docker run -it --rm -e SERVIDOR=IP_DO_SERVIDOR caronas python passageiro.py
```

O `-it` é obrigatório nos clientes: sem ele o menu não recebe entrada
de teclado.

### 5. Rodar os testes contra o servidor remoto (opcional)

```bash
docker run --rm -e SERVIDOR=IP_DO_SERVIDOR -e PORTA=6000 caronas python testes.py
```

