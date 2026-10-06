"""
Ideia geral:
- O GLFW só cria a janela e avisa dos eventos do mouse.

- Tudo que aparece na tela está no array "framebuffer": uma lista de bytes
  com 3 bytes (vermelho, verde, azul) para cada pixel da janela.

- Os algoritmos (linha, círculo, balde...) só mudam esse array,
  através de put_pixel / get_pixel.

- A cada quadro, o OpenGL só copia o array inteiro para a tela (glDrawPixels).

"""

import math   # sqrt do raio do círculo

import glfw

from OpenGL.GL import (
    glClear, glPixelZoom, glRasterPos2f, glDrawPixels,
    GL_COLOR_BUFFER_BIT, GL_RGB, GL_UNSIGNED_BYTE,
)

# ---------------------------------------------------------------------------
# Tamanhos e cores
# ---------------------------------------------------------------------------
LARGURA = 800                    # largura da janela e do canvas, em pixels
ALTURA_CANVAS = 600              # altura da área de desenho (fixa: 800x600)
BARRA = 84                       # altura da barra de ferramentas (no topo)
ALTURA = BARRA + ALTURA_CANVAS   # altura total da janela (barra + canvas)

# Cores no formato (R, G, B), cada valor de 0 a 255.
PRETO = (0, 0, 0)
BRANCO = (255, 255, 255)
VERMELHO = (255, 0, 0)
VERDE = (0, 255, 0)
AZUL = (0, 0, 255)
AMARELO = (255, 255, 0)
CIANO = (0, 255, 255)
MAGENTA = (255, 0, 255)

# As 8 cores que aparecem na paleta (a ordem é a ordem dos botões na barra).
PALETA = [PRETO, BRANCO, VERMELHO, VERDE, AZUL, AMARELO, CIANO, MAGENTA]
# Cor que a borracha pinta e que o botão "Novo" usa para limpar o canvas.
COR_FUNDO = BRANCO

# Cores só da interface (barra e botões).
CINZA_CLARO = (240, 240, 240)    # fundo de um botão normal
CINZA = (210, 210, 210)          # fundo da barra
CINZA_ESCURO = (100, 100, 100)   # bordas dos botões e linha de separação
AZUL_CLARO = (180, 210, 255)     # fundo do botão selecionado
AZUL_SELECAO = (0, 90, 200)      # borda do botão/cor selecionado

# ---------------------------------------------------------------------------
# Framebuffer
# A linha 0 é o topo da janela (igual ao mouse do GLFW, que tem o y
# crescendo para baixo).
# As primeiras BARRA linhas são a barra; o canvas começa na linha BARRA.
# ---------------------------------------------------------------------------
# bytearray = lista de bytes que pode ser alterada.
# Tamanho: LARGURA * ALTURA pixels, 3 bytes cada (R, G, B).
framebuffer = bytearray(LARGURA * ALTURA * 3)


def escrever(x, y, cor):
    """Escreve um pixel sem conferir limites (só uso quando já sei que cabe)."""
    # Posição do pixel (x, y) no array:
    #   y * LARGURA   -> pula as linhas de cima (cada linha tem LARGURA pixels)
    #   + x           -> anda x pixels dentro da linha
    #   * 3           -> cada pixel ocupa 3 bytes
    i = (y * LARGURA + x) * 3
    framebuffer[i] = cor[0]       # vermelho
    framebuffer[i + 1] = cor[1]   # verde
    framebuffer[i + 2] = cor[2]   # azul


def put_pixel(x, y, cor):
    """Pinta um pixel do CANVAS. Fora do canvas (ou sobre a barra) não faz nada."""
    # Só pinta se estiver dentro da janela E abaixo da barra (y >= BARRA).
    # Isso impede que as ferramentas desenhem por cima da barra, e que
    # linhas/círculos que saem da tela causem erro de índice.
    if 0 <= x < LARGURA and BARRA <= y < ALTURA:
        escrever(x, y, cor)


def get_pixel(x, y):
    """Lê a cor de um pixel do canvas. Fora do canvas devolve None."""
    if 0 <= x < LARGURA and BARRA <= y < ALTURA:
        i = (y * LARGURA + x) * 3                      # mesma fórmula de escrever()
        return (framebuffer[i], framebuffer[i + 1], framebuffer[i + 2])
    return None   # o flood fill usa esse None como "parede" nas bordas do canvas


def limpar():
    """Botão Novo: pinta o canvas inteiro com a cor de fundo."""
    # Índice do primeiro byte do canvas (pula as BARRA linhas da barra).
    inicio_canvas = BARRA * LARGURA * 3
    # bytes(COR_FUNDO) vira 3 bytes (255, 255, 255); multiplicar repete essa
    # sequência uma vez para cada pixel do canvas. A atribuição com [x:]
    # troca o conteúdo de uma vez só, sem precisar de um laço.
    framebuffer[inicio_canvas:] = bytes(COR_FUNDO) * (LARGURA * ALTURA_CANVAS)


def mostrar_tela():
    """Copia o framebuffer para a janela. É chamada a cada quadro."""
    glClear(GL_COLOR_BUFFER_BIT)     # limpa a tela antes de desenhar
    # O OpenGL usa coordenadas de -1 a 1. (-1, 1) é o canto superior esquerdo.
    glRasterPos2f(-1, 1)             # a imagem começa a ser colocada aí...
    # ...e como o OpenGL normalmente desenha de baixo para cima, o zoom -1 em y
    # inverte isso, para a nossa linha 0 (topo) ficar mesmo no topo.
    glPixelZoom(1, -1)
    # Envia o array: largura, altura, formato RGB, 1 byte por componente.
    glDrawPixels(LARGURA, ALTURA, GL_RGB, GL_UNSIGNED_BYTE, bytes(framebuffer))


# ---------------------------------------------------------------------------
# Algoritmos de desenho (só usam put_pixel / get_pixel)
# ---------------------------------------------------------------------------
def pincel(x, y, cor, esp):
    """Pinta um quadrado de lado 'esp' em volta de (x, y)."""
    # esp = espessura (1, 3 ou 5). r = "raio" do quadrado:
    # esp 1 -> r = 0 (só o pixel), esp 3 -> r = 1 (3x3), esp 5 -> r = 2 (5x5).
    r = esp // 2
    for dy in range(-r, r + 1):          # dy, dx = deslocamento em relação ao centro
        for dx in range(-r, r + 1):
            put_pixel(x + dx, y + dy, cor)


def linha(x0, y0, x1, y1, cor, esp):
    """Linha reta pelo algoritmo de Bresenham (todos os octantes)."""
    # (x0, y0) = ponto atual, começa no início da linha e vai andando.
    # (x1, y1) = ponto final.
    #
    # Ideia: a cada passo escolhemos o pixel mais próximo da reta ideal,
    # usando só somas e comparações de números inteiros.
    dx = abs(x1 - x0)           # distância horizontal total (sempre positiva)
    dy = -abs(y1 - y0)          # distância vertical total, de propósito NEGATIVA
    sx = 1 if x0 < x1 else -1   # sentido em x: 1 = para a direita, -1 = esquerda
    sy = 1 if y0 < y1 else -1   # sentido em y: 1 = para baixo, -1 = para cima
    erro = dx + dy              # quanto o pixel atual se afasta da reta ideal

    while True:
        pincel(x0, y0, cor, esp)             # pinta o pixel atual
        if x0 == x1 and y0 == y1:            # chegou no fim da linha
            break
        e2 = 2 * erro                        # erro dobrado (evita usar frações)
        if e2 >= dy:          # o erro pede um passo em x
            erro += dy
            x0 += sx
        if e2 <= dx:          # o erro pede um passo em y
            erro += dx
            y0 += sy
        # Os dois 'if' são separados de propósito: numa diagonal os dois
        # acontecem no mesmo passo (anda em x e em y). Em linhas retas só um.
        # Como usamos dx, dy, sx e sy, o mesmo código serve para qualquer
        # direção (todos os octantes).


