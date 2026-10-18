"""Show routing explanations or raw archived records without an API call."""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from stat_rag.core import Corpus


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser()
    p.add_argument('--archive',type=Path,default=ROOT/'results/stat_online/traces.jsonl.gz')
    p.add_argument('--demo',type=Path);p.add_argument('--id',default='stat-09');p.add_argument('--size',type=int,default=30)
    p.add_argument('--method',default='dynamic');p.add_argument('--repetition',type=int,default=0);p.add_argument('--json',action='store_true')
    args=p.parse_args();record=None
    if args.demo:record={'run':json.loads(args.demo.read_text(encoding='utf-8'))}
    else:
        with gzip.open(args.archive,'rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line)
                if (row['sample_id'],row['run']['size'],row['run']['method'],row['repetition'])==(args.id,args.size,args.method,args.repetition):record=row;break
    if record is None:p.exit(1,'Trace not found\n')
    if args.json:print(json.dumps(record,ensure_ascii=False,indent=2));return
    run=record['run'];c=Corpus(run['size'])
    print(run['query']);print('方法：'+run['method'])
    for step in run['rounds']:
        print(f"\n第{step['round']}轮，尚缺：{', '.join(step['missing_before'])}")
        for sid in step['selected']:
            source=c.by_id[sid];condition=source['profile']['conditions']
            print(f"  选中 {sid}：{source['document']['title']}；条件={condition}")
            decision=next((d for d in step['decisions'] if d['source']==sid),None)
            if decision:print('  预期支持与边界：'+json.dumps(dict(expected_support=decision['expected_support'],boundaries=decision['boundaries']),ensure_ascii=False))
        rejected=step.get('verification',{}).get('rejections',[])
        if rejected:print('  实际证据被拒绝/待核实：'+json.dumps(rejected,ensure_ascii=False))
    print('\n回答：'+json.dumps(run['output'],ensure_ascii=False,indent=2))
    print('停止：'+run['stop']);print('开销：'+json.dumps(dict(api=run['api'],metrics=run['metrics']),ensure_ascii=False))


if __name__=='__main__':main()
