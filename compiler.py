# compiler.py
# Compilador universal para BrickScript
# Uso: python compiler.py <archivo_entrada.brick>
#
# CAMBIOS ACTIVIDAD 3 (Tetris remake): soporte de atributo COLOR en DEFINE SHAPE.
# CAMBIOS SELECCION PONDERADA: soporte de atributo WEIGHT (entero >= 0) en DEFINE SHAPE.
#   WEIGHT es opcional (por defecto 1), asi los .brick antiguos siguen funcionando.
#
# CAMBIOS ACTIVIDAD 4 (Snake evolved): todo el codigo nuevo lleva el comentario "# ACT4:".
#   - DEFINE SHAPE acepta FORM, PENALTY, COUNT y DURATION en las figuras SNAKE_BODY,
#     POISON_FRUIT, CLOUD y SHIELD_FRUIT (solo con GAME_TYPE SNAKE).
#   - Bloque nuevo DEFINE LEVELS ... END con DEFAULT_LEVEL, LEVEL_UP_SCORE y LEVEL <nombre>.
#   - Si un SNAKE no trae LEVELS se escribe solo el nivel BABY con los valores del Snake original.
#   - Los errores indican el numero de linea del .brick.
#   - El lexer avisa (sin detener la compilacion) de las palabras escritas en minuscula, que ignora.
#   Todo lo nuevo es opcional: snake.brick, tetris.brick y tetris_remake.brick generan el mismo JSON de antes
#   (snake.brick solo agrega las claves default_level, level_order y levels con el nivel BABY).

import sys
import re
import json

# --- NUEVO: color hexadecimal (#RGB o #RRGGBB) y color por defecto ---
PATRON_COLOR = r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b'
COLOR_POR_DEFECTO = '#00FFFF'
# --- NUEVO: peso por defecto de una figura en la seleccion ponderada ---
PESO_POR_DEFECTO = 1

# ACT4: figuras especiales de Snake y los atributos nuevos que admite cada una
ATRIBUTOS_SNAKE = ('FORM', 'PENALTY', 'COUNT', 'DURATION')
ENTIDADES_SNAKE = {
    'SNAKE_BODY': ('COLOR', 'FORM'),
    'POISON_FRUIT': ('COLOR', 'PENALTY', 'COUNT'),
    'CLOUD': ('COLOR', 'COUNT'),
    'SHIELD_FRUIT': ('COLOR', 'DURATION'),
}
FORMAS_VALIDAS = ('RECTANGLE', 'CIRCULAR', 'TRIANGULAR')
# ACT4: niveles en el orden en que se suben (BABY -> ENTUSIASTA -> NYAN_CAT)
NIVELES_VALIDOS = ('BABY', 'ENTUSIASTA', 'NYAN_CAT')
NIVEL_POR_DEFECTO = 'BABY'
VENENO_VALIDOS = ('OFF', 'SUBTRACT', 'KILL')
CABEZAS_VALIDAS = ('NORMAL', 'CAT')
COLAS_VALIDAS = ('NORMAL', 'RAINBOW')
ATRIBUTOS_NIVEL = ('TICK', 'POISON', 'SHIELD', 'CLOUDS', 'HEAD', 'TAIL', 'SHIELD_DURATION')
# ACT4: etiquetas que cierran un LEVEL dentro de DEFINE LEVELS
CIERRAN_NIVEL = ('LEVEL', 'END', 'DEFAULT_LEVEL', 'LEVEL_UP_SCORE')
PASO_TICK_MS = 25   # el runtime avanza de 25 en 25 ms
# ACT4: valores del Snake original = nivel BABY (150 ms, sin veneno, nubes ni escudo)
NIVEL_BABY_ORIGINAL = {'tick': 150, 'poison': 'OFF', 'shield': False,
                       'clouds': False, 'head': 'NORMAL', 'tail': 'NORMAL'}

# ACT4: palabras con minusculas (el lenguaje solo usa MAYUSCULAS). El lexer las ignora igual que el
# original, pero ahora deja una advertencia con su linea para que un error de tipeo no pase desapercibido.
PATRON_MINUSCULAS = r'\b[A-Za-z_]*[a-z][A-Za-z_]*\b'
AVISOS_LEXER = []

TIPOS_TANQUE = ('PLAYER', 'ENEMY', 'BOSS')
FORMAS_TANQUE = ('RECTANGLE', 'SQUARE', 'CIRCULAR', 'TRIANGULAR')
OBJETIVOS_TANQUE = ('PLAYER', 'ENEMIES', 'BOSS')
IA_TANQUE = ('AGGRESSIVE', 'PATROL', 'STATIONARY')
ATRIBUTOS_TANQUE = ('TYPE', 'COLOR', 'HP', 'SPEED', 'DAMAGE', 'FIRE_RATE', 'FORM', 'TARGET', 'AI', 'POINTS')
ATRIBUTOS_BALA = ('TYPE', 'COLOR', 'DAMAGE', 'SPEED', 'SIZE')
ATRIBUTOS_MURO = ('COLOR', 'HP', 'DESTRUCTIBLE')
ATRIBUTOS_POWERUP_TANKS = ('TYPE', 'COLOR', 'HEAL', 'CHANCE')
ENTEROS_TANKS = {'HP': 1, 'SPEED': 1, 'DAMAGE': 1, 'FIRE_RATE': 1, 'SIZE': 1, 'HEAL': 1, 'CHANCE': 0, 'POINTS': 0}
ELECCIONES_TANKS = {'FORM': FORMAS_TANQUE, 'TARGET': OBJETIVOS_TANQUE, 'AI': IA_TANQUE}
PALABRAS_RESERVADAS_TANKS = ('END', 'ON', 'DEFINE', 'STATE', 'AT', 'BY', 'USING', 'IF')
EVENTOS_TANKS = ('START', 'TICK', 'KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT', 'KEY_SPACE',
                 'COLLISION_WALL', 'COLLISION_BULLET_WALL', 'COLLISION_BULLET_ENEMY',
                 'COLLISION_BULLET_PLAYER', 'COLLISION_BULLET_BOSS', 'COLLISION_PLAYER_ENEMY',
                 'COLLISION_PLAYER_POWERUP', 'DESTROY_ENEMY', 'DESTROY_BOSS', 'PLAYER_HIT',
                 'HAMMER_COLLECTED', 'GAME_OVER')
DIRECCIONES_TANKS = ('UP', 'DOWN', 'LEFT', 'RIGHT')
MOVILES_TANKS = ('PLAYER', 'ENEMY', 'BOSS')
TIRADORES_TANKS = ('PLAYER', 'ENEMIES', 'BOSS')
OBJETIVOS_DANIO_TANKS = ('PLAYER', 'ENEMY', 'BOSS', 'WALL')
GRID_TANKS_POR_DEFECTO = [20, 16]
ESTADO_TANQUE_POR_DEFECTO = [[0, 1, 0], [1, 1, 1], [1, 0, 1]]
ESTADO_JEFE_POR_DEFECTO = [[1, 1, 1, 1, 1], [1, 1, 1, 1, 1], [0, 1, 1, 1, 0], [0, 1, 0, 1, 0]]
ESTADO_MURO_POR_DEFECTO = [[1]]
ESTADO_POWERUP_TANKS_POR_DEFECTO = [[1, 1], [0, 1]]
TANQUE_POR_DEFECTO = {
    'PLAYER': {'color': '#20B2AA', 'hp': 100, 'speed': 1, 'damage': 20, 'fire_rate': 1,
               'form': 'RECTANGLE', 'target': None, 'ai': None, 'points': 0},
    'ENEMY': {'color': '#E74C3C', 'hp': 30, 'speed': 1, 'damage': 10, 'fire_rate': 3,
              'form': 'RECTANGLE', 'target': 'PLAYER', 'ai': 'AGGRESSIVE', 'points': 100},
    'BOSS': {'color': '#7D3C98', 'hp': 300, 'speed': 1, 'damage': 25, 'fire_rate': 2,
             'form': 'SQUARE', 'target': 'PLAYER', 'ai': 'AGGRESSIVE', 'points': 1000},
}
BALA_POR_DEFECTO = {'color': '#FFFF00', 'damage': 10, 'speed': 2, 'size': 1}
MURO_POR_DEFECTO = {'color': '#B5651D', 'hp': 40, 'destructible': True}
POWERUP_TANKS_POR_DEFECTO = {'color': '#FFD700', 'heal': 25, 'chance': 1}

def lexer_con_lineas(codigo_fuente):
    # ACT4: igual que el lexer original pero recuerda la linea de cada token, para que los
    # errores digan en que linea del .brick esta el problema. Devuelve (tokens, lineas).
    # Un '#' seguido de un color valido NO es comentario; cualquier otro '#' si lo es.
    # ACT4: el numero admite signo (-?\d+) para poder rechazar un TICK negativo con un mensaje claro.
    token_regex = PATRON_COLOR + r'|\b[A-Z_]+\b|-?\d+|[\[\](),:]'
    tokens = []
    lineas = []
    del AVISOS_LEXER[:]
    for numero, linea in enumerate(codigo_fuente.splitlines()):
        linea = re.sub(r'#(?!(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b).*', '', linea)
        # ACT4: se quitan los colores antes de buscar palabras en minuscula (#00ff00 es un color valido)
        for palabra in re.findall(PATRON_MINUSCULAS, re.sub(PATRON_COLOR, ' ', linea)):
            AVISOS_LEXER.append("Advertencia: se ignora la palabra '" + palabra + "' porque BrickScript solo usa MAYUSCULAS (linea " + str(numero + 1) + ")")
        for token in re.findall(token_regex, linea):
            tokens.append(token)
            lineas.append(numero + 1)
    return tokens, lineas


def lexer(codigo_fuente):
    # Se conserva la firma original: devuelve solo la lista de tokens.
    return lexer_con_lineas(codigo_fuente)[0]


