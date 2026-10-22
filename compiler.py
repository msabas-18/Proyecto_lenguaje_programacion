# compiler.py
# Compilador universal para BrickScript
# Uso: python compiler.py <archivo_entrada.brick>
#
# CAMBIOS ACTIVIDAD 3 (Tetris remake): soporte de atributo COLOR en DEFINE SHAPE.
# CAMBIOS SELECCION PONDERADA: soporte de atributo WEIGHT (entero >= 0) en DEFINE SHAPE.
#   WEIGHT es opcional (por defecto 1), asi los .brick antiguos siguen funcionando.
#
# CAMBIOS ACTIVIDAD 4 (Snake evolved): todo el codigo nuevo lleva el comentario "# ACT4".
#   - DEFINE SHAPE acepta FORM, PENALTY, COUNT y DURATION en las figuras SNAKE_BODY,
#     POISON_FRUIT, CLOUD y SHIELD_FRUIT (solo con GAME_TYPE SNAKE).
#   - Bloque nuevo DEFINE LEVELS ... END con DEFAULT_LEVEL, LEVEL_UP_SCORE y LEVEL <nombre>.
#   - Si un SNAKE no trae LEVELS se escribe solo el nivel BABY con los valores del Snake original.
#   - Los errores indican el numero de linea del .brick.
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

def lexer_con_lineas(codigo_fuente):
    # ACT4: igual que el lexer original pero recuerda la linea de cada token, para que los
    # errores digan en que linea del .brick esta el problema. Devuelve (tokens, lineas).
    # Un '#' seguido de un color valido NO es comentario; cualquier otro '#' si lo es.
    # ACT4: el numero admite signo (-?\d+) para poder rechazar un TICK negativo con un mensaje claro.
    token_regex = PATRON_COLOR + r'|\b[A-Z_]+\b|-?\d+|[\[\](),:]'
    tokens = []
    lineas = []
    for numero, linea in enumerate(codigo_fuente.splitlines()):
        linea = re.sub(r'#(?!(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b).*', '', linea)
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
        self.ast = {"tipo_juego": None, "config": {}, "shapes": {}, "colors": {}, "weights": {}, "events": {}, "powerups": {}}

    def parse(self):
        while self.posicion < len(self.tokens):
            token_actual = self.tokens[self.posicion]
            if token_actual == 'GAME_TYPE':
                self.parsear_tipo_juego()
            elif token_actual == 'GAME_GRID':
                self.parsear_grid()
            elif token_actual == 'DEFINE':
                if self.posicion + 1 < len(self.tokens) and self.tokens[self.posicion + 1] == 'POWERUP':
                    self.parsear_powerup()
                elif self.posicion + 1 < len(self.tokens) and self.tokens[self.posicion + 1] == 'LEVELS':
                    self.parsear_levels()  # ACT4
                else:
                    self.parsear_shape()
            elif token_actual == 'ON':
                self.parsear_evento()
            else:
                self.posicion += 1
        self.validar_pesos()
        self.completar_snake()  # ACT4: niveles por defecto (solo GAME_TYPE SNAKE)
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
            linea_clave = self.linea_de(self.posicion - 1)  # ACT4
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
                extras['color'] = valor  # ACT4
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
        linea_end = self.linea_de(self.posicion)  # ACT4
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
        parser = Parser(tokens, lineas)
        ast = parser.parse()
        generar_codigo(ast, archivo_salida)
        for aviso in parser.advertencias:  # ACT4
            print aviso
        print "Compilacion exitosa! Archivo de juego creado en " + archivo_salida
    except Exception as e:
        print "\n!!! ERROR DE COMPILACION !!!"
        print str(e)
        sys.exit(1)