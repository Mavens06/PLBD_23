"""
test_robot_navigation.py — Décomposition Manhattan des trajets du robot réel.

`manhattan_legs()` est la partie PURE de AdeeptRobotController.move_to_point
(reprise du code mission validé sur le robot) : orientation par cap N/E/S/W
puis lignes droites |dx| et |dy|. Testable sans matériel.
"""

from __future__ import annotations

import unittest

from raspberry_pi.robot.adeept_controller import manhattan_legs


class TestManhattanLegs(unittest.TestCase):
    def test_same_point_no_legs(self):
        legs, heading = manhattan_legs(2.0, 3.0, 2.0, 3.0, "N")
        self.assertEqual(legs, [])
        self.assertEqual(heading, "N")

    def test_pure_north_no_turn(self):
        legs, heading = manhattan_legs(0.0, 0.0, 0.0, 3.0, "N")
        self.assertEqual(legs, [("drive", 3.0)])
        self.assertEqual(heading, "N")

    def test_north_first_then_east(self):
        # Y d'abord : cap N conservé pour la 1re ligne droite, puis virage Est.
        legs, heading = manhattan_legs(0.0, 0.0, 2.0, 3.0, "N")
        self.assertEqual(legs, [("drive", 3.0),
                                ("turn", "E"), ("drive", 2.0)])
        self.assertEqual(heading, "E")

    def test_south_first_then_west_negative_deltas(self):
        legs, heading = manhattan_legs(4.0, 5.0, 1.0, 2.0, "N")
        self.assertEqual(legs, [("turn", "S"), ("drive", 3.0),
                                ("turn", "W"), ("drive", 3.0)])
        self.assertEqual(heading, "W")

    def test_no_turn_if_already_heading(self):
        legs, _ = manhattan_legs(0.0, 0.0, 5.0, 0.0, "E")
        self.assertEqual(legs, [("drive", 5.0)])

    def test_unknown_heading_defaults_to_north(self):
        legs, heading = manhattan_legs(0.0, 0.0, 0.0, 1.0, "???")
        self.assertEqual(legs, [("drive", 1.0)])
        self.assertEqual(heading, "N")

    def test_distances_always_positive(self):
        legs, _ = manhattan_legs(3.0, 3.0, -2.0, -1.0, "N")
        for kind, value in legs:
            if kind == "drive":
                self.assertGreater(value, 0)


if __name__ == "__main__":
    unittest.main()
