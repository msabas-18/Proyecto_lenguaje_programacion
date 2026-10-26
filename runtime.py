# -*- coding: utf-8 -*-
# runtime.py (VERSION CON INTERFAZ GRAFICA USANDO Tkinter y caracteres ASCII unicamente)
#
# CAMBIOS ACTIVIDAD 3 (Tetris remake): el color de cada pieza se lee del JSON ("colors")
# en lugar de estar fijo en el codigo. Si el JSON no trae colores (juegos viejos) se usa
# el color por defecto, por lo que los .json antiguos siguen funcionando.
#
# CAMBIOS ACTIVIDAD 4 (Snake evolved): niveles BABY/ENTUSIASTA/NYAN_CAT, formas CIRCULAR/TRIANGULAR,
# frutas venenosas, nubes, power-up "No Morir" con temporizador y panel de nivel. Todo el codigo
# nuevo lleva el comentario "# ACT4:". Sin "levels" en el JSON el Snake se comporta como el original.

import sys
import json
import time
import math  # ACT4: para dibujar la estrella de la fruta de escudo
import random
# Tkinter es la libreria GUI estandar de Python, compatible con 2.7
import Tkinter as tk
import tkMessageBox # Necesario para el GAME OVER
# Quitamos os y msvcrt ya que la GUI maneja el dibujo y el input
# import os
# import msvcrt 

# NUEVO: color por defecto de una pieza si el .brick no define COLOR
COLOR_PIEZA_DEFECTO = '#00FFFF'

# ACT4: (Snake evolved): valores por defecto. Si el JSON no trae "levels" el juego usa
# el nivel BABY con estos valores, que reproducen el Snake original.
SNAKE_NIVEL_DEFECTO = {'tick': 150, 'poison': 'OFF', 'shield': False, 'clouds': False,
                       'head': 'NORMAL', 'tail': 'NORMAL'}
SNAKE_ORDEN_NIVELES = ['BABY', 'ENTUSIASTA', 'NYAN_CAT']
SNAKE_ENTIDADES_DEFECTO = {
    'poison': {'color': '#8A2BE2', 'penalty': 10, 'count': 1},
    'cloud': {'color': '#DDDDDD', 'count': 6},
    'shield': {'color': '#FFD700', 'duration': 8},
}
SNAKE_ESPERA_ESCUDO = 6   # segundos que pasan antes de que reaparezca la fruta de escudo
SNAKE_COLORES_ARCOIRIS = ['#FF0000', '#FF9900', '#FFFF00', '#33FF00', '#00CCFF', '#6633FF']


def _minusculas(d):
    # ACT4: pasa las claves de un diccionario a minusculas ("FORM" y "form" valen igual)
    resultado = {}
    for k, v in d.items():
        resultado[str(k).lower()] = v
    return resultado


def _es_si(valor):
    # ACT4: acepta true/false, 1/0 o "ON"/"OFF" para las banderas del nivel
    if isinstance(valor, basestring):
        return valor.strip().upper() in ('ON', 'TRUE', 'YES', 'SI', '1')
    return bool(valor)


def _aclarar(color, factor=0.4):
    # ACT4: mezcla un color #RRGGBB con blanco (para que la cabeza se distinga del cuerpo)
    try:
        if len(color) == 4:
            color = '#' + color[1] * 2 + color[2] * 2 + color[3] * 2
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except (ValueError, TypeError):
        return color
    r, g, b = [int(v + (255 - v) * factor) for v in (r, g, b)]
    return '#%02X%02X%02X' % (r, g, b)


