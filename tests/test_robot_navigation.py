"""
test_robot_navigation.py — Décomposition Manhattan des trajets du robot réel.

`manhattan_legs()` est la partie PURE de AdeeptRobotController.move_to_point
(reprise du code mission validé sur le robot) : orientation par cap N/E/S/W
puis lignes droites |dx| et |dy|. Testable sans matériel.
"""

from __future__ import annotations

import unittest

from collections import namedtuple

from raspberry_pi.robot.adeept_controller import AdeeptRobotController, manhattan_legs

_Pt = namedtuple("_Pt", "x y")


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

    def test_heading_east_continues_east_then_turns(self):
        # Cap E : prolonge vers l'Est PUIS tourne (axe du cap traité en premier).
        legs, heading = manhattan_legs(1.0, 3.0, 2.0, 2.0, "E")
        self.assertEqual(legs, [("drive", 1.0), ("turn", "S"), ("drive", 1.0)])
        self.assertEqual(heading, "S")

    def test_unknown_heading_defaults_to_north(self):
        legs, heading = manhattan_legs(0.0, 0.0, 0.0, 1.0, "???")
        self.assertEqual(legs, [("drive", 1.0)])
        self.assertEqual(heading, "N")

    def test_distances_always_positive(self):
        legs, _ = manhattan_legs(3.0, 3.0, -2.0, -1.0, "N")
        for kind, value in legs:
            if kind == "drive":
                self.assertGreater(value, 0)


class TestFitToField(unittest.TestCase):
    """Garde-fou d'emprise : le parcours physique ne dépasse jamais le carré.

    fit_to_field ne touche que deux attributs → on isole l'objet via __new__
    pour ne pas dépendre du PCA9685 / I2C (absent en CI)."""

    def _ctrl(self, world_scale, max_field_m):
        c = AdeeptRobotController.__new__(AdeeptRobotController)
        c._world_scale = world_scale
        c._max_field_m = max_field_m
        return c

    def test_large_plan_is_scaled_down_to_fit(self):
        # Plan de 6 m d'envergure, échelle 1.0 → 6 m physiques : on borne à 0.9.
        c = self._ctrl(world_scale=1.0, max_field_m=0.9)
        c.fit_to_field([_Pt(0, 0), _Pt(6, 4)])
        self.assertAlmostEqual(c._world_scale, 0.9 / 6.0)

    def test_small_plan_keeps_configured_scale(self):
        # Plan qui tient déjà (1 m × échelle 0.5 = 0.5 m) : on n'augmente jamais.
        c = self._ctrl(world_scale=0.5, max_field_m=0.9)
        c.fit_to_field([_Pt(0, 0), _Pt(1, 1)])
        self.assertEqual(c._world_scale, 0.5)

    def test_origin_included_in_bounding_box(self):
        # Points loin de l'origine : l'envergure inclut (0,0) (départ + retour).
        c = self._ctrl(world_scale=1.0, max_field_m=0.9)
        c.fit_to_field([_Pt(8, 8), _Pt(10, 9)])
        self.assertAlmostEqual(c._world_scale, 0.9 / 10.0)

    def test_empty_or_degenerate_plan_is_noop(self):
        c = self._ctrl(world_scale=0.3, max_field_m=0.9)
        c.fit_to_field([])
        self.assertEqual(c._world_scale, 0.3)
        c.fit_to_field([_Pt(0, 0)])   # un seul point sur l'origine : envergure 0
        self.assertEqual(c._world_scale, 0.3)


if __name__ == "__main__":
    unittest.main()