class Parser:
    def __init__(self, tokens, lineas=None):
        self.tokens = tokens
        self.posicion = 0
        # ACT4: linea del .brick de cada token (opcional) y datos del bloque DEFINE LEVELS
        self.lineas = lineas
        self.advertencias = []
        self.niveles = None
        self.nivel_defecto = None
        self.linea_nivel_defecto = None
        self.subida_nivel = None
        # "colors" guarda el color de cada shape (retrocompatible: "shapes" no cambia)
        # "weights" guarda el peso de cada shape para la seleccion ponderada
        self.nombres_tanks = []
        self.tanques = {}
        self.orden_tanques = []
        self.balas = {}
        self.muros = {}
        self.puntajes = []
        self.referencias = []
        self.hay_spawn_jugador = False
        self.ast = {"tipo_juego": None, "config": {}, "shapes": {}, "colors": {}, "weights": {}, "events": {}, "powerups": {}}

    def parse(self):
        while self.posicion < len(self.tokens):
            token_actual = self.tokens[self.posicion]
            if token_actual == 'GAME_TYPE':
                self.parsear_tipo_juego()
            elif token_actual == 'GAME_GRID':
                self.parsear_grid()
            elif token_actual == 'DEFINE':
                if self.es_definicion_tanks():
                    self.parsear_definicion_tanks()
                elif self.posicion + 1 < len(self.tokens) and self.tokens[self.posicion + 1] == 'POWERUP':
                    self.parsear_powerup()
                elif self.posicion + 1 < len(self.tokens) and self.tokens[self.posicion + 1] == 'LEVELS':
                    self.parsear_levels()  # ACT4:
                else:
                    self.parsear_shape()
            elif token_actual == 'ON':
                self.parsear_evento()
            else:
                self.posicion += 1
        self.validar_pesos()
        self.completar_snake()  # ACT4: niveles por defecto (solo GAME_TYPE SNAKE)
        self.completar_tanks()
        return self.ast

    def validar_pesos(self):
        # Si hay figuras, al menos una debe tener peso > 0; si no, nunca saldria ninguna.
        pesos = self.ast['weights']
        if pesos and sum(pesos.values()) <= 0:
            raise Exception("Error semantico: todas las figuras tienen WEIGHT 0; al menos una debe tener un peso mayor que 0")

    def consumir(self, token_esperado=None):
        if self.posicion < len(self.tokens):
            token = self.tokens[self.posicion]
            if token_esperado and token != token_esperado:
                raise Exception("Error de sintaxis: Se esperaba '" + token_esperado + "' pero se encontro '" + token + "'" + self.donde())  # ACT4: linea
            self.posicion += 1
            return token
        if token_esperado:
            raise Exception("Error de sintaxis: Se esperaba '" + token_esperado + "' pero se llego al final del archivo." + self.donde())  # ACT4: linea
        return None

    # ACT4: ---- ayudas para indicar la linea del error y validar valores ----
    def linea_de(self, indice):
        # Linea del .brick del token numero 'indice' (si el archivo termino, la del ultimo token).
        if not self.lineas:
            return None
        if indice >= len(self.lineas):
            indice = len(self.lineas) - 1
        if indice < 0:
            return None
        return self.lineas[indice]

    def donde(self, linea=None):
        # Texto " (linea N)" para agregar al final de un mensaje de error.
        if linea is None:
            linea = self.linea_de(self.posicion)
        if linea is None:
            return ""
        return " (linea " + str(linea) + ")"

    def entero(self, valor, linea, descripcion, minimo):
        # Valida que 'valor' sea un entero >= minimo y lo devuelve como int.
        if valor is None or not re.match(r'^-?\d+$', valor):
            raise Exception("Error de sintaxis: Se esperaba un numero entero en " + descripcion +
                            " pero se encontro '" + str(valor) + "'" + self.donde(linea))
        n = int(valor)
        if n < minimo:
            if minimo == 1:
                limite = "mayor que cero"
            else:
                limite = "mayor o igual que " + str(minimo)
            raise Exception("Error semantico: " + descripcion + " debe ser " + limite +
                            " (se encontro " + valor + ")" + self.donde(linea))
        return n

    def elegir(self, valor, validos, linea, descripcion):
        # Valida que 'valor' sea una de las palabras permitidas.
        if valor not in validos:
            raise Exception("Error semantico: " + descripcion + " debe ser " + " | ".join(validos) +
                            " pero se encontro '" + str(valor) + "'" + self.donde(linea))
        return valor

    def parsear_tipo_juego(self):
        self.consumir('GAME_TYPE')
        self.ast['tipo_juego'] = self.consumir()

    def parsear_grid(self):
        self.consumir('GAME_GRID')
        self.consumir('(')
        ancho = int(self.consumir())
        self.consumir(',')
        alto = int(self.consumir())
        self.consumir(')')
        self.ast['config']['grid_size'] = [ancho, alto]

    def parsear_shape(self):
        self.consumir('DEFINE')
        self.consumir('SHAPE')
        nombre_shape = self.consumir()
        self.consumir(':')
        # ACT4: SNAKE_BODY, POISON_FRUIT, CLOUD y SHIELD_FRUIT son figuras especiales de Snake: se guardan
        # como diccionario con lo que escribio el programador (form, color, penalty, count, duration).
        es_entidad = self.ast['tipo_juego'] == 'SNAKE' and nombre_shape in ENTIDADES_SNAKE
        extras = {}
        # Atributos opcionales
        color = COLOR_POR_DEFECTO
        peso = PESO_POR_DEFECTO
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] in ('COLOR', 'WEIGHT') + ATRIBUTOS_SNAKE:  # ACT4: + atributos nuevos
            clave = self.consumir()
            linea_clave = self.linea_de(self.posicion - 1)  # ACT4:
            self.consumir(':')
            linea_valor = linea_clave  # ACT4: los errores de valor apuntan a la linea de la etiqueta
            valor = self.consumir()
            if clave in ATRIBUTOS_SNAKE or (es_entidad and clave == 'WEIGHT'):  # ACT4: atributos nuevos de Snake
                if not es_entidad or clave not in ENTIDADES_SNAKE[nombre_shape]:
                    if es_entidad:
                        permitidos = ", ".join(ENTIDADES_SNAKE[nombre_shape])
                    else:
                        permitidos = "solo existe en SNAKE_BODY, POISON_FRUIT, CLOUD y SHIELD_FRUIT con GAME_TYPE SNAKE"
                    raise Exception("Error semantico: El atributo " + clave + " no se puede usar en la figura '" + nombre_shape +
                                    "' (" + permitidos + ")" + self.donde(linea_clave))
                if clave == 'FORM':
                    extras['form'] = self.elegir(valor, FORMAS_VALIDAS, linea_valor, "FORM de la figura '" + nombre_shape + "'")
                elif clave == 'PENALTY':
                    extras['penalty'] = self.entero(valor, linea_valor, "PENALTY de la figura '" + nombre_shape + "'", 0)
                elif clave == 'COUNT':
                    extras['count'] = self.entero(valor, linea_valor, "COUNT de la figura '" + nombre_shape + "'", 0)
                else:
                    extras['duration'] = self.entero(valor, linea_valor, "DURATION de la figura '" + nombre_shape + "'", 1)
            elif clave == 'COLOR':
                if valor is None or not re.match('^' + PATRON_COLOR + '$', valor):
                    raise Exception("Error de sintaxis: Se esperaba un color hexadecimal (#RRGGBB) en la figura '" + nombre_shape + "' pero se encontro '" + str(valor) + "'" + self.donde(linea_valor))  # ACT4: linea
                color = valor
                extras['color'] = valor  # ACT4:
            else:
                if valor is None or not re.match(r'^\d+$', valor):
                    raise Exception("Error de sintaxis: Se esperaba un entero >= 0 como WEIGHT en la figura '" + nombre_shape + "' pero se encontro '" + str(valor) + "'" + self.donde(linea_valor))  # ACT4: linea
                peso = int(valor)
        # ACT4: estas figuras no tienen matriz de estados
        if es_entidad and self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'STATE':
            raise Exception("Error semantico: La figura '" + nombre_shape + "' no admite STATE; se define solo con " +
                            ", ".join(ENTIDADES_SNAKE[nombre_shape]) + self.donde())
        estados = []
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'STATE':
            self.consumir('STATE')
            self.consumir()
            self.consumir(':')
            matriz = []
            while self.posicion < len(self.tokens) and self.tokens[self.posicion] == '[':
                fila = []
                self.consumir('[')
                while self.tokens[self.posicion] != ']':
                    fila.append(int(self.consumir()))
                    if self.tokens[self.posicion] == ',':
                        self.consumir(',')
                self.consumir(']')
                matriz.append(fila)
            estados.append(matriz)
        linea_end = self.linea_de(self.posicion)  # ACT4:
        self.consumir('END')
        if es_entidad:  # ACT4: figura especial de Snake -> diccionario; no entra en colors ni weights
            if isinstance(self.ast['shapes'].get(nombre_shape), dict):
                raise Exception("Error semantico: La figura '" + nombre_shape + "' esta definida mas de una vez" + self.donde(linea_end))
            self.ast['shapes'][nombre_shape] = extras
            return
        self.ast['shapes'][nombre_shape] = estados
        self.ast['colors'][nombre_shape] = color
        self.ast['weights'][nombre_shape] = peso

    # ACT4: ---- bloque DEFINE LEVELS ----
    def parsear_levels(self):
        # DEFINE LEVELS:
        #   DEFAULT_LEVEL: BABY        (opcional)
        #   LEVEL_UP_SCORE: 50         (opcional; 0 = sin avance automatico)
        #   LEVEL <nombre>: TICK: n  POISON: .. SHIELD: .. CLOUDS: .. HEAD: .. TAIL: ..
        # END
        # Un LEVEL termina cuando empieza otro LEVEL o cuando llega el END del bloque.
        linea_bloque = self.linea_de(self.posicion)
        if self.ast['tipo_juego'] != 'SNAKE':
            raise Exception("Error semantico: DEFINE LEVELS solo se puede usar con GAME_TYPE SNAKE (declarado antes)" + self.donde(linea_bloque))
        if self.niveles is not None:
            raise Exception("Error semantico: DEFINE LEVELS esta definido mas de una vez" + self.donde(linea_bloque))
        self.consumir('DEFINE')
        self.consumir('LEVELS')
        self.consumir(':')
        self.niveles = {}
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] != 'END':
            clave = self.tokens[self.posicion]
            linea = self.linea_de(self.posicion)
            if clave == 'DEFAULT_LEVEL':
                self.consumir()
                self.consumir(':')
                linea_valor = linea  # linea de la etiqueta
                nombre = self.consumir()
                self.elegir(nombre, NIVELES_VALIDOS, linea_valor, "DEFAULT_LEVEL")
                self.nivel_defecto = nombre
                self.linea_nivel_defecto = linea_valor
            elif clave == 'LEVEL_UP_SCORE':
                self.consumir()
                self.consumir(':')
                linea_valor = linea  # linea de la etiqueta
                self.subida_nivel = self.entero(self.consumir(), linea_valor, "LEVEL_UP_SCORE", 0)
            elif clave == 'LEVEL':
                self.parsear_nivel()
            else:
                ayuda = ""
                if clave in ('ON', 'DEFINE'):
                    ayuda = " (falta el END que cierra DEFINE LEVELS?)"
                raise Exception("Error de sintaxis: Dentro de DEFINE LEVELS se esperaba DEFAULT_LEVEL, LEVEL_UP_SCORE o LEVEL " +
                                "pero se encontro '" + clave + "'" + ayuda + self.donde(linea))
        self.consumir('END')
        if not self.niveles:
            raise Exception("Error semantico: DEFINE LEVELS no tiene ningun LEVEL" + self.donde(linea_bloque))

    def parsear_nivel(self):
        self.consumir('LEVEL')
        linea_nombre = self.linea_de(self.posicion)
        nombre = self.consumir()
        if nombre is None or nombre not in NIVELES_VALIDOS:
            raise Exception("Error semantico: Nivel desconocido '" + str(nombre) + "'; los niveles validos son " +
                            ", ".join(NIVELES_VALIDOS) + self.donde(linea_nombre))
        if nombre in self.niveles:
            raise Exception("Error semantico: El nivel " + nombre + " esta definido mas de una vez" + self.donde(linea_nombre))
        self.consumir(':')
        cfg = dict(NIVEL_BABY_ORIGINAL)  # lo que no se escribe queda como en el Snake original
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] not in CIERRAN_NIVEL:
            linea_clave = self.linea_de(self.posicion)
            clave = self.consumir()
            if clave not in ATRIBUTOS_NIVEL:
                ayuda = ""
                if clave in ('ON', 'DEFINE'):
                    ayuda = " (falta el END que cierra DEFINE LEVELS?)"
                raise Exception("Error de sintaxis: En el nivel " + nombre + " se esperaba una de " + ", ".join(ATRIBUTOS_NIVEL) +
                                " pero se encontro '" + clave + "'" + ayuda + self.donde(linea_clave))
            self.consumir(':')
            linea_valor = linea_clave  # los errores de valor apuntan a la linea de la etiqueta
            valor = self.consumir()
            etiqueta = clave + " del nivel " + nombre
            if clave == 'TICK':
                etiqueta = etiqueta + " (en milisegundos, numero entero)"
            if clave == 'TICK':
                cfg['tick'] = self.entero(valor, linea_valor, etiqueta, 1)
                if cfg['tick'] % PASO_TICK_MS != 0:
                    redondeado = ((cfg['tick'] + PASO_TICK_MS - 1) // PASO_TICK_MS) * PASO_TICK_MS
                    self.advertencias.append("Advertencia: TICK del nivel " + nombre + " = " + str(cfg['tick']) + " ms no es multiplo de " +
                                             str(PASO_TICK_MS) + "; el juego lo redondeara a " + str(redondeado) + " ms" + self.donde(linea_valor))
            elif clave == 'POISON':
                cfg['poison'] = self.elegir(valor, VENENO_VALIDOS, linea_valor, etiqueta)
            elif clave == 'SHIELD':
                cfg['shield'] = self.elegir(valor, ('ON', 'OFF'), linea_valor, etiqueta) == 'ON'
            elif clave == 'CLOUDS':
                cfg['clouds'] = self.elegir(valor, ('ON', 'OFF'), linea_valor, etiqueta) == 'ON'
            elif clave == 'HEAD':
                cfg['head'] = self.elegir(valor, CABEZAS_VALIDAS, linea_valor, etiqueta)
            elif clave == 'TAIL':
                cfg['tail'] = self.elegir(valor, COLAS_VALIDAS, linea_valor, etiqueta)
            else:
                cfg['shield_duration'] = self.entero(valor, linea_valor, etiqueta, 1)
        self.niveles[nombre] = cfg

    def completar_snake(self):
        # ACT4: deja listas las claves de niveles en el JSON. Sin DEFINE LEVELS solo existe BABY con los
        # valores del Snake original (asi snake.brick corre igual que antes). BABY siempre existe.
        if self.ast['tipo_juego'] != 'SNAKE':
            return
        niveles = self.niveles
        if niveles is None:
            niveles = {}
        if NIVEL_POR_DEFECTO not in niveles:
            niveles[NIVEL_POR_DEFECTO] = dict(NIVEL_BABY_ORIGINAL)
        inicial = self.nivel_defecto or NIVEL_POR_DEFECTO
        if inicial not in niveles:
            raise Exception("Error semantico: DEFAULT_LEVEL " + inicial + " no esta definido con LEVEL dentro de DEFINE LEVELS" +
                            self.donde(self.linea_nivel_defecto))
        orden = [n for n in NIVELES_VALIDOS if n in niveles]
        shapes = self.ast['shapes']
        for n in orden:
            for activo, figura in ((niveles[n]['clouds'], 'CLOUD'), (niveles[n]['poison'] != 'OFF', 'POISON_FRUIT'),
                                   (niveles[n]['shield'], 'SHIELD_FRUIT')):
                if activo and not isinstance(shapes.get(figura), dict):
                    self.advertencias.append("Advertencia: el nivel " + n + " usa " + figura +
                                             " pero no hay DEFINE SHAPE " + figura + "; se usan los valores por defecto")
        self.ast['default_level'] = inicial
        self.ast['level_order'] = orden
        self.ast['levels'] = niveles
        if self.subida_nivel is not None:
            self.ast['level_up_score'] = self.subida_nivel

    def parsear_powerup(self):
        self.consumir('DEFINE')
        self.consumir('POWERUP')
        nombre = self.consumir()
        self.consumir(':')
        pu = {"estados": [], "color": "#ADD8E6", "efecto": None, "params": {}, "condiciones": []}
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] != 'END':
            clave = self.consumir()
            if clave == 'STATE':
                self.consumir()
                self.consumir(':')
                matriz = []
                while self.posicion < len(self.tokens) and self.tokens[self.posicion] == '[':
                    fila = []
                    self.consumir('[')
                    while self.tokens[self.posicion] != ']':
                        fila.append(int(self.consumir()))
                        if self.tokens[self.posicion] == ',':
                            self.consumir(',')
                    self.consumir(']')
                    matriz.append(fila)
                pu['estados'].append(matriz)
            else:
                self.consumir(':')
                if clave == 'COLOR':
                    pu['color'] = self.consumir()
                elif clave == 'EFFECT':
                    pu['efecto'] = self.consumir()
                elif clave == 'WHEN':
                    tipo = self.consumir()
                    pu['condiciones'].append([tipo, int(self.consumir())])
                else:
                    pu['params'][clave] = int(self.consumir())
        self.consumir('END')
        if not pu['estados']:
            raise Exception("Error: el POWERUP " + nombre + " no tiene ningun STATE")
        self.ast['powerups'][nombre] = pu

    def parsear_evento(self):
        if self.ast['tipo_juego'] == 'TANKS':
            self.parsear_evento_tanks()
            return
        self.consumir('ON')
        nombre_evento = 'ON_' + self.consumir()
        self.consumir(':')
        acciones = []
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] != 'END':
            verbo = self.consumir()

            # Si el comando es de una sola palabra, lo anadimos y continuamos
            if verbo == 'GAME_OVER':
                acciones.append({'accion': verbo, 'objeto': None, 'params': []})
                continue

            # Si no, parseamos el resto de la accion
            objeto = self.consumir()
            params = []
            if self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'AT':
                self.consumir('AT')
                if self.tokens[self.posicion] == 'RANDOM':
                    params.append(self.consumir())
                else:
                    self.consumir('(')
                    x = int(self.consumir())
                    self.consumir(',')
                    y = int(self.consumir())
                    self.consumir(')')
                    params.append([x, y])
            elif self.posicion < len(self.tokens) and self.tokens[self.posicion] not in ['END', 'ON', 'DEFINE', 'SPAWN', 'MOVE', 'ROTATE', 'INCREASE_SCORE', 'SET_DIRECTION', 'GROW', 'GAME_OVER']:
                params.append(self.consumir())
            acciones.append({'accion': verbo, 'objeto': objeto, 'params': params})
        self.consumir('END')
        self.ast['events'][nombre_evento] = acciones

    def es_definicion_tanks(self):
        if self.posicion + 1 >= len(self.tokens):
            return False
        siguiente = self.tokens[self.posicion + 1]
        if siguiente in ('TANK', 'BULLET', 'WALL'):
            return True
        return siguiente == 'POWERUP' and self.ast['tipo_juego'] == 'TANKS'

    def siguiente(self, descripcion):
        linea = self.linea_de(self.posicion)
        token = self.consumir()
        if token is None:
            raise Exception("Error de sintaxis: Se esperaba " + descripcion + " pero se llego al final del archivo." + self.donde(linea))
        return token, linea

    def identificador_tanks(self, descripcion):
        token, linea = self.siguiente(descripcion)
        if not re.match(r'^[A-Z_]+$', token) or token in PALABRAS_RESERVADAS_TANKS:
            raise Exception("Error de sintaxis: Se esperaba " + descripcion + " pero se encontro '" + token + "'" + self.donde(linea))
        return token, linea

    def elegir_siguiente(self, validos, descripcion):
        token, linea = self.siguiente(descripcion)
        return self.elegir(token, validos, linea, descripcion)

    def entero_siguiente(self, descripcion, minimo):
        token, linea = self.siguiente(descripcion)
        return self.entero(token, linea, descripcion, minimo)

    def leer_coordenadas_tanks(self):
        self.consumir('(')
        x = self.entero_siguiente("la coordenada X", 0)
        self.consumir(',')
        y = self.entero_siguiente("la coordenada Y", 0)
        linea = self.linea_de(self.posicion)
        self.consumir(')')
        grid = self.ast['config'].get('grid_size')
        if grid and (x >= grid[0] or y >= grid[1]):
            raise Exception("Error semantico: La coordenada (" + str(x) + ", " + str(y) + ") esta fuera de la cuadricula de " +
                            str(grid[0]) + "x" + str(grid[1]) + self.donde(linea))
        return [x, y]

    def convertir_valor_tanks(self, entidad, clave, valor, linea, tipos=None):
        etiqueta = clave + " de '" + entidad + "'"
        if clave in ENTEROS_TANKS:
            return self.entero(valor, linea, etiqueta, ENTEROS_TANKS[clave])
        if clave == 'COLOR':
            if not re.match('^' + PATRON_COLOR + '$', valor):
                raise Exception("Error de sintaxis: Se esperaba un color hexadecimal (#RRGGBB) en " + etiqueta +
                                " pero se encontro '" + valor + "'" + self.donde(linea))
            return valor
        if clave == 'TYPE':
            return self.elegir(valor, tipos, linea, etiqueta)
        if clave == 'DESTRUCTIBLE':
            return self.elegir(valor, ('ON', 'OFF'), linea, etiqueta) == 'ON'
        return self.elegir(valor, ELECCIONES_TANKS[clave], linea, etiqueta)

    def leer_estado_tanks(self, entidad):
        self.entero_siguiente("el numero de STATE de '" + entidad + "'", 1)
        self.consumir(':')
        matriz = []
        linea_estado = self.linea_de(self.posicion)
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] == '[':
            self.consumir('[')
            fila = []
            while True:
                valor, linea = self.siguiente("un 0 o un 1 en la matriz de '" + entidad + "'")
                if valor not in ('0', '1'):
                    raise Exception("Error de sintaxis: Se esperaba 0 o 1 en la matriz de '" + entidad +
                                    "' pero se encontro '" + valor + "'" + self.donde(linea))
                fila.append(int(valor))
                separador, linea = self.siguiente("',' o ']' en la matriz de '" + entidad + "'")
                if separador == ']':
                    break
                if separador != ',':
                    raise Exception("Error de sintaxis: Se esperaba ',' o ']' en la matriz de '" + entidad +
                                    "' pero se encontro '" + separador + "'" + self.donde(linea))
            matriz.append(fila)
        if not matriz:
            raise Exception("Error de sintaxis: El STATE de '" + entidad + "' no tiene ninguna fila" + self.donde(linea_estado))
        if len(set([len(f) for f in matriz])) != 1:
            raise Exception("Error semantico: Las filas del STATE de '" + entidad + "' no tienen la misma longitud" + self.donde(linea_estado))
        if not sum([sum(f) for f in matriz]):
            raise Exception("Error semantico: El STATE de '" + entidad + "' no tiene ninguna celda con 1" + self.donde(linea_estado))
        return matriz

    def leer_atributos_tanks(self, entidad, permitidos, con_estado):
        atributos = {}
        estados = []
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] != 'END':
            linea = self.linea_de(self.posicion)
            clave = self.consumir()
            if clave == 'STATE' and con_estado:
                estados.append(self.leer_estado_tanks(entidad))
                continue
            if clave not in permitidos:
                ayuda = ""
                if clave in ('ON', 'DEFINE'):
                    ayuda = " (falta el END que cierra la definicion?)"
                validos = list(permitidos)
                if con_estado:
                    validos.append('STATE')
                raise Exception("Error de sintaxis: En '" + entidad + "' se esperaba una de " + ", ".join(validos) +
                                " pero se encontro '" + str(clave) + "'" + ayuda + self.donde(linea))
            if clave in atributos:
                raise Exception("Error semantico: El atributo " + clave + " esta repetido en '" + entidad + "'" + self.donde(linea))
            self.consumir(':')
            valor, linea_valor = self.siguiente("el valor de " + clave)
            atributos[clave] = (valor, linea_valor)
        self.consumir('END')
        return atributos, estados

    def copiar_matriz(self, matriz):
        return [list(fila) for fila in matriz]

    def parsear_definicion_tanks(self):
        clase = self.tokens[self.posicion + 1]
        linea = self.linea_de(self.posicion)
        if self.ast['tipo_juego'] != 'TANKS':
            raise Exception("Error semantico: DEFINE " + clase + " solo se puede usar con GAME_TYPE TANKS (declarado antes)" + self.donde(linea))
        self.consumir('DEFINE')
        self.consumir(clase)
        nombre, linea_nombre = self.identificador_tanks("el nombre de " + clase)
        if nombre in self.nombres_tanks:
            raise Exception("Error semantico: '" + nombre + "' esta definido mas de una vez" + self.donde(linea_nombre))
        self.nombres_tanks.append(nombre)
        self.consumir(':')
        if clase == 'TANK':
            self.parsear_tanque(nombre, linea_nombre)
        elif clase == 'BULLET':
            self.parsear_bala(nombre)
        elif clase == 'WALL':
            self.parsear_muro(nombre)
        else:
            self.parsear_powerup_tanks(nombre)

    def parsear_tanque(self, nombre, linea_nombre):
        atributos, estados = self.leer_atributos_tanks(nombre, ATRIBUTOS_TANQUE, True)
        if 'TYPE' not in atributos:
            raise Exception("Error semantico: El tanque '" + nombre + "' no tiene TYPE (" + " | ".join(TIPOS_TANQUE) + ")" + self.donde(linea_nombre))
        tipo = self.convertir_valor_tanks(nombre, 'TYPE', atributos['TYPE'][0], atributos['TYPE'][1], TIPOS_TANQUE)
        tanque = dict(TANQUE_POR_DEFECTO[tipo])
        for clave in atributos:
            if clave != 'TYPE':
                tanque[clave.lower()] = self.convertir_valor_tanks(nombre, clave, atributos[clave][0], atributos[clave][1])
        tanque['type'] = tipo
        if not estados:
            estados = [self.copiar_matriz(ESTADO_JEFE_POR_DEFECTO if tipo == 'BOSS' else ESTADO_TANQUE_POR_DEFECTO)]
        tanque['estados'] = estados
        self.tanques[nombre] = tanque
        self.orden_tanques.append(nombre)

    def parsear_bala(self, nombre):
        atributos, estados = self.leer_atributos_tanks(nombre, ATRIBUTOS_BALA, False)
        bala = dict(BALA_POR_DEFECTO)
        for clave in atributos:
            if clave == 'TYPE':
                self.convertir_valor_tanks(nombre, clave, atributos[clave][0], atributos[clave][1], ('BULLET',))
            else:
                bala[clave.lower()] = self.convertir_valor_tanks(nombre, clave, atributos[clave][0], atributos[clave][1])
        bala['type'] = 'BULLET'
        self.balas[nombre] = bala

    def parsear_muro(self, nombre):
        atributos, estados = self.leer_atributos_tanks(nombre, ATRIBUTOS_MURO, True)
        muro = dict(MURO_POR_DEFECTO)
        for clave in atributos:
            muro[clave.lower()] = self.convertir_valor_tanks(nombre, clave, atributos[clave][0], atributos[clave][1])
        if not estados:
            estados = [self.copiar_matriz(ESTADO_MURO_POR_DEFECTO)]
        muro['estados'] = estados
        self.muros[nombre] = muro

    def parsear_powerup_tanks(self, nombre):
        atributos, estados = self.leer_atributos_tanks(nombre, ATRIBUTOS_POWERUP_TANKS, True)
        powerup = dict(POWERUP_TANKS_POR_DEFECTO)
        for clave in atributos:
            if clave == 'TYPE':
                self.convertir_valor_tanks(nombre, clave, atributos[clave][0], atributos[clave][1], ('HAMMER',))
            else:
                powerup[clave.lower()] = self.convertir_valor_tanks(nombre, clave, atributos[clave][0], atributos[clave][1])
        if not estados:
            estados = [self.copiar_matriz(ESTADO_POWERUP_TANKS_POR_DEFECTO)]
        powerup['type'] = 'HAMMER'
        powerup['estados'] = estados
        powerup['efecto'] = 'HEAL'
        powerup['params'] = {'HEAL': powerup['heal'], 'CHANCE': powerup['chance']}
        powerup['condiciones'] = []
        self.ast['powerups'][nombre] = powerup

    def parsear_evento_tanks(self):
        linea_evento = self.linea_de(self.posicion)
        self.consumir('ON')
        nombre, linea_nombre = self.siguiente("el nombre del evento")
        clave_evento = 'ON_' + nombre
        if nombre == 'TARGET_SCORE':
            puntaje = self.entero_siguiente("la puntuacion de TARGET_SCORE", 0)
            if self.puntajes:
                raise Exception("Error semantico: Solo puede existir un evento ON TARGET_SCORE (ya se definio el de " +
                                str(self.puntajes[0]['score']) + ")" + self.donde(linea_nombre))
            clave_evento = 'ON_TARGET_SCORE_' + str(puntaje)
            self.puntajes.append({'score': puntaje, 'event': clave_evento})
        elif nombre not in EVENTOS_TANKS:
            raise Exception("Error semantico: Evento desconocido '" + nombre + "'; los eventos validos son TARGET_SCORE, " +
                            ", ".join(EVENTOS_TANKS) + self.donde(linea_nombre))
        if clave_evento in self.ast['events']:
            raise Exception("Error semantico: El evento " + nombre + " esta definido mas de una vez" + self.donde(linea_nombre))
        self.consumir(':')
        acciones = []
        while self.posicion < len(self.tokens) and self.tokens[self.posicion] != 'END':
            acciones.append(self.parsear_accion_tanks())
        self.consumir('END')
        if not acciones:
            raise Exception("Error semantico: El evento " + nombre + " no tiene ninguna accion" + self.donde(linea_evento))
        self.ast['events'][clave_evento] = acciones

    def referenciar_tanks(self, clase, descripcion):
        nombre, linea = self.identificador_tanks(descripcion)
        self.referencias.append((clase, nombre, linea))
        return nombre

    def destino_tanks(self, permite_random):
        self.consumir('AT')
        if permite_random and self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'RANDOM':
            return self.consumir()
        return self.leer_coordenadas_tanks()

    def accion_spawn_tanks(self):
        objeto = self.elegir_siguiente(('PLAYER', 'ENEMY', 'WALL', 'POWERUP', 'BOSS'), "lo que se crea con SPAWN")
        if objeto == 'PLAYER':
            self.hay_spawn_jugador = True
            return {'accion': 'SPAWN', 'objeto': objeto, 'params': [self.destino_tanks(False)]}
        if objeto == 'ENEMY' and self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'RANDOM':
            return {'accion': 'SPAWN', 'objeto': objeto, 'params': [self.consumir()]}
        nombre = self.referenciar_tanks(objeto, "el nombre de la definicion en SPAWN " + objeto)
        return {'accion': 'SPAWN', 'objeto': objeto, 'params': [nombre, self.destino_tanks(objeto == 'POWERUP')]}

    def accion_move_tanks(self):
        objeto = self.elegir_siguiente(MOVILES_TANKS + ('BULLETS',), "lo que se mueve con MOVE")
        if objeto == 'BULLETS':
            return {'accion': 'MOVE', 'objeto': objeto, 'params': [self.elegir_siguiente(('FORWARD',), "la direccion de MOVE BULLETS")]}
        direccion = self.elegir_siguiente(DIRECCIONES_TANKS + ('FORWARD',), "la direccion de MOVE " + objeto)
        return {'accion': 'MOVE', 'objeto': objeto, 'params': [direccion]}

    def accion_fire_tanks(self):
        objeto = self.elegir_siguiente(TIRADORES_TANKS, "quien dispara con FIRE")
        self.consumir('USING')
        bala = self.referenciar_tanks('BULLET', "el nombre del proyectil en FIRE " + objeto)
        return {'accion': 'FIRE', 'objeto': objeto, 'params': [bala]}

    def valor_con_simbolo_tanks(self, simbolo, descripcion):
        token, linea = self.siguiente(descripcion)
        if token == simbolo:
            return token
        return self.entero(token, linea, descripcion, 1)

    def accion_tanks_simple(self, verbo):
        if verbo == 'ROTATE':
            return {'accion': verbo, 'objeto': self.elegir_siguiente(('PLAYER',), "lo que rota con ROTATE"), 'params': []}
        if verbo == 'DAMAGE':
            objeto = self.elegir_siguiente(OBJETIVOS_DANIO_TANKS, "el objetivo de DAMAGE")
            self.consumir('BY')
            return {'accion': verbo, 'objeto': objeto, 'params': [self.valor_con_simbolo_tanks('BULLET_DAMAGE', "el dano de DAMAGE " + objeto)]}
        if verbo == 'HEAL':
            objeto = self.elegir_siguiente(('PLAYER',), "el objetivo de HEAL")
            self.consumir('BY')
            return {'accion': verbo, 'objeto': objeto, 'params': [self.valor_con_simbolo_tanks('POWERUP_VALUE', "la curacion de HEAL")]}
        if verbo == 'INCREASE_SCORE':
            return {'accion': verbo, 'objeto': str(self.valor_con_simbolo_tanks('ENEMY_POINTS', "los puntos de INCREASE_SCORE")), 'params': []}
        if verbo == 'DESTROY':
            return {'accion': verbo, 'objeto': self.elegir_siguiente(OBJETIVOS_DANIO_TANKS + ('POWERUP',), "lo que se destruye con DESTROY"), 'params': []}
        if verbo == 'VICTORY':
            return {'accion': verbo, 'objeto': None, 'params': []}
        if verbo == 'GAME_OVER':
            if self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'IF':
                self.consumir('IF')
                self.consumir('PLAYER')
                self.consumir('HP_ZERO')
                return {'accion': 'GAME_OVER_IF', 'objeto': 'PLAYER', 'params': ['HP_ZERO']}
            return {'accion': verbo, 'objeto': None, 'params': []}
        self.consumir('PLAYER')
        self.consumir('INVULNERABLE')
        self.consumir(':')
        return {'accion': verbo, 'objeto': 'PLAYER', 'params': ['INVULNERABLE', self.elegir_siguiente(('ON', 'OFF'), "el valor de INVULNERABLE")]}

    def parsear_accion_tanks(self):
        linea = self.linea_de(self.posicion)
        verbo = self.consumir()
        if verbo == 'SPAWN':
            return self.accion_spawn_tanks()
        if verbo == 'MOVE':
            return self.accion_move_tanks()
        if verbo == 'FIRE':
            return self.accion_fire_tanks()
        if verbo in ('ROTATE', 'DAMAGE', 'HEAL', 'INCREASE_SCORE', 'DESTROY', 'VICTORY', 'GAME_OVER', 'SET'):
            return self.accion_tanks_simple(verbo)
        ayuda = ""
        if verbo in ('ON', 'DEFINE'):
            ayuda = " (falta el END que cierra el evento?)"
        raise Exception("Error de sintaxis: Accion desconocida '" + str(verbo) + "'" + ayuda + self.donde(linea))

    def completar_tanks(self):
        if self.ast['tipo_juego'] != 'TANKS':
            return
        tanques = self.tanques
        jugadores = [n for n in self.orden_tanques if tanques[n]['type'] == 'PLAYER']
        enemigos = [n for n in self.orden_tanques if tanques[n]['type'] == 'ENEMY']
        jefes = [n for n in self.orden_tanques if tanques[n]['type'] == 'BOSS']
        if len(jugadores) != 1:
            raise Exception("Error semantico: Debe existir exactamente un tanque TYPE: PLAYER (se encontraron " + str(len(jugadores)) + ")")
        if not enemigos:
            raise Exception("Error semantico: Debe existir al menos un tanque TYPE: ENEMY")
        if len(jefes) != 1:
            raise Exception("Error semantico: Debe existir exactamente un tanque TYPE: BOSS (se encontraron " + str(len(jefes)) + ")")
        if not self.balas:
            raise Exception("Error semantico: Debe existir al menos una definicion DEFINE BULLET")
        for clase, nombre, linea in self.referencias:
            if clase == 'ENEMY':
                existe = nombre in enemigos
            elif clase == 'BOSS':
                existe = nombre in jefes
            elif clase == 'WALL':
                existe = nombre in self.muros
            elif clase == 'POWERUP':
                existe = nombre in self.ast['powerups']
            else:
                existe = nombre in self.balas
            if not existe:
                raise Exception("Error semantico: '" + nombre + "' no corresponde a ninguna definicion de tipo " + clase +
                                " (se usa en un evento)" + self.donde(linea))
        if 'grid_size' not in self.ast['config']:
            self.ast['config']['grid_size'] = list(GRID_TANKS_POR_DEFECTO)
        self.advertir_tanks(enemigos, jefes[0])
        self.ast['tanks'] = tanques
        self.ast['bullets'] = self.balas
        self.ast['walls'] = self.muros
        self.ast['tank_roles'] = {'player': jugadores[0], 'enemies': enemigos, 'boss': jefes[0]}
        self.ast['target_scores'] = self.puntajes

    def advertir_tanks(self, enemigos, jefe):
        eventos = self.ast['events']
        if not self.hay_spawn_jugador:
            self.advertencias.append("Advertencia: ningun evento crea al jugador con SPAWN PLAYER")
        aparece = False
        for puntaje in self.puntajes:
            for accion in eventos[puntaje['event']]:
                if accion['accion'] == 'SPAWN' and accion['objeto'] == 'BOSS':
                    aparece = True
        if not aparece:
            self.advertencias.append("Advertencia: ningun ON TARGET_SCORE crea al jefe final con SPAWN BOSS; el jefe nunca aparecera")
        victoria = False
        for accion in eventos.get('ON_DESTROY_BOSS', []):
            if accion['accion'] == 'VICTORY':
                victoria = True
        if not victoria:
            self.advertencias.append("Advertencia: ON DESTROY_BOSS no tiene VICTORY; el jugador no podra ganar")
        celdas = lambda nombre: sum([sum(f) for f in self.tanques[nombre]['estados'][0]])
        matriz_jefe = self.tanques[jefe]['estados'][0]
        alto_jefe, ancho_jefe = len(matriz_jefe), len(matriz_jefe[0])
        dimensiones_enemigos = []
        for nombre in enemigos:
            matriz_enemigo = self.tanques[nombre]['estados'][0]
            dimensiones_enemigos.append((len(matriz_enemigo), len(matriz_enemigo[0])))
        mayor_alto = max([d[0] for d in dimensiones_enemigos]) if dimensiones_enemigos else 0
        mayor_ancho = max([d[1] for d in dimensiones_enemigos]) if dimensiones_enemigos else 0
        if enemigos and (celdas(jefe) <= max([celdas(n) for n in enemigos]) or
                         alto_jefe <= mayor_alto or ancho_jefe <= mayor_ancho):
            self.advertencias.append("Advertencia: la matriz del jefe '" + jefe +
                                     "' deberia ser mas grande en alto, ancho y celdas ocupadas que la de los enemigos")
        if self.ast['powerups'] and not sum([p['chance'] for p in self.ast['powerups'].values()]):
            self.advertencias.append("Advertencia: todos los POWERUP tienen CHANCE 0")


def generar_codigo(ast, archivo_salida):
    with open(archivo_salida, 'w') as f:
        json.dump(ast, f, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Uso: python compiler.py <archivo_entrada.brick>"
        sys.exit(1)
    archivo_entrada = sys.argv[1]
    archivo_salida = archivo_entrada.replace('.brick', '.json')
    print "Compilando " + archivo_entrada + "..."
    try:
        with open(archivo_entrada, 'r') as f:
            codigo = f.read()
        tokens, lineas = lexer_con_lineas(codigo)  # ACT4: el lexer tambien devuelve la linea de cada token
        for aviso in AVISOS_LEXER:  # ACT4: advertencias del lexer (palabras en minuscula)
            print aviso
        parser = Parser(tokens, lineas)
        ast = parser.parse()
        generar_codigo(ast, archivo_salida)
        for aviso in parser.advertencias:  # ACT4:
            print aviso
        print "Compilacion exitosa! Archivo de juego creado en " + archivo_salida
    except Exception as e:
        print "\n!!! ERROR DE COMPILACION !!!"
        print str(e)
        sys.exit(1)