class Juego:
    def __init__(self, datos_juego):
        self.datos_juego = datos_juego
        self.tipo_juego = self.datos_juego.get('tipo_juego', 'TETRIS')
        config = self.datos_juego.get('config', {})
        self.ancho = config.get('grid_size', [10, 20])[0]
        self.alto = config.get('grid_size', [10, 20])[1]
        self.grid = [[0 for _ in range(self.ancho)] for _ in range(self.alto)]
        self.puntuacion = 0
        self.juego_terminado = False
        
        # ACT4: paso del game_loop en segundos. Snake usa 25 ms (los TICK de los niveles pueden ser
        # multiplos de 25 ms); Tetris sigue con 50 ms como antes.
        self.paso_loop = 0.025 if self.tipo_juego == 'SNAKE' else 0.05
        # ACT4: con pasos de 25 ms la suma de decimales puede quedar en 0.1499999; la tolerancia lo evita.
        # Tetris usa 0 para conservar exactamente su temporizacion anterior.
        self.tolerancia_tick = 1e-9 if self.tipo_juego == 'SNAKE' else 0.0

        # --- Configuracion de la GUI ---
        self.root = tk.Tk()
        self.root.title("BrickScript - " + self.tipo_juego)
        # Configurar la accion al cerrar la ventana ('X' de la barra de titulo)
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_ventana)
        
        self.taman_celda = 25 # Pixeles por celda
        self.ancho_canvas = self.ancho * self.taman_celda
        self.alto_canvas = self.alto * self.taman_celda
        
        # Canvas para dibujar el juego
        self.canvas = tk.Canvas(self.root, width=self.ancho_canvas, height=self.alto_canvas, bg='#111111')
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)

        # Marco lateral para la puntuacion y controles
        self.marco_score = tk.Frame(self.root, width=150, height=self.alto_canvas, bg='#222222')
        self.marco_score.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        self.label_score = tk.Label(self.marco_score, text="PUNTUACION\n0", bg='#222222', fg='white', font=('Consolas', 16, 'bold'))
        self.label_score.pack(pady=40, padx=10)
        
        # Nota: Se ha eliminado 'Q: Salir' de los controles en pantalla
        self.label_controles = tk.Label(self.marco_score, text="CONTROLES\nFlechas: Mover/Rotar", bg='#222222', fg='gray', font=('Consolas', 10))
        self.label_controles.pack(pady=20, padx=10)

        # Configurar eventos de teclado. Usamos <Key> para capturar cualquier tecla
        self.root.bind('<Key>', self.manejar_input_gui)
        
        if self.tipo_juego == 'TETRIS':
            self.pieza_actual = None
            self.pieza_color = COLOR_PIEZA_DEFECTO  # NUEVO: color de la pieza activa
            self.pieza_x, self.pieza_y, self.pieza_rotacion = 0, 0, 0
            self.velocidad_gravedad = 0.4
            self.velocidad_base = self.velocidad_gravedad
            self.pieza_color = '#00FFFF'
            self.pieza_powerup = None
            self.piezas_lentas = 0
            self.slow_div = 2
            self.powerups = self.datos_juego.get('powerups', {})
            self.contadores = {}
            for nombre in self.powerups:
                self.contadores[nombre] = {'LINES_CLEARED': 0, 'PIECES_SPAWNED': 0, 'ROTATIONS': 0}

        if self.tipo_juego == 'SNAKE':
            self.serpiente_cuerpo = []
            self.serpiente_direccion = (1, 0)
            self.posicion_comida = None
            self.velocidad_gravedad = 0.15
            # ACT4: configuracion de niveles / entidades y panel lateral
            self.snake_cargar_config()
            if self.snake_multinivel:
                self.label_controles.config(text="CONTROLES\nFlechas: Mover\n1/2/3: Nivel")
                self.label_nivel = tk.Label(self.marco_score, text="NIVEL\n", bg='#222222', fg='#00FFFF', font=('Consolas', 12, 'bold'))
                self.label_nivel.pack(pady=10, padx=10)
                self.label_escudo = tk.Label(self.marco_score, text="", bg='#222222', fg='#FFD700', font=('Consolas', 12, 'bold'))
                self.label_escudo.pack(pady=10, padx=10)
        
        self.timer_gravedad = 0
        self.ejecutar_evento('ON_START')
        # ACT4: el nivel se aplica despues de ON_START porque ahi aparece la serpiente
        if self.tipo_juego == 'SNAKE':
            self.snake_aplicar_nivel(self.snake_nivel_inicial)
        self.timer_id = None # Para controlar el loop de Tkinter

    def run(self):
        # Inicia el ciclo principal de juego de Tkinter
        self.root.after(50, self.game_loop) 
        self.root.mainloop() 

    def game_loop(self):
        if self.juego_terminado:
            self.mostrar_game_over()
            return

        # Logica de TICK/Gravedad
        # El loop se ejecuta cada 50ms (0.05 segundos)
        self.timer_gravedad += self.paso_loop  # ACT4: antes 0.05 fijo 
        if self.timer_gravedad + self.tolerancia_tick >= self.velocidad_gravedad:  # ACT4: tolerancia de decimales (solo Snake)
            self.timer_gravedad = 0
            self.ejecutar_evento('ON_TICK')

        # ACT4: manejador de estados (vence el escudo, reaparece la fruta, sube de nivel)
        if self.tipo_juego == 'SNAKE':
            self.snake_actualizar_estado()

        self.dibujar()

        # Programa el siguiente ciclo de juego
        self.timer_id = self.root.after(int(self.paso_loop * 1000), self.game_loop)  # ACT4: antes 50
        
    def cerrar_ventana(self):
        # Detiene el loop de juego de forma segura
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.root.destroy()
        sys.exit(0)


    def manejar_input_gui(self, event):
        key = event.keysym.upper()
        
        # La opcion de salir con 'Q' ha sido eliminada.
        
        # Mapeo de teclas de flecha
        if self.tipo_juego == 'TETRIS':
            if key == 'UP': self.ejecutar_evento('ON_KEY_UP')
            elif key == 'DOWN': self.ejecutar_evento('ON_KEY_DOWN')
            elif key == 'LEFT': self.ejecutar_evento('ON_KEY_LEFT')
            elif key == 'RIGHT': self.ejecutar_evento('ON_KEY_RIGHT')
        elif self.tipo_juego == 'SNAKE':
            # Llamamos a las funciones internas para Snake
            if key == 'UP': self.snake_cambiar_direccion('UP')
            elif key == 'DOWN': self.snake_cambiar_direccion('DOWN')
            elif key == 'LEFT': self.snake_cambiar_direccion('LEFT')
            elif key == 'RIGHT': self.snake_cambiar_direccion('RIGHT')
            # ACT4: teclas 1, 2 y 3 saltan de nivel (util para la demo)
            elif key in ('1', '2', '3'): self.snake_saltar_nivel(int(key) - 1)


    def dibujar(self):
        self.canvas.delete("all") # Borrar todo en cada frame
        self.label_score.config(text="PUNTUACION\n" + str(self.puntuacion))
        
        # Colores
        COLOR_GRID_FIJA = '#343434' # Gris oscuro para celdas fijadas sin color propio (compatibilidad)
        COLOR_SNAKE_CABEZA = '#00FF00' # Verde brillante
        COLOR_SNAKE_CUERPO = '#33CC33' # Verde normal
        COLOR_FOOD = '#FF0000'      # Rojo
        
        # 1. Dibujar la cuadricula estatica (grid base)
        # NUEVO: cada celda fijada guarda el color de su pieza (texto '#RRGGBB').
        # Si vale 1 (valor antiguo) se dibuja en gris como antes.
        for y in range(self.alto):
            for x in range(self.ancho):
                celda = self.grid[y][x]
                if celda:
                    if isinstance(celda, basestring):
                        self.dibujar_celda(x, y, celda)
                    else:
                        self.dibujar_celda(x, y, COLOR_GRID_FIJA)

        # 2. Dibujar la pieza actual de Tetris (con su color dinamico)
        if self.tipo_juego == 'TETRIS' and self.pieza_actual:
            matriz_pieza = self.pieza_actual[self.pieza_rotacion]
            for y_offset, fila in enumerate(matriz_pieza):
                for x_offset, celda in enumerate(fila):
                    if celda == 1:
                        self.dibujar_celda(self.pieza_x + x_offset, self.pieza_y + y_offset, self.pieza_color)
        
        # 3. Dibujar Snake y Comida
        # ACT4: todo el dibujo de Snake paso a snake_dibujar_todo() (bloque DIBUJO, mas abajo)
        if self.tipo_juego == 'SNAKE':
            self.snake_dibujar_todo()

    def dibujar_celda(self, x, y, color):
        ts = self.taman_celda # Alias para taman de celda
        x1, y1 = x * ts, y * ts
        x2, y2 = x1 + ts, y1 + ts
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='#000000')


    def ejecutar_evento(self, nombre_evento):
        if nombre_evento in self.datos_juego['events']:
            for accion in self.datos_juego['events'][nombre_evento]:
                verbo, objeto = accion.get('accion'), accion.get('objeto')
                
                if verbo == 'INCREASE_SCORE': self.puntuacion += int(objeto)
                if verbo == 'GAME_OVER': self.juego_terminado = True

                if self.tipo_juego == 'TETRIS':
                    if verbo == 'SPAWN': self.tetris_spawn_pieza()
                    if verbo == 'MOVE': self.tetris_mover_pieza(accion['params'][0])
                    if verbo == 'ROTATE': self.tetris_rotar_pieza()
                
                if self.tipo_juego == 'SNAKE':
                    if verbo == 'SPAWN' and objeto == 'PLAYER': self.snake_spawn_jugador(accion)
                    if verbo == 'SPAWN' and objeto == 'FOOD': self.snake_spawn_comida()
                    if verbo == 'MOVE' and objeto == 'PLAYER': self.snake_mover_jugador()
                    if verbo == 'GROW': self.snake_crecer()


    # METODOS DE LOGICA DE JUEGO (MANTENIDOS DEL ARCHIVO ORIGINAL)
    # ---------------------------------------------------------------------
    """ TETRIS """
    def tetris_spawn_pieza(self):
        if self.tetris_spawn_powerup():
            return
        self.tetris_preparar_normal()
        nombre_pieza = self.elegir_shape_ponderado()
        self.pieza_actual = self.datos_juego['shapes'][nombre_pieza]
        # NUEVO: leer el color de la pieza desde el JSON (con valor por defecto si no existe)
        self.pieza_color = self.datos_juego.get('colors', {}).get(nombre_pieza, COLOR_PIEZA_DEFECTO)
        self.pieza_x, self.pieza_y, self.pieza_rotacion = self.ancho / 2 - 2, 0, 0
        if self.tetris_verificar_colision(self.pieza_x, self.pieza_y, self.pieza_rotacion):
            self.juego_terminado = True

    def elegir_shape_ponderado(self):
        # Seleccion ponderada: cada shape tiene un peso entero (WEIGHT en el .brick).
        # Si el JSON no trae "weights" (juegos viejos) todos pesan 1 = eleccion uniforme.
        nombres = sorted(self.datos_juego['shapes'].keys())
        pesos = self.datos_juego.get('weights', {})
        total = 0
        for nombre in nombres:
            total += pesos.get(nombre, 1)
        if total <= 0:
            return random.choice(nombres)
        r = random.randint(1, total)
        acumulado = 0
        for nombre in nombres:
            acumulado += pesos.get(nombre, 1)
            if r <= acumulado:
                return nombre
        return nombres[-1]

    def tetris_mover_pieza(self, direccion):
        if not self.pieza_actual: return
        dx, dy = 0, 0
        if direccion == 'LEFT': dx = -1
        elif direccion == 'RIGHT': dx = 1
        elif direccion == 'DOWN': dy = 1
        if not self.tetris_verificar_colision(self.pieza_x + dx, self.pieza_y + dy, self.pieza_rotacion):
            self.pieza_x += dx
            self.pieza_y += dy
        elif dy > 0:
            self.tetris_fijar_pieza()

    def tetris_rotar_pieza(self):
        if not self.pieza_actual: return
        nueva_rotacion = (self.pieza_rotacion + 1) % len(self.pieza_actual)
        if not self.tetris_verificar_colision(self.pieza_x, self.pieza_y, nueva_rotacion):
            self.pieza_rotacion = nueva_rotacion

    def tetris_fijar_pieza(self):
        self.tetris_aplicar_efecto()
        matriz_pieza = self.pieza_actual[self.pieza_rotacion]
        for y_offset, fila in enumerate(matriz_pieza):
            for x_offset, celda in enumerate(fila):
                if celda == 1:
                    if 0 <= self.pieza_y + y_offset < self.alto and 0 <= self.pieza_x + x_offset < self.ancho:
                        # NUEVO: la celda fijada conserva el color de su pieza (antes guardaba 1)
                        self.grid[self.pieza_y + y_offset][self.pieza_x + x_offset] = self.pieza_color
        self.pieza_actual = None
        self.tetris_limpiar_lineas()
        self.ejecutar_evento('ON_START')

    def tetris_verificar_colision(self, x, y, rotacion):
        if not self.pieza_actual: return False
        matriz_pieza = self.pieza_actual[rotacion]
        for y_offset, fila in enumerate(matriz_pieza):
            for x_offset, celda in enumerate(fila):
                if celda == 1:
                    nuevo_x, nuevo_y = x + x_offset, y + y_offset
                    if not (0 <= nuevo_x < self.ancho and 0 <= nuevo_y < self.alto and self.grid[nuevo_y][nuevo_x] == 0):
                        return True
        return False

    def tetris_limpiar_lineas(self):
        nuevo_grid = [fila for fila in self.grid if not all(fila)]
        lineas_limpias = self.alto - len(nuevo_grid)
        if lineas_limpias > 0:
            self.grid = [[0] * self.ancho for _ in range(lineas_limpias)] + nuevo_grid
            self.tetris_contar('LINES_CLEARED', lineas_limpias)            
            for _ in range(lineas_limpias): self.ejecutar_evento('ON_LINE_CLEAR')
            
    """SNAKE"""
    
        # --- POWER-UPS (Hielo) ---
    def tetris_contar(self, tipo, n=1):
        for nombre in self.contadores:
            self.contadores[nombre][tipo] += n

    def tetris_spawn_powerup(self):
        for nombre, pu in self.powerups.items():
            conds = pu.get('condiciones', [])
            if not conds:
                continue
            listo = True
            for tipo, n in conds:
                if self.contadores[nombre].get(tipo, 0) < n:
                    listo = False
            if listo:
                self.pieza_actual = pu['estados']
                self.pieza_color = pu.get('color', '#ADD8E6')
                self.pieza_powerup = nombre
                for k in self.contadores[nombre]:
                    self.contadores[nombre][k] = 0
                self.pieza_x, self.pieza_y, self.pieza_rotacion = self.ancho / 2 - 2, 0, 0
                if self.tetris_verificar_colision(self.pieza_x, self.pieza_y, self.pieza_rotacion):
                    self.juego_terminado = True
                return True
        return False

    def tetris_preparar_normal(self):
        self.pieza_color = '#00FFFF'
        self.pieza_powerup = None
        if self.piezas_lentas > 0:
            self.velocidad_gravedad = self.velocidad_base * self.slow_div
            self.piezas_lentas -= 1
        else:
            self.velocidad_gravedad = self.velocidad_base
        self.tetris_contar('PIECES_SPAWNED')

    def tetris_aplicar_efecto(self):
        if self.pieza_powerup:
            pu = self.powerups[self.pieza_powerup]
            if pu.get('efecto') == 'SLOW_DOWN':
                self.piezas_lentas = pu['params'].get('DURATION', 5)
                self.slow_div = pu['params'].get('SLOW_DIV', 2)
            self.pieza_powerup = None

    def snake_spawn_jugador(self, accion):
        coords = accion['params'][0] if accion['params'] else [self.ancho / 2, self.alto / 2]
        self.serpiente_cuerpo = [(coords[0], coords[1])]
        self.serpiente_direccion = (1, 0)
        
    def snake_spawn_comida(self):
        # ACT4: el ciclo "while True" original se limito a 500 intentos al azar (los mismos numeros
        # aleatorios que antes mientras haya sitio); si no se encuentra celda se elige entre las libres
        # y, si no queda ninguna, no hay comida. Asi un tablero lleno ya no congela el juego.
        for _ in range(500):
            x, y = random.randint(0, self.ancho - 1), random.randint(0, self.alto - 1)
            # ACT4: tampoco sobre nubes, venenos ni escudo
            if (x, y) not in self.serpiente_cuerpo and not self.snake_ocupada_extra((x, y)):
                self.posicion_comida = (x, y)
                return
        libres = [(x, y) for y in range(self.alto) for x in range(self.ancho)
                  if (x, y) not in self.serpiente_cuerpo and not self.snake_ocupada_extra((x, y))]
        if libres:
            self.posicion_comida = random.choice(libres)
        else:
            self.posicion_comida = None
                
    def snake_mover_jugador(self):
        if not self.serpiente_cuerpo: return
        cabeza_x, cabeza_y = self.serpiente_cuerpo[0]
        dir_x, dir_y = self.serpiente_direccion
        nueva_cabeza = (cabeza_x + dir_x, cabeza_y + dir_y)

        # Las paredes siempre matan, tambien con invulnerabilidad (decision D3)
        if not (0 <= nueva_cabeza[0] < self.ancho and 0 <= nueva_cabeza[1] < self.alto):
            self.ejecutar_evento('ON_COLLISION_WALL')
            return

        # ACT4: el propio cuerpo solo mata si NO esta invulnerable
        if nueva_cabeza in self.serpiente_cuerpo[:-1] and not self.snake_es_invulnerable():
            self.ejecutar_evento('ON_COLLISION_SELF')
            return

        self.serpiente_cuerpo.insert(0, nueva_cabeza)

        # ACT4: nubes, frutas venenosas y fruta de escudo
        self.snake_procesar_entidades(nueva_cabeza)
        if self.juego_terminado:
            return

        if nueva_cabeza == self.posicion_comida:
            self.ejecutar_evento('ON_EAT_FOOD')
        else:
            self.serpiente_cuerpo.pop()

    def snake_cambiar_direccion(self, direccion):
        if direccion == 'UP' and self.serpiente_direccion[1] != 1:
            self.serpiente_direccion = (0, -1)
        elif direccion == 'DOWN' and self.serpiente_direccion[1] != -1:
            self.serpiente_direccion = (0, 1)
        elif direccion == 'LEFT' and self.serpiente_direccion[0] != 1:
            self.serpiente_direccion = (-1, 0)
        elif direccion == 'RIGHT' and self.serpiente_direccion[0] != -1:
            self.serpiente_direccion = (1, 0)

    def snake_crecer(self):
        pass


    # =====================================================================
    # ACT4: (Snake evolved) - LOGICA DEL JUEGO                [Integrante 2]
    # ---------------------------------------------------------------------
    # QUE SE AGREGO: manejador de estados (NORMAL / INVULNERABLE / GAME_OVER),
    # niveles BABY / ENTUSIASTA / NYAN_CAT, frutas venenosas, nubes, fruta de
    # escudo ("No Morir") con temporizador en segundos reales (time.time()).
    # COMO FUNCIONA: snake_cargar_config() lee el JSON una sola vez (con
    # valores por defecto); snake_aplicar_nivel() activa un nivel (velocidad
    # y entidades); snake_mover_jugador() llama a snake_procesar_entidades()
    # en cada paso; snake_actualizar_estado() corre en cada vuelta del
    # game_loop (vence el escudo, reaparece la fruta, sube de nivel).
    # RETROCOMPATIBILIDAD: si el JSON no trae "levels", solo existe el nivel
    # BABY con tick 150 ms, sin veneno, nubes ni escudo = Snake original.
    # =====================================================================

    def snake_cargar_config(self):
        # ACT4: lee del JSON niveles, estilo del cuerpo y entidades. Toda la
        # lectura del JSON esta AQUI: si el contrato de Laura cambia un nombre,
        # solo se ajusta esta funcion.
        shapes = self.datos_juego.get('shapes', {})
        ents = self.datos_juego.get('entities', {})

        # Estilo del cuerpo: shapes.SNAKE_BODY {form, color} o "snake_style"
        cuerpo = shapes.get('SNAKE_BODY')
        if not isinstance(cuerpo, dict):
            cuerpo = self.datos_juego.get('snake_style', {})
        cuerpo = _minusculas(cuerpo)
        forma = str(cuerpo.get('form', 'RECTANGLE')).upper()
        if forma not in ('RECTANGLE', 'CIRCULAR', 'TRIANGULAR'):
            forma = 'RECTANGLE'
        self.snake_estilo = {'form': forma, 'color': cuerpo.get('color')}

        # Entidades: POISON_FRUIT, CLOUD, SHIELD_FRUIT (o "entities")
        self.snake_ent = {}
        for clave, nombre_shape in (('poison', 'POISON_FRUIT'), ('cloud', 'CLOUD'), ('shield', 'SHIELD_FRUIT')):
            cfg = dict(SNAKE_ENTIDADES_DEFECTO[clave])
            origen = shapes.get(nombre_shape)
            if not isinstance(origen, dict):
                origen = ents.get(clave, {})
            cfg.update(_minusculas(origen))
            self.snake_ent[clave] = cfg

        # Niveles: sin "levels" solo existe BABY (Snake original)
        niveles_json = self.datos_juego.get('levels')
        # Con un solo nivel (el BABY que el compilador agrega a un snake.brick viejo) no hay
        # panel de niveles ni teclas 1-3: el juego se ve igual que el Snake original.
        self.snake_multinivel = bool(niveles_json) and len(niveles_json) > 1
        self.snake_niveles = {}
        if niveles_json:
            for nombre, cfg in niveles_json.items():
                self.snake_niveles[str(nombre).upper()] = _minusculas(cfg)
        else:
            self.snake_niveles['BABY'] = {}
        orden = self.datos_juego.get('level_order')
        if orden:
            lista = [str(n).upper() for n in orden if str(n).upper() in self.snake_niveles]
        else:
            lista = [n for n in SNAKE_ORDEN_NIVELES if n in self.snake_niveles]
        lista += sorted([n for n in self.snake_niveles if n not in lista])
        self.snake_orden = lista
        inicial = str(self.datos_juego.get('default_level', 'BABY')).upper()
        if inicial not in self.snake_niveles:
            inicial = lista[0]
        self.snake_nivel_inicial = inicial
        self.snake_subida = int(self.datos_juego.get('level_up_score', 0) or 0)
        # ACT4: puntaje al que el jugador salto de nivel a mano (teclas 1-3); el avance automatico
        # exige superarlo, para que saltar a un nivel bajo con muchos puntos no suba solo de inmediato
        self.snake_puntos_salto = -1

        # Estado dinamico
        self.nivel_actual = inicial
        self.cfg_nivel = dict(SNAKE_NIVEL_DEFECTO)
        self.estado_snake = 'NORMAL'          # NORMAL | INVULNERABLE | GAME_OVER
        self.invulnerable_hasta = 0.0         # time.time() en que termina el escudo
        self.escudo_reaparece = 0.0           # time.time() desde el que puede reaparecer
        self.nubes = []
        self.venenos = []
        self.escudo = None

    def snake_aplicar_nivel(self, nombre):
        # ACT4: activa un nivel. Mezcla los valores del nivel con los de
        # SNAKE_NIVEL_DEFECTO (lo que falte queda como en el Snake original),
        # ajusta la velocidad y regenera nubes / venenos / escudo.
        cfg = dict(SNAKE_NIVEL_DEFECTO)
        cfg.update(self.snake_niveles.get(nombre, {}))
        try:
            tick = int(cfg['tick'])
        except (TypeError, ValueError):
            tick = SNAKE_NIVEL_DEFECTO['tick']
        if tick <= 0:
            tick = SNAKE_NIVEL_DEFECTO['tick']
        cfg['tick'] = tick
        veneno = cfg['poison']
        if veneno is True:
            veneno = 'SUBTRACT'
        elif not veneno:
            veneno = 'OFF'
        cfg['poison'] = str(veneno).upper()
        cfg['shield'] = _es_si(cfg['shield'])
        cfg['clouds'] = _es_si(cfg['clouds'])
        cfg['head'] = str(cfg['head']).upper()
        cfg['tail'] = str(cfg['tail']).upper()

        self.nivel_actual = nombre
        self.cfg_nivel = cfg
        self.velocidad_gravedad = tick / 1000.0   # el tick del .brick va en milisegundos
        self.timer_gravedad = 0

        # Se limpia lo del nivel anterior y se crea lo que este nivel activa
        self.nubes = []
        self.venenos = []
        self.escudo = None
        self.estado_snake = 'NORMAL'
        self.invulnerable_hasta = 0.0
        if cfg['clouds']:
            self.snake_generar_nubes()
        if cfg['poison'] != 'OFF':
            self.snake_reponer_venenos()
        if cfg['shield']:
            self.snake_generar_escudo()

    def snake_saltar_nivel(self, indice):
        # ACT4: teclas 1, 2, 3 (decision D2). Con el snake.brick original
        # (sin LEVELS) no hace nada.
        if self.snake_multinivel and 0 <= indice < len(self.snake_orden):
            self.snake_puntos_salto = self.puntuacion  # ACT4: ver snake_revisar_subida_nivel
            self.snake_aplicar_nivel(self.snake_orden[indice])

    def snake_revisar_subida_nivel(self):
        # ACT4: avance automatico. Pasar del nivel i al i+1 exige
        # LEVEL_UP_SCORE * (i + 1) puntos. Si level_up_score no esta, no hay avance.
        # Tras un salto manual (teclas 1-3) hace falta ganar puntos nuevos para volver a subir solo.
        if self.snake_subida <= 0 or not self.snake_multinivel:
            return
        i = self.snake_orden.index(self.nivel_actual)
        if i + 1 < len(self.snake_orden) and self.puntuacion >= self.snake_subida * (i + 1) \
                and self.puntuacion > self.snake_puntos_salto:
            self.snake_aplicar_nivel(self.snake_orden[i + 1])

    def snake_actualizar_estado(self):
        # ACT4: MANEJADOR DE ESTADOS. Se llama en cada vuelta del game_loop.
        # NORMAL -> INVULNERABLE al comer el escudo; INVULNERABLE -> NORMAL
        # cuando time.time() supera invulnerable_hasta; cualquiera -> GAME_OVER.
        if self.juego_terminado:
            self.estado_snake = 'GAME_OVER'
            return
        ahora = time.time()
        if self.estado_snake == 'INVULNERABLE' and ahora >= self.invulnerable_hasta:
            self.estado_snake = 'NORMAL'
        if self.cfg_nivel['shield'] and self.escudo is None and ahora >= self.escudo_reaparece \
                and self.estado_snake != 'INVULNERABLE':
            self.snake_generar_escudo()
        self.snake_revisar_subida_nivel()

    def snake_es_invulnerable(self):
        # ACT4: True mientras el escudo siga activo (compara contra time.time())
        return self.estado_snake == 'INVULNERABLE' and time.time() < self.invulnerable_hasta

    def snake_segundos_restantes(self):
        # ACT4: segundos que le quedan al escudo (lo muestra el panel)
        if self.estado_snake != 'INVULNERABLE':
            return 0.0
        return max(0.0, self.invulnerable_hasta - time.time())

    def snake_duracion_escudo(self):
        # ACT4: duracion del escudo en segundos (nivel o SHIELD_FRUIT)
        # Duracion en segundos: la del nivel (shield_duration) o la de SHIELD_FRUIT
        valor = self.cfg_nivel.get('shield_duration', self.snake_ent['shield']['duration'])
        try:
            return float(valor)
        except (TypeError, ValueError):
            return float(SNAKE_ENTIDADES_DEFECTO['shield']['duration'])

    def snake_game_over(self):
        # ACT4: pasa al estado GAME_OVER
        self.juego_terminado = True
        self.estado_snake = 'GAME_OVER'

    # --- Aparicion de entidades (decision D4: solo celdas libres) ---

    def snake_ocupada_extra(self, pos):
        # ACT4: True si la celda tiene nube, veneno o escudo
        # True si hay una nube, veneno o escudo en esa celda
        return pos in self.nubes or pos in self.venenos or pos == self.escudo

    def snake_celda_libre(self, lejos_de_cabeza=0):
        # ACT4: aparicion en celdas libres (decision D4)
        # Elige una celda al azar que no tenga serpiente, comida ni otra
        # entidad. Con lejos_de_cabeza=n evita un cuadro de radio n alrededor
        # de la cabeza (para que una nube no aparezca pegada a la serpiente).
        ocupadas = set(self.serpiente_cuerpo) | set(self.nubes) | set(self.venenos)
        if self.escudo:
            ocupadas.add(self.escudo)
        if self.posicion_comida:
            ocupadas.add(self.posicion_comida)
        cab = self.serpiente_cuerpo[0] if self.serpiente_cuerpo else None
        libres = []
        for y in range(self.alto):
            for x in range(self.ancho):
                if (x, y) in ocupadas:
                    continue
                if cab and lejos_de_cabeza > 0 and max(abs(x - cab[0]), abs(y - cab[1])) <= lejos_de_cabeza:
                    continue
                libres.append((x, y))
        if not libres:
            return None
        return random.choice(libres)

    def snake_generar_nubes(self):
        # ACT4: crea las nubes fijas del nivel
        for _ in range(int(self.snake_ent['cloud']['count'])):
            celda = self.snake_celda_libre(3)
            if celda:
                self.nubes.append(celda)

    def snake_reponer_venenos(self):
        # ACT4: mantiene la cantidad de frutas venenosas del nivel
        while len(self.venenos) < int(self.snake_ent['poison']['count']):
            celda = self.snake_celda_libre()
            if not celda:
                break
            self.venenos.append(celda)

    def snake_generar_escudo(self):
        # ACT4: crea la fruta de escudo en una celda libre
        celda = self.snake_celda_libre()
        if celda:
            self.escudo = celda
        else:
            self.escudo_reaparece = time.time() + SNAKE_ESPERA_ESCUDO

    # --- Colisiones y efectos ---

    def snake_procesar_entidades(self, pos):
        # ACT4: se llama cada vez que la cabeza llega a una celda nueva.
        if pos in self.nubes:
            self.snake_colision_nube()
        if pos in self.venenos:
            self.venenos.remove(pos)           # la fruta se consume
            self.snake_comer_veneno()
            if self.cfg_nivel['poison'] != 'OFF':
                self.snake_reponer_venenos()   # y aparece otra
        if self.escudo is not None and pos == self.escudo:
            self.snake_activar_escudo()

    def snake_colision_nube(self):
        # ACT4: LOGICA DE COLISION CON NUBES
        #   invulnerable        -> se ignora
        #   puntos > 0          -> puntos a 0 y la serpiente SIGUE VIVA
        #   puntos == 0         -> GAME OVER inmediato
        if self.snake_es_invulnerable():
            return
        if self.puntuacion > 0:
            self.puntuacion = 0
        else:
            self.snake_game_over()

    def snake_comer_veneno(self):
        # ACT4: modo SUBTRACT resta "penalty" sin bajar de 0; modo KILL termina
        # el juego; con invulnerabilidad no tiene efecto (decision D3).
        if self.snake_es_invulnerable():
            return
        if self.cfg_nivel['poison'] == 'KILL':
            self.snake_game_over()
        else:
            self.puntuacion = max(0, self.puntuacion - int(self.snake_ent['poison']['penalty']))

    def snake_activar_escudo(self):
        # ACT4: TEMPORIZADOR DEL POWER-UP. Se guarda la hora de fin
        # (time.time() + DURATION). La duracion es en segundos reales: no
        # depende del tick, que cambia entre niveles.
        self.invulnerable_hasta = time.time() + self.snake_duracion_escudo()
        self.estado_snake = 'INVULNERABLE'
        self.escudo = None
        self.escudo_reaparece = self.invulnerable_hasta + SNAKE_ESPERA_ESCUDO

    # =====================================================================
    # ACT4: (Snake evolved) - DIBUJO Y EFECTOS VISUALES       [Integrante 3]
    # ---------------------------------------------------------------------
    # QUE SE AGREGO: segmentos CIRCULAR / TRIANGULAR (create_oval /
    # create_polygon), cabeza de gato, cola arcoiris (COLORES[i % n]),
    # dibujos de nube, fruta venenosa y fruta de escudo, parpadeo mientras es
    # invulnerable y panel lateral (nivel y segundos de escudo).
    # COMO FUNCIONA: dibujar() llama a snake_dibujar_todo(), que SOLO LEE el
    # estado que mantiene la logica (serpiente_cuerpo, nubes, venenos, escudo,
    # cfg_nivel, estado_snake) y pinta. No cambia ninguna variable de juego.
    # RETROCOMPATIBILIDAD: sin FORM ni niveles se dibuja el rectangulo con los
    # mismos colores del Snake original (cabeza #00FF00, cuerpo #33CC33).
    # =====================================================================

    def _esc(self, v):
        # ACT4: escala medidas con el tamano de celda
        # Escala una medida pensada para una celda de 25 px al tamano real
        return int(round(v * self.taman_celda / 25.0))

    def snake_dibujar_todo(self):
        # ACT4: dibuja comida, entidades, serpiente y panel
        COLOR_FOOD = '#FF0000'
        if self.posicion_comida:
            x, y = self.posicion_comida
            self.dibujar_celda(x, y, COLOR_FOOD)
        for (x, y) in self.nubes:
            self.snake_dibujar_nube(x, y)
        for (x, y) in self.venenos:
            self.snake_dibujar_veneno(x, y)
        if self.escudo is not None:
            self.snake_dibujar_escudo(self.escudo[0], self.escudo[1])
        self.snake_dibujar_serpiente()
        self.snake_actualizar_panel()

    def snake_dibujar_serpiente(self):
        # ACT4: dibuja la serpiente de la cola a la cabeza (forma, colores, parpadeo)
        cuerpo = self.serpiente_cuerpo
        forma = self.snake_estilo['form']
        base = self.snake_estilo['color']
        cfg = self.cfg_nivel
        # Parpadeo: mientras es invulnerable alterna con blanco ~6 veces por segundo
        parpadeo = self.snake_es_invulnerable() and int(time.time() * 6) % 2 == 0
        # Fase que "desplaza" los colores del arcoiris para que parezca moverse
        fase = int(time.time() * 8)
        n_colores = len(SNAKE_COLORES_ARCOIRIS)
        # Se dibuja de la cola a la cabeza para que la cabeza quede encima
        for i in range(len(cuerpo) - 1, -1, -1):
            x, y = cuerpo[i]
            if i == 0:
                if parpadeo:
                    color = '#FFFFFF'
                elif base:
                    color = _aclarar(base)
                else:
                    color = '#00FF00'
                if cfg['head'] == 'CAT':
                    self.snake_dibujar_cabeza_gato(x, y, color)
                else:
                    self.snake_dibujar_forma(x, y, forma, color, self.serpiente_direccion)
            else:
                if parpadeo:
                    color = '#FFFFFF'
                elif cfg['tail'] == 'RAINBOW':
                    # Un color distinto por segmento: indice del cuerpo % cantidad de colores
                    color = SNAKE_COLORES_ARCOIRIS[(i + fase) % n_colores]
                elif base:
                    color = base
                else:
                    color = '#33CC33'
                dx = cuerpo[i - 1][0] - x
                dy = cuerpo[i - 1][1] - y
                direccion = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
                self.snake_dibujar_forma(x, y, forma, color, direccion)

    def snake_dibujar_forma(self, x, y, forma, color, direccion=(0, -1)):
        # ACT4: rectangulo, circulo o triangulo
        # Firma comun de dibujo: (columna, fila, forma, color[, direccion]).
        # RECTANGLE reutiliza dibujar_celda (comportamiento original).
        ts = self.taman_celda
        x1, y1 = x * ts, y * ts
        x2, y2 = x1 + ts, y1 + ts
        mx, my = x1 + ts // 2, y1 + ts // 2
        if forma == 'CIRCULAR':
            self.canvas.create_oval(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill=color, outline='#000000')
        elif forma == 'TRIANGULAR':
            # El triangulo apunta hacia donde avanza el segmento
            dx, dy = direccion
            if dx > 0:
                pts = [x2 - 1, my, x1 + 1, y1 + 1, x1 + 1, y2 - 1]
            elif dx < 0:
                pts = [x1 + 1, my, x2 - 1, y1 + 1, x2 - 1, y2 - 1]
            elif dy > 0:
                pts = [mx, y2 - 1, x1 + 1, y1 + 1, x2 - 1, y1 + 1]
            else:
                pts = [mx, y1 + 1, x1 + 1, y2 - 1, x2 - 1, y2 - 1]
            self.canvas.create_polygon(pts, fill=color, outline='#000000')
        else:
            self.dibujar_celda(x, y, color)

    def snake_dibujar_cabeza_gato(self, x, y, color):
        # ACT4: cabeza de gato con primitivas del Canvas
        # Cabeza de Nyan Cat con pocas primitivas: circulo + 2 orejas
        # triangulares + 2 ojos + nariz + bigotes.
        p = self._esc
        x1, y1 = x * self.taman_celda, y * self.taman_celda
        x2 = x1 + self.taman_celda
        c = self.canvas
        c.create_polygon([x1 + p(2), y1 + p(11), x1 + p(4), y1 + p(1), x1 + p(11), y1 + p(7)],
                         fill=color, outline='#000000')
        c.create_polygon([x2 - p(2), y1 + p(11), x2 - p(4), y1 + p(1), x2 - p(11), y1 + p(7)],
                         fill=color, outline='#000000')
        c.create_oval(x1 + 1, y1 + p(4), x2 - 1, y1 + self.taman_celda - 1, fill=color, outline='#000000')
        c.create_oval(x1 + p(6), y1 + p(10), x1 + p(10), y1 + p(15), fill='#FFFFFF', outline='#000000')
        c.create_oval(x2 - p(10), y1 + p(10), x2 - p(6), y1 + p(15), fill='#FFFFFF', outline='#000000')
        c.create_oval(x1 + p(7), y1 + p(11), x1 + p(9), y1 + p(14), fill='#000000', outline='')
        c.create_oval(x2 - p(9), y1 + p(11), x2 - p(7), y1 + p(14), fill='#000000', outline='')
        c.create_polygon([x1 + p(11), y1 + p(16), x2 - p(11), y1 + p(16), x1 + p(12), y1 + p(18)],
                         fill='#FF69B4', outline='')
        c.create_line(x1 + p(1), y1 + p(17), x1 + p(7), y1 + p(18), fill='#000000')
        c.create_line(x2 - p(1), y1 + p(17), x2 - p(7), y1 + p(18), fill='#000000')

    def snake_dibujar_nube(self, x, y):
        # ACT4: nube de tres ovalos
        # Nube: 3 ovalos solapados del color de CLOUD
        p = self._esc
        x1, y1 = x * self.taman_celda, y * self.taman_celda
        color = self.snake_ent['cloud']['color']
        for (a, b, c2, d) in ((1, 10, 15, 23), (6, 4, 19, 18), (11, 10, 24, 23)):
            self.canvas.create_oval(x1 + p(a), y1 + p(b), x1 + p(c2), y1 + p(d), fill=color, outline='')

    def snake_dibujar_veneno(self, x, y):
        # ACT4: fruta venenosa (circulo morado con calavera)
        # Fruta venenosa: circulo del color de POISON_FRUIT con "calavera" simple
        p = self._esc
        x1, y1 = x * self.taman_celda, y * self.taman_celda
        c = self.canvas
        c.create_oval(x1 + p(2), y1 + p(2), x1 + p(23), y1 + p(23),
                      fill=self.snake_ent['poison']['color'], outline='#000000')
        c.create_oval(x1 + p(7), y1 + p(8), x1 + p(11), y1 + p(12), fill='#FFFFFF', outline='')
        c.create_oval(x1 + p(14), y1 + p(8), x1 + p(18), y1 + p(12), fill='#FFFFFF', outline='')
        c.create_line(x1 + p(8), y1 + p(17), x1 + p(17), y1 + p(17), fill='#FFFFFF')

    def snake_dibujar_escudo(self, x, y):
        # ACT4: fruta de escudo (estrella dorada)
        # Fruta de escudo: estrella de 5 puntas del color de SHIELD_FRUIT
        ts = self.taman_celda
        cx, cy = x * ts + ts / 2.0, y * ts + ts / 2.0
        r_ext, r_int = ts * 0.46, ts * 0.20
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            r = r_ext if k % 2 == 0 else r_int
            pts.append(cx + r * math.cos(ang))
            pts.append(cy + r * math.sin(ang))
        self.canvas.create_polygon(pts, fill=self.snake_ent['shield']['color'], outline='#000000')

    def snake_actualizar_panel(self):
        # ACT4: panel lateral: nivel y cuenta regresiva del escudo
        # Panel lateral: nivel actual y cuenta regresiva del escudo
        if not self.snake_multinivel:
            return
        self.label_nivel.config(text="NIVEL\n" + self.nivel_actual)
        if self.snake_es_invulnerable():
            self.label_escudo.config(text="ESCUDO\n%.1f s" % self.snake_segundos_restantes())
        else:
            self.label_escudo.config(text="")

    # METODOS DE SALIDA (ADAPTADOS A GUI)
    # -----------------------------------

    def mostrar_game_over(self):
        # Muestra una ventana de mensaje de Tkinter
        tkMessageBox.showinfo("Juego Terminado", "Puntuacion Final: " + str(self.puntuacion))
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python runtime.py <archivo_juego.json>")
        sys.exit(1)
    archivo_juego = sys.argv[1]
    try:
        with open(archivo_juego, 'r') as f:
            datos_juego = json.load(f)
    except IOError:
        print("Error: No se pudo encontrar el archivo ") + archivo_juego
        sys.exit(1)
    juego = Juego(datos_juego)
    juego.run()