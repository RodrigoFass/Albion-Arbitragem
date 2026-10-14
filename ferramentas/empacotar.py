################################
#                              #
#          EMPACOTAR           #
#                              #
################################

# Gera o Albion Arbitragem como aplicativo Windows: uma pasta com um .exe que
# roda em maquina sem Python, sem pip e sem Tesseract instalado.
#
#   pip install pyinstaller
#   python ferramentas/empacotar.py
#
# O resultado sai em dist/Albion Arbitragem/ e tambem zipado, pronto para mandar.
#
# O QUE VAI DENTRO
#
#   Albion Arbitragem.exe   o app com o Python e as bibliotecas embutidos
#   web/                    a interface (HTML e CSS), desenhada pelo WebView2
#   *.json                  o catalogo inicial, o mapa de ids e os graus base
#   tesseract/              o motor de OCR, so os arquivos que ele de fato usa
#   LEIA.txt                instrucoes para quem receber
#
# O WebView2 ja vem no Windows 11 (e no 10 atualizado); nao vai na pasta.
#
# O TESSERACT NAO VEM DO PIP. O pytesseract e so uma ponte para um executavel
# externo, que normalmente se instala a parte. Como a ideia e rodar em maquina
# alheia sem instalar nada, o binario vai junto - mas a instalacao completa tem
# 239 MB, quase toda em DLLs de ferramentas de treinamento que o app nunca chama.
# Por isso este script le a TABELA DE IMPORTACAO do tesseract.exe e copia apenas
# as DLLs que ele realmente carrega, recursivamente. Sao ~30 MB em vez de 239.
#
# Tesseract e Apache 2.0, entao redistribuir e permitido - a licenca vai junto.

import os
import shutil
import struct
import subprocess
import sys
import zipfile

# a raiz do projeto: este arquivo mora em ferramentas/
PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOME_APP = 'Albion Arbitragem'
TESSERACT_ORIGEM = r'C:\Program Files\Tesseract-OCR'

# Uma pasta em vez de um unico .exe. Num arquivo so, o Windows extrai os ~40 MB
# para uma pasta temporaria a CADA execucao, o que atrasa a abertura em alguns
# segundos. Em pasta o programa abre na hora. Para gerar arquivo unico, troque
# para True - o codigo ja resolve os caminhos nos dois modos.
ARQUIVO_UNICO = False

# Idiomas do OCR. So digitos sao lidos, entao ingles basta. O osd.traineddata
# (11 MB) so serve para deteccao de orientacao, que nenhum psm usado aqui pede.
IDIOMAS = ['eng.traineddata']

#region Dependencias do tesseract


def _rva_para_offset(secoes, rva):
    """Converte endereco virtual em posicao dentro do arquivo."""

    for inicio_virtual, tamanho_virtual, inicio_bruto in secoes:
        if inicio_virtual <= rva < inicio_virtual + tamanho_virtual:
            return inicio_bruto + (rva - inicio_virtual)

    return None


def dlls_importadas(caminho):
    """Nomes das DLLs que este PE importa, lendo o cabecalho do arquivo.

    Sem dependencia externa: a alternativa seria o dumpbin do Visual Studio, que
    nao existe numa maquina qualquer. O formato PE e estavel desde os anos 90 e
    a parte que interessa aqui - o diretorio de importacao - sao poucos campos."""

    try:
        with open(caminho, 'rb') as f:
            dados = f.read()
    except OSError:
        return []

    if dados[:2] != b'MZ':
        return []

    # e_lfanew: onde comeca o cabecalho PE
    pe = struct.unpack_from('<I', dados, 0x3C)[0]

    if dados[pe:pe + 4] != b'PE\0\0':
        return []

    n_secoes = struct.unpack_from('<H', dados, pe + 6)[0]
    tam_opcional = struct.unpack_from('<H', dados, pe + 20)[0]

    inicio_opcional = pe + 24
    magia = struct.unpack_from('<H', dados, inicio_opcional)[0]

    # PE32+ (64 bits) tem campos maiores antes dos diretorios de dados
    desloc_diretorios = 112 if magia == 0x20B else 96

    # diretorio 1 = importacao
    rva_import = struct.unpack_from('<I', dados, inicio_opcional + desloc_diretorios + 8)[0]

    if not rva_import:
        return []

    secoes = []
    inicio_secoes = inicio_opcional + tam_opcional

    for i in range(n_secoes):
        base = inicio_secoes + i * 40
        tamanho_virtual, inicio_virtual, _, inicio_bruto = struct.unpack_from(
            '<IIII', dados, base + 8)
        secoes.append((inicio_virtual, max(tamanho_virtual, 1), inicio_bruto))

    posicao = _rva_para_offset(secoes, rva_import)

    if posicao is None:
        return []

    nomes = []

    # descritores de 20 bytes, terminados por um bloco de zeros
    while True:

        bloco = dados[posicao:posicao + 20]

        if len(bloco) < 20 or bloco == b'\0' * 20:
            break

        rva_nome = struct.unpack_from('<I', bloco, 12)[0]
        onde = _rva_para_offset(secoes, rva_nome)

        if onde is not None:
            fim = dados.index(b'\0', onde)
            nomes.append(dados[onde:fim].decode('ascii', 'replace'))

        posicao += 20

    return nomes


def dependencias(origem, raiz='tesseract.exe'):
    """Fecho transitivo das DLLs que <raiz> precisa, dentro de <origem>.

    DLLs do proprio Windows (kernel32, msvcrt...) ficam de fora: elas ja existem
    na maquina de destino e nao estao nesta pasta."""

    disponiveis = {f.lower(): f for f in os.listdir(origem) if f.lower().endswith('.dll')}

    vistos = set()
    fila = [raiz]

    while fila:

        atual = fila.pop()

        for nome in dlls_importadas(os.path.join(origem, atual)):

            chave = nome.lower()

            # so as que moram na pasta do tesseract; o resto e do sistema
            if chave in disponiveis and chave not in vistos:
                vistos.add(chave)
                fila.append(disponiveis[chave])

    return sorted(disponiveis[c] for c in vistos)

#endregion

#region Etapas


def passo(texto):
    print(f'\n=== {texto}')


def preparar_tesseract(destino):
    """Copia o tesseract.exe, as DLLs que ele usa e os dados do idioma."""

    if not os.path.isdir(TESSERACT_ORIGEM):
        print(f'  Tesseract nao encontrado em {TESSERACT_ORIGEM}')
        print('  Instale com:  winget install UB-Mannheim.TesseractOCR')
        return False

    os.makedirs(destino, exist_ok=True)

    shutil.copy2(os.path.join(TESSERACT_ORIGEM, 'tesseract.exe'), destino)

    dlls = dependencias(TESSERACT_ORIGEM)

    total = 0

    for dll in dlls:
        origem = os.path.join(TESSERACT_ORIGEM, dll)
        shutil.copy2(origem, destino)
        total += os.path.getsize(origem)

    todas = len([f for f in os.listdir(TESSERACT_ORIGEM) if f.lower().endswith('.dll')])

    print(f'  tesseract.exe + {len(dlls)} DLLs ({total / 1e6:.0f} MB)')
    print(f'  (a instalacao tem {todas} DLLs; as outras {todas - len(dlls)} sao das '
          f'ferramentas de treinamento, que o app nao chama)')

    dados = os.path.join(destino, 'tessdata')
    os.makedirs(dados, exist_ok=True)

    for idioma in IDIOMAS:
        shutil.copy2(os.path.join(TESSERACT_ORIGEM, 'tessdata', idioma), dados)

    origem_configs = os.path.join(TESSERACT_ORIGEM, 'tessdata', 'configs')

    if os.path.isdir(origem_configs):
        shutil.copytree(origem_configs, os.path.join(dados, 'configs'),
                        dirs_exist_ok=True)

    # Apache 2.0 permite redistribuir, desde que a licenca acompanhe
    for licenca in ('LICENSE', 'COPYING', 'LICENSE.txt'):
        caminho = os.path.join(TESSERACT_ORIGEM, licenca)
        if os.path.isfile(caminho):
            shutil.copy2(caminho, os.path.join(destino, 'LICENSE-tesseract.txt'))
            break
    else:
        with open(os.path.join(destino, 'LICENSE-tesseract.txt'), 'w',
                  encoding='utf-8') as f:
            f.write('Tesseract OCR - Apache License 2.0\n'
                    'https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE\n')

    return True


def testar_tesseract(pasta):
    """Roda o tesseract copiado para provar que ele funciona sem a instalacao.

    Sem isto, uma DLL faltando so apareceria na maquina do usuario, no meio de
    uma varredura - e como o erro sai do processo filho, apareceria como leitura
    vazia, nao como erro de carregamento."""

    exe = os.path.join(pasta, 'tesseract.exe')

    try:
        r = subprocess.run([exe, '--version'], capture_output=True, text=True,
                           timeout=30)
    except Exception as e:
        print(f'  FALHOU ao executar: {e}')
        return False

    if r.returncode != 0:
        print(f'  FALHOU (codigo {r.returncode}): {r.stderr.strip()[:200]}')
        return False

    print(f'  {r.stdout.strip().splitlines()[0]}')

    # OCR de verdade, num numero desenhado na hora - e o que o bot faz
    from PIL import Image, ImageDraw

    img = Image.new('L', (240, 60), 'black')
    ImageDraw.Draw(img).text((10, 12), '158869', fill='white')
    img = img.resize((960, 240), Image.LANCZOS)

    teste = os.path.join(pasta, '_teste.png')
    img.save(teste)

    try:
        r = subprocess.run(
            [exe, teste, 'stdout', '--psm', '7', '--oem', '1',
             '-c', 'tessedit_char_whitelist=0123456789'],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'TESSDATA_PREFIX': os.path.join(pasta, 'tessdata')})

        lido = ''.join(c for c in r.stdout if c.isdigit())

        if lido == '158869':
            print(f'  leitura de teste: {lido} - correto')
            return True

        print(f'  leitura de teste devolveu {lido!r}, esperado 158869')
        print(f'  stderr: {r.stderr.strip()[:200]}')
        return False

    finally:
        try:
            os.remove(teste)
        except OSError:
            pass


def pacote_em_uso():
    """O .exe da build anterior ainda esta rodando? Devolve (sim, pid).

    O PyInstaller apaga a pasta dist antes de recompilar, e o Windows nao deixa
    apagar um arquivo aberto. Sem esta checagem, o erro que aparece e um
    PermissionError no meio de um stack trace de dez linhas apontando para um
    .pyd do Pillow - que nao diz nada sobre a causa real."""

    try:
        saida = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {NOME_APP}.exe', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=20).stdout

    except Exception:
        return False, None

    for linha in saida.splitlines():
        partes = [p.strip('"') for p in linha.split('","')]
        if len(partes) >= 2 and partes[0].lower() == f'{NOME_APP}.exe'.lower():
            return True, partes[1]

    return False, None


def compilar():
    """Chama o PyInstaller."""

    rodando, pid = pacote_em_uso()

    if rodando:
        print(f'\n  O "{NOME_APP}.exe" da build anterior ainda esta aberto '
              f'(PID {pid}).')
        print('  Feche-o antes de empacotar - o Windows nao deixa apagar a pasta')
        print('  dist enquanto um arquivo dela estiver em uso.\n')
        return False

    argumentos = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--name', NOME_APP,
        '--windowed',          # sem janela de console atras do app
        '--onefile' if ARQUIVO_UNICO else '--onedir',

        # O pynput escolhe o backend em tempo de execucao, por importacao
        # dinamica - o PyInstaller nao ve isso sozinho e o app abriria sem as
        # teclas F11 e F12 funcionando.
        '--hidden-import', 'pynput.keyboard._win32',
        '--hidden-import', 'pynput.mouse._win32',

        # Nada aqui usa numpy, scipy ou matplotlib; sem excluir, o PyInstaller
        # os empacota se estiverem instalados, e sao centenas de MB.
        '--exclude-module', 'numpy',
        '--exclude-module', 'scipy',
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'pandas',
        '--exclude-module', 'PyQt5',
        '--exclude-module', 'PySide2',
        '--exclude-module', 'tkinter',
        '--exclude-module', 'test',

        # o icone do .exe, da janela e da barra de tarefas
        # (python ferramentas/gerar_icone.py, se a marca mudar)
        '--icon', os.path.join(PASTA, 'recursos', 'marca.ico'),

        'app.py',
    ]

    print('  ' + ' '.join(argumentos[2:]))

    return subprocess.run(argumentos, cwd=PASTA).returncode == 0


