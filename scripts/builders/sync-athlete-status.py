# -*- coding: utf-8 -*-
"""Record each athlete's onboarding status for the athlete page build.

build-athletes.py publishes a profile only when the athlete is "accepted" in
the dashboard (agreement signed and Stripe payouts set up). This script reads
the dashboard's applications list and writes the answer to the PRIVATE data
folder as athletes/_data/onboarding.json:

    {"checked": "...", "source": "...",
     "athletes": {"<slug>": {"status": "accepted", "application": 12, "matched_by": "instagram"}},
     "accepted_without_record": [{"name": ..., "school": ..., "sport": ..., "instagram": ...}]}

Records are matched by Instagram handle, then TikTok handle, then full name.
Only status, id, name, school, sport and handles are written; contact details
never leave the dashboard.

    NILTV_DASHBOARD_API_KEY=... python scripts/builders/sync-athlete-status.py
    ... --api https://api-dev.niltv.com/api     # another environment (default: prod)
    ... --dry-run                               # print, write nothing
"""
import io, json, os, re, sys, datetime, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from private_data import private_path, HOWTO

DEFAULT_API = 'https://api.niltv.com/api'


def handle(v):
    """'@Jane.Doe' or 'https://instagram.com/jane.doe/' -> 'jane.doe' (the dashboard's normalize_handle)."""
    if not v:
        return None
    v = re.sub(r'^https?://(www\.)?(instagram\.com|tiktok\.com)/', '', str(v).strip(), flags=re.I)
    v = v.split('?')[0].strip('/').lstrip('@').strip().lower()
    return v or None


def name_key(v):
    return re.sub(r'[^a-z]', '', (v or '').lower()) or None


def fetch(api, key):
    req = urllib.request.Request(api.rstrip('/') + '/applications/?status=all&limit=2000',
                                 headers={'X-API-Key': key, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    args = sys.argv[1:]
    api = args[args.index('--api') + 1] if '--api' in args else DEFAULT_API
    key = os.environ.get('NILTV_DASHBOARD_API_KEY')
    if not key:
        print('sync-athlete-status: set NILTV_DASHBOARD_API_KEY (the dashboard X-API-Key)')
        return 1
    data = private_path('athletes', '_data', 'athletes.json')
    if not data or not os.path.exists(data):
        print('sync-athlete-status: private data not found (%s)' % HOWTO)
        return 1
    records = json.load(io.open(data, encoding='utf-8'))
    try:
        apps = fetch(api, key)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print('sync-athlete-status: the dashboard rejected the key (HTTP %d). Set NILTV_DASHBOARD_API_KEY to the '
                  'X-API-Key value the dashboard API accepts.' % e.code)
            return 1
        raise

    by = {'instagram': {}, 'tiktok': {}, 'name': {}}
    for ap in apps:
        for f in ('instagram', 'tiktok'):
            h = handle(ap.get(f))
            if h: by[f].setdefault(h, []).append(ap)
        n = name_key('%s %s' % (ap.get('first_name') or '', ap.get('last_name') or ''))
        if n: by['name'].setdefault(n, []).append(ap)

    # the furthest-along application wins when an athlete has more than one row
    order = ('declined', 'applicant', 'approved', 'agreement_sent', 'signed', 'stripe_pending', 'accepted')
    rank = lambda ap: order.index(ap.get('status')) if ap.get('status') in order else -1

    out, matched_ids = {}, set()
    for rec in records:
        hit = None
        for so in rec.get('socials') or []:
            f = so.get('platform')
            if f in ('instagram', 'tiktok') and by[f].get(handle(so.get('handle'))):
                hit = (f, by[f][handle(so.get('handle'))]); break
        if not hit and by['name'].get(name_key(rec.get('name'))):
            hit = ('name', by['name'][name_key(rec.get('name'))])
        if not hit:
            out[rec['slug']] = {'status': None, 'matched_by': None}
            continue
        best = max(hit[1], key=rank)
        matched_ids.add(best['id'])
        out[rec['slug']] = {'status': best['status'], 'application': best['id'], 'matched_by': hit[0]}

    extra = [dict(name=('%s %s' % (ap.get('first_name') or '', ap.get('last_name') or '')).strip(),
                  school=ap.get('university'), sport=ap.get('sport'), instagram=handle(ap.get('instagram')))
             for ap in apps if ap.get('status') == 'accepted' and ap['id'] not in matched_ids]
    extra.sort(key=lambda x: (x['school'] or '', x['name']))

    doc = {'checked': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'source': api, 'athletes': out, 'accepted_without_record': extra}

    for slug, v in out.items():
        print('%-28s %s' % (slug, v['status'] or 'no matching application'))
    print('accepted in the dashboard with no page record yet: %d' % len(extra))
    for x in extra:
        print('  %s | %s | %s' % (x['name'], x['school'] or '-', x['sport'] or '-'))
    if '--dry-run' in args:
        return 0
    dest = private_path('athletes', '_data', 'onboarding.json')
    io.open(dest, 'w', encoding='utf-8', newline='\n').write(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    print('wrote', dest)
    return 0


if __name__ == '__main__':
    sys.exit(main())
