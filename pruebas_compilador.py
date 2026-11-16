import os
import sys
import json
import unittest

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import compiler

CABECERA = "GAME_TYPE TANKS\nGAME_GRID (20, 16)\n"
JUGADOR = "DEFINE TANK P:\n TYPE: PLAYER\nEND\n"
ENEMIGO = "DEFINE TANK E:\n TYPE: ENEMY\nEND\n"
JEFE = "DEFINE TANK B:\n TYPE: BOSS\nEND\n"
BALA = "DEFINE BULLET BA:\n TYPE: BULLET\nEND\n"
BASICO = CABECERA + JUGADOR + ENEMIGO + JEFE + BALA


def compilar(codigo):
    tokens, lineas = compiler.lexer_con_lineas(codigo)
    parser = compiler.Parser(tokens, lineas)
    ast = parser.parse()
    return ast, parser


def compilar_archivo(nombre):
    with open(os.path.join(BASE, 'games', nombre + '.brick'), 'r') as f:
        return compilar(f.read())


class PruebasRetrocompatibilidad(unittest.TestCase):
    CLAVES_TANKS = ('tanks', 'bullets', 'walls', 'tank_roles', 'target_scores')

    def test_juegos_anteriores_compilan_sin_claves_de_tanks(self):
        for nombre in ('tetris', 'tetris_remake', 'snake', 'snake_evolved'):
            ast, parser = compilar_archivo(nombre)
            for clave in self.CLAVES_TANKS:
                self.assertFalse(clave in ast, nombre + " no debe tener " + clave)

    def test_tetris_conserva_estructura(self):
        ast, parser = compilar_archivo('tetris')
        self.assertEqual(ast['tipo_juego'], 'TETRIS')
        self.assertTrue(len(ast['shapes']) > 0)
        self.assertTrue('ON_START' in ast['events'])

    def test_tetris_remake_conserva_powerups(self):
        ast, parser = compilar_archivo('tetris_remake')
        self.assertTrue(len(ast['powerups']) > 0)
        for pu in ast['powerups'].values():
            self.assertTrue('efecto' in pu and 'estados' in pu)

    def test_snake_conserva_niveles(self):
        ast, parser = compilar_archivo('snake')
        self.assertEqual(ast['default_level'], 'BABY')
        ast, parser = compilar_archivo('snake_evolved')
        self.assertEqual(ast['level_order'], ['BABY', 'ENTUSIASTA', 'NYAN_CAT'])

    def test_define_tank_rechazado_fuera_de_tanks(self):
        for tipo in ('TETRIS', 'SNAKE'):
            codigo = "GAME_TYPE " + tipo + "\nGAME_GRID (10, 20)\n" + JUGADOR
            self.assertRaises(Exception, compilar, codigo)


class PruebasTanks(unittest.TestCase):
    def test_tanks_brick_compila(self):
        ast, parser = compilar_archivo('tanks')
        self.assertEqual(ast['tipo_juego'], 'TANKS')
        self.assertEqual(ast['config']['grid_size'], [20, 16])
        self.assertEqual(parser.advertencias, [])

    def test_roles_de_tanques(self):
        ast, parser = compilar_archivo('tanks')
        roles = ast['tank_roles']
        self.assertEqual(roles['player'], 'PLAYER_TANK')
        self.assertEqual(roles['boss'], 'FINAL_BOSS')
        self.assertEqual(roles['enemies'], ['SCOUT_TANK', 'RAPID_TANK', 'HEAVY_TANK'])

    def test_atributos_de_tanques(self):
        ast, parser = compilar_archivo('tanks')
        jefe = ast['tanks']['FINAL_BOSS']
        self.assertEqual(jefe['type'], 'BOSS')
        self.assertEqual(jefe['hp'], 300)
        self.assertEqual(jefe['color'], '#7D3C98')
        self.assertEqual(len(jefe['estados'][0]), 4)
        self.assertEqual(len(jefe['estados'][0][0]), 5)
        self.assertEqual(ast['tanks']['PLAYER_TANK']['color'], '#20B2AA')
        self.assertEqual(ast['tanks']['RAPID_TANK']['form'], 'TRIANGULAR')

    def test_balas_muros_y_powerups(self):
        ast, parser = compilar_archivo('tanks')
        self.assertEqual(ast['bullets']['BOSS_BULLET']['size'], 2)
        self.assertEqual(ast['walls']['BRICK_WALL']['destructible'], True)
        self.assertEqual(ast['walls']['STEEL_WALL']['destructible'], False)
        self.assertEqual(ast['powerups']['REPAIR_HAMMER']['heal'], 25)
        self.assertEqual(ast['powerups']['REPAIR_HAMMER']['params']['HEAL'], 25)

    def test_target_score_y_move_forward(self):
        ast, parser = compilar_archivo('tanks')
        self.assertEqual(ast['target_scores'], [{'score': 1000, 'event': 'ON_TARGET_SCORE_1000'}])
        accion = ast['events']['ON_TARGET_SCORE_1000'][0]
        self.assertEqual(accion, {'accion': 'SPAWN', 'objeto': 'BOSS', 'params': ['FINAL_BOSS', [10, 2]]})
        tick = ast['events']['ON_TICK']
        self.assertEqual(tick[0], {'accion': 'MOVE', 'objeto': 'PLAYER', 'params': ['FORWARD']})
        self.assertEqual(tick[1], {'accion': 'MOVE', 'objeto': 'BULLETS', 'params': ['FORWARD']})

    def test_acciones_de_combate(self):
        ast, parser = compilar_archivo('tanks')
        self.assertEqual(ast['events']['ON_COLLISION_BULLET_BOSS'][0]['params'], ['BULLET_DAMAGE'])
        self.assertEqual(ast['events']['ON_COLLISION_PLAYER_ENEMY'][0]['params'], [10])
        self.assertEqual(ast['events']['ON_COLLISION_PLAYER_POWERUP'][0]['params'], ['POWERUP_VALUE'])
        self.assertEqual(ast['events']['ON_DESTROY_BOSS'][1]['accion'], 'VICTORY')
        self.assertEqual(ast['events']['ON_PLAYER_HIT'][0]['accion'], 'GAME_OVER_IF')

    def test_valores_por_defecto(self):
        ast, parser = compilar(BASICO)
        jugador = ast['tanks']['P']
        self.assertEqual(jugador['hp'], 100)
        self.assertEqual(jugador['color'], '#20B2AA')
        self.assertEqual(ast['tanks']['E']['points'], 100)
        self.assertEqual(ast['tanks']['B']['hp'], 300)
        self.assertTrue(len(ast['tanks']['B']['estados'][0]) > len(ast['tanks']['E']['estados'][0]) - 1)
        self.assertEqual(ast['bullets']['BA']['damage'], 10)

    def test_muro_y_powerup_por_defecto(self):
        codigo = BASICO + "DEFINE WALL W:\nEND\nDEFINE POWERUP H:\nEND\n"
        ast, parser = compilar(codigo)
        self.assertEqual(ast['walls']['W']['hp'], 40)
        self.assertEqual(ast['walls']['W']['estados'], [[[1]]])
        self.assertEqual(ast['powerups']['H']['heal'], 25)

    def test_grid_por_defecto(self):
        codigo = "GAME_TYPE TANKS\n" + JUGADOR + ENEMIGO + JEFE + BALA
        ast, parser = compilar(codigo)
        self.assertEqual(ast['config']['grid_size'], [20, 16])

    def test_spawn_enemy_random(self):
        codigo = BASICO + "ON START:\n SPAWN ENEMY RANDOM\n SPAWN POWERUP H AT RANDOM\nEND\nDEFINE POWERUP H:\nEND\n"
        ast, parser = compilar(codigo)
        self.assertEqual(ast['events']['ON_START'][0]['params'], ['RANDOM'])
        self.assertEqual(ast['events']['ON_START'][1]['params'], ['H', 'RANDOM'])

    def test_advertencias(self):
        ast, parser = compilar(BASICO)
        self.assertTrue(len(parser.advertencias) >= 3)

    def test_json_serializable(self):
        ast, parser = compilar_archivo('tanks')
        self.assertEqual(json.loads(json.dumps(ast)), ast)


class PruebasErrores(unittest.TestCase):
    def assertError(self, codigo, fragmento):
        try:
            compilar(codigo)
        except Exception as e:
            self.assertTrue(fragmento in str(e), str(e))
            return
        self.fail("se esperaba un error con: " + fragmento)

    def test_sin_jugador(self):
        self.assertError(CABECERA + ENEMIGO + JEFE + BALA, "exactamente un tanque TYPE: PLAYER")

    def test_dos_jugadores(self):
        self.assertError(BASICO + "DEFINE TANK PP:\n TYPE: PLAYER\nEND\n", "exactamente un tanque TYPE: PLAYER")

    def test_sin_enemigos(self):
        self.assertError(CABECERA + JUGADOR + JEFE + BALA, "al menos un tanque TYPE: ENEMY")

    def test_sin_jefe(self):
        self.assertError(CABECERA + JUGADOR + ENEMIGO + BALA, "exactamente un tanque TYPE: BOSS")

    def test_sin_bala(self):
        self.assertError(CABECERA + JUGADOR + ENEMIGO + JEFE, "DEFINE BULLET")

    def test_tanque_sin_type(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n HP: 10\nEND\n", "no tiene TYPE")

    def test_hp_cero(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n HP: 0\nEND\n", "mayor que cero")

    def test_tipo_invalido(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ALIADO\nEND\n", "PLAYER | ENEMY | BOSS")

    def test_forma_invalida(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n FORM: HEXAGONO\nEND\n", "FORM")

    def test_color_invalido(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n COLOR: ROJO\nEND\n", "color hexadecimal")

    def test_atributo_desconocido(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n VIDA: 5\nEND\n", "se esperaba una de")

    def test_atributo_repetido(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n HP: 5\n HP: 6\nEND\n", "repetido")

    def test_falta_end(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\nON START:\n SPAWN PLAYER AT (1, 1)\nEND\n", "falta el END")

    def test_nombre_duplicado(self):
        self.assertError(BASICO + JUGADOR, "mas de una vez")

    def test_matriz_irregular(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n STATE 1:\n [1, 1]\n [1]\nEND\n", "misma longitud")

    def test_matriz_con_valor_invalido(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n STATE 1:\n [1, 2]\nEND\n", "0 o 1")

    def test_evento_desconocido(self):
        self.assertError(BASICO + "ON NADA:\n VICTORY\nEND\n", "Evento desconocido")

    def test_evento_duplicado(self):
        self.assertError(BASICO + "ON TICK:\n VICTORY\nEND\nON TICK:\n VICTORY\nEND\n", "mas de una vez")

    def test_evento_vacio(self):
        self.assertError(BASICO + "ON TICK:\nEND\n", "ninguna accion")

    def test_dos_target_score(self):
        self.assertError(BASICO + "ON TARGET_SCORE 10:\n VICTORY\nEND\nON TARGET_SCORE 20:\n VICTORY\nEND\n", "Solo puede existir un evento")

    def test_accion_desconocida(self):
        self.assertError(BASICO + "ON TICK:\n VOLAR PLAYER\nEND\n", "Accion desconocida")

    def test_spawn_enemigo_inexistente(self):
        self.assertError(BASICO + "ON START:\n SPAWN ENEMY FANTASMA AT (1, 1)\nEND\n", "FANTASMA")

    def test_spawn_enemigo_con_definicion_de_otro_tipo(self):
        self.assertError(BASICO + "ON START:\n SPAWN ENEMY P AT (1, 1)\nEND\n", "tipo ENEMY")

    def test_spawn_jefe_con_definicion_de_enemigo(self):
        self.assertError(BASICO + "ON START:\n SPAWN BOSS E AT (1, 1)\nEND\n", "tipo BOSS")

    def test_fire_con_bala_inexistente(self):
        self.assertError(BASICO + "ON KEY_SPACE:\n FIRE PLAYER USING NOEXISTE\nEND\n", "NOEXISTE")

    def test_coordenada_fuera_de_la_cuadricula(self):
        self.assertError(BASICO + "ON START:\n SPAWN PLAYER AT (30, 1)\nEND\n", "fuera de la cuadricula")

    def test_direccion_invalida(self):
        self.assertError(BASICO + "ON KEY_UP:\n MOVE PLAYER ARRIBA\nEND\n", "direccion")

    def test_error_indica_linea(self):
        self.assertError(CABECERA + "DEFINE TANK X:\n TYPE: ENEMY\n HP: 0\nEND\n", "(linea 5)")


if __name__ == '__main__':
    unittest.main()
