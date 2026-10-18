import argparse
import json
from pathlib import Path
import sys
from .core import Agent,METHODS
from boundary_rag.credentials import load_ccswitch


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser()
    p.add_argument('query',nargs='?',default='中国2026年成年人研究：随机试验的因果效应估计是多少，同时独立同分布数据的验证方案是什么？')
    p.add_argument('--size',type=int,default=10,choices=(10,20,30))
    p.add_argument('--method',choices=METHODS,default='dynamic')
    p.add_argument('--backend',choices=('offline','deepseek'),default='offline')
    p.add_argument('--ccswitch',action='store_true');p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.ccswitch:load_ccswitch()
    r=Agent(args.size,backend=args.backend).run(args.query,args.method)
    print(json.dumps(r['output'],ensure_ascii=False,indent=2))
    print('Selected:',r['selected_sources'],'Stop:',r['stop'])
    print(json.dumps(dict(metrics=r['metrics'],api=r['api']),ensure_ascii=False,indent=2))
    if args.output:
        from .fixtures import write
        write(args.output,r)
    if r['generation_error']:p.exit(1,r['generation_error']+'\n')


if __name__=='__main__':main()
