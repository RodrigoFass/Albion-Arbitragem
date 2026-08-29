# Albion Arbitragem

Automação de arbitragem entre mercados do Albion Online: lê os preços das cidades e do Mercado Negro,
calcula a margem **depois das taxas do jogo**, monta a lista de compras ordenada por rentabilidade,
compra e revende.

---

## O problema

A operação é conhecida por qualquer jogador: comprar barato numa cidade, levar para Caerleon e vender
no Mercado Negro. O que ninguém faz bem na mão é a parte de comparar — são **1.573 preços** entre
7 mercados e 13 combinações de grau e encantamento por item. Ler todos e escolher os melhores é o que
o programa faz.

A dificuldade real não é a leitura, é a **conta**. A diferença crua entre dois preços não é lucro:

```
Assassin Jacket 5.0    compra 10.994    venda 18.444    67,76% bruto
```

Com as taxas que o jogo cobra de verdade, esses 67,76% viram:

| Cenário | Margem real |
|---|---|
| Sem Premium (8%), comprando por ordem (+2,5%) | 50,6% |
| Sem Premium (8%), comprando na hora | 54,3% |
| Com Premium (4%), comprando por ordem | 57,1% |
| Com Premium (4%), comprando na hora | 61,1% |

Dezessete pontos entre o número aparente e o pior caso. Um mínimo de 23% bruto pode ser 8% líquido.
Por isso a margem configurada no programa é sempre a **líquida**, e o cálculo vive isolado em
`lucro.py` — é a única parte do sistema que pode ser conferida sem o jogo aberto, e é ela que manda
gastar prata.

---

## Como usar

As quatro telas seguem a ordem da operação:

| | Tela | O que resolve |
|---|---|---|
| 1 | **Itens** | o que negociar, em que grupo, quanto de cada combinação |
| 2 | **Conferir** | lê os preços — uma passada em Caerleon, uma na cidade |
| 3 | **Comprar** | a lista pronta, da melhor margem para a pior, e a compra |
| 4 | **Painel** | o que rendeu e o que falta ler |

```bash
python app.py
```

Os **grupos** existem porque o inventário tem limite: cada grupo é uma viagem. A loja do Mercado Negro
é infinita, o inventário não.

### Quantidades em três níveis

Cada nível sobrescreve o anterior:

- **Tabela** — vale para todos os itens: quanto comprar de cada T5.2, de cada T6.0, e assim por diante
- **Grupo** — vale para os itens dele: "as armaduras eu quero 20, as armas 8"
- **Exceções** — por item e por combinação

Um nível só não daria conta: um número por combinação ignora que um item líquido aguenta vinte
unidades e um travado não aguenta duas; um número por item ignora que o mesmo item é barato no T5 e
caro no T8.

---

## Como o programa compra

Dois caminhos, escolhidos linha a linha — o **Smart Buy**:

- **Pedido de compra** quando são 8 ou mais unidades e o item não passa de 100.000 de prata. Uma ordem
  casa de uma vez com todas as ofertas naquele preço ou abaixo: 53 unidades num clique, em vez de
  53 vezes três cliques.
- **Compra imediata** no resto.

O tamanho da ordem sai do livro de ofertas, não de um chute. Uma ordem maior do que há para vender não
desaparece — fica de pé no mercado com a prata presa dentro.

### Três barreiras antes de cada gasto

1. **O livro relido no lugar** — a oferta ainda paga a margem?
2. **O teto de gasto** — ainda há prata reservada para esta viagem?
3. **O diálogo do jogo** — o valor que ele vai cobrar ainda vale?

A terceira é a única que não passa pela aritmética do programa nem pelo OCR duas vezes: é o próprio
jogo dizendo o número antes de cobrar.

## Como o programa vende

- **Na hora** quando um pedido de compra já paga perto do alvo (95% por padrão) — receber agora é
  melhor que receber talvez
- **Por ordem**, uma prata abaixo do vendedor mais barato, quando não paga
- **Nunca abaixo do custo** — a carga não estraga e o mercado muda

O alvo sai do que **foi pago** por aquela unidade, lido do histórico, e não de uma tabela fixa.

---

## Leitura de tela e calibração

O programa não tem acesso a API: ele lê a tela do jogo com OCR (Tesseract) e clica com `win32api`.
Isso impõe três cuidados que estão embutidos no código:

**O dropdown de grau não começa no Grau 1.** Ele começa no grau base do item — Espada Larga abre em
Grau 1, Arco em Grau 2, Besta em Grau 3, Arco de Guerra em Grau 4 — e com encantamento é truncado no
Grau 4. A mesma coordenada seleciona graus diferentes conforme o item. Ignorar isso não gera erro:
gera preço do grau errado gravado como se fosse do certo, que é a pior forma de estar quebrado.
O programa descobre sozinho — clica, **lê o rótulo**, e se o número não for o esperado corrige pela
diferença. Uma correção basta, porque o erro é um deslocamento constante.

**A leitura é confirmada pelo valor, não pelos pixels.** Ao trocar um filtro a lista se redesenha —
os bytes da tela mudam — mas o número exibido continua o antigo por alguns quadros.

**Cada preço carrega a hora em que foi lido.** Preço de mercado envelhece em horas. A idade fica dentro
do registro do preço, e não numa coluna separada que alguém esquece de atualizar, justamente para
impedir uma compra decidida sobre a leitura da semana passada.

O padrão assume o jogo em **1920×1080, tela cheia, monitor principal**. Para qualquer outra
configuração existe **Ajustes → Calibrar coordenadas**, que captura a tela e permite remarcar as
posições sem editar código.

