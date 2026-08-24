################################
#                              #
#             TEMA             #
#                              #
################################

# As cores, em duas versoes: escura e clara.
#
# A PALETA E A DO BOT DE REFERENCIA, copiada de perto: fundo quase preto com um
# leve desvio para o roxo, superficies que sobem em degraus curtos, e um MAGENTA
# que aparece so em tres lugares - o titulo da pagina, a barra do item ativo na
# lateral, e a marca. Ele nunca vira botao.
#
# POR QUE O MAGENTA NAO E BOTAO. Numa tela onde um clique gasta prata, a cor mais
# forte tem de significar "voce esta aqui", e nao "clique aqui" - senao o olho e
# puxado para o lugar errado a cada troca de pagina. O bot de referencia faz
# exatamente isso, e e por isso que a tela dele parece calma tendo uma cor tao
# saturada.
#
# AS ACOES TEM CORES PROPRIAS, cada uma com um significado so:
#
#     roxo      comecar uma operacao longa (varrer, comprar, vender)
#     azul      salvar, confirmar o que nao custa prata
#     verde     criar - grupo, categoria
#     rosa      apagar, limpar
#     cinza     tudo o mais
#
# O vermelho fica reservado para "isto gasta prata de verdade". Um botao que
# gasta e um botao que apaga nao podem ter a mesma cor.
#
#
# OS NOMES ANTIGOS CONTINUAM VALENDO. `destaque` e apelido de `primario`, e
# `painel_topo` de `painel_alto`. As caixas de dialogo e o formulario foram
# escritos contra os nomes antigos e funcionam; renomear tudo seria mexer em
# codigo que nao esta em questao para ganhar consistencia de dicionario.
#
# Antes de alterar: python -m pyflakes tema.py

ESCURO = 'escuro'
CLARO = 'claro'

TEMAS = (ESCURO, CLARO)

ROTULO = {ESCURO: 'Escuro', CLARO: 'Claro'}

MARCA = '#D6409F'


def _completar(base):
    """Preenche os apelidos que o codigo antigo usa."""

    base['painel_topo'] = base['painel_alto']
    base['destaque'] = base['primario']
    base['destaque_alto'] = base['primario_alto']
    base['destaque_fundo'] = base['primario_fundo']
    base['texto_medio'] = base['texto']

    return base


PALETAS = {

    ESCURO: _completar({
        # --- superficies, do fundo para cima ---
        # Quase preto com um leve desvio para o roxo. Cinza puro ao lado de um
        # magenta saturado parece sujo; meio ponto de roxo no fundo faz os dois
        # pertencerem a mesma tela.
        'fundo':          '#17171D',
        'rodape':         '#1C1C24',
        'painel':         '#1F1F27',
        'painel_alto':    '#26262F',
        'borda':          '#2E2E3A',
        'borda_clara':    '#3C3C4A',

        # --- texto, em tres pesos ---
        'texto_forte':    '#E8E8EE',
        'texto':          '#A6A6B4',
        'texto_fraco':    '#6E6E7E',

        # --- acao: roxo comeca operacao longa ---
        'primario':       '#8B5CF6',
        'primario_alto':  '#A78BFA',
        'primario_fundo': '#2A2140',
        'sobre_primario': '#FFFFFF',

        # --- identidade: o magenta, e so ele ---
        'marca':          MARCA,

        # --- perigo: gasta prata de verdade ---
        'perigo':         '#E8256B',
        'perigo_alto':    '#F2568A',
        'perigo_fundo':   '#3A1526',
        'sobre_perigo':   '#FFFFFF',

        # --- estado ---
        'ok':             '#22A94E',
        'aviso':          '#E5B93C',
        'info':           '#2DD4BF',

        # --- as outras acoes, cada uma com um significado so ---
        'salvar':         '#2F6FED',
        'salvar_alto':    '#4C87F5',
        'criar':          '#22A94E',
        'criar_alto':     '#31C462',
        'limpar':         '#E8256B',
        'limpar_alto':    '#F2568A',
    }),

    CLARO: _completar({
        'fundo':          '#F7F7FA',
        'rodape':         '#EDEDF2',
        'painel':         '#FFFFFF',
        'painel_alto':    '#F1F1F6',
        'borda':          '#DCDCE4',
        'borda_clara':    '#C4C4D0',

        'texto_forte':    '#1B1B22',
        'texto':          '#4A4A58',
        'texto_fraco':    '#8A8A98',

        'primario':       '#7C3AED',
        'primario_alto':  '#6D28D9',
        'primario_fundo': '#EFE8FE',
        'sobre_primario': '#FFFFFF',

        'marca':          '#C0227F',

        'perigo':         '#D01159',
        'perigo_alto':    '#AC0E49',
        'perigo_fundo':   '#FCE8F0',
        'sobre_perigo':   '#FFFFFF',

        'ok':             '#1B8438',
        'aviso':          '#A5700A',
        'info':           '#0D9488',

        'salvar':         '#2563EB',
        'salvar_alto':    '#1D4ED8',
        'criar':          '#1B8438',
        'criar_alto':     '#146C2D',
        'limpar':         '#D01159',
        'limpar_alto':    '#AC0E49',
    }),
}


def escuro(nome):
    return nome != CLARO


def cores(nome):
    """A paleta daquele tema. Sempre uma copia - o COR do visual e mutavel."""

    return dict(PALETAS[nome if nome in PALETAS else ESCURO])


def tema_valido(nome):
    return nome in PALETAS
