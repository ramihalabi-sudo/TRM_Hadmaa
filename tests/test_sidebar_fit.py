"""Engine 2.39 - the sidebar in a low window.

On a display of 768 lines the page list of the Engineering and Lab workflows filled the whole sidebar, and "Show
advanced parameters" below it was pushed off the screen (found by the CI runner, whose screen is that low: the guide
could not frame the control).  The sidebar now fits itself to its height: the two version lines go first, then the
rows of the page list get tighter.
"""
import time
import tkinter as tk
import unittest

import _common  # noqa: F401  (puts the project on the path)
from trm4 import gui as G


class SidebarFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app = G.App()
        except tk.TclError as e:
            raise unittest.SkipTest("no display: %s" % e)
        cls.app.state("normal")

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def layout(self, workflow, geometry):
        app = self.app
        app.set_workflow(workflow)
        app.geometry(geometry)
        for _ in range(4):                                       # resize, lay out, fit, lay out again
            app.update()
            time.sleep(0.03)
        side = app.side
        last = list(app.side_items.values())[-1]
        adv = app.adv_check
        return {"height": side.winfo_height(),
                "last_bottom": last.winfo_rooty() - side.winfo_rooty() + last.winfo_height(),
                "adv_mapped": bool(adv.winfo_ismapped()),
                "adv_whole": adv.winfo_height() >= adv.winfo_reqheight(),
                "last_whole": last.winfo_height() >= last.winfo_reqheight(),
                "adv_bottom": adv.winfo_rooty() - side.winfo_rooty() + adv.winfo_height(),
                "lines": sum(bool(w.winfo_ismapped()) for w in app.foot_labels), "fit": app._side_fit}

    def test_low_window_keeps_the_pages_and_the_advanced_switch(self):
        for workflow in ("engineering", "lab"):
            for geometry in ("1100x680", "1100x640"):
                s = self.layout(workflow, geometry)
                if s["height"] > 640:
                    self.skipTest("the window manager did not make the window that low")
                where = "%s %s %s" % (workflow, geometry, s)
                self.assertTrue(s["adv_mapped"], where)
                self.assertTrue(s["adv_whole"], where)             # not squeezed: its text is not cut
                self.assertTrue(s["last_whole"], where)
                self.assertLessEqual(s["adv_bottom"], s["height"], where)
                self.assertLessEqual(s["last_bottom"], s["adv_bottom"], where)

    def test_rows_get_tighter_only_as_far_as_needed(self):
        pads = [self.layout("lab", g)["fit"][1] for g in ("1100x900", "1100x720", "1100x680", "1100x640")]
        self.assertEqual(pads, sorted(pads, reverse=True))
        self.assertLess(pads[-1], pads[0])
        self.assertIn(pads[-1], G.App.SIDE_PADS)

    def test_quick_workflow_is_left_alone(self):
        s = self.layout("quick", "1100x680")
        self.assertEqual(s["fit"], (True, G.App.SIDE_PADS[0]))
        self.assertEqual(s["lines"], 2)
        self.assertFalse(s["adv_mapped"])                         # Quick has no advanced switch

    def test_switching_back_from_quick_restores_the_switch(self):
        self.layout("quick", "1100x680")
        s = self.layout("engineering", "1100x680")
        self.assertTrue(s["adv_mapped"])
        # ... above the version lines when there is room for them again
        s = self.layout("quick", "1100x900")
        s = self.layout("engineering", "1100x900")
        app = self.app
        if s["lines"] == 2:
            self.assertLess(app.adv_check.winfo_rooty(), app.foot_labels[0].winfo_rooty())


if __name__ == "__main__":
    unittest.main()