---

## Controles

| Tecla | O que faz |
|---|---|
| **F11** | pausa ao terminar o item atual, e retoma |
| **F12** | para na hora |

São atalhos globais, armados apenas enquanto uma operação roda. Nenhum dos dois fecha o programa:
depois de um susto, a primeira coisa que se quer é ler o log. Um segundo F12 encerra, como válvula
para um travamento que nenhuma checagem alcança.

Durante a operação o jogo fica em primeiro plano e o mouse pertence ao programa. A janela se minimiza
sozinha; uma faixa no topo e cartões no canto inferior mostram o andamento sem roubar o foco.

---

## Arquitetura

35 módulos, cerca de 16.400 linhas. A divisão segue responsabilidade, não tipo de arquivo:

| Módulo | Responsabilidade |
|---|---|
| `comum.py` | infraestrutura: captura de tela, OCR, cliques, esperas adaptativas, log, trava de execução, parada de emergência |
| `coordenadas.py` | todas as posições de clique e regiões de leitura, num lugar só |
| `calibrador.py` | remarca essas posições sem editar código |
| `conferidor.py` | o laço de leitura — **um só** para os dois mercados |
| `mercado_negro.py` | o que muda na tela do Mercado Negro |
| `mercado.py` | o banco de preços por cidade, com a hora de cada leitura |
| `lucro.py` | as taxas e a conta que decide o que comprar |
| `catalogo.py` | itens, grupos e quantidades em três níveis |
| `compra.py` | o plano de uma linha, a ordem, os três cliques |
| `comprador.py` | o laço que percorre a lista e compra |
| `vendedor.py` | a decisão de venda e a execução |
| `historico.py` | o que aconteceu com a prata |
| `menu.py`, `categorias.py`, `filtros.py`, `nomes.py` | navegação do menu em cascata do mercado e nomes em dois idiomas |
| `planilha.py` | importação opcional da `Tabela-BM.xlsx` da versão anterior |
| `app.py`, `tela_*.py` | a interface: casca e as cinco telas |
| `visual.py`, `tema.py`, `marca.py` | componentes, paletas clara e escura, identidade |
| `empacotar.py` | gera o executável Windows |

**Um laço de leitura só.** A cidade e o Mercado Negro têm telas diferentes e a mesma leitura. Isso já
foi resolvido com três cópias do laço, e cada correção precisava ser aplicada nas três — não foi, e a
que ficou para trás lia a região errada em silêncio. Hoje o laço mora em `conferidor.ler_item` e o que
varia é um objeto com sete métodos: `abrir`, `fechar`, `base`, `ler`, `vazio`, `encantamento`, `grau`.

### Duas paradas, não uma

`parada_pedida` termina a unidade de trabalho, grava e devolve o controle. `aborto_pedido` para onde
estiver. O aborto vira uma exceção `Abortado` que **herda de `BaseException`, não de `Exception`** —
cada item roda dentro de um `except Exception` para que um item problemático não derrube uma varredura
de meia hora, e um aborto comum viraria "erro neste item" com a varredura seguindo adiante.

Dentro de seção crítica o aborto aguarda: gravar a planilha é escrever um ZIP, confirmar uma compra são
dois cliques que precisam acontecer os dois. Sair no meio trocaria um susto por um estrago.

---

## Instalação

**Pré-requisitos:** Python 3.10+ e Windows.

```bash
git clone https://github.com/RodrigoFass/Albion-Arbitragem.git
cd Albion-Arbitragem
pip install -r requirements.txt
winget install UB-Mannheim.TesseractOCR
python app.py
```

As versões em `requirements.txt` são fixadas com `==`, não `>=`: o programa depende de detalhes finos
do OCR e da captura de tela, e uma atualização silenciosa de Pillow ou pytesseract muda o resultado de
uma leitura.

Para gerar o executável que roda sem Python instalado:

```bash
pip install pyinstaller
python empacotar.py
```

## Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `catalogo.json` | o que você escolheu negociar |
| `precos.json` | os preços lidos, com a hora de cada um |
| `precos-anterior.json` | cópia do que foi apagado na última varredura |
| `historico.csv` | uma linha por compra e por venda — abre no Excel |
| `ajustes.json` | taxa, margem, idade máxima de preço, limites de tempo |
| `coordenadas.json` | aparece após calibrar; apagar volta ao padrão |
| `registros/` | logs por sessão, um por mercado e por dia |

## Testes

```bash
python testes/testar.py            # lógica: leitura, decisão, catálogo, lucro
python testes/testar_interface.py  # monta a interface de verdade e clica nela
python -m pyflakes .               # nome indefinido e import inútil
```

Há um arquivo de teste por módulo. Os testes de lógica rodam em qualquer lugar, sem o jogo aberto.

---

## Relação com o Albion BM

Este programa nasceu do [Albion BM](https://github.com/RodrigoFass/Albion-BM), que opera **dentro de um
único mercado**. A arbitragem entre cidades quebrou duas premissas daquele código: o mesmo item passou a
ter um preço em cada mercado, e a decisão passou a depender da diferença entre dois deles. Virou outro
fluxo, outra interface e outros arquivos — por isso outro repositório.

---

## Aviso

Projeto pessoal de estudo em automação de interface, OCR e modelagem de custos. Automatizar ações em
jogos costuma violar os termos de uso do serviço, incluindo os do Albion Online. O código está aqui
como registro técnico; o uso é responsabilidade de quem executa.