LEIA = """ALBION ARBITRAGEM {versao}
==================

Compra itens barato numa cidade e vende no Mercado Negro de Caerleon. Le os
precos, monta a lista pela margem DEPOIS das taxas do jogo, compra e vende.

COMO USAR

  1. Abra o Albion Online em 1920x1080, em tela cheia, no monitor principal.
     (Outra resolucao: Ajustes > Leitura > Calibrar.)
  2. De dois cliques em "Albion Arbitragem.exe".
  3. Itens: escolha o que negociar e quanto de cada combinacao.
  4. Operacao, na ordem dos passos:
       Ler precos   uma vez na cidade, uma no Mercado Negro
       Comprar      a lista sai pronta, da melhor margem para a pior
       Vender       no Mercado Negro, na hora ou por ordem

Nao precisa instalar nada. Python, bibliotecas e o motor de OCR ja vao dentro
desta pasta. A janela usa o WebView2, que ja vem no Windows 11.

ENQUANTO RODA

  F11   pausa ao terminar o item atual; F11 de novo retoma
  F2    pula o item atual
  F12   para na hora (o botao Parar faz o mesmo); um segundo F12 encerra

As teclas so valem enquanto uma operacao roda, e podem ser trocadas em Ajustes.
O jogo precisa estar em primeiro plano: por isso o app se minimiza sozinho e
mostra o andamento numa faixa no topo da tela e em cartoes no canto, por cima
do jogo. Eles nao aceitam clique, de proposito.

ANTES DE MEXER COM PRATA

Rode uma vez em Simular, que faz tudo menos confirmar. As coordenadas de clique
foram medidas em 1920x1080: em outra resolucao os cliques caem no lugar errado.

LEITURA PELA REDE

Recomendada. Instale o Albion Data Client (github.com/ao-data/albiondata-client,
o instalador ja traz o Npcap). O bot o abre sozinho mandando os precos SO para
este computador - nada vai para o projeto publico - e le cada preco exato pelo
pacote do servidor, sem OCR. Depois de abrir o bot, troque de zona uma vez no
jogo: e assim que o cliente descobre em que mercado voce esta. A situacao
aparece em Ajustes > Leitura. Sem o cliente, a leitura e pela tela, com OCR.

COMPRAR POR QUALIDADE

Desligado de fabrica: tudo e comprado e vendido como Normal, que vende mais
rapido. Ligado (Ajustes > Compra), uma qualidade maior so entra na lista quando
o Mercado Negro paga por ela pelo menos 15% a mais de lucro que a Normal. Precisa
da leitura pela rede e do filtro de qualidade calibrado (Ajustes > Leitura >
Calibrar > "Filtro de qualidade da tela de compra").

SEUS ARQUIVOS (na pasta dados, ao lado do .exe)

  catalogo-padrao.json  o seu catalogo. Nasce do recursos/catalogo-inicial.json.
  precos.json           os precos lidos, com a hora de cada leitura.
  precos-anterior.json  a copia do que foi apagado na ultima leitura.
  ajustes.json          as preferencias.
  coordenadas.json      aparece so depois de calibrar. Apagar volta ao padrao.
  registros/            historico.csv (uma linha por compra e venda, abre no
                        Excel), os logs e os PNGs de diagnostico de leitura.

Para atualizar o programa, troque tudo MENOS a pasta dados.

DEIXE ESTA PASTA NUM LUGAR SEU - a Area de Trabalho ou Documentos. Dentro de
"Arquivos de Programas" o Windows nao deixa o programa gravar.

SE NAO ABRIR

O Windows pode avisar que o programa e de origem desconhecida, porque o
executavel nao tem assinatura digital. Em "Mais informacoes" ha a opcao de
executar assim mesmo. Antivirus as vezes marcam programas empacotados com
PyInstaller por semelhanca, sem haver nada de errado.
"""

# O que vai ao lado do .exe, alem do LEIA: a interface e os recursos do
# programa, nas mesmas pastas de quando roda pelo Python.
PASTAS_DO_PROGRAMA = (os.path.join('interface', 'web'), 'recursos')