def retangulo(x0, y0, x1, y1, cor, esp, cheio):
    """Retângulo com cantos opostos (x0, y0) e (x1, y1)."""
    # O usuário pode arrastar em qualquer direção, então descobrimos qual
    # é o canto de menor e de maior coordenada.
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)

    if cheio:
        # Preenchido: pinta linha por linha, pixel por pixel.
        for y in range(ymin, ymax + 1):
            for x in range(xmin, xmax + 1):
                put_pixel(x, y, cor)
    else:
        # Vazado: 4 linhas ligando os cantos (topo, direita, base, esquerda).
        # Aqui a espessura (esp) é usada. No preenchido ela não importa.
        linha(xmin, ymin, xmax, ymin, cor, esp)
        linha(xmax, ymin, xmax, ymax, cor, esp)
        linha(xmax, ymax, xmin, ymax, cor, esp)
        linha(xmin, ymax, xmin, ymin, cor, esp)


def circulo(cx, cy, x1, y1, cor, esp, cheio):
    """
    Círculo pelo algoritmo do ponto médio.
    O centro é (cx, cy) e o raio é a distância até (x1, y1).
    Calcula só 1/8 do círculo e repete nos outros 7 pedaços por simetria.
    """
    # cx, cy = centro (onde o mouse foi apertado).
    # x1, y1 = onde o mouse está agora; só serve para medir o raio.
    # raio = distância entre os dois pontos (Pitágoras), arredondada para baixo.
    raio = int(math.sqrt((x1 - cx) ** 2 + (y1 - cy) ** 2))

    # (x, y) = ponto do arco que estamos calculando, relativo ao centro.
    # Começa no topo do círculo, (0, raio), e anda até a diagonal (x == y).
    x = 0
    y = raio
    # d = variável de decisão: diz se o ponto do meio entre dois candidatos
    # está dentro ou fora do círculo. Valor inicial vem da conta do algoritmo.
    d = 1 - raio

    while x <= y:    # só o arco de 45 graus; o resto vem por simetria
        if cheio:
            # Cada par de pontos simétricos vira uma linha horizontal pintada.
            # xi = posição horizontal do pixel que está sendo pintado.
            for xi in range(cx - x, cx + x + 1):
                put_pixel(xi, cy + y, cor)
                put_pixel(xi, cy - y, cor)
            for xi in range(cx - y, cx + y + 1):
                put_pixel(xi, cy + x, cor)
                put_pixel(xi, cy - x, cor)
        else:
            # Simetria de 8 pontos: um ponto (x, y) do arco gera mais 7,
            # trocando x e y de lugar e/ou os sinais.
            pincel(cx + x, cy + y, cor, esp)
            pincel(cx - x, cy + y, cor, esp)
            pincel(cx + x, cy - y, cor, esp)
            pincel(cx - x, cy - y, cor, esp)
            pincel(cx + y, cy + x, cor, esp)
            pincel(cx - y, cy + x, cor, esp)
            pincel(cx + y, cy - x, cor, esp)
            pincel(cx - y, cy - x, cor, esp)

        # Anda um pixel em x e decide se y continua ou diminui 1.
        x += 1
        if d < 0:
            # ponto do meio dentro do círculo: mantém y
            d = d + 2 * x + 1
        else:
            # ponto do meio fora do círculo: y desce um pixel
            y -= 1
            d = d + 2 * (x - y) + 1


def flood_fill(x, y, nova_cor):
    """Balde de tinta: flood fill 4-conectado usando uma pilha (sem recursão)."""
    # (x, y) = pixel clicado, onde o preenchimento começa.
    # nova_cor = cor com que vamos pintar.
    # cor_antiga = cor da região clicada. É ela que vamos substituir.
    cor_antiga = get_pixel(x, y)
    if cor_antiga is None or cor_antiga == nova_cor:
        # Se a cor já é a mesma, pintar não mudaria nada e o laço abaixo
        # nunca terminaria, então voltamos logo.
        return                      # clicou fora, ou a cor já é a mesma

    # pilha = lista de pixels que ainda precisam ser visitados.
    # pop() tira sempre o último que entrou (por isso é uma pilha).
    pilha = [(x, y)]
    while len(pilha) > 0:
        x, y = pilha.pop()
        # Se o pixel não tem mais a cor antiga, ele já foi pintado,
        # é de outra cor (contorno) ou está fora do canvas (None).
        if get_pixel(x, y) != cor_antiga:
            continue                # já foi pintado (ou é outra cor)
        put_pixel(x, y, nova_cor)
        # "4-conectado": empilha os 4 vizinhos (direita, esquerda, baixo, cima).
        # Diagonais não contam, por isso o preenchimento não vaza por
        # contornos finos desenhados na diagonal.
        pilha.append((x + 1, y))
        pilha.append((x - 1, y))
        pilha.append((x, y + 1))
        pilha.append((x, y - 1))


