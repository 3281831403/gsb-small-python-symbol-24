import copy
import unittest
from unittest import mock

import main


def make_battlers():
    player = main.Player()
    enemy = main.Enemy()
    player.enemy = enemy
    enemy.enemy = player
    return player, enemy


class FakeScreen:
    def __init__(self, keys):
        self.keys = list(keys)

    def addstr(self, *args):
        return None

    def refresh(self):
        return None

    def move(self, row, col):
        return None

    def getch(self, *args):
        return self.keys.pop(0)


class BattleRulesTests(unittest.TestCase):
    def test_player_move_validation_table(self):
        cases = (
            ('sword', 0, 0, None),
            ('dodge', 0, 0, None),
            ('shield', 0, 0, None),
            ('cleanse', 0, 0, None),
            ('fire', 3, 0, None),
            ('poison', 1, 0, None),
            ('heal', 2, 0, None),
            ('fire', 2, 0, 'Not enough energy!'),
            ('poison', 0, 0, 'Not enough energy!'),
            ('heal', 1, 0, 'Not enough energy!'),
            ('shield', 0, 2, 'You will be able to use shield again in 2 turns.'),
            ('unknown', 10, 0, 'Invalid action!'),
        )

        for move, energy, until_shield, expected in cases:
            with self.subTest(move=move, energy=energy, until_shield=until_shield):
                self.assertEqual(
                    main.validate_player_move(move, energy, until_shield),
                    expected,
                )

    def test_enemy_strategy_weights_table(self):
        def weights(history=(), player_health=100, enemy_health=100,
                    player_energy=10, player_shield=0, player_effects=(),
                    enemy_effects=()):
            player, enemy = make_battlers()
            player.history = list(history)
            player.health = player_health
            player.energy = player_energy
            player.until_shield = player_shield
            player.effects = {effect: 1 for effect in player_effects}
            enemy.health = enemy_health
            enemy.effects = {effect: 1 for effect in enemy_effects}
            return enemy.get_weights()

        cases = (
            ({'history': ('sword',)}, (9, 10, 5, 6, 8, 5, 0)),
            ({'history': ('sword',) * 5, 'player_energy': 2}, (10, 10, 5, 6, 8, 5, 0)),
            ({'history': ('sword',) * 5}, (9, 11, 5, 6, 8, 5, 0)),
            ({'history': ('sword',), 'enemy_health': 49}, (9, 10, 5, 6, 10, 5, 0)),
            ({'history': ('sword',), 'enemy_health': 24}, (9, 12, 5, 7, 10, 5, 0)),
            ({'history': ('sword',), 'enemy_health': 14}, (7, 14, 3, 5, 10, 3, 0)),
            ({'history': ('sword',), 'player_health': 24}, (11, 10, 7, 6, 8, 7, 0)),
            ({'history': ('sword',), 'player_health': 9}, (10, 10, 7, 6, 8, 7, 0)),
            ({'history': ('sword',), 'player_shield': 1}, (10, 10, 5, 6, 8, 5, 0)),
            ({
                'history': ('fire',),
                'player_effects': ('fire', 'poison'),
                'enemy_effects': ('poison',),
            }, (8, 5, 5, 4, 9, 3, 10)),
            ({'history': ('fire', 'poison') * 3}, (8, 5, 7, 4, 9, 5, 1)),
            ({}, (9, 10, 5, 6, 8, 5, 0)),
            ({'history': ('shield',)}, (3, 3, 8, 4, 4, 8, 0)),
        )

        for setup, expected in cases:
            with self.subTest(setup=setup):
                actual = weights(**setup)
                self.assertEqual(actual, tuple(min(value, 10) for value in expected))
                for value in actual:
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, 10)

    def test_weights_do_not_depend_on_strategy_table_order(self):
        player, enemy = make_battlers()
        player.history = ['sword', 'sword', 'fire']
        forward = dict(main.STRATEGY_WEIGHTS)
        reverse = dict(reversed(list(main.STRATEGY_WEIGHTS.items())))
        original = copy.deepcopy(main.STRATEGY_WEIGHTS)

        self.assertEqual(enemy.get_weights(forward), enemy.get_weights(reverse))
        self.assertEqual(main.STRATEGY_WEIGHTS, original)

    def test_failed_ui_input_rolls_back_and_does_not_pollute_next_turn(self):
        cases = (
            'xyz',
            'fire',
            'heal',
            'shield',
            'poison',
        )

        for failed_move in cases:
            with self.subTest(failed_move=failed_move):
                player, enemy = make_battlers()
                if failed_move == 'fire':
                    player.energy = 2
                elif failed_move == 'heal':
                    player.energy = 1
                elif failed_move == 'poison':
                    player.energy = 0
                elif failed_move == 'shield':
                    player.until_shield = 2
                before = copy.deepcopy(main.battle_snapshot(player, enemy))
                keys = [ord(char) for char in failed_move]
                keys += [10]
                keys += [ord('s'), ord('w'), ord('o'), ord('r'), ord('d'), 10]
                screen = FakeScreen(keys)

                with mock.patch.object(main.curses, 'color_pair', return_value=0):
                    player.take_turn(screen)

                after = main.battle_snapshot(player, enemy)
                self.assertEqual(player.move, 'sword')
                self.assertEqual(player.history, ['sword'])
                self.assertEqual(after['player']['energy'], before['player']['energy'])
                self.assertEqual(after['player']['until_shield'], before['player']['until_shield'])
                self.assertEqual(screen.keys, [])

    def test_failed_fixed_battle_leaves_no_battle_state_for_later_run(self):
        bad_moves = ('fire', 'fire', 'fire', 'sword', 'fire')

        with self.assertRaises(ValueError):
            main.run_fixed_battle(bad_moves, seed=main.FIXED_SEED)

        first = main.run_fixed_battle(seed=main.FIXED_SEED)
        second = main.run_fixed_battle(seed=main.FIXED_SEED)
        self.assertEqual(first, second)

    def test_fixed_battle_is_deterministic_with_deep_snapshots(self):
        first = main.run_fixed_battle()
        second = main.run_fixed_battle()

        self.assertEqual(first['seed'], main.FIXED_SEED)
        self.assertEqual(first['outcome'], 'lose')
        self.assertEqual(len(first['turns']), 21)
        self.assertEqual(len(first['snapshots']), 22)
        self.assertEqual(
            [turn['enemy_move'] for turn in first['turns']],
            ['fire', 'heal', 'shield', 'shield', 'fire', 'cleanse', 'dodge',
             'heal', 'sword', 'heal', 'cleanse', 'fire', 'heal', 'dodge',
             'sword', 'sword', 'heal', 'sword', 'fire', 'sword', 'shield'],
        )
        self.assertEqual(first, second)

        first['turns'][0]['snapshot']['player']['health'] = 999
        first['snapshots'][1]['enemy']['effects']['poison'] = 9
        self.assertEqual(first['snapshots'][1]['player']['health'], 95)
        self.assertNotIn('poison', first['turns'][0]['snapshot']['enemy']['effects'])
        self.assertNotEqual(first, second)
        self.assertEqual(second['snapshots'][0]['player']['health'], 100)
        self.assertNotIn('poison', second['snapshots'][1]['enemy']['effects'])

        final = first['snapshots'][-1]
        self.assertEqual(final['player']['health'], 0)
        self.assertEqual(final['enemy']['health'], 23)
        self.assertEqual(final['enemy']['until_shield'], 2)

    def test_battle_snapshot_is_a_deep_copy(self):
        player, enemy = make_battlers()
        player.history = ['fire']
        player.effects['poison'] = 2
        enemy.history = ['sword']
        enemy.effects['fire'] = 3

        snapshot = main.battle_snapshot(player, enemy)
        player.history.append('sword')
        player.effects['poison'] = 1
        player.effects['fire'] = 1
        enemy.history.clear()
        enemy.effects.clear()

        self.assertEqual(snapshot['player']['history'], ['fire'])
        self.assertEqual(snapshot['player']['effects'], {'poison': 2})
        self.assertEqual(snapshot['enemy']['history'], ['sword'])
        self.assertEqual(snapshot['enemy']['effects'], {'fire': 3})


if __name__ == '__main__':
    unittest.main()
