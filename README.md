# Albion Arbitragem

Bot de arbitragem para Albion Online: lê os preços das cidades e do Mercado
Negro, monta a lista de compras pela margem **depois das taxas do jogo**, compra
e vende.

A operação é a mesma que se faz na mão: comprar barato numa cidade, levar para
Caerleon e vender no Mercado Negro. O que o programa faz é a parte que ninguém
consegue fazer bem manualmente — ler 1.573 preços e comparar todos.

---

## A ordem de uso

| | Tela | O que ela resolve |
|---|---|---|
| 1 | **Itens** | o que negociar, em que grupo, e quanto de cada combinação |
| 2 | **Conferir** | os preços — uma passada em Caerleon, uma na cidade |
| 3 | **Comprar** | a lista pronta, da melhor margem para a pior, e a compra |
| 4 | **Painel** | o que rendeu, e o que está faltando ler |

Os grupos existem porque **o inventário tem limite**: cada grupo é uma viagem. A
loja do Mercado Negro é infinita; o seu inventário não.

---

## A margem é o que decide tudo

O programa nunca compra sem calcular quanto sobra **depois** das taxas do jogo:

- **8%** de imposto sobre a venda — **4%** com Premium
- **2,5%** por ordem, na compra e na venda

A margem que você escolhe em Ajustes é o que sobra depois disso, e não a
diferença crua entre os preços. Uma margem bruta de 20% costuma virar 8% real.

---

## Como o bot compra

Dois caminhos, escolhidos por linha — é o "Smart Buy":

- **Pedido de compra** quando são 8 ou mais unidades e o item não passa de
  100.000 de prata. Uma ordem casa na hora com todas as ofertas naquele preço ou
  abaixo — 53 unidades num clique, em vez de 53 vezes três cliques.
- **Compra na hora** no resto.

O tamanho da ordem sai do livro de ofertas, e não de um chute: uma ordem maior do
que há para vender não desaparece, fica de pé no mercado com a sua prata presa
dentro.

**Três barreiras antes de cada prata sair:**

1. o livro relido no lugar — a oferta ainda paga a margem?
2. o teto de gasto — ainda há prata reservada para esta viagem?
3. **o diálogo do jogo** — o valor que ele vai cobrar ainda vale?

A terceira é a única que não passa pela nossa aritmética nem pelo nosso OCR duas
vezes. É o próprio jogo dizendo o número, antes de cobrar.

---

## Como o bot vende

- **Na hora** se um pedido de compra já paga perto do alvo (95% por padrão) —
  receber agora é melhor que receber talvez.
- **Por ordem**, uma prata abaixo do vendedor mais barato, quando não paga.
- **Não vende** abaixo do custo. A carga não estraga, e o mercado muda.

O alvo sai do que **foi pago** por aquela unidade, lido do histórico — não de uma
tabela.

---

## Teclas

| Tecla | O que faz |
|---|---|
| **F11** | pausa ao terminar o item atual, e retoma |
| **F12** | para na hora |

Durante a operação o jogo fica em primeiro plano e o mouse é do bot. A janela se
minimiza sozinha; a faixa no topo da tela e os cartões no canto de baixo mostram
o que está acontecendo sem tirar o foco do jogo.

---

## Se os números saírem estranhos

**Ajustes → Calibrar coordenadas.** Ele captura a tela do jogo e deixa remarcar
cada ponto de clique e cada recorte de leitura sobre a imagem parada, com lupa.

Isso não é opcional numa resolução diferente de 1920×1080, e vale a pena mesmo
nela: um recorte seis pixels fora já fez o "5" de 540.000 ser lido como **9** —
sem erro nenhum aparecer.

Quando uma leitura falha sem explicação, o bot guarda o PNG do que ele viu em
`registros/falhas_conferidor/`. É a diferença entre consertar e adivinhar.

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `catalogo.json` | o que você escolheu negociar |
| `precos.json` | os preços lidos, com a hora de cada um |
| `precos-anterior.json` | a cópia do que foi apagado na última varredura |
| `historico.csv` | uma linha por compra e por venda — abre no Excel |
| `ajustes.json` | as preferências |
| `coordenadas.json` | aparece só depois de calibrar; apagar volta ao padrão |
| `registros/` | logs por sessão, um log por mercado e por dia, diagnósticos |
| `Tabela-BM.xlsx` | **opcional** — só para trazer os itens da versão antiga |

---

## Para desenvolver

```bash
python testes/testar.py
```

```bash
python testes/testar_interface.py
```

O primeiro cobre a lógica — leitura, decisão de compra e venda, catálogo, lucro.
O segundo monta a interface de verdade e clica nela.

Antes de alterar qualquer arquivo:

```bash
python -m pyflakes .
```

### O que cada módulo faz

| Módulo | Responsabilidade |
|---|---|
| `comum.py` | tela, OCR, cliques, teclas, log, diagnóstico |
| `coordenadas.py` | onde clicar e onde ler — **e o que o calibrador remarca** |
| `conferidor.py` | o laço de leitura, um só para os dois mercados |
| `mercado_negro.py` | a tela do painel de venda: o que muda no Mercado Negro |
| `compra.py` | o plano de uma linha, a ordem, os três cliques |
| `comprador.py` | o laço que percorre a lista e compra |
| `vendedor.py` | a decisão de venda e a execução |
| `lucro.py` | as taxas e a conta que decide |
| `catalogo.py` | itens, grupos e quantidades |
| `mercado.py` | o banco de preços |
| `historico.py` | o que aconteceu com a prata |
| `visual.py` | os componentes; `tema.py` as duas paletas |

**Um laço de leitura só.** A cidade e o Mercado Negro têm telas diferentes e a
mesma leitura. Isso já foi resolvido com três cópias do laço, e cada correção
precisava ser aplicada nas três — não foi, e a que ficou para trás lia a região
errada em silêncio. Hoje o laço mora em `conferidor.ler_item` e o que muda é um
objeto com sete métodos: `abrir`, `fechar`, `base`, `ler`, `vazio`,
`encantamento`, `grau`.
