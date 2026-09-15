#!/usr/bin/env python3
"""Build and validate source-backed BDA plugin manuals against a dated inventory."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs/plugins'
SNAP = ROOT / 'private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json'
CAT = ROOT / 'private/datasets/plugin-docs-audit-20260915/snapshots/parameter-library.json'
LIB = {'RFdiffusion':'rfdiffusion','RFdiffusion3':'rfdiffusion3','ProteinMPNN':'proteinmpnn','AlphaFold2':'alphafold2','AlphaFold 3':'alphafold3','Boltz':'boltz','Chai-1':'chai1','BindCraft':'bindcraft','Mask RGN':'maskrgn','Rosetta':'rosetta'}

def dump(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)
def safe(x):
    t = x if isinstance(x,str) else dump(x)
    # Site absolute paths are documented by role, not copied into portable examples.
    return re.sub(r'/(?:work|home|Users)/[^\s"\'<>;,]+', '<SITE_PATH>', t)
def cell(x): return safe(x).replace('|','\\|').replace('\n','<br>')
def fields(schema):
    """Include same-object conditional properties without flattening nested input objects."""
    found = {p['key']:dict(p) for p in schema.get('fields',[]) if isinstance(p,dict) and 'key' in p}
    def visit(node, path='root'):
        if not isinstance(node,dict): return
        for key, value in node.get('properties',{}).items():
            value = dict(value) if isinstance(value,dict) else {'schema':value}
            if key in node.get('required',[]): value['required']=True
            if key not in found: found[key]=dict(value)
            if path != 'root':
                found[key].setdefault('x-bda-conditional-schemas',[]).append({'branch':path,'schema':value})
        for group in ('allOf','anyOf','oneOf'):
            for i, child in enumerate(node.get(group,[])):visit(child,f'{path}.{group}[{i}]')
        for group in ('if','then','else'):
            if group in node:visit(node[group],f'{path}.{group}')
    visit(schema)
    return found
def base(key): return key.split('-authoring-')[0]
def rows(snapshot,key):
    return [r for r in snapshot['models'] if r['plugin_key']==key]+[dict(r,plugin_version=r['specification'].get('version','unknown'),parameter_schema=r['specification'].get('parameter_schema',{})) for r in snapshot['methods'] if r['plugin_key']==key]
def refs(p,ids):
    sm={x['id']:x for x in p['sources']}
    return ', '.join(f"[{i}]({sm[i].get('url') or '../../../'+sm[i].get('path','')})" for i in ids)
def validate(snapshot,catalog,profiles):
    errors=[]; stats=[]
    keys={r['plugin_key'] for r in snapshot['models']+snapshot['methods']}
    for key in sorted(keys):
        p=profiles.get(base(key))
        if not p:errors.append(f'{key}: missing profile');continue
        required=set()
        for r in rows(snapshot,key):required.update(fields(r['parameter_schema']))
        lib=catalog['models'].get(LIB.get(base(key),''),{})
        required.update(x['key'] for x in lib.get('parameters',[]))
        if p.get('schema_version') != 'bda-plugin-documentation.v1':errors.append(f'{key}: invalid schema_version')
        pp=p['parameters']; present={x['key'] for x in pp}
        covered=present | {alias for x in pp for alias in x.get('bda_keys',[])}
        missing=required-covered
        if missing:errors.append(f'{key}: uncovered parameters {sorted(missing)}')
        if len(pp)!=len(present):errors.append(f'{key}: duplicate parameter keys')
        sourceids=[x['id'] for x in p['sources']]; modeids=[x['id'] for x in p['modes']]
        if len(sourceids)!=len(set(sourceids)):errors.append(f'{key}: duplicate source id')
        if len(modeids)!=len(set(modeids)):errors.append(f'{key}: duplicate mode id')
        for mode in p['modes']:
            if mode.get('bda_status') not in {'declared','configuration_only','not_exposed','unverified'}:errors.append(f'{key}: invalid bda_status')
        for group,reqs in [('parameters',['key','type','description','unit','flag_or_mapping','source_refs']),('modes',['id','title','purpose','required_inputs','parameters','bda_status','output_checks','limitations','source_refs']),('outputs',['name','meaning','unit','interpretation','source_refs'])]:
            for x in p[group]:
                for f in reqs:
                    if f not in x or (f in ['description','meaning','source_refs','flag_or_mapping','unit'] and not x[f]):errors.append(f'{key}/{x.get("key",x.get("id",x.get("name")))}: missing {f}')
                for ref in x.get('source_refs',[]):
                    if ref not in sourceids:errors.append(f'{key}: missing source {ref}')
                if group=='parameters':
                    for mode in x.get('modes',[]):
                        if mode not in modeids:errors.append(f'{key}/{x["key"]}: unknown mode {mode}')
        for source in p['sources']:
            if not source.get('url') and not (ROOT/source.get('path','__missing__')).is_file(): errors.append(f'{key}: missing source path {source}')
        stats.append({'plugin_key':key,'profile':p['slug'],'versions':len(rows(snapshot,key)),'required_parameters':len(required),'documented_parameters':len(present),'missing_parameters':sorted(missing),'modes':len(p['modes']),'outputs':len(p['outputs']),'gaps':len(p['gaps'])})
    return errors,stats

def render(p,key,versions,catalog):
    lines=[f'# {key} — 功能、参数与使用手册','', '> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。','',p['summary'],'','[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/'+p['slug']+'.json)','','## 版本与实际状态','','| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |','|---|---|---|---|---|']
    if '-authoring-' in key: lines.insert(6,'本页是独立 authoring 草稿；共用基础工具解释，但以下版本参数/命令摘要来自草稿本身，不能继承基础版本的运行证明。\n')
    for r in versions:
        lines.append('| '+' | '.join(cell(x) for x in [r['plugin_version'],r['enabled'],r.get('validation_status','方法 demo 未校验'),r.get('runtime_validation_status','无'),r.get('runtime_validation_current',False)])+' |')
    lines+=['','`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。','','## 功能模式与配方','']
    for m in p['modes']:
        lines += [f"### {m['title']} (`{m['id']}`)",'',f"{m['purpose']}。BDA 接入：`{m['bda_status']}`。",'', '输入：'+ '; '.join(m['required_inputs']), '', '配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：','', '```json',json.dumps(m['parameters'],ensure_ascii=False,indent=2),'```','', '输出检查：'+'；'.join(m['output_checks']), '', '限制：'+'；'.join(m['limitations']), '', '依据：'+refs(p,m['source_refs']), '']
    lines+=['## 使用方法','']+[f'{i}. {s}' for i,s in enumerate(p['usage_steps'],1)]+['','## 参数解释','', '下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。','']
    for q in p['parameters']:
        lines += [f"### `{q['key']}`",'',q['description'],'',f"类型：`{q['type']}`；单位：{q['unit']}；来源记录默认：`{cell(q['default']) if 'default' in q else '未声明'}`。",'', '适用模式：'+(', '.join(q.get('modes',[])) or '按相应模式/版本映射检查'), '', '生成映射：`'+cell(q['flag_or_mapping'])+'`；BDA 别名：`'+cell(q.get('bda_keys',[]))+'`。','', '约束与版本差异：'+cell(q.get('constraints','未声明额外约束')), '', '依据：'+refs(p,q['source_refs']), '']
    if not p['parameters']: lines+=['当前 schema 无参数。它表示尚无可用参数契约，不能理解为已实现的零参数算法。','']
    lines+=['## 当前 BDA 输入默认与生成声明','', '每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。','']
    for r in versions:
        lines += [f"### 版本 `{r['plugin_version']}`",'', '| BDA key | 类型 | 表单默认 | 允许值/约束 |','|---|---|---|---|']
        for k,v in fields(r['parameter_schema']).items():lines.append('| '+' | '.join(cell(x) for x in [k,v.get('type','未声明'),v['default'] if 'default' in v else '未声明',{a:v[a] for a in ['enum','options','minimum','maximum','required','x-bda-conditional-schemas'] if a in v}])+' |')
        for name in ['input_ports','output_ports','output_schema','resources']:
            lines += ['', f'**{name}**','', '```json',safe(json.dumps(r.get(name,{}),ensure_ascii=False,indent=2)),'```']
        cmd=r.get('command') or '';cmd='\n'.join(cmd) if isinstance(cmd,list) else cmd
        flags=sorted(set(re.findall(r'(?<![\w-])(-{1,2}[A-Za-z][A-Za-z0-9_:.-]*)(?=[\s=\"\'])',cmd)))
        envs=sorted(set(re.findall(r'\$(?:\{)?([A-Za-z_][A-Za-z0-9_]*)',cmd)))
        lines += ['', '命令摘要 SHA-256：`'+hashlib.sha256(cmd.encode()).hexdigest()+'`。', '', '命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`'+cell(flags)+'`。', '', '命令文本引用的变量（含包装器局部变量，不全是用户参数）：`'+cell(envs)+'`。', '', '输入适配器：`'+cell(r.get('input_adapter'))+'`；输出解析器：`'+cell(r.get('output_parser'))+'`。', '']
    lines+=['## 自动生成参数与可复现记录','', '| 项目 | 含义、生成方法与核对要求 |','|---|---|','| 最终 argv/config | 由上面的模式映射、端口文件和包装器默认共同产生；保存渲染后的最终版本，检查用户值是否被覆盖。命令摘要只标识文本，不证明参数得到消费。 |','| BDA_INPUT_DIR / BDA_OUTPUT_DIR | 每次任务 staging 输入/输出根目录；内部端口相对路径对应实际工件，不能填本机路径代替。 |','| BDA_CPUS / 资源 | 由资源声明及调度分配产生；CPU、GPU、内存、墙钟上限不是科学结果。资源与程序线程数需一致。 |','| seed / model / sample / tag | 由所用 wrapper/模型分配。每项保存实际值与对应输出；没有固定种子接口时明确不可由此配置复现。tag/数字是身份元数据，不是序列。 |','| 链、残基与结构映射 | 记录输入至输出的链 ID、残基编号、裁剪、重编号与修饰残基处理。由实际结构/映射文件提取，不能从文件名猜。 |','| 生效配置、权重和数据库 | 保存完整配置、输入 SHA-256、实际软件版本/commit、权重/参考库标识及哈希；当前未自动生成的字段标“待补采集”。 |','| 缺失结果 | 区分未请求、未支持、未计算、计算失败和解析失败。无结果不写 0。 |','','## 生成的结果参数','', '| 输出 | 定义 | 单位/尺度 | 解释与限制 | 依据 |','|---|---|---|---|---|']
    for o in p['outputs']:lines.append('| '+' | '.join(cell(x) for x in [o['name'],o['meaning'],o['unit'],o['interpretation'],refs(p,o['source_refs'])])+' |')
    if not p['outputs']: lines += ['| 无已定义科学输出 | 空 demo schema | 不适用 | 不得参与候选评分 | 当前注册声明 |']
    lines+=['','保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。','','## 已知缺口与后续验收','']+[f'- {g}' for g in p['gaps']]+['','## 易错点','']+[f'- {s}' for s in p['pitfalls']]+['','## 来源与版本','']
    for s in p['sources']:
        dest=s.get('url') or '../../../'+s.get('path','')
        lines += [f"- [{s['id']}]({dest})：{s.get('scope','参数/功能依据')}；commit `{s.get('commit','未固定/本地快照')}`；读取 {s.get('retrieved_on','2026-09-15')}。"]
    return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--write',action='store_true');g.add_argument('--check',action='store_true');a=ap.parse_args()
    snapshot=json.loads(SNAP.read_text());catalog=json.loads(CAT.read_text());profiles={}
    for path in sorted((DOCS/'profiles').glob('*.json')):
        p=json.loads(path.read_text());profiles[p['plugin_key']]=p
    errors,stats=validate(snapshot,catalog,profiles)
    if errors:
        print('\n'.join(errors));return 1
    files={}; index=['# BDA 插件说明总览','', '盘点日期：2026-09-15。19 个模型键（含 3 个 authoring 草稿），23 条模型版本记录，另有 4 个方法插件；合计 23 个独立插件键。','', '[统一解释与使用规范](STANDARD.md) · [审计与审阅记录](REVIEW.md)','', '覆盖表统计当前 library/BDA 已知字段；上游未接入功能和科学证据不足逐页列出。运行状态以当前声明指纹匹配为准。','','| 插件 | 版本数 | 必须解释字段 | 已解释字段（含上游扩展） | 模式 | 输出定义 | 待解决缺口 |','|---|---:|---:|---:|---:|---:|---:|']
    for item in stats:
        key=item['plugin_key'];p=profiles[base(key)];slug=p['slug'] if base(key)==key else key.lower()
        files[ROOT/'qm-scripts/plugins'/slug/'REFERENCE.md']=render(p,key,rows(snapshot,key),catalog)
        index.append('| ['+key+'](../../qm-scripts/plugins/'+slug+'/REFERENCE.md) | '+' | '.join(str(item[k]) for k in ['versions','required_parameters','documented_parameters','modes','outputs','gaps'])+' |')
    uniqueprofiles=set(item['profile'] for item in stats)
    report={'schema_version':1,'captured_on':snapshot['captured_on'],'registry_sha256':hashlib.sha256(SNAP.read_bytes()).hexdigest(),'catalog_sha256':hashlib.sha256(CAT.read_bytes()).hexdigest(),'plugin_keys':len(stats),'model_versions':len(snapshot['models']),'method_plugins':len(snapshot['methods']),'unique_profiles':len(uniqueprofiles),'unique_documented_parameters':sum(len(p['parameters']) for p in profiles.values()),'current_runtime_proofs':sum(r.get('runtime_validation_current',False) for r in snapshot['models']),'coverage_errors':errors,'plugins':stats}
    files[DOCS/'INDEX.md']='\n'.join(index)+'\n';files[DOCS/'coverage.json']=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.write:
        for path,content in files.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
    else:
        stale=[str(p.relative_to(ROOT)) for p,c in files.items() if not p.exists() or p.read_text()!=c]
        if stale: print('Stale files:\n'+'\n'.join(stale));return 1
    print(f'OK: {len(stats)} plugin keys, {len(snapshot["models"])} model versions, {report["unique_documented_parameters"]} unique profile parameters; no coverage errors. Current runtime proofs: {report["current_runtime_proofs"]}.')
    return 0
if __name__=='__main__':raise SystemExit(main())
