"""Build original synthetic fixtures. No external/private documents are ingested."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'boundary_rag' / 'data'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # (id, evidence requirement, matching groups, source, title, verbatim fact)
    rows = [
        ('leave', '年假天数和申请规则', [['年假|休假', '天|申请|规则|流程|多久']], 'hr', '员工年假政策', '示例公司的正式员工每年享有15天年假，提前3个工作日在员工门户申请。'),
        ('bonus_policy', '奖金资格和政策计算', [['奖金', '资格|条件|政策|绩效|系数|如何计算|怎么算']], 'hr', '研发员工奖金政策', '示例公司的研发员工奖金为月基本工资乘绩效系数，绩效系数由HR确认，适用对象为已转正员工。'),
        ('bonus_budget', '奖金预算和成本口径', [['奖金', '预算|预提|成本|入账']], 'finance', '研发奖金预算计算', '奖金预算为HR核定奖金总额乘1.12，额外12%为示例雇主附加成本；每月按预计年度奖金的十二分之一预提。'),
        ('option_eligibility', '期权授予资格和归属条件', [['期权', '资格|授予|条件|归属|谁能']], 'hr', '员工股票期权授予条件', '示例期权授予对象为入职满12个月的正式员工，授予需薪酬委员会批准，归属期为4年。'),
        ('option_tax', '期权税务公式和计算依据', [['期权', '税|扣缴']], 'finance', '员工期权模拟税务规则', '仅在本合成案例中，期权税基为行权价差乘股数，模拟扣缴额为税基乘20%；这不是任何地区的真实税法。'),
        ('travel_policy', '出差审批和舱位资格', [['出差|差旅|机票', '资格|政策|审批|舱位|经济舱']], 'hr', '员工出差审批政策', '示例公司出差需直属经理批准，普通员工国内航班乘经济舱。'),
        ('travel_claim', '差旅报销凭证和期限', [['出差|差旅|机票', '报销|发票|凭证|期限']], 'finance', '差旅报销规则', '差旅报销应在返程后30天内提交电子发票、行程单和审批编号。'),
        ('portal_access', '报销系统权限开通', [['报销|财务|差旅', '权限|账号|登录|开通|进不去']], 'it', '财务报销系统账号权限', '报销系统权限由部门负责人批准后提交IT工单，IT在2个工作日内开通，并启用多因素认证。'),
        ('vpn', 'VPN连接故障排查', [['vpn|远程连接|虚拟专网', '连|故障|错误|排查|失败']], 'it', 'VPN连接故障排查', 'VPN连接失败时先检查网络和多因素认证，再更新客户端；仍失败时附错误码提交IT工单。'),
        ('password', '密码重置流程', [['密码|口令', '忘|重置|修改|找回']], 'it', '员工门户密码重置', '员工门户密码可在自助服务页重置，需通过已登记的多因素认证；验证失败时提交IT工单。'),
        ('equipment_policy', '远程办公设备补贴资格', [['设备|电脑|笔记本|远程办公', '补贴|资格|政策']], 'hr', '远程办公设备补贴政策', '完成试用期的远程办公员工可申请一次性设备补贴，额度上限为3000元。'),
        ('equipment_claim', '设备报销和资产入账', [['设备|电脑|笔记本', '报销|发票|入账|资产']], 'finance', '办公设备费用处理', '办公设备报销需发票与审批记录；单件含税价达到5000元时登记为固定资产。'),
        ('equipment_setup', '电脑配置和加密安装', [['设备|电脑|笔记本', '配置|加密|安装|设置']], 'it', '办公电脑安全配置', '办公电脑需启用全盘加密、安装终端防护，并通过IT设备管理平台注册。'),
        ('offboarding_policy', '离职通知和交接流程', [['离职', '通知|交接|流程|申请']], 'hr', '员工离职交接政策', '示例公司离职申请应提前30天提交，离职日前完成经理确认的交接清单。'),
        ('offboarding_account', '离职账号停用', [['离职', '账号|权限|停用|访问']], 'it', '离职员工账号停用', 'IT依据已批准的离职工单，在离职日18点停用员工账号并撤销远程访问权限。'),
        ('invoice', '增值税发票抬头和税号', [['发票', '抬头|税号|开具']], 'finance', '示例发票开具信息', '示例发票抬头为星河示例实验室，税号为DEMO-TAX-000，不对应真实企业。'),
        ('training_policy', '培训审批资格', [['培训', '资格|审批|政策|报名']], 'hr', '员工培训审批', '转正员工可申请与岗位相关的培训，须在报名之前获得经理批准。'),
        ('training_claim', '培训报销额度', [['培训', '报销|额度|费用']], 'finance', '培训费用报销', '已审批培训每人每年最多报销2000元，需课程凭证和发票。'),
        ('support_contact', '服务台联系方式', [['服务台|IT支持|技术支持', '联系|邮箱|找谁']], 'it', '技术支持服务台', '技术支持服务台邮箱为helpdesk@example.invalid，工作时间为工作日9点至18点。'),
    ]
    docs, tasks = [], []
    for i, (task, label, patterns, source, title, quote) in enumerate(rows):
        doc_id = f'{source}-{task}'
        docs.append(dict(id=doc_id, source=source, title=title, version='2026-10-01',
                         text=quote, claims=[dict(task=task, quote=quote)]))
        tasks.append(dict(id=task, label=label, patterns=patterns,
                          inherit_patterns=[[p[0], p[1]] for p in patterns]))
    # A valid alternative source: do not penalize either HR or IT for this question.
    shared = docs[-1]['claims'][0]['quote']
    docs.append(dict(id='hr-support_contact', source='hr', title='员工手册服务台联系方式',
                     version='2026-10-01', text=shared, claims=[dict(task='support_contact', quote=shared)]))
    # Surface-level distractors; they do not support the neighboring tasks.
    for source, suffix, title, text in [
        ('hr', 'tax_notice', '员工奖金期权税务说明', '员工奖金与期权可能涉及税务。本员工手册不提供税务计算规则，请咨询财务。'),
        ('finance', 'access_notice', '财务报销系统登录说明', '财务审核报销单据，但不处理报销系统登录失败或权限开通，请联系IT。'),
        ('it', 'bonus_notice', '研发奖金系统技术维护', 'IT维护研发奖金系统的运行，但不制定员工奖金资格、绩效系数或奖金预算规则。'),
        ('hr', 'equipment_notice', '员工电脑设备申请入口', '员工门户提供电脑申请入口；电脑安装、设备加密和技术配置由IT负责。'),
        ('finance', 'leave_notice', '员工年假期间费用说明', '财务账目可记录年假期间的费用，但不规定年假天数或休假申请流程。'),
    ]:
        docs.append(dict(id=f'{source}-{suffix}', source=source, title=title, text=text,
                         version='2026-10-01', claims=[]))
    positives = {
        'hr': ('人力资源员工手册：员工奖金绩效、期权福利、年假、出差、培训、远程办公、电脑补贴、离职制度和申请。',
               ['员工奖金政策如何计算', '员工期权授予条件是什么', '年假申请有几天', '培训和出差怎么申请'],
               ['税', '预算', '入账', '报销', '登录', '配置']),
        'finance': ('财务：员工奖金预算、期权税务、差旅报销、培训费用、电脑资产、发票及财务报销系统的业务流程。',
                    ['奖金预算如何计算', '期权税务怎么算', '报销系统提交哪些凭证', '发票如何开具'],
                    ['资格', '授予', '密码', '登录', '权限', '配置']),
        'it': ('技术支持：员工门户、奖金系统、财务报销系统、VPN远程连接、账号权限、电脑配置、离职账号和服务台。',
               ['报销系统登录失败怎么办', 'VPN连接失败如何排查', '电脑怎么配置', '离职账号何时停用'],
               ['预算', '税', '补贴', '报销额度', '资格']),
    }
    profiles = []
    for source, (positive, examples, fixed) in positives.items():
        supports = {}
        for d in docs:
            if d['source'] == source:
                for claim in d['claims']:
                    supports.setdefault(claim['task'], []).append(d['id'])
        profiles.append(dict(id=source, version='2026-10-01', updated_at='2026-10-01',
                             positive=positive, examples=examples, supports=supports,
                             unsupported={t['id']: '已核查此合成快照，无支持该任务的事实；不代表该部门永久无能力。'
                                          for t in tasks if t['id'] not in supports},
                             fixed_negative_patterns=fixed,
                             boundary_basis=[d['id'] for d in docs if d['source'] == source]))
    for name, value in [('documents', docs), ('tasks', tasks), ('profiles', profiles)]:
        (OUT / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
