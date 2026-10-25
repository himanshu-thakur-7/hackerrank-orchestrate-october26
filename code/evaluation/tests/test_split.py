"""Frozen dev/holdout split of the 32 labeled samples."""

import unittest
from collections import Counter

from evaluation import scorer, split
from evaluation.tests.helpers import GOLD, MANIFEST


class FrozenSplit(unittest.TestCase):
    def setUp(self):
        self.dev, self.hold, self.seed = split.load_frozen()
        self.gold = scorer.load(GOLD)

    def test_sizes_disjoint_and_complete(self):
        self.assertEqual((len(self.dev), len(self.hold)), (22, 10))
        self.assertFalse(set(self.dev) & set(self.hold))
        self.assertEqual(set(self.dev) | set(self.hold), set(self.gold))

    def test_frozen_file_is_reproducible_from_its_seed(self):
        dev, hold = split.make_split(self.gold, MANIFEST, self.seed)
        self.assertEqual((sorted(dev), sorted(hold)), (sorted(self.dev), sorted(self.hold)))

    def test_holdout_is_stratified_by_status(self):
        mix = Counter(self.gold[c][0] for c in self.hold)
        self.assertEqual(mix, Counter({"INCOMPLETE": 7, "COMPLETE": 3}))  # 22:10 of 32 -> 6.9 / 3.1

    def test_every_multi_case_evidence_format_appears_on_both_sides(self):
        fmt = split.formats(self.gold, MANIFEST)
        strata = Counter(fmt[c] for c in self.gold)
        for f, k in strata.items():
            if k >= 3:
                self.assertTrue(any(fmt[c] == f for c in self.hold), f)
                self.assertTrue(any(fmt[c] == f for c in self.dev), f)