# ---------------------------------------------------------------------------
# Salvar (formato PPM: um cabeçalho de texto + os bytes RGB do canvas)
# ---------------------------------------------------------------------------
def salvar(nome_arquivo):
    arquivo = open(nome_arquivo, "wb")     # "wb" = escrever em modo binário
    # Cabeçalho do PPM: "P6" (RGB binário), largura e altura, e o valor
    # máximo de cada cor (255). Cada parte separada por quebra de linha.
    arquivo.write(b"P6\n800 600\n255\n")
    # Depois vêm os bytes RGB dos pixels, linha por linha. Pulamos a barra
    # (BARRA * LARGURA * 3 bytes), então só o canvas é salvo.
    arquivo.write(framebuffer[BARRA * LARGURA * 3:])   # só o canvas
    arquivo.close()


# ---------------------------------------------------------------------------
# Estado do programa
# Estas variáveis guardam "o que está selecionado agora" e mudam durante
# a execução (por isso as funções que as alteram usam 'global').
# ---------------------------------------------------------------------------
# Nomes das ferramentas, na MESMA ordem dos botões da barra (da esquerda
# para a direita). Os nomes são usados nos 'if' para saber o que fazer.
FERRAMENTAS = ["lapis", "borracha", "linha", "retangulo vazado",
               "retangulo cheio", "circulo vazado", "circulo cheio", "balde"]
# Ferramentas que são "formas": o usuário arrasta do clique até o mouse atual
# e vê uma pré-visualização enquanto arrasta.
FORMAS = ["linha", "retangulo vazado", "retangulo cheio",
          "circulo vazado", "circulo cheio"]
ESPESSURAS = [1, 3, 5]           # fino, médio, grosso (em pixels)

ferramenta = "lapis"             # ferramenta selecionada agora
cor_atual = PRETO                # cor selecionada agora
espessura = 1                    # espessura selecionada agora

desenhando = False               # True enquanto o botão do mouse está apertado
ultimo = (0, 0)                  # última posição do mouse (lápis e borracha)
inicio = (0, 0)                  # onde o mouse foi apertado (formas)
copia = b""                      # cópia da tela no clique (para a pré-visualização)


# ---------------------------------------------------------------------------
# Barra de ferramentas (desenhada direto no framebuffer)
# Layout (cada botão tem 32x32):
#   linha de cima (y = 8):  8 ferramentas | 3 espessuras | Novo | Salvar
#   linha de baixo (y = 46): 8 cores
# Os números do layout (8, 38, 330, 470, 512...) são posições em pixels
# escolhidas à mão. Se mudar um, precisa mudar também em clicar_barra().
# ---------------------------------------------------------------------------
def ui_retangulo(x, y, largura, altura, cor):
    """Retângulo preenchido da interface. (x, y) é o canto superior esquerdo."""
    # xx, yy = pixel que está sendo pintado agora (dois 'x' e 'y' para não
    # confundir com os parâmetros). Usa 'escrever' direto: a barra fica numa
    # região onde put_pixel não deixa pintar.
    for yy in range(y, y + altura):
        for xx in range(x, x + largura):
            escrever(xx, yy, cor)


def ui_borda(x, y, largura, altura, cor, grossura):
    """Só a moldura de um retângulo, com a grossura dada, para dentro."""
    ui_retangulo(x, y, largura, grossura, cor)                        # topo
    ui_retangulo(x, y + altura - grossura, largura, grossura, cor)    # base
    ui_retangulo(x, y, grossura, altura, cor)                         # esquerda
    ui_retangulo(x + largura - grossura, y, grossura, altura, cor)    # direita


