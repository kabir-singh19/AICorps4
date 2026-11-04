import unittest
from countermeasure_matcher import load_library, match_site


class MatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_library()

    def match(self, **changes):
        site = dict(site_id='TEST', example=True, site_type='signalized intersection',
                    crash_patterns=['pedestrian'], area_type='urban', severity_scope='All')
        site.update(changes)
        return match_site(site, self.rows)

    def ids(self, **changes):
        return {c['cm_id'] for c in self.match(**changes)['candidates']}

    def review_ids(self, **changes):
        return {c['cm_id'] for c in self.match(**changes)['engineering_review']}

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
        self.assertNotIn('CM020', self.review_ids(**args, time_of_day='day'))
        self.assertNotIn('CM020', self.review_ids(**args))
        self.assertIn('CM020', self.review_ids(**args, time_of_day='night'))

    def test_aggregate_scope_is_flagged(self):
        c = next(c for c in self.match()['engineering_review'] if c['cm_id'] == 'CM013')
        self.assertEqual(c['match_kind'], 'aggregate_crash_scope')
        self.assertTrue(any('subtype' in x for x in c['review_needed']))

    def test_fatal_serious_scope_not_inferred(self):
        result = self.match(severity_scope='K;A')
        for c in result['candidates'] + result['engineering_review']:
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
        self.assertNotIn('CM011', self.review_ids(**args))
        self.assertIn('CM011', self.review_ids(**args, intersection_related=False, animal_related=False))
        self.assertNotIn('CM011', self.review_ids(**args, intersection_related=False, animal_related=True))

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



    def test_pedestrian_segment_separates_broad_treatments(self):
        result = self.match(site_type='segment')
        direct = {c['cm_id'] for c in result['candidates']}
        broader = {c['cm_id'] for c in result['engineering_review']}
        self.assertTrue({'CM021', 'CM023'} <= broader)
        self.assertFalse({'CM021', 'CM023'} & direct)
        self.assertIn('CM006', direct)
        self.assertFalse(direct & broader)

    def test_partial_support_names_supported_subset(self):
        result = self.match(crash_patterns=['pedestrian', 'rear_end'])
        self.assertNotIn('CM001', {c['cm_id'] for c in result['candidates']})
        c = next(c for c in result['engineering_review'] if c['cm_id'] == 'CM001')
        self.assertEqual(c['category'], 'partial_crash_type_support')
        self.assertEqual(c['matched_crash_patterns'], ['pedestrian'])

    def test_all_request_does_not_imply_subtype_support(self):
        result = self.match(crash_patterns=['all'])
        self.assertEqual(result['candidates'], [])
        self.assertTrue(result['engineering_review'])
        self.assertTrue(all(c['category'] == 'broader_evidence'
                            for c in result['engineering_review']))

    def test_groups_preserve_safety_and_scope(self):
        import json
        from countermeasure_matcher import ROOT
        for site in json.loads((ROOT / 'example_sites.json').read_text()):
            result = self.match(**site)
            for c in result['candidates']:
                self.assertEqual(c['category'], 'direct_crash_type_support')
                self.assertEqual(set(c['matched_crash_patterns']), set(site['crash_patterns']))
            for c in result['engineering_review']:
                self.assertEqual(c['status'], 'engineering_review_only')
            for c in result['candidates'] + result['engineering_review']:
                self.assertFalse(c['eligible_for_benefit_calculation'])
                self.assertTrue(c['review_needed'])
            self.assertFalse({'CM022', 'CM024'} & {
                c['cm_id'] for c in result['candidates'] + result['engineering_review']})

    def test_cli_labels_both_groups(self):
        import subprocess
        import sys
        from countermeasure_matcher import ROOT
        run = subprocess.run([sys.executable, str(ROOT / 'countermeasure_matcher.py')],
                             check=True, capture_output=True, text=True)
        self.assertIn('DIRECT CRASH-TYPE MATCHES', run.stdout)
        self.assertIn('ENGINEERING REVIEW ONLY', run.stdout)
        self.assertIn('Direct matches:', run.stdout)



    def test_shoulder_rumble_matches_rural_departure(self):
        self.assertIn('CM025', self.ids(site_type='segment', area_type='rural', crash_patterns=['run_off_road']))

    def test_shoulder_rumble_rejects_urban_and_head_on(self):
        self.assertNotIn('CM025', self.ids(site_type='segment', area_type='urban', crash_patterns=['run_off_road']))
        self.assertNotIn('CM025', self.ids(site_type='segment', area_type='rural', crash_patterns=['head_on']))

    def test_shoulder_severity_does_not_transfer_to_ka(self):
        for severity, expected in [('K;A;B;C', True), ('K;A', False)]:
            result = self.match(site_type='segment', area_type='rural', crash_patterns=['run_off_road'], severity_scope=severity)
            c = next(c for c in result['candidates'] if c['cm_id'] == 'CM025')
            self.assertEqual(c['severity_scope_matches'], expected)
            self.assertFalse(c['eligible_for_benefit_calculation'])

    def test_countdown_pedestrian_match_and_exclusions(self):
        self.assertIn('CM026', self.ids())
        self.assertNotIn('CM026', self.ids(crash_patterns=['angle']))
        self.assertNotIn('CM026', self.ids(site_type='segment'))
        self.assertNotIn('CM026', self.ids(site_type='unsignalized intersection'))
        self.assertNotIn('CM026', self.ids(area_type='rural'))

    def test_countdown_partial_support_stays_in_review(self):
        result = self.match(crash_patterns=['pedestrian', 'rear_end'])
        c = next(c for c in result['engineering_review'] if c['cm_id'] == 'CM026')
        self.assertEqual(c['matched_crash_patterns'], ['pedestrian'])
        self.assertEqual(c['category'], 'partial_crash_type_support')

    def test_new_aggregate_treatments_are_review_only(self):
        args = dict(site_type='unsignalized intersection', area_type='rural', crash_patterns=['angle'])
        self.assertTrue({'CM027', 'CM028', 'CM029'} <= self.review_ids(**args))
        self.assertFalse({'CM027', 'CM028', 'CM029'} & self.ids(**args))

    def test_stop_treatments_reject_signals_and_rural_mismatch(self):
        result = self.match(area_type='rural', crash_patterns=['angle'])
        ids = {c['cm_id'] for c in result['candidates'] + result['engineering_review']}
        self.assertFalse({'CM027', 'CM028', 'CM029'} & ids)
        urban = self.review_ids(site_type='unsignalized intersection', crash_patterns=['angle'])
        self.assertFalse({'CM027', 'CM028'} & urban)
        self.assertIn('CM029', urban)

    def test_uncertainty_and_manual_prerequisites_remain_visible(self):
        result = self.match(site_type='unsignalized intersection', area_type='rural', crash_patterns=['all'])
        c = next(c for c in result['engineering_review'] if c['cm_id'] == 'CM029')
        self.assertIn('caution', c['evidence']['limitations'])
        self.assertTrue(any('Four-leg' in x for x in c['review_needed']))
        c = next(c for c in result['engineering_review'] if c['cm_id'] == 'CM028')
        self.assertIn('Near-neutral', c['evidence']['limitations'])

    def test_new_evidence_records_are_traceable(self):
        expected = {'CM025': ('3454', '0.64', '5'), 'CM026': ('10119', '0.912', '4'),
                    'CM027': ('315', '0.52', '2'), 'CM028': ('2708', '0.987', '3'),
                    'CM029': ('446', '0.95', '4')}
        for row in self.rows:
            if row['cm_id'] in expected:
                self.assertEqual((row['cmf_id'], row['cmf'], row['star_rating']), expected[row['cm_id']])
                self.assertTrue(row['source_url'].endswith('facid=' + row['cmf_id']))
                self.assertEqual(row['original_study_review_status'], 'not_reviewed_this_pass')
        self.assertEqual(len({r['cmf_id'] for r in self.rows if r['cmf_id']}), 32)

    def test_output_exposes_evidence_verification_limits(self):
        c = next(c for c in self.match()['candidates'] if c['cm_id'] == 'CM026')
        self.assertEqual(c['evidence']['record_check_status'], 'indexed_record_crosschecked')
        self.assertEqual(c['evidence']['original_study_review_status'], 'not_reviewed_this_pass')
        self.assertEqual(c['evidence']['review_date'], '2026-10-21')



    def test_speed_humps_area_and_injury_scope(self):
        args = dict(site_type='segment', crash_patterns=['all'], area_type='suburban', severity_scope='A;B;C')
        c = next(c for c in self.match(**args)['engineering_review'] if c['cm_id'] == 'CM030')
        self.assertTrue(c['severity_scope_matches'])
        self.assertNotIn('CM030', self.review_ids(**dict(args, area_type='rural')))
        c = next(c for c in self.match(**dict(args, severity_scope='K;A'))['engineering_review'] if c['cm_id'] == 'CM030')
        self.assertFalse(c['severity_scope_matches'])

    def test_curve_feedback_keeps_aggregate_and_rural_limits(self):
        args = dict(site_type='segment', crash_patterns=['run_off_road'], area_type='rural')
        self.assertIn('CM031', self.review_ids(**args))
        self.assertNotIn('CM031', self.ids(**args))
        self.assertNotIn('CM031', self.review_ids(**dict(args, area_type='urban')))

    def test_conflict_warning_control_and_area(self):
        args = dict(site_type='unsignalized intersection', crash_patterns=['angle'], area_type='rural')
        self.assertIn('CM032', self.review_ids(**args))
        self.assertNotIn('CM032', self.ids(**args))
        self.assertNotIn('CM032', self.review_ids(**dict(args, area_type='urban')))
        self.assertNotIn('CM032', self.review_ids(**dict(args, site_type='signalized intersection')))

    def test_markings_preserve_scope_and_manual_road_class(self):
        result = self.match(site_type='segment', crash_patterns=['all'], severity_scope='K;A;B;C')
        c = next(c for c in result['engineering_review'] if c['cm_id'] == 'CM033')
        self.assertTrue(c['severity_scope_matches'])
        self.assertTrue(any('Freeway/expressway' in x for x in c['review_needed']))
        self.assertFalse(c['eligible_for_benefit_calculation'])

    def test_larger_heads_only_direct_for_angle(self):
        self.assertIn('CM034', self.ids(crash_patterns=['angle']))
        self.assertNotIn('CM034', self.ids(crash_patterns=['rear_end']))
        self.assertNotIn('CM034', self.ids(crash_patterns=['angle'], site_type='unsignalized intersection'))
        c = next(c for c in self.match(crash_patterns=['angle','rear_end'])['engineering_review'] if c['cm_id'] == 'CM034')
        self.assertEqual(c['matched_crash_patterns'], ['angle'])

    def test_second_expansion_traceability_and_missing_error(self):
        expected = {'CM030': ('132','0.6','3'), 'CM031': ('6885','0.95','4'),
                    'CM032': ('8474','0.704','5'), 'CM033': ('8102','0.893','5'), 'CM034': ('2333','0.58','5')}
        self.assertEqual(len(self.rows), 34)
        for r in self.rows:
            if r['cm_id'] in expected:
                self.assertEqual((r['cmf_id'],r['cmf'],r['star_rating']), expected[r['cm_id']])
                self.assertTrue(r['source_url'].endswith('facid='+r['cmf_id']))
                self.assertEqual(r['original_study_review_status'], 'not_reviewed_this_pass')
        hump = next(r for r in self.rows if r['cm_id']=='CM030')
        self.assertEqual(hump['standard_error_unadjusted'], '')
        self.assertIn('Adjusted SE is 0.16', hump['limitations'])


if __name__ == '__main__':
    unittest.main()