def montar_pasta(destino):
    """Coloca ao lado do exe a interface e os recursos do programa."""

    for pasta in PASTAS_DO_PROGRAMA:
        shutil.copytree(os.path.join(PASTA, pasta), os.path.join(destino, pasta),
                        dirs_exist_ok=True)

    # a versao vem do comum.py, e nao de um numero repetido aqui
    sys.path.insert(0, PASTA)
    from motor import comum

    with open(os.path.join(destino, 'LEIA.txt'), 'w', encoding='utf-8') as f:
        f.write(LEIA.format(versao=comum.VERSAO))

    # a licenca vai junto de cada copia, e nao so no repositorio
    shutil.copy2(os.path.join(PASTA, 'LICENSE'), os.path.join(destino, 'LICENCA.txt'))


# Coisas que o app cria ao rodar. Testar o pacote antes de enviar e o normal, e
# sem esta lista o zip levaria junto as preferencias, os precos e o catalogo de
# quem empacotou - inclusive a trava de execucao apontando para um PID que nao
# existe na maquina de destino.
NAO_DISTRIBUIR = {'ajustes.json', 'precos.json', 'precos-anterior.json',
                  'coordenadas.json', 'catalogo-padrao.json', '.bot_em_execucao'}
PASTAS_NAO_DISTRIBUIR = {'dados', 'registros', 'backups', '__pycache__'}


def zipar(pasta, destino):

    ignorados = []

    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:

        for raiz, subpastas, arquivos in os.walk(pasta):

            subpastas[:] = [d for d in subpastas if d not in PASTAS_NAO_DISTRIBUIR]

            for nome in arquivos:

                if nome in NAO_DISTRIBUIR:
                    ignorados.append(nome)
                    continue

                completo = os.path.join(raiz, nome)
                z.write(completo, os.path.join(
                    NOME_APP, os.path.relpath(completo, pasta)))

    if ignorados:
        print(f'  fora do zip (sao seus, nao de quem receber): '
              f'{", ".join(sorted(set(ignorados)))}')

    return os.path.getsize(destino)


def tamanho_da_pasta(pasta):

    return sum(
        os.path.getsize(os.path.join(raiz, f))
        for raiz, _, arquivos in os.walk(pasta)
        for f in arquivos)

#endregion


def main():

    print('=' * 64)
    print(f' EMPACOTANDO {NOME_APP}')
    print('=' * 64)

    import importlib.util

    if importlib.util.find_spec('PyInstaller') is None:
        print('\nPyInstaller nao esta instalado:\n')
        print('  pip install pyinstaller\n')
        return 1

    passo('1/5  compilando com o PyInstaller')

    if not compilar():
        print('\nO PyInstaller falhou - a saida dele esta acima.')
        return 1

    destino = os.path.join(PASTA, 'dist', NOME_APP)

    if ARQUIVO_UNICO:
        # em arquivo unico o exe sai solto em dist/; a pasta e montada em volta
        destino = os.path.join(PASTA, 'dist', NOME_APP + ' (app)')
        os.makedirs(destino, exist_ok=True)
        shutil.move(os.path.join(PASTA, 'dist', NOME_APP + '.exe'), destino)

    passo('2/5  copiando o Tesseract')

    if not preparar_tesseract(os.path.join(destino, 'tesseract')):
        return 1

    passo('3/5  testando o Tesseract empacotado')

    if not testar_tesseract(os.path.join(destino, 'tesseract')):
        print('\n  O OCR nao funcionou com os arquivos copiados. Sem isso o app')
        print('  abriria normalmente e leria tudo vazio na hora de escanear.')
        return 1

    passo('4/5  montando a pasta')

    montar_pasta(destino)

    print(f'  {tamanho_da_pasta(destino) / 1e6:.0f} MB em {destino}')

    passo('5/5  zipando')

    zip_final = os.path.join(PASTA, 'dist', f'{NOME_APP}.zip')
    tamanho = zipar(destino, zip_final)

    print(f'  {tamanho / 1e6:.0f} MB')

    print('\n' + '=' * 64)
    print(' PRONTO')
    print('=' * 64)
    print(f' Pasta : {destino}')
    print(f' Zip   : {zip_final}')
    print()
    print(' Para testar, rode o .exe DA PASTA dist: ele usa os arquivos de la.')
    print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