def ui_circulo(cx, cy, raio, cor, cheio):
    """Círculo simples só para os ícones (não é o algoritmo do trabalho)."""
    # Testa todos os pixels do quadrado em volta e pinta os que estão na
    # distância certa do centro. d = distância ao quadrado (dx² + dy²),
    # assim não precisa de raiz quadrada.
    for dy in range(-raio, raio + 1):
        for dx in range(-raio, raio + 1):
            d = dx * dx + dy * dy
            if cheio:
                if d <= raio * raio:                  # dentro do círculo
                    escrever(cx + dx, cy + dy, cor)
            else:
                # só o anel: dentro do círculo, mas fora do círculo menor
                if (raio - 1) * (raio - 1) < d <= raio * raio:
                    escrever(cx + dx, cy + dy, cor)


def botao(x, y, selecionado):
    """Desenha o quadro de um botão 32x32. O selecionado fica azul e destacado."""
    if selecionado:
        ui_retangulo(x, y, 32, 32, AZUL_CLARO)
        ui_borda(x, y, 32, 32, AZUL_SELECAO, 3)
    else:
        ui_retangulo(x, y, 32, 32, CINZA_CLARO)
        ui_borda(x, y, 32, 32, CINZA_ESCURO, 1)


def icone_ferramenta(nome, x, y):
    """Desenha o ícone de uma ferramenta dentro do botão que começa em (x, y)."""
    # 'nome' é um dos nomes da lista FERRAMENTAS. Os números somados a x e y
    # posicionam o desenho dentro do botão de 32x32.
    if nome == "lapis":
        for i in range(16):         # i = passo ao longo da diagonal
            ui_retangulo(x + 8 + i, y + 24 - i, 2, 2, PRETO)
    elif nome == "borracha":
        ui_retangulo(x + 7, y + 11, 18, 10, (240, 150, 150))   # rosa
        ui_borda(x + 7, y + 11, 18, 10, PRETO, 1)
    elif nome == "linha":
        for i in range(18):         # diagonal fina, 1 pixel por passo
            ui_retangulo(x + 7 + i, y + 25 - i, 1, 1, PRETO)
    elif nome == "retangulo vazado":
        ui_borda(x + 7, y + 9, 18, 14, PRETO, 2)
    elif nome == "retangulo cheio":
        ui_retangulo(x + 7, y + 9, 18, 14, PRETO)
    elif nome == "circulo vazado":
        ui_circulo(x + 16, y + 16, 9, PRETO, False)    # centro do botão, raio 9
    elif nome == "circulo cheio":
        ui_circulo(x + 16, y + 16, 9, PRETO, True)
    elif nome == "balde":
        ui_retangulo(x + 8, y + 12, 16, 14, AZUL)      # corpo do balde
        ui_borda(x + 8, y + 12, 16, 14, PRETO, 1)
        ui_retangulo(x + 12, y + 7, 8, 1, PRETO)       # alça
        ui_retangulo(x + 12, y + 7, 1, 5, PRETO)
        ui_retangulo(x + 19, y + 7, 1, 5, PRETO)


