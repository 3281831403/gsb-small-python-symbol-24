import copy
import json
import random
import sys
import curses

MOVES = ['sword', 'shield', 'fire', 'dodge', 'heal', 'poison', 'cleanse']
ENERGY_COSTS = {
    'sword': 0,
    'shield': 0,
    'fire': 3,
    'dodge': 0,
    'heal': 2,
    'poison': 1,
    'cleanse': 0,
}
MOVES_COLORS = {0: 2,
                1: 1,
                2: 7,
                3: 1,
                4: 3,
                5: 7,
                6: 3}
CHOOSE_MESSAGE = f'Choose your action: '

SW, SH, FIRE, DODGE, HEAL, POISON, CLEANSE = range(7)

STRATEGY_WEIGHTS = {
    'sword': (9, 10, 5, 6, 8, 5, 3),
    'shield': (3, 3, 8, 4, 4, 8, 4),
    'fire': (8, 5, 7, 4, 8, 5, 10),
    'dodge': (8, 4, 8, 3, 7, 8, 4),
    'heal': (6, 5, 8, 4, 7, 7, 4),
    'poison': (8, 5, 7, 4, 8, 7, 10),
    'cleanse': (10, 5, 5, 6, 7, 5, 5),
}
DEFAULT_WEIGHTS = (5, 5, 5, 5, 5, 5, 5)
FIXED_PLAYER_MOVES = (
    'fire', 'sword', 'poison', 'heal', 'shield',
    'sword', 'dodge', 'sword', 'fire', 'sword',
    'poison', 'sword', 'sword', 'shield', 'sword',
    'sword', 'sword', 'sword', 'sword', 'sword',
    'sword', 'sword', 'sword', 'sword', 'sword',
)
FIXED_SEED = 20260930


def validate_player_move(move, energy, until_shield):
    if move not in MOVES:
        return 'Invalid action!'
    if energy < ENERGY_COSTS[move]:
        return 'Not enough energy!'
    if move == 'shield' and until_shield:
        return f'You will be able to use shield again in {until_shield} turns.'
    return None


def dominant_player_move(history):
    counts = {move: history.count(move) for move in MOVES}
    return max(MOVES, key=lambda move: (counts[move], -MOVES.index(move)))


def battle_snapshot(player, enemy):
    return {
        'player': {
            'health': player.health,
            'energy': player.energy,
            'move': player.move,
            'effects': dict(player.effects),
            'history': list(player.history),
            'until_shield': player.until_shield,
        },
        'enemy': {
            'health': enemy.health,
            'energy': enemy.energy,
            'move': enemy.move,
            'effects': dict(enemy.effects),
            'history': list(enemy.history),
            'until_shield': enemy.until_shield,
        },
    }


def run_fixed_battle(player_moves=FIXED_PLAYER_MOVES, seed=FIXED_SEED):
    player = Player()
    enemy = Enemy()
    player.enemy = enemy
    enemy.enemy = player
    rng = random.Random(seed)

    snapshots = [copy.deepcopy(battle_snapshot(player, enemy))]
    turns = []

    for turn_number, player_move in enumerate(player_moves, start=1):
        error = validate_player_move(player_move, player.energy, player.until_shield)
        if error is not None:
            raise ValueError(f'Invalid fixed battle move on turn {turn_number}: {error}')

        player.move = player_move
        player.history.append(player.move)
        if len(player.history) > 10:
            player.history = player.history[len(player.history) - 10:]

        enemy.take_turn(rng)
        enemy.play()
        player.play()
        player.check_effects()
        enemy.check_effects()

        snapshot = copy.deepcopy(battle_snapshot(player, enemy))
        snapshots.append(copy.deepcopy(snapshot))
        turns.append({
            'turn': turn_number,
            'player_move': player_move,
            'enemy_move': enemy.move,
            'snapshot': copy.deepcopy(snapshot),
        })

        if player.health <= 0 or enemy.health <= 0:
            break

    if player.health <= 0 and enemy.health <= 0:
        outcome = 'draw'
    elif enemy.health <= 0:
        outcome = 'win'
    elif player.health <= 0:
        outcome = 'lose'
    else:
        outcome = 'ongoing'

    return {
        'seed': seed,
        'outcome': outcome,
        'turns': turns,
        'snapshots': snapshots,
    }


class Player:
    def __init__(self):
        self.health = 100
        self.energy = 10
        self.enemy = None
        self.move = 'None'
        self.effects = {}
        self.history = []

        self.sword_dmg = 8
        self.poison_dmg = 2
        self.fire_dmg = 5
        self.fire_time = 3
        self.poison_time = 5
        self.dodged_dmg = 2

        self.until_shield = 0

    def take_turn(self, stdscr):
        stdscr.addstr(5, 0, CHOOSE_MESSAGE)
        offset = 0
        for i in range(len(MOVES)):
            move = MOVES[i]
            add = ' | ' if i < len(MOVES) - 1 else ''
            c = 0 if move == 'shield' and self.until_shield else 1
            stdscr.addstr(6, offset, move.swapcase(), curses.color_pair(MOVES_COLORS[c]))
            stdscr.addstr(6, offset + len(move), add, curses.color_pair(1))
            offset += len(move) + 3
        stdscr.refresh()

        move = []
        cursor_x = 0

        while True:
            key = stdscr.getch(8, cursor_x)

            if key in [curses.KEY_ENTER, 10, 13]:
                stdscr.addstr(10, 0, " " * 100)
                move_str = ''.join(move).lower()
                msg = validate_player_move(move_str, self.energy, self.until_shield)
                valid = msg is None

                if not valid:
                    stdscr.addstr(10, 0, " " * 100)
                    stdscr.addstr(10, 0, msg, curses.color_pair(2))
                    stdscr.refresh()
                    move.clear()
                    cursor_x = 0
                    stdscr.addstr(8, 0, " " * 100)
                    stdscr.move(8, 0)
                    continue
                break

            elif key in [curses.KEY_BACKSPACE, 127]:
                if move:
                    move.pop()
                    cursor_x -= 1
                    stdscr.addstr(8, cursor_x, " ")
                    stdscr.move(8, cursor_x)

            elif 32 <= key <= 126:
                move.append(chr(key))
                stdscr.addstr(8, cursor_x, chr(key))
                cursor_x += 1

            stdscr.refresh()

        self.move = ''.join(move)
        self.history.append(self.move)
        if len(self.history) > 10:
            self.history = self.history[len(self.history) - 10:]

    def check_effects(self):
        if self.move == 'cleanse':
            self.effects.clear()
        else:
            if 'fire' in self.effects.keys():
                self.effects['fire'] -= 1
                self.health -= self.enemy.fire_dmg
                if self.effects['fire'] == 0:
                    self.effects.pop('fire')
            if 'poison' in self.effects.keys():
                self.effects['poison'] -= 1
                self.health -= self.enemy.poison_dmg
                if self.effects['poison'] == 0:
                    self.effects.pop('poison')

    def play(self):
        self.until_shield = max(0, self.until_shield - 1)
        if self.move == 'shield':
            self.until_shield = 2
        if self.enemy.move == 'sword':
            if self.move != 'shield':
                if self.move == 'dodge':
                    self.health -= self.enemy.sword_dmg // 2
                else:
                    self.health -= self.enemy.sword_dmg
        if self.move == 'fire':
            self.enemy.effects['fire'] = self.enemy.fire_time
            self.energy -= ENERGY_COSTS['fire']
        if self.move == 'poison':
            self.enemy.effects['poison'] = self.enemy.poison_time
            self.energy -= ENERGY_COSTS['poison']
        if self.move == 'heal':
            self.health = min(self.health + 10, 100)
            self.energy -= ENERGY_COSTS['heal']


class Enemy(Player):
    def __init__(self):
        super().__init__()
        self.energy = 10000
        self.effects = {}
        self.sword_dmg = 10

    def get_weights(self, strategy_table=None):
        table = STRATEGY_WEIGHTS if strategy_table is None else strategy_table
        preferred = dominant_player_move(self.enemy.history)
        base_weights = table.get(preferred, DEFAULT_WEIGHTS)
        weights = list(base_weights)

        if self.enemy.energy < 3:
            weights[SW] = min(10, weights[SW] + 2)

        if self.health < 50:
            weights[HEAL] = min(10, weights[HEAL] + 2)
        if self.health < 25:
            weights[CLEANSE] = min(10, weights[CLEANSE] + 1)
            weights[HEAL] = min(10, weights[HEAL] + 4)
            weights[DODGE] = min(10, weights[DODGE] + 1)
            weights[SH] = min(10, weights[SH] + 2)

        if self.enemy.history.count('sword') > 4:
            weights[SH] = min(10, weights[SH] + 1)

        if self.enemy.health < 25:
            weights[SW] = min(10, weights[SW] + 2)
            weights[POISON] = min(10, weights[POISON] + 2)
            weights[FIRE] = min(10, weights[FIRE] + 2)

        if self.health < 15:
            weights[SH] = min(10, weights[SH] + 2)
            weights[HEAL] = min(10, weights[HEAL] + 3)
            weights[CLEANSE] = min(10, weights[CLEANSE] + 2)
            weights[DODGE] = max(1, weights[DODGE] - 2)
            weights[SW] = max(1, weights[SW] - 2)
            weights[POISON] = max(1, weights[POISON] - 2)
            weights[FIRE] = max(1, weights[FIRE] - 2)

        if self.enemy.health < 10:
            weights[SW] = 10

        if self.enemy.until_shield:
            weights[SW] = min(10, weights[SW] + 1)

        if 'fire' in self.enemy.history[-2:] or 'poison' in self.enemy.history[-2:]:
            weights[CLEANSE] = min(10, weights[CLEANSE] + 2)
            weights[HEAL] = min(10, weights[HEAL] + 1)

        if 'fire' in self.enemy.effects.keys():
            weights[FIRE] = max(1, weights[FIRE] - 2)
        if 'poison' in self.enemy.effects.keys():
            weights[POISON] = max(1, weights[POISON] - 2)

        if not self.effects.keys():
            weights[CLEANSE] = 0

        if self.enemy.history.count('poison') + self.enemy.history.count('fire') > 4:
            weights[CLEANSE] = min(10, weights[CLEANSE] + 1)

        return tuple(weights)

    def take_turn(self, rng=random):
        weights = self.get_weights()

        self.move = rng.choices(MOVES, k=1, weights=weights)[0]
        self.energy = 10000


def main(stdscr):
    curses.start_color()

    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

    player = Player()
    enemy = Enemy()
    player.enemy = enemy
    enemy.enemy = player

    while True:
        stdscr.clear()
        restart = False
        if player.health <= 0 and enemy.health <= 0:
            stdscr.addstr(0, 0, 'The battle drained both of you.', curses.color_pair(4))
            restart = True
        elif player.health <= 0:
            stdscr.addstr(0, 0, 'You died!', curses.color_pair(2))
            restart = True
        elif enemy.health <= 0:
            stdscr.addstr(0, 0, 'You won!', curses.color_pair(3))
            restart = True

        if restart:
            player = Player()
            enemy = Enemy()
            player.enemy = enemy
            enemy.enemy = player
            stdscr.addstr(10, 0, 'Press any key to restart...')
        else:
            player_fx = ' | '.join([f'{i[0].capitalize().ljust(6, " ")} {i[1]}' for i in player.effects.items()])
            enemy_fx = ' | '.join([f'{i[0].capitalize().ljust(6, " ")} {i[1]}' for i in enemy.effects.items()])
            stdscr.addstr(0, 0, f'You   | Hp {str(player.health).rjust(3, " ")} '
                                f'| Energy {str(player.energy).rjust(2, " ")} | '
                                f'{player_fx}', curses.color_pair(1))
            stdscr.addstr(1, 0, f'Enemy | Hp {str(enemy.health).rjust(3, " ")} |           '
                                f'| {enemy_fx}', curses.color_pair(4))

            player.take_turn(stdscr)
            enemy.take_turn()

            enemy.play()
            player.play()

            player.check_effects()
            enemy.check_effects()

            player_msg = f'You played {player.move.swapcase()}!'
            enemy_msg = f'Enemy played {enemy.move.swapcase()}!'

            stdscr.addstr(10, 0, player_msg, curses.color_pair(1))
            stdscr.addstr(10, len(player_msg), ' | ')
            stdscr.addstr(10, len(player_msg) + 3, enemy_msg, curses.color_pair(4))

            stdscr.addstr(11, 0, 'Press any key to continue...')

        stdscr.refresh()
        stdscr.getch()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixed-battle':
        print(json.dumps(run_fixed_battle(), sort_keys=True))
    else:
        curses.wrapper(main)
