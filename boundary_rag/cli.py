import argparse
import json
from pathlib import Path
import sys
from .agent import Agent
from .credentials import load_ccswitch
from .routing import METHODS
from .schema import Config


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='边界感知自适应 RAG 演示')
    parser.add_argument('query', nargs='?', default='员工期权的授予资格是什么，期权税务怎么算？')
    parser.add_argument('--method', choices=METHODS, default='dynamic')
    parser.add_argument('--backend', choices=('extractive', 'deepseek'), default='extractive')
    parser.add_argument('--ccswitch', action='store_true', help='Explicitly read only the DeepSeek provider into process environment')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-rounds', type=int, default=3)
    parser.add_argument('--max-retrieval-calls', type=int, default=9)
    parser.add_argument('--max-work-tokens', type=int, default=40000)
    parser.add_argument('--max-llm-tokens', type=int, default=8000)
    args = parser.parse_args()
    try:
        if args.ccswitch:
            load_ccswitch()
        agent = Agent(config=Config(max_rounds=args.max_rounds, max_retrieval_calls=args.max_retrieval_calls,
                                    max_work_tokens=args.max_work_tokens, max_llm_tokens=args.max_llm_tokens), backend=args.backend)
        result = agent.answer(args.query, args.method)
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc)+'\n')
    print(result['answer'])
    for step in result['rounds']:
        print(f"\n第 {step['round']} 轮：{', '.join(step['selected'])}")
        for decision in step['decisions']:
            print(f"  {decision['source']} [{'选中' if decision['selected'] else '保留'}] {decision['reason']}")
    print('\n停止原因：'+result['stop_reason'])
    print(json.dumps(result['metrics'], ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('轨迹已保存：'+str(args.output))
    if result['generation_error']:
        parser.exit(1, result['generation_error']+'\n')


if __name__ == '__main__':
    main()
