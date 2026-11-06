# -*- coding: utf-8 -*-
"""Export the athlete publish set: what the prod build needs and nothing more.

Reads the private data folder (see private_data.py), applies the same publish
gate as build-athletes.py (onboarding "accepted" + a complete record), and
writes to OUT_DIR:

    athletes/_data/athletes.json     published records only, review notes and
                                     source lists removed
    athletes/_data/onboarding.json   status "accepted" for those records only
    athletes/_data/collage.json      collage entries for published athletes
    athletes/_photos/<slug>/         only the photos those pages use

Upload it to the private S3 folder the Deploy Prod workflow reads
(ATHLETE_DATA_S3), replacing what is there:

    python scripts/builders/export-athlete-publish-set.py <OUT_DIR>
    aws s3 sync <OUT_DIR> s3://<bucket>/niltv-web --delete
"""
import importlib.util, io, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('build_athletes', os.path.join(HERE, 'build-athletes.py'))
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)

PRIVATE_ONLY = ('review_notes', 'bio_sources')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    out = os.path.abspath(sys.argv[1])
    if not ba.DATA or not os.path.exists(ba.DATA):
        print('export: private data not found (%s)' % ba.HOWTO)
        return 1
    records = json.load(io.open(ba.DATA, encoding='utf-8'))
    publish, held = ba.gate(records, ba.load_onboarding(), drafts=False)
    if os.path.isdir(out):
        shutil.rmtree(out)
    data_dir = os.path.join(out, 'athletes', '_data')
    os.makedirs(data_dir)
    recs, n_photos = [], 0
    for a in publish:
        a = {k: v for k, v in a.items() if k not in PRIVATE_ONLY}
        src = ba.photo_dir(a)
        dst = os.path.join(out, 'athletes', '_photos', a['slug'])
        os.makedirs(dst)
        for it in [a['photos']['hero']] + ba.wall_items(a):
            shutil.copy2(os.path.join(src, it['file']), os.path.join(dst, it['file']))
            n_photos += 1
        a['photos'] = dict(a['photos'], src_dir='athletes/_photos/' + a['slug'])
        recs.append(a)
    io.open(os.path.join(data_dir, 'athletes.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(recs, indent=1) + '\n')
    slugs = {a['slug'] for a in recs}
    io.open(os.path.join(data_dir, 'onboarding.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(
        {'source': 'publish set', 'athletes': {s: {'status': 'accepted'} for s in sorted(slugs)}}, indent=1) + '\n')
    collage_src = os.path.join(ba.PRIVATE, 'athletes', '_data', 'collage.json')
    if os.path.exists(collage_src):
        collage = [c for c in json.load(io.open(collage_src, encoding='utf-8')) if c['slug'] in slugs]
        io.open(os.path.join(data_dir, 'collage.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(collage, indent=1) + '\n')
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    print('publish set: %d athletes, %d photos, %.1f MB -> %s' % (len(recs), n_photos, size / 1e6, out))
    print('held back: %d (not exported)' % len(held))
    return 0


if __name__ == '__main__':
    sys.exit(main())
