"""Agent 3 preliminary candidate screening. Python 3.9+, standard library only."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALIASES = {'vehicle/pedestrian': 'pedestrian', 'head on': 'head_on',
           'rear end': 'rear_end', 'run off road': 'run_off_road',
           'fixed object': 'fixed_object', 'single vehicle': 'single_vehicle',
           'cross median': 'cross_median', 'all crashes': 'all'}
PATTERNS = {'pedestrian', 'head_on', 'rear_end', 'run_off_road', 'fixed_object',
            'single_vehicle', 'cross_median', 'angle', 'sideswipe', 'all', 'bicycle'}
LOCATIONS = {'segment', 'signalized intersection', 'unsignalized intersection'}


def normalize(value):
    value = value.strip().lower().replace('-', ' ')
    return ALIASES.get(value, value)


def load_library(path=ROOT / 'countermeasure_library.csv'):
    with open(path, encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'cm_id', 'specific_treatment', 'cmf_crash_types', 'site_type',
                    'severity_scope', 'area_type', 'cmf', 'cmf_id', 'star_rating',
                    'verification_status', 'applicability_conditions', 'source_url',
                    'limitations', 'rating_status'}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Missing CSV columns: ' + ', '.join(sorted(missing)))
        rows = list(reader)
    if len({r['cm_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate countermeasure IDs')
    for row in rows:
        if row['cmf'] and float(row['cmf']) <= 0:
            raise ValueError('CMF must be positive: ' + row['cm_id'])
    return rows


def validate_site(site):
    if not isinstance(site, dict):
        raise ValueError('Each site must be a JSON object')
    for key in ('site_id', 'site_type', 'crash_patterns'):
        if key not in site:
            raise ValueError('Missing site field: ' + key)
    if not isinstance(site['site_id'], str) or not site['site_id'].strip():
        raise ValueError('site_id must be a nonempty string')
    if site['site_type'] not in LOCATIONS:
        raise ValueError('Unsupported site_type; use: ' + ', '.join(sorted(LOCATIONS)))
    patterns = site['crash_patterns']
    if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) for p in patterns):
        raise ValueError('crash_patterns must be a nonempty list of strings')
    patterns = {normalize(p) for p in patterns}
    if patterns - PATTERNS:
        raise ValueError('Unsupported crash pattern: ' + ', '.join(sorted(patterns - PATTERNS)))
    if 'all' in patterns and len(patterns) > 1:
        raise ValueError('Use all alone, or list specific crash patterns')
    if site.get('area_type', 'unknown') not in {'urban', 'suburban', 'rural', 'unknown'}:
        raise ValueError('area_type must be urban, suburban, rural, or unknown')
    if site.get('time_of_day', 'unknown') not in {'day', 'night', 'unknown'}:
        raise ValueError('time_of_day must be day, night, or unknown')
    severity = site.get('severity_scope', 'unknown')
    if severity not in {'All', 'K;A', 'K;A;B', 'K;A;B;C', 'A;B;C', 'unknown'}:
        raise ValueError('Unsupported severity_scope; use K;A for fatal/serious injury')
    for field in ('intersection_related', 'animal_related', 'interchange_related', 'winter_month'):
        if field in site and not isinstance(site[field], bool):
            raise ValueError(field + ' must be true or false')
    return patterns


def match_site(site, rows):
    patterns = validate_site(site)
    candidates, excluded = [], []
    for row in rows:
        reasons, review = [], []
        rejected = None
        scope = row['cmf_crash_types']
        sites = set(row['site_type'].split(';'))
        area = site.get('area_type', 'unknown')
        study_area = row['area_type'].lower()
        if not row['cmf']:
            rejected = 'Process entry without a selected treatment CMF.'
        elif site['site_type'] not in sites:
            rejected = 'Location type does not match the library entry.'
        elif area != 'unknown' and study_area not in {'all', 'any', 'not specified'} and area not in study_area:
            rejected = 'Known area type conflicts with the study setting.'
        if rejected:
            excluded.append({'cm_id': row['cm_id'], 'reason': rejected})
            continue
        reasons.append('Location type matches: ' + site['site_type'] + '.')
        if area == 'unknown' or study_area == 'not specified':
            review.append('Area setting needs review: study=' + row['area_type'] + '.')
        else:
            reasons.append('Area setting is compatible with the recorded study setting.')
        match_kind = 'specific_crash_type'
        if scope == 'All nighttime crashes':
            if site.get('time_of_day') == 'day':
                rejected = 'Nighttime-only study conflicts with daytime input.'
            elif site.get('time_of_day') != 'night':
                rejected = 'Nighttime status must be supplied for this CMF.'
            else:
                match_kind = 'aggregate_crash_scope'
                reasons.append('Nighttime condition matches; study covers all nighttime crashes.')
        elif scope.startswith('All except '):
            restrictions = {
                'All except intersection-related and animal-related crashes': ['intersection_related', 'animal_related'],
                'All except intersection/interchange and winter-month crashes': ['intersection_related', 'interchange_related', 'winter_month'],
            }.get(scope)
            if restrictions is None or any(site.get(key) is not False for key in restrictions):
                rejected = 'Excluded-event conditions must explicitly be false: ' + ', '.join(restrictions or ['unmapped scope'])
            else:
                match_kind = 'aggregate_crash_scope'
                reasons.append('Study exclusion conditions match the supplied flags.')
        elif scope == 'All':
            match_kind = 'aggregate_crash_scope'
            reasons.append('Study covers all crash types combined.')
        else:
            supported = {normalize(p) for p in scope.split(';')} - {'non intersection'}
            overlap = patterns & supported
            if not overlap:
                rejected = 'No overlap with CMF-supported crash types: ' + scope + '.'
            else:
                reasons.append('CMF-supported crash pattern matches: ' + ', '.join(sorted(overlap)) + '.')
                if patterns - supported:
                    review.append('This study does not cover every requested crash pattern.')
        if rejected:
            excluded.append({'cm_id': row['cm_id'], 'reason': rejected})
            continue
        if match_kind == 'aggregate_crash_scope' and patterns != {'all'}:
            review.append('Aggregate CMF does not establish a reduction for the requested crash subtype alone.')
        severity = site.get('severity_scope', 'unknown')
        severity_match = severity != 'unknown' and severity == row['severity_scope']
        if not severity_match:
            review.append('Severity scope is unknown or differs: requested=' + severity + '; study=' + row['severity_scope'] + '. Do not transfer this CMF to fatal/serious-injury crashes.')
        review.extend([
            'Check treatment prerequisites, geometry, traffic volumes, and existing equipment: ' + row['applicability_conditions'],
            'Complete source verification; current status: ' + row['verification_status'],
        ])
        if row['rating_status'] == 'Cannot Be Rated':
            review.append('Research quality is officially unrated.')
        candidates.append({
            'cm_id': row['cm_id'], 'treatment': row['specific_treatment'],
            'status': 'candidate_needs_review', 'match_kind': match_kind,
            'reasons': reasons, 'review_needed': review,
            'severity_scope_matches': severity_match,
            'eligible_for_benefit_calculation': False,
            'evidence': {'cmf': float(row['cmf']), 'cmf_id': row['cmf_id'],
                         'crash_types': scope, 'severity_scope': row['severity_scope'],
                         'star_rating': int(row['star_rating']) if row['star_rating'] else None,
                         'rating_status': row['rating_status'], 'source_url': row['source_url'],
                         'verification_status': row['verification_status'],
                         'limitations': row['limitations']},
        })
    # Stable ID order is deliberate: the prototype does not rank effectiveness.
    return {'site_id': site['site_id'], 'synthetic': site.get('synthetic', False),
            'input': site, 'candidates': candidates, 'excluded': excluded,
            'notice': 'Preliminary screening only. No crash reductions or benefit rankings are calculated. No candidates means no supported match in this small library.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sites', type=Path, default=ROOT / 'synthetic_sites.json')
    parser.add_argument('--library', type=Path, default=ROOT / 'countermeasure_library.csv')
    parser.add_argument('--output', type=Path, help='Optional JSON output path')
    args = parser.parse_args()
    try:
        sites = json.loads(args.sites.read_text(encoding='utf-8'))
        if not isinstance(sites, list):
            sites = [sites]
        rows = load_library(args.library)
        results = [match_site(site, rows) for site in sites]
        if args.output:
            args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        for result in results:
            print('\n' + result['site_id'] + ' (synthetic=' + str(result['synthetic']) + ')')
            print(result['notice'])
            for candidate in result['candidates']:
                print('  ' + candidate['cm_id'] + ': ' + candidate['treatment'])
                for reason in candidate['reasons']:
                    print('    MATCH: ' + reason)
                for item in candidate['review_needed']:
                    print('    REVIEW: ' + item)
            print('Candidates:', len(result['candidates']))
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
