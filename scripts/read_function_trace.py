"""Read one full or concise archived configuration comparison trace."""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=ROOT/'results/function_online_v2')
    p.add_argument('--id',default='route-04');p.add_argument('--method',default='dynamic');p.add_argument('--json',action='store_true')
    args=p.parse_args();record=None
    with gzip.open(args.directory/'traces.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line)
            if (r['case_id'],r['decision']['method'])==(args.id,args.method):record=r;break
    if record is None:p.exit(1,'Trace not found\n')
    if args.json:print(json.dumps(record,ensure_ascii=False,indent=2));return
    d=record['decision'];print(f"{record['case_id']} {d['method']}: {d['state']}; selected={d['selected']}; action={d['action']}")
    for row in d['candidates']:
        print(f"  {row['id']}: {row['state']}")
        for g in row['goal_checks']:
            if g['status']!='satisfied':print('    goal:',g['key'],g['status'])
        if row['guard']:
            for c in row['guard']['checks']:
                if c['critical'] and c['status'] in ('conflict','unknown','documentation_conflict'):
                    print('   ',c['claim_id'],c['status'],c['reason'])
                    for e in c['evidence']:print('      ',e['url'],e['section'])
    print(json.dumps(record['generation']['output'],ensure_ascii=False,indent=2))
    print('API:',json.dumps(record['generation']['api'],ensure_ascii=False))

if __name__=='__main__':main()
