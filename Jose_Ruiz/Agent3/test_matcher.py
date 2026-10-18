import unittest
from countermeasure_matcher import load_library, match_site


class MatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_library()

    def match(self, **changes):
        site = dict(site_id='TEST', synthetic=True, site_type='signalized intersection',
                    crash_patterns=['pedestrian'], area_type='urban', severity_scope='All')
        site.update(changes)
        return match_site(site, self.rows)

    def ids(self, **changes):
        return {c['cm_id'] for c in self.match(**changes)['candidates']}

    def test_pedestrian_signal_candidates(self):
        self.assertTrue({'CM001', 'CM002'} <= self.ids())
        self.assertNotIn('CM004', self.ids())

    def test_general_tags_cannot_create_false_angle_match(self):
        ids = self.ids(site_type='unsignalized intersection', crash_patterns=['angle'])
        self.assertNotIn('CM003', ids)  # Broad CSV tag includes angle; its CMF does not.
        self.assertNotIn('CM001', ids)

    def test_urban_site_rejects_rural_study(self):
        self.assertNotIn('CM007', self.ids(site_type='segment', crash_patterns=['run_off_road']))

    def test_rural_departure_candidate(self):
        self.assertIn('CM007', self.ids(site_type='segment', area_type='rural', crash_patterns=['run_off_road']))

    def test_nighttime_required(self):
        args = dict(site_type='segment', crash_patterns=['rear_end'])
        self.assertNotIn('CM020', self.ids(**args, time_of_day='day'))
        self.assertNotIn('CM020', self.ids(**args))
        self.assertIn('CM020', self.ids(**args, time_of_day='night'))

    def test_aggregate_scope_is_flagged(self):
        c = next(c for c in self.match()['candidates'] if c['cm_id'] == 'CM013')
        self.assertEqual(c['match_kind'], 'aggregate_crash_scope')
        self.assertTrue(any('subtype' in x for x in c['review_needed']))

    def test_fatal_serious_scope_not_inferred(self):
        for c in self.match(severity_scope='K;A')['candidates']:
            self.assertFalse(c['severity_scope_matches'])
            self.assertFalse(c['eligible_for_benefit_calculation'])

    def test_process_entries_excluded(self):
        self.assertFalse({'CM022', 'CM024'} & self.ids())

    def test_unrated_evidence_keeps_null_rating(self):
        c = next(c for c in self.match(site_type='segment')['candidates'] if c['cm_id'] == 'CM006')
        self.assertIsNone(c['evidence']['star_rating'])
        self.assertIn('Research quality is officially unrated.', c['review_needed'])

    def test_conditional_study_requires_explicit_flags(self):
        args = dict(site_type='segment', area_type='rural', crash_patterns=['run_off_road'])
        self.assertNotIn('CM011', self.ids(**args))
        self.assertIn('CM011', self.ids(**args, intersection_related=False, animal_related=False))
        self.assertNotIn('CM011', self.ids(**args, intersection_related=False, animal_related=True))

    def test_invalid_input_is_actionable(self):
        for changes in [dict(crash_patterns=['speeding']), dict(site_type='intersection'),
                        dict(crash_patterns=[]), dict(winter_month='false')]:
            with self.assertRaises(ValueError):
                self.match(**changes)

    def test_no_matches_is_valid(self):
        result = match_site(dict(site_id='EMPTY', site_type='segment',
                                 crash_patterns=['bicycle'], area_type='rural'),
                            [r for r in self.rows if r['cm_id'] == 'CM002'])
        self.assertEqual(result['candidates'], [])



if __name__ == '__main__':
    unittest.main()