def desenhar_barra():
    """Redesenha a barra inteira. Chamada no início e após cada clique nela."""
    # fundo e linha de separação
    ui_retangulo(0, 0, LARGURA, BARRA, CINZA)
    ui_retangulo(0, BARRA - 1, LARGURA, 1, CINZA_ESCURO)

    # ferramentas: 8 botões, um a cada 38 pixels (32 do botão + 6 de espaço)
    for i in range(len(FERRAMENTAS)):          # i = índice do botão (0 a 7)
        x = 8 + i * 38                         # 8 = margem da esquerda
        botao(x, 8, ferramenta == FERRAMENTAS[i])    # destaca se for a atual
        icone_ferramenta(FERRAMENTAS[i], x, 8)

    # espessuras: uma barrinha com a grossura de cada opção
    for i in range(len(ESPESSURAS)):           # i = índice da espessura (0 a 2)
        x = 330 + i * 38                       # começam em x = 330
        botao(x, 8, espessura == ESPESSURAS[i])
        ui_retangulo(x + 6, 8 + 16 - ESPESSURAS[i] // 2, 20, ESPESSURAS[i], PRETO)

    # Novo (folha em branco), botão em x = 470
    botao(470, 8, False)
    ui_retangulo(470 + 9, 8 + 6, 14, 20, BRANCO)
    ui_borda(470 + 9, 8 + 6, 14, 20, PRETO, 1)

    # Salvar (disquete), botão em x = 512
    botao(512, 8, False)
    ui_retangulo(512 + 7, 8 + 7, 18, 18, (60, 60, 160))
    ui_retangulo(512 + 12, 8 + 7, 8, 5, (220, 220, 220))     # parte de cima
    ui_retangulo(512 + 10, 8 + 15, 12, 10, (235, 235, 235))  # etiqueta

    # paleta de cores: 8 quadrados de 30x30, um a cada 36 pixels, na linha de baixo
    for i in range(len(PALETA)):               # i = índice da cor (0 a 7)
        x = 8 + i * 36
        ui_retangulo(x, 46, 30, 30, PALETA[i])
        if cor_atual == PALETA[i]:
            ui_borda(x, 46, 30, 30, AZUL_SELECAO, 3)    # borda azul = cor atual
        else:
            ui_borda(x, 46, 30, 30, CINZA_ESCURO, 1)


def clicar_barra(x, y):
    """Descobre qual botão foi clicado, pela posição do mouse."""
    # 'global' é necessário porque vamos ALTERAR essas variáveis de estado.
    global ferramenta, espessura, cor_atual

    if 8 <= y < 40:                                   # linha de cima
        # i = em qual "casa" de 38 pixels o clique caiu (0 = primeira ferramenta).
        # (x - 8) tira a margem da esquerda; // 38 é divisão inteira.
        i = (x - 8) // 38
        # 0 <= i < 8: existe um botão ali.
        # (x - 8) % 38 < 32: o resto da divisão diz onde caiu dentro da casa;
        # se for menor que 32, foi no botão; senão foi no espaço entre botões.
        if 0 <= i < 8 and (x - 8) % 38 < 32:
            ferramenta = FERRAMENTAS[i]

        # j = índice da espessura clicada (mesma ideia, começando em x = 330)
        j = (x - 330) // 38
        if 0 <= j < 3 and (x - 330) % 38 < 32:
            espessura = ESPESSURAS[j]

        if 470 <= x < 502:                            # Novo (botão de 32 pixels)
            limpar()

        if 512 <= x < 544:                            # Salvar (botão de 32 pixels)
            salvar("desenho.ppm")
            print("Salvo em desenho.ppm")

    elif 46 <= y < 76:                                # linha de baixo
        # k = índice da cor clicada (casas de 36 pixels, quadrado de 30)
        k = (x - 8) // 36
        if 0 <= k < 8 and (x - 8) % 36 < 30:
            cor_atual = PALETA[k]

    desenhar_barra()      # atualiza o destaque do que está selecionado


# ---------------------------------------------------------------------------
# Eventos do mouse
# ---------------------------------------------------------------------------
def desenhar_forma(x0, y0, x1, y1):
    """Desenha a forma escolhida entre o ponto inicial e o atual."""
    # (x0, y0) = onde o mouse foi apertado; (x1, y1) = onde está agora.
    # Escolhe o algoritmo conforme a ferramenta selecionada.
    if ferramenta == "linha":
        linha(x0, y0, x1, y1, cor_atual, espessura)
    elif ferramenta == "retangulo vazado":
        retangulo(x0, y0, x1, y1, cor_atual, espessura, False)
    elif ferramenta == "retangulo cheio":
        retangulo(x0, y0, x1, y1, cor_atual, espessura, True)
    elif ferramenta == "circulo vazado":
        circulo(x0, y0, x1, y1, cor_atual, espessura, False)
    elif ferramenta == "circulo cheio":
        circulo(x0, y0, x1, y1, cor_atual, espessura, True)


def ao_clicar(janela, botao_mouse, acao, mods):
    """Chamada quando um botão do mouse é apertado ou solto."""
    # O GLFW chama esta função sozinho (callback) e passa 4 informações:
    #   janela       = a janela onde ocorreu (precisamos dela para ler o mouse)
    #   botao_mouse  = qual botão: esquerdo, direito ou do meio
    #   acao         = glfw.PRESS (apertou) ou glfw.RELEASE (soltou)
    #   mods         = teclas como Shift/Ctrl seguradas (não usamos, mas o GLFW
    #                  exige que a função aceite esse parâmetro)
    global desenhando, ultimo, inicio, copia

    if botao_mouse != glfw.MOUSE_BUTTON_LEFT:      # ignora o botão direito/meio
        return

    if acao == glfw.RELEASE:          # soltou o botão
        desenhando = False
        return

    # apertou o botão: descobre onde o mouse está (valores decimais, por isso int)
    x, y = glfw.get_cursor_pos(janela)
    x = int(x)
    y = int(y)

    if y < BARRA:                     # clicou na barra de ferramentas
        clicar_barra(x, y)
        return

    # A partir daqui o clique foi no canvas.
    desenhando = True
    if ferramenta == "balde":
        flood_fill(x, y, cor_atual)
        desenhando = False            # o balde é um clique só, não tem arrasto
    elif ferramenta in FORMAS:
        inicio = (x, y)               # guarda onde a forma começa
        copia = bytes(framebuffer)    # guarda a tela antes de desenhar a forma
        desenhar_forma(x, y, x, y)
    else:                         # lápis ou borracha
        # A borracha é igual ao lápis, só que pinta com a cor do fundo.
        cor = COR_FUNDO if ferramenta == "borracha" else cor_atual
        ultimo = (x, y)           # ponto de partida para a próxima linha
        pincel(x, y, cor, espessura)


def ao_mover(janela, x, y):
    """Chamada toda vez que o mouse se mexe (arrasto = mexer com botão apertado)."""
    # x, y = nova posição do mouse (decimais, vindos do GLFW).
    global ultimo
    if not desenhando:      # mouse só passeando, sem botão apertado
        return

    x = int(x)
    y = int(y)

    if ferramenta in FORMAS:
        # Pré-visualização: restaura a tela como estava no clique (apagando
        # a forma desenhada no movimento anterior) e desenha a forma de novo
        # até a posição atual. O 'framebuffer[:]' troca o conteúdo sem criar
        # outro objeto, então a variável continua a mesma.
        framebuffer[:] = copia        # volta a tela ao que era antes da forma
        desenhar_forma(inicio[0], inicio[1], x, y)
    else:                         # lápis ou borracha
        cor = COR_FUNDO if ferramenta == "borracha" else cor_atual
        # O mouse "pula" vários pixels entre dois eventos; ligar o ponto
        # anterior ao atual com uma linha (Bresenham) evita falhas no traço.
        linha(ultimo[0], ultimo[1], x, y, cor, espessura)
        ultimo = (x, y)


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    if not glfw.init():                     # inicia o GLFW
        raise RuntimeError("Falha ao iniciar o GLFW")

    glfw.window_hint(glfw.RESIZABLE, glfw.FALSE)    # janela de tamanho fixo
    # create_window(largura, altura, título, monitor, janela_compartilhada)
    # Os dois None significam: modo janela (sem tela cheia) e sem compartilhar.
    janela = glfw.create_window(LARGURA, ALTURA, "Mini Paint", None, None)
    if not janela:
        glfw.terminate()
        raise RuntimeError("Falha ao criar a janela")

    glfw.make_context_current(janela)   # diz ao OpenGL em qual janela desenhar
    glfw.swap_interval(1)               # sincroniza com o monitor (evita gastar CPU)

    # Registra as nossas funções para o GLFW chamar quando houver eventos.
    glfw.set_mouse_button_callback(janela, ao_clicar)   # apertar/soltar botão
    glfw.set_cursor_pos_callback(janela, ao_mover)      # mexer o mouse

    limpar()            # canvas começa branco
    desenhar_barra()    # desenha a barra pela primeira vez

    # Laço principal: repete até o usuário fechar a janela.
    while not glfw.window_should_close(janela):
        mostrar_tela()                  # copia o framebuffer para a tela
        glfw.swap_buffers(janela)       # exibe o que foi desenhado
        glfw.poll_events()              # processa eventos (chama ao_clicar/ao_mover)

    glfw.terminate()


# Só roda main() se o arquivo for executado diretamente (python paint.py),
# e não se ele for importado por outro arquivo.
if __name__ == "__main__":
    main()