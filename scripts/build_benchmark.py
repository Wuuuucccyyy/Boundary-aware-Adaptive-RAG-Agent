"""Hand-authored task gold, intentionally includes parser/retrieval challenges."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = [
        ('single', '年假有几天，怎么申请年假？', ['leave']),
        ('single', '研发员工奖金资格和绩效系数政策是什么？', ['bonus_policy']),
        ('single', '员工期权授予条件和归属期是什么？', ['option_eligibility']),
        ('single', '出差机票报销要哪些凭证？', ['travel_claim']),
        ('single', 'VPN连接失败如何排查？', ['vpn']),
        ('single', '忘记员工门户密码如何重置？', ['password']),
        ('single', '电脑设备补贴资格是什么？', ['equipment_policy']),
        ('single', '培训费用报销额度是多少？', ['training_claim']),
        ('single', '技术支持服务台联系邮箱是什么？', ['support_contact']),
        ('single', '入职后每年能歇几天带薪假？', ['leave']),
        ('cross', '员工期权授予资格和期权税务规则是什么？', ['option_eligibility', 'option_tax']),
        ('cross', '研发员工奖金政策如何计算，奖金预算如何计算？', ['bonus_policy', 'bonus_budget']),
        ('cross', '出差审批政策是什么，差旅报销需要哪些发票？', ['travel_policy', 'travel_claim']),
        ('cross', '设备补贴资格是什么，电脑设备报销要什么发票？', ['equipment_policy', 'equipment_claim']),
        ('cross', '离职通知交接流程是什么，离职账号何时停用？', ['offboarding_policy', 'offboarding_account']),
        ('cross', '培训报名审批条件是什么，培训报销额度是多少？', ['training_policy', 'training_claim']),
        ('cross', '差旅报销要哪些凭证，报销系统权限如何开通？', ['travel_claim', 'portal_access']),
        ('cross', '电脑补贴资格、电脑资产入账和电脑加密配置分别怎么处理？', ['equipment_policy', 'equipment_claim', 'equipment_setup']),
        ('cross', '期权归属条件是什么，税务怎么算？', ['option_eligibility', 'option_tax']),
        ('cross', '我要离开公司，谁处理交接和撤掉我的登录？', ['offboarding_policy', 'offboarding_account']),
        ('confusing', '员工期权税务怎么算？', ['option_tax']),
        ('confusing', '研发人员奖金预算如何计算？', ['bonus_budget', 'bonus_policy']),
        ('confusing', '财务报销系统登录失败，账号权限找谁开通？', ['portal_access']),
        ('confusing', '员工电脑需要什么加密配置？', ['equipment_setup']),
        ('confusing', '员工离职后账号权限什么时候停用？', ['offboarding_account']),
        ('confusing', '员工培训费用报销额度上限？', ['training_claim']),
        ('confusing', '员工年假期间，年假有几天？', ['leave']),
        ('confusing', '奖金系统里的奖金预提成本口径是什么？', ['bonus_budget']),
        ('confusing', '财务发票抬头和税号是什么？', ['invoice']),
        ('confusing', '财务软件一直转圈，我进不了那个填费用的页面。', ['portal_access']),
        ('unanswerable', '明天上海天气如何？', []),
        ('unanswerable', '公司股票明天涨多少？', []),
        ('unanswerable', '员工张三本月实际工资是多少？', []),
        ('unanswerable', '德国2027年个人所得税最新税率是多少？', []),
        ('unanswerable', '奖金系统数据库的管理员密钥是什么？', []),
        ('unanswerable', '客户合同违约赔偿应如何计算？', []),
        ('unanswerable', '公司的季度营业收入准确数值是多少？', []),
        ('unanswerable', '你能替我批准这笔贷款吗？', []),
        ('unanswerable', '期权税务规则是什么，明天股价是多少？', ['option_tax', 'unknown:future_price']),
        ('unanswerable', '年假天数是多少，张三账户余额是多少？', ['leave', 'unknown:balance']),
    ]
    dev = [
        ('single', '年假申请流程是什么？', ['leave']),
        ('single', '员工门户密码忘了怎么办？', ['password']),
        ('cross', '培训资格政策和培训费用报销怎么规定？', ['training_policy', 'training_claim']),
        ('cross', '离职申请流程和离职权限停用流程是什么？', ['offboarding_policy', 'offboarding_account']),
        ('confusing', '员工期权的模拟扣缴规则是什么？', ['option_tax']),
        ('confusing', '报销系统账号开通需要哪些操作？', ['portal_access']),
        ('unanswerable', '今年的火星人口是多少？', []),
        ('unanswerable', '最新外汇汇率是多少？', []),
    ]
    docs = json.loads((ROOT/'boundary_rag/data/documents.json').read_text(encoding='utf-8'))
    samples = []
    for split, collection in [('dev', dev), ('test', rows)]:
        for i, (category, query, tasks) in enumerate(collection, 1):
            evidence = {t: [d['id'] for d in docs if any(c['task'] == t for c in d['claims'])] for t in tasks}
            sources = {t: sorted({d['source'] for d in docs if d['id'] in ids}) for t, ids in evidence.items()}
            samples.append(dict(id=f'{split}-{i:02}', split=split, category=category, query=query,
                                required_tasks=tasks, acceptable_documents=evidence, acceptable_sources=sources,
                                fully_answerable=bool(tasks) and all(evidence.values())))
    (ROOT/'experiments').mkdir(exist_ok=True)
    (ROOT/'experiments/queries.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
