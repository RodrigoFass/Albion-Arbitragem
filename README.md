# Albion Arbitragem

Bot de arbitragem do Albion Online: compra itens barato numa cidade e vende no Mercado Negro de
Caerleon. Lê os preços, monta a lista de compras pela margem **depois das taxas do jogo**, compra e
vende sozinho.

## Instalação

**O jeito fácil:** baixe o `.zip` da [última versão](https://github.com/RodrigoFass/Albion-Arbitragem/releases/latest),
extraia numa pasta sua (Área de Trabalho ou Documentos, não em "Arquivos de Programas") e abra o
`Albion Arbitragem.exe`. Não precisa instalar Python nem o Tesseract: vai tudo dentro da pasta.

Para a leitura pela rede (recomendada), instale também o
[Albion Data Client](https://github.com/ao-data/albiondata-client/releases). O instalador já traz o Npcap.

**Pelo código-fonte** (Windows 10/11 e Python 3.10+):

```bash
git clone https://github.com/RodrigoFass/Albion-Arbitragem.git
cd Albion-Arbitragem
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
winget install UB-Mannheim.TesseractOCR
.venv\Scripts\python app.py
```

A janela é HTML/CSS (pasta `interface/web/`) desenhada pelo WebView2 do Windows através do
[pywebview](https://pywebview.flowrl.com/).

## Como usar

| Tela | O que resolve |
|---|---|
| **Operação** | os três passos da viagem: **Ler preços** (na cidade e no Mercado Negro), **Comprar**, **Vender** |
| **Itens** | o que negociar, em que grupo (cada grupo é uma viagem) e quanto de cada combinação |
| **Histórico** | o que foi comprado e vendido — o lucro de verdade, não o previsto |
| **Ajustes** | em abas: Geral, Compra, Leitura e Avançado — salva sozinho a cada mudança |

O jogo precisa estar em **1920×1080, tela cheia, monitor principal**; para outra configuração use
**Ajustes → Leitura → Calibrar**. Rode uma vez em **Simular** antes de gastar prata.

| Tecla | O que faz |
|---|---|
| F11 | pausa ao terminar o item atual, e retoma |
| F2 | pula o item atual |
| F12 | para na hora (o botão Parar faz o mesmo); um segundo F12 encerra |

### Leitura pela rede (albiondata-client)

Com o [Albion Data Client](https://github.com/ao-data/albiondata-client/releases) instalado, o bot o
abre sozinho mandando os preços **só para este computador** (nada vai para o projeto público). O bot
continua abrindo cada item no mercado — o servidor só manda o que o jogo pede —, mas o preço chega
**exato pelo pacote**, com grau, encantamento, qualidade e quantidade, sem print e sem OCR:

- a leitura não erra dígito nem grau, e a compra vê o livro de ofertas inteiro;
- o mercado onde você está é descoberto sozinho (troque de zona uma vez depois de abrir o bot);
- abrir um item na mão também atualiza os preços;
- se os pacotes pararem de chegar, o bot volta ao OCR sozinho.

Ligar, desligar e ver a situação: **Ajustes → Leitura**. O caminho do cliente fica em **Ajustes → Avançado**.

### Comprar por qualidade

Desligado por padrão: tudo é comprado e vendido como Normal, que gira mais rápido. Ligado
(**Ajustes → Compra**), uma qualidade maior só entra na lista quando o Mercado Negro paga por ela
pelo menos 15% a mais de lucro que a Normal. Ela só compra com a leitura pela rede recebendo e com o
filtro de qualidade **calibrado** (Ajustes → Leitura → Calibrar → "Filtro de qualidade da tela de compra"), sempre
na hora, e a unidade comprada assim é vendida contando com o pedido da qualidade dela.

## A conta

A diferença crua entre dois preços não é lucro. Com as taxas do jogo — 8% de venda (4% com
Premium) e 2,5% por ordem — 67,8% de margem bruta viram entre 50,6% e 61,1%. A margem configurada
é sempre a **líquida**, e a conta vive isolada em `lucro.py`.

A lista vem da melhor margem para a pior. O teto de prata e os espaços do inventário (equipamento
não empilha: cada unidade ocupa um espaço) cortam sempre o pior negócio.

## Organização

```
app.py            abre a janela
interface/        ponte.py (tudo que a interface pode pedir), sobreposicao.py, web/ (HTML/CSS/JS)
motor/            o bot: leitura, decisão, compra, venda e dados
recursos/         o que vem com o programa: catálogo inicial, ids da API, graus base, ícone
dados/            os SEUS arquivos: preços, catálogo, ajustes, coordenadas, registros/ (não vai para o git)
ferramentas/      empacotar, gerar os ids da API, gerar o ícone
testes/
```

| Módulo de `motor/` | Responsabilidade |
|---|---|
| `lucro.py` | as taxas e a conta que decide o que comprar |
| `escuta.py` | os preços que o albiondata-client captura da rede, recebidos em 127.0.0.1 |
| `identificadores.py` | o nome de cada item → o identificador do jogo (`T5_MAIN_SWORD@2`) |
| `conferidor.py`, `mercado_negro.py`, `menu.py`, `filtros.py`, `categorias.py` | a leitura dos preços na tela |
| `compra.py`, `comprador.py`, `vendedor.py` | comprar e vender |
| `mercado.py`, `catalogo.py`, `historico.py`, `ajustes.py` | os dados |
| `comum.py`, `coordenadas.py` | captura, OCR, cliques, teclas, posições na tela |

## Testes

```bash
python testes/testar.py         # lógica: leitura, decisão, catálogo, lucro, qualidade
python testes/testar_ponte.py   # tudo que a interface pede, sem janela
python testes/testar_escuta.py  # a leitura pela rede, com pacotes no formato do cliente
python testes/testar_telas.py   # a interface de verdade, numa janela escondida: telas e erros de JavaScript
python -m pyflakes .
```

Rodam sem o jogo aberto e numa pasta temporária — nunca nos seus arquivos.

## Empacotar

```bash
python ferramentas/empacotar.py
```

Gera `dist/Albion Arbitragem/` com o `.exe`, a interface e o Tesseract, e um `.zip` pronto para mandar.

## Aviso

Automatizar ações no jogo viola os termos de uso do Albion Online e pode levar a banimento da conta.
O uso é responsabilidade de quem executa.

## Licença

Todos os direitos reservados. Você pode baixar a versão das [Releases](https://github.com/RodrigoFass/Albion-Arbitragem/releases) e usar para você, mas não pode copiar, modificar, redistribuir nem usar o código em outro projeto sem autorização do autor. Detalhes em [LICENSE](LICENSE).
