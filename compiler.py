# compiler.py
# Compilador universal para BrickScript (Version Final y Depurada)
# Uso: python compiler.py <archivo_entrada.brick>

# CAMBIOS ACTIVIDAD 3 (Tetris remake): soporte de atributo COLOR en DEFINE SHAPE.

import sys
import re
import json

# --- NUEVO: color hexadecimal (#RGB o #RRGGBB) y color por defecto ---
PATRON_COLOR = r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b'
COLOR_POR_DEFECTO = '#00FFFF'

def lexer(codigo_fuente):
   # Un '#' seguido de un color valido NO es comentario; cualquier otro '#' si lo es. 
    codigo_fuente = re.sub(r'#(?![0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b).*', '', codigo_fuente)
    token_regex = PATRON_COLOR + r'#[0-9A-Fa-f]{6}\b|\b[A-Z_]+\b|\d+|[\[\](),:]'
    tokens = re.findall(token_regex, codigo_fuente)
    return tokens

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.posicion = 0
        # NUEVO: "colors" guarda el color de cada shape (retrocompatible: "shapes" no cambia)
        # NUEVO: "powerups" guarda el powerup en el shape
        self.ast = {"tipo_juego": None, "config": {}, "shapes": {}, "colors": {}, "events": {}, "powerups": {}}

    def parse(self):
        while self.posicion < len(self.tokens):
            token_actual = self.tokens[self.posicion]
            if token_actual == 'GAME_TYPE':
                self.parsear_tipo_juego()
            elif token_actual == 'GAME_GRID':
                self.parsear_grid()
            elif token_actual == 'DEFINE':
                if self.tokens[self.posicion + 1] == 'POWERUP':
                    self.parsear_powerup()
                else:
                    self.parsear_shape()
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
                                        if self.tokens[self.posicion] == ',': self.consumir(',')
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
            elif token_actual == 'ON':
                self.parsear_evento()
            else:
                self.posicion += 1
        return self.ast

    def consumir(self, token_esperado=None):
        if self.posicion < len(self.tokens):
            token = self.tokens[self.posicion]
            if token_esperado and token != token_esperado:
                raise Exception("Error de sintaxis: Se esperaba '" + token_esperado + "' pero se encontro '" + token + "'")
            self.posicion += 1
            return token
        if token_esperado:
            raise Exception("Error de sintaxis: Se esperaba '" + token_esperado + "' pero se llego al final del archivo.")
        return None

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
        # --- NUEVO: atributo opcional COLOR: #RRGGBB ---
        color = COLOR_POR_DEFECTO
        if self.posicion < len(self.tokens) and self.tokens[self.posicion] == 'COLOR':
            self.consumir('COLOR')
            self.consumir(':')
            color = self.consumir()
            if color is None or not re.match('^' + PATRON_COLOR + '$', color):
                raise Exception("Error de sintaxis: Se esperaba un color hexadecimal (#RRGGBB) en la figura '" + nombre_shape + "' pero se encontro '" + str(color) + "'")
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
                    if self.tokens[self.posicion] == ',': self.consumir(',')
                self.consumir(']')
                matriz.append(fila)
            estados.append(matriz)
        self.consumir('END')
        self.ast['shapes'][nombre_shape] = estados
        self.ast['colors'][nombre_shape] = color

    # --- FUNCION CORREGIDA ---
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
        tokens = lexer(codigo)
        parser = Parser(tokens)
        ast = parser.parse()
        generar_codigo(ast, archivo_salida)
        print "Compilacion exitosa! Archivo de juego creado en " + archivo_salida
    except Exception as e:
        print "\n!!! ERROR DE COMPILACION !!!"
        print str(e)
        sys.exit(1)