"""Reproduce a NEW offline research package. No inference, code execution or source edits."""
import argparse
import csv
from collections import Counter
from datetime import datetime
import hashlib
import html
import importlib.util
import json
import math
from pathlib import Path
import platform
import re
import secrets
import statistics
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

RUN_ID='2026-11-03T114345.873149_0000_35a3d7539e39'
ANALYSIS_ID=RUN_ID+'-offline-1b1d6d878b27'
REVIEW_ID='human-review-20261104-cd80448ab4a3'
SEED=42
N_BOOT=20000
Z=1.959963984540054
MODELS=['qwen3:1.7b','qwen3:8b','gemma4:12b']
LABELS=['Qwen3 1.7B','Qwen3 8B','Gemma4 12B']
COLORS=['#0072B2','#E69F00','#009E73']
DIMS=['correctness','instruction_following','relevance','completeness','conciseness']
VERDICTS=['correct','partly_correct','incorrect','uncertain']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write_json(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def write_csv(path,rows):
    require(bool(rows),'Empty output table')
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def write_md(path,text):
    with path.open('x',encoding='utf-8') as f:f.write(text)
def stamp(text):return datetime.fromisoformat(re.sub(r'(\.\d{6})\d+',r'\1',text).replace('Z','+00:00'))
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-11)
def wilson(k,n):
    require(0<=k<=n and n>0,'Invalid Wilson input')
    p=k/n;den=1+Z*Z/n;mid=(p+Z*Z/(2*n))/den
    half=Z*math.sqrt(p*(1-p)/n+Z*Z/(4*n*n))/den
    return (0. if k==0 else max(0.,mid-half)),(1. if k==n else min(1.,mid+half))
def markdown_table(rows,fields,labels=None):
    labels=labels or fields
    return '| '+' | '.join(labels)+' |\n|'+ '|'.join('---' for _ in fields)+'|\n'+''.join('| '+' | '.join(str(row.get(k,'')) for k in fields)+' |\n' for row in rows)


def build(project,output=None):
    project=Path(project).resolve();sys.path.insert(0,str(project))
    from evaluation import runner,scoring
    from evaluation.validate import validate as validate_datasets
    from evaluation.common import DATASETS
    run=project/'evaluation_runs'/RUN_ID
    analysis=project/'evaluation_analysis'/ANALYSIS_ID
    packet=project/'evaluation_human_review'/REVIEW_ID
    human_dir=packet/'private/results/reviewer_R1_01'
    roots=['evaluation_runs','evaluation_analysis','evaluation_human_review','evaluation_smoke_runs',
           'evaluation_smoke_assessments','evaluation_dev_runs','evaluation_preflight_scoped_01',
           'evaluation/datasets','evaluation/configs','evaluation/evidence','evaluation/reports']
    before={str(p.relative_to(project)):sha(p) for name in roots for p in sorted((project/name).rglob('*')) if p.is_file()}
    used={};checks={}
    def check(name,condition):
        checks[name]=bool(condition);require(condition,'Validation failed: '+name)
    def source(path,role):
        path=Path(path);used[str(path.relative_to(project))]={'sha256':sha(path),'bytes':path.stat().st_size,'role':role}
        return path
    def load(path,role):return json.loads(source(path,role).read_text(encoding='utf-8'))
    def csvload(path,role):
        with source(path,role).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    manifest=load(run/'manifest.json','frozen execution manifest');plan=load(run/'plan.json','frozen execution plan')
    config=manifest['config'];snapshot=config['model_snapshot']
    check('config_hash',canonical(config)==manifest['config_sha256'])
    check('plan_hash',canonical(plan)==manifest['plan_sha256'])
    check('frozen_file',config==load(project/'evaluation_preflight_scoped_01/frozen.json','frozen configuration'))
    check('runner_sources',manifest['source_sha256']==runner.code_hashes())
    runner.validate_config(config,frozen=True)
    check('frozen_verification',True)
    check('plan_reconstruction',plan==runner.make_plan(config,manifest['suites'],manifest['question_ids']))
    check('210_unique_records',len(plan)==210 and len({x['request_id'] for x in plan})==210)
    check('one_repetition',config['repetitions']==1 and all(p['repetition']==1 for p in plan))
    scores=load(analysis/'scores.json','original automatic scores')
    scores_csv=csvload(analysis/'scores.csv','original automatic score CSV')
    metric_csv=csvload(analysis/'request_metrics.csv','original raw-derived metrics CSV')
    original_summary=load(analysis/'summary.json','previous analysis summary')
    score_manifest=load(analysis/'analysis_manifest.json','original scoring provenance')
    analysis_audit=load(analysis/'audit_manifest.json','original analysis file inventory')
    for name,checksum in analysis_audit['files_sha256'].items():check('analysis_hash_'+name,sha(analysis/name)==checksum)
    check('score_manifest_run_hash',score_manifest['input_manifest_sha256']==sha(run/'manifest.json'))
    score_by={s['request_id']:s for s in scores};metric_by={m['request_id']:m for m in metric_csv}
    check('score_row_coverage',len(scores)==len(score_by)==len(scores_csv)==210 and set(score_by)=={p['request_id'] for p in plan})
    check('metrics_row_coverage',len(metric_csv)==len(metric_by)==210 and set(metric_by)==set(score_by))
    for s in scores_csv:
        j=score_by[s['request_id']]
        check(s['request_id']+'_csv_outcomes',s['answer_correct']==('' if j['answer_correct'] is None else str(j['answer_correct'])) and s['format_compliant']==str(j['format_compliant']))
    questions={};refs={}
    for suite in manifest['suites']:
        directory=project/'evaluation/datasets'/suite
        dm=load(directory/'manifest.json','dataset manifest')
        check(suite+'_manifest',dm==manifest['dataset_manifests'][suite])
        check(suite+'_reference_hash',sha(directory/'references.jsonl')==dm['references_sha256']==score_manifest['reference_hashes'][suite])
        qpath=source(directory/'questions.jsonl','public evaluation prompts')
        rpath=source(directory/'references.jsonl','existing scoring reference criteria')
        questions.update({r['id']:r for r in map(json.loads,qpath.read_text().splitlines())})
        refs.update({r['id']:r for r in map(json.loads,rpath.read_text().splitlines())})
    raw_by={};rows=[]
    for item in plan:
        rid=item['request_id'];a=run/'requests'/rid/'attempt-0001'
        check(rid+'_one_attempt',len(list((run/'requests'/rid).glob('attempt-*')))==1)
        request=load(a/'request.json','saved scored request');raw=load(a/'response.json','saved scored response');completion=load(a/'complete.json','saved completion/hash/timing')
        check(rid+'_request_identity',request==item and canonical(item)==completion['request_sha256'])
        check(rid+'_file_hashes',sha(a/'request.json')==completion['request_file_sha256'] and sha(a/'response.json')==completion['response_sha256']==score_by[rid]['response_sha256'])
        check(rid+'_completion',raw.get('model')==item['model'] and raw.get('done') is True and completion['status']==runner.response_status(raw)=='completed' and raw['done_reason']=='stop')
        check(rid+'_no_uncertainty',completion.get('server_completion_unconfirmed') is False and not raw.get('error') and not raw.get('_collector_error'))
        check(rid+'_thinking_off',not raw['message'].get('thinking','').strip())
        rescored=scoring.score(raw['message']['content'],refs[item['question_id']],completion['status'])
        check(rid+'_score_recomputed',all(score_by[rid][k]==v for k,v in rescored.items()))
        mc=metric_by[rid]
        for key,value in [('wall_time_s',completion['wall_time_s']),('prompt_tokens',raw['prompt_eval_count']),
                          ('generated_tokens',raw['eval_count']),('generation_s',raw['eval_duration']/1e9),
                          ('load_s',raw['load_duration']/1e9)]:
            check(rid+'_metric_'+key,close(mc[key],value))
        rows.append({'request_id':rid,'model':item['model'],'question_id':item['question_id'],
            'category':questions[item['question_id']]['category'],**rescored,
            'wall_time_s':completion['wall_time_s'],'prompt_tokens':raw['prompt_eval_count'],
            'generated_tokens':raw['eval_count'],'generation_s':raw['eval_duration']/1e9,
            'load_s':raw['load_duration']/1e9,'response_sha256':sha(a/'response.json')})
        raw_by[rid]=raw
    for model in MODELS:check(model+'_70_unique_questions',len([r for r in rows if r['model']==model])==70 and len({r['question_id'] for r in rows if r['model']==model})==70)

    # Validate actual imported decisions and regenerate reported human/automatic tables.
    packet_manifest=load(packet/'private/manifest.json','private review packet manifest; identity mapping not copied')
    imported=load(human_dir/'import_manifest.json','human import provenance')
    human=load(human_dir/'human_ratings.json','actual imported researcher decisions')
    check('packet_hash_bound',sha(packet/'private/manifest.json')==imported['packet_manifest_sha256'])
    check('ratings_hash_bound',sha(human_dir/'completed_ratings.csv')==imported['ratings_file_sha256'])
    source(human_dir/'completed_ratings.csv','original completed researcher rating CSV')
    for relative,checksum in packet_manifest['packet_files_sha256'].items():
        check('packet_'+relative,sha(packet/relative)==checksum)
        source(packet/relative,'reviewer material/import helper')
    for name,checksum in packet_manifest['source_files_sha256'].items():check('review_source_'+name,sha(name)==checksum)
    spec=importlib.util.spec_from_file_location('nectec_human_import',packet/'private/import_ratings.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    normalized=helper.validate_rows(human_dir/'completed_ratings.csv',packet_manifest['responses'])
    expected_human=[{**r,'model':packet_manifest['responses'][r['blind_id']]['model'],
                     'request_id':packet_manifest['responses'][r['blind_id']]['request_id']} for r in normalized]
    check('imported_human_rows_exact',human==expected_human and len(human)==36)
    check('human_matches_required_scores',{h['request_id'] for h in human}=={r['request_id'] for r in rows if r['manual_review_required']})
    check('one_researcher',len({r['reviewer_id'] for r in human})==1 and imported['rating_rows']==36)
    check('only_correctness_dimension_rated',all(r['correctness'] is not None and all(r[d] is None for d in DIMS[1:]) for r in human))
    imported_models=csvload(human_dir/'model_metrics.csv','imported combined-table with separate denominators')
    imported_human_categories=csvload(human_dir/'human_category_metrics.csv','imported human category summary')
    imported_auto_categories=csvload(human_dir/'automatic_category_metrics.csv','imported automatic category summary')
    load(human_dir/'category_metrics.json','imported category JSON')
    def verify_summary(actual,expected,prefix):
        for key,value in expected.items():
            check(prefix+'_'+key,actual[key]=='' if value is None else close(actual[key],value))
    summary_rows=[];auto_categories=[];human_categories=[];latency=[];token_rows=[]
    for model in MODELS:
        rr=[r for r in rows if r['model']==model];aa=[r for r in rr if r['answer_correct'] is not None];hh=[r for r in human if r['model']==model]
        check(model+'_58_12',len(aa)==58 and len(hh)==12)
        auto_correct=sum(r['answer_correct'] is True for r in aa)
        current=next(x for x in imported_models if x['model']==model)
        verify_summary(current,{'automatic_correct':auto_correct,'automatic_n':58,'automatic_accuracy':auto_correct/58,**helper.review_summary(hh)},model+'_imported_model')
        counts=Counter(r['human_verdict'] for r in hh)
        gsm=[r for r in rr if r['category']=='gsm8k'];k=sum(r['answer_correct'] is True for r in gsm);lo,hi=wilson(k,50)
        summary_rows.append({'model':model,'automatic_correct':auto_correct,'automatic_n':58,'automatic_accuracy_percent':100*auto_correct/58,
            'gsm8k_correct':k,'gsm8k_n':50,'gsm8k_accuracy_percent':2*k,'gsm8k_wilson95_low_percent':100*lo,'gsm8k_wilson95_high_percent':100*hi,
            'human_reviewed_n':12,**{'human_'+v:counts[v] for v in VERDICTS},
            'human_fully_correct_percent':100*counts['correct']/12,'human_correctness_mean_1_to_5':statistics.mean(h['correctness'] for h in hh),
            'format_compliant_n':sum(r['format_compliant'] for r in rr),'format_n':70,'format_compliant_percent':100*sum(r['format_compliant'] for r in rr)/70})
        for cat in ('reasoning','instruction','gsm8k'):
            group=[r for r in aa if r['category']==cat];correct=sum(r['answer_correct'] is True for r in group)
            old=next(x for x in imported_auto_categories if x['model']==model and x['category']==cat)
            verify_summary(old,{'automatic_n':len(group),'automatic_correct':correct,'automatic_accuracy':correct/len(group)},model+'_'+cat)
            auto_categories.append({'model':model,'category':cat,'correct_n':correct,'questions_n':len(group),'automatic_accuracy_percent':100*correct/len(group),
                'format_compliant_n':sum(r['format_compliant'] for r in group),'format_percent':100*sum(r['format_compliant'] for r in group)/len(group)})
        for cat in ('coding','knowledge','summarization'):
            group=[r for r in hh if r['category']==cat];summ=helper.review_summary(group)
            old=next(x for x in imported_human_categories if x['model']==model and x['category']==cat)
            verify_summary(old,summ,model+'_'+cat)
            human_categories.append({'model':model,'category':cat,'reviewed_n':len(group),
                **{v+'_n':sum(r['human_verdict']==v for r in group) for v in VERDICTS},
                'human_fully_correct_percent':100*sum(r['human_verdict']=='correct' for r in group)/len(group),
                'correctness_mean_1_to_5':statistics.mean(r['correctness'] for r in group),
                'runtime_correctness':'not evaluated' if cat=='coding' else 'not applicable'})
        times=np.array([r['wall_time_s'] for r in rr],dtype=float)
        latency.append({'model':model,'requests_n':70,'mean_s':float(times.mean()),'median_s':float(np.median(times)),
            'p05_s':float(np.quantile(times,.05)),'p95_s':float(np.quantile(times,.95)),'min_s':float(times.min()),'max_s':float(times.max()),'sum_s':float(times.sum())})
        tok=sum(r['generated_tokens'] for r in rr);duration=sum(r['generation_s'] for r in rr)
        token_rows.append({'model':model,'requests_n':70,'prompt_tokens_total':sum(r['prompt_tokens'] for r in rr),
            'prompt_tokens_median':statistics.median(r['prompt_tokens'] for r in rr),'prompt_tokens_max':max(r['prompt_tokens'] for r in rr),
            'generated_tokens_total':tok,'generated_tokens_median':statistics.median(r['generated_tokens'] for r in rr),
            'generated_tokens_max':max(r['generated_tokens'] for r in rr),'generation_duration_total_s':duration,
            'aggregate_generation_tokens_per_s':tok/duration})

    # Every paired comparison uses exactly the same 50 original question IDs.
    ids=sorted({r['question_id'] for r in rows if r['category']=='gsm8k'})
    check('50_matched_gsm8k_ids',len(ids)==50)
    by_model={m:{r['question_id']:int(r['answer_correct']) for r in rows if r['model']==m and r['category']=='gsm8k'} for m in MODELS}
    check('all_gsm8k_scored',all(set(x)==set(ids) and len(x)==50 for x in by_model.values()))
    matrix=np.array([[by_model[m][qid] for m in MODELS] for qid in ids],dtype=int)
    rng=np.random.default_rng(SEED);indices=rng.integers(0,50,size=(N_BOOT,50))
    resampled=matrix[indices].mean(axis=1)
    paired=[]
    for a,b in ((0,1),(0,2),(1,2)):
        diff=matrix[:,b]-matrix[:,a];draws=resampled[:,b]-resampled[:,a]
        low,high=np.quantile(draws,[.025,.975],method='linear')
        wins=int((diff==1).sum());losses=int((diff==-1).sum())
        check('paired_count_'+str(a)+str(b),wins-losses==int(matrix[:,b].sum()-matrix[:,a].sum()))
        paired.append({'reference_model':MODELS[a],'comparison_model':MODELS[b],'question_pairs_n':50,
            'comparison_only_correct_n':wins,'reference_only_correct_n':losses,
            'both_correct_n':int(((matrix[:,a]==1)&(matrix[:,b]==1)).sum()),
            'both_incorrect_n':int(((matrix[:,a]==0)&(matrix[:,b]==0)).sum()),
            'accuracy_difference_percentage_points':100*float(diff.mean()),
            'paired_bootstrap95_low_percentage_points':100*float(low),'paired_bootstrap95_high_percentage_points':100*float(high),
            'bootstrap_resamples':N_BOOT,'bootstrap_seed':SEED,'hypothesis_test_performed':False})
    check('wilson_boundary_validation',wilson(0,50)[0]==0 and close(wilson(0,50)[1],0.07134759913335872) and close(wilson(50,50)[0],0.9286524008666413))

    residency_paths=sorted(run.glob('session-*-residency-*.json'));samples=[load(p,'recorded Ollama residency') for p in residency_paths]
    allocations={m:set() for m in MODELS};order=[]
    for i,sample in enumerate(samples):
        mm=sample['ollama_ps']['models'];check('sample_'+str(i),not sample.get('error') and len(mm)<=1)
        for m in mm:
            name=m['name'];check('resident_identity_'+str(i),name in MODELS and m['digest']==snapshot['models'][name]['digest'] and m['context_length']==8192 and m['size']==m['size_vram'])
            allocations[name].add((m['size'],m['size_vram']))
            if not order or order[-1]!=name:order.append(name)
    check('sequential_residency',order==MODELS and not samples[0]['ollama_ps']['models'] and not samples[-1]['ollama_ps']['models'])
    check('empty_before_warmups',sum(x['phase']=='before_warmup' for x in samples)==3 and all(not x['ollama_ps']['models'] for x in samples if x['phase']=='before_warmup'))
    check('sample_count_307',len(samples)==307)
    memory=[]
    for model in MODELS:
        check(model+'_consistent_allocation',len(allocations[model])==1)
        size,vram=next(iter(allocations[model]));memory.append({'model':model,'size_bytes':size,'size_vram_bytes':vram,'ollama_allocation_mib':vram/1048576,'independent_gpu_peak_measured':False})
    warmups=[]
    for a in sorted((run/'warmups').iterdir()):
        req=load(a/'request.json','warm-up request');raw=load(a/'response.json','warm-up response');done=load(a/'complete.json','warm-up completion')
        check(a.name+'_warmup',raw['model']==req['model'] and raw['done'] is True and done['server_completion_unconfirmed'] is False and raw['eval_count']==1)
        warmups.append({'model':raw['model'],'load_s':raw['load_duration']/1e9,'status':done['status'],'excluded_from_scored_latency':True})
    check('three_warmups',len(warmups)==3)
    errors={'scored_completed':len(rows),'scored_truncations':sum(r['status']=='truncated' for r in rows),
        'missing_records':0,'extra_attempts':0,'recorded_infrastructure_errors':0,
        'automatic_incorrect':sum(r['answer_correct'] is False for r in rows),
        'format_failures':sum(not r['format_compliant'] for r in rows),
        'parse_or_representation_failures':sum(r['details'].startswith('Malformed output') for r in rows),
        'manual_correctness_reviewed':36,'no_combined_70_accuracy':True}
    validation=validate_datasets()
    base=project/'evaluation_final_report';base.mkdir(exist_ok=True)
    out=Path(output).resolve() if output else base/(RUN_ID+'-final-'+secrets.token_hex(6))
    require(out.is_relative_to(base) and out!=base,'Output must be a NEW evaluation_final_report subdirectory')
    out.mkdir(exist_ok=False)
    for sub in ('figures','tables','validation'):(out/sub).mkdir()
    with (out/'build_report.py').open('xb') as f:f.write(Path(__file__).read_bytes())
    write_csv(out/'tables/model_results.csv',summary_rows)
    write_csv(out/'tables/automatic_categories.csv',auto_categories)
    write_csv(out/'tables/human_categories.csv',human_categories)
    write_csv(out/'tables/latency_seconds.csv',latency)
    write_csv(out/'tables/tokens_and_generation.csv',token_rows)
    write_csv(out/'tables/ollama_memory_allocations.csv',memory)
    write_csv(out/'tables/gsm8k_paired_comparisons.csv',paired)
    write_csv(out/'tables/gsm8k_question_outcomes.csv',[{'question_id':qid,**{m:by_model[m][qid] for m in MODELS}} for qid in ids])
    write_csv(out/'tables/request_metrics.csv',[{k:r[k] for k in ('request_id','model','question_id','category','wall_time_s','prompt_tokens','generated_tokens','generation_s','load_s','response_sha256')} for r in rows])
    examples=[]
    for model,qid in [('qwen3:1.7b','C01'),('qwen3:1.7b','C03'),('qwen3:1.7b','K03'),('qwen3:8b','I02'),('gemma4:12b','I03'),('gemma4:12b','R01')]:
        rr=next(r for r in rows if r['model']==model and r['question_id']==qid)
        hh=next((h for h in human if h['request_id']==rr['request_id']),None)
        examples.append({'model':model,'question_id':qid,'assessment_source':'researcher R1 (AI-assisted)' if hh else 'original automatic scorer',
            'recorded_verdict':hh['human_verdict'] if hh else str(rr['answer_correct']),
            'rationale_or_diagnostic':hh['rationale'] if hh else rr['details'],
            'response_excerpt_exact':raw_by[rr['request_id']]['message']['content'][:240],'response_sha256':rr['response_sha256']})
    write_csv(out/'tables/notable_failures.csv',examples)
    stats={'models':summary_rows,'automatic_categories':auto_categories,'human_categories':human_categories,
           'latency':latency,'tokens':token_rows,'memory':memory,'gsm8k_paired':paired,'counts':errors,
           'human_review':{'reviewers_n':1,'reviewer_id':imported['reviewer_id'],'AI_assisted_assessment_suggestions':True,
                          'provenance':'Researcher disclosure supplied in final-report task; recorded ratings used unchanged.',
                          'independent_inter_rater_agreement_measured':False,'only_correctness_dimension_rated':True},
           'warmups':warmups,'dataset_integrity':validation,'residency_samples':len(samples),
           'wilson_z':Z,'bootstrap_seed':SEED,'bootstrap_resamples':N_BOOT,'formal_significance_claims':False}
    write_json(out/'statistics.json',stats)

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,
        'axes.spines.top':False,'axes.spines.right':False,'axes.titlepad':14,'figure.dpi':120,
        'savefig.dpi':300,'svg.fonttype':'none','axes.axisbelow':True})
    figure_info=[]
    def save(fig,name,caption,derivation):
        fig.text(.02,.015,caption,ha='left',va='bottom',fontsize=8,color='#444444')
        fig.savefig(out/'figures'/f'{name}.png',dpi=300,bbox_inches='tight',facecolor='white')
        fig.savefig(out/'figures'/f'{name}.svg',bbox_inches='tight',facecolor='white',metadata={'Creator':'NECTEC offline research analysis'})
        plt.close(fig)
        figure_info.append({'name':name,'caption':caption,'derivation':derivation})
    x=np.arange(3)
    fig,ax=plt.subplots(figsize=(7.2,4.4));fig.subplots_adjust(bottom=.20)
    values=[r['automatic_accuracy_percent'] for r in summary_rows]
    ax.bar(x,values,color=COLORS,width=.56)
    for i,r in enumerate(summary_rows):ax.text(i,values[i]+2.5,f"{r['automatic_correct']}/58\n{values[i]:.1f}%",ha='center',va='bottom',fontsize=10)
    ax.set(xticks=x,xticklabels=LABELS,ylim=(0,112),yticks=np.arange(0,101,20),ylabel='Automatic correctness (%)',title='Automatic correctness on 58 prespecified items')
    ax.grid(axis='y',alpha=.18)
    save(fig,'01_automatic_accuracy','50 GSM8K + 4 reasoning + 4 instruction items per model; human-reviewed items excluded.',
         'Count answer_correct=True among the 58 objective items/model; no /70 composite.')
    fig,ax=plt.subplots(figsize=(7.2,4.5));fig.subplots_adjust(bottom=.22)
    for i,r in enumerate(summary_rows):
        p=r['gsm8k_accuracy_percent'];lo=r['gsm8k_wilson95_low_percent'];hi=r['gsm8k_wilson95_high_percent']
        ax.errorbar(i,p,yerr=[[p-lo],[hi-p]],fmt='o',markersize=9,color=COLORS[i],capsize=7,lw=2)
        ax.text(i,hi+2.3,f"{r['gsm8k_correct']}/50 ({p:.0f}%)",ha='center',va='bottom')
    ax.set(xticks=x,xticklabels=LABELS,ylim=(0,112),yticks=np.arange(0,101,20),ylabel='GSM8K accuracy (%)',title='GSM8K accuracy with 95% Wilson intervals')
    ax.grid(axis='y',alpha=.18)
    save(fig,'02_gsm8k_accuracy_wilson','Same 50 questions/model; pointwise binomial intervals describe item sampling, not run-to-run variability.',
         'Wilson score interval using z=1.959963984540054, n=50; all wrong/format-failed answers retained.')
    fig,ax=plt.subplots(figsize=(8.5,4.4));fig.subplots_adjust(bottom=.25,left=.17)
    left=np.zeros(3);vc=['#009E73','#E69F00','#D55E00','#999999']
    for verdict,color in zip(VERDICTS,vc):
        data=np.array([r['human_'+verdict] for r in summary_rows])
        ax.barh(x,data,left=left,color=color,label=verdict.replace('_',' ').capitalize(),height=.55)
        for i,n in enumerate(data):
            if n:ax.text(left[i]+n/2,i,str(n),ha='center',va='center',color='white' if verdict in ('correct','incorrect') else '#222',fontweight='bold')
        left+=data
    ax.set(yticks=x,yticklabels=LABELS,xlim=(0,12),xticks=range(0,13,2),xlabel='Responses (12 reviewed per model)',title='Researcher correctness verdicts');ax.invert_yaxis()
    ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,-.17),frameon=False,fontsize=9)
    save(fig,'03_human_verdict_distribution','One researcher, AI-assisted assessment suggestions; no independent inter-rater agreement was measured.',
         'Explicit imported verdict counts; partly-correct answers are retained separately, without half credit.')
    fig,axes=plt.subplots(1,2,figsize=(11.8,4.7));fig.subplots_adjust(bottom=.22,wspace=.55,left=.12,right=.94)
    for ax,cats,records,cmap,title,human_flag in [
       (axes[0],['reasoning','instruction','gsm8k'],auto_categories,'Blues','Automatic correctness',False),
       (axes[1],['coding','knowledge','summarization'],human_categories,'YlOrBr','Human fully-correct verdicts',True)]:
        grid=np.array([[next(r for r in records if r['model']==m and r['category']==c)[
            'human_fully_correct_percent' if human_flag else 'automatic_accuracy_percent'] for c in cats] for m in MODELS])
        im=ax.imshow(grid,vmin=0,vmax=100,cmap=cmap,aspect='auto')
        for i,m in enumerate(MODELS):
            for j,c in enumerate(cats):
                row=next(r for r in records if r['model']==m and r['category']==c)
                n=row['reviewed_n'] if human_flag else row['questions_n'];k=row['correct_n']
                ax.text(j,i,f'{k}/{n}\n{grid[i,j]:.0f}%',ha='center',va='center',color='white' if grid[i,j]>=70 else '#111',fontsize=10)
        ax.set(yticks=x,yticklabels=LABELS,xticks=x,xticklabels=[c.capitalize()+'\nn='+str(50 if c=='gsm8k' else 4) for c in cats],title=title)
        fig.colorbar(im,ax=ax,fraction=.045,pad=.03,label='%')
    save(fig,'04_category_correctness','Automatic and human metrics are distinct. Internal cells have only 4 questions; coding review was static, without execution.',
         'Left: objective answer_correct proportions. Right: explicit human correct verdicts; not numeric-rating thresholds.')
    fig,ax=plt.subplots(figsize=(7.7,4.7));fig.subplots_adjust(bottom=.24)
    datasets=[[r['wall_time_s'] for r in rows if r['model']==m] for m in MODELS]
    boxes=ax.boxplot(datasets,positions=x,widths=.35,patch_artist=True,showfliers=False,medianprops={'color':'black','linewidth':1.6})
    for patch,color in zip(boxes['boxes'],COLORS):patch.set_facecolor(color);patch.set_alpha(.55)
    jitter=np.random.default_rng(SEED)
    for i,(values,color) in enumerate(zip(datasets,COLORS)):
        ax.scatter(i+jitter.uniform(-.10,.10,len(values)),values,s=12,color=color,alpha=.45,zorder=3)
    ax.set_yscale('log');ax.set(xticks=x,xticklabels=LABELS,ylabel='Scored-request wall time (seconds; log scale)',title='Observed response latency distributions')
    ax.grid(axis='y',which='both',alpha=.17)
    ax.annotate(f"Maximum: {max(datasets[2]):.2f} s",xy=(2,max(datasets[2])),xytext=(1.0,20),arrowprops={'arrowstyle':'->','color':'#555'},fontsize=9)
    save(fig,'05_latency_distributions','70 requests/model; points retain all observations. Box = IQR; line = median; whiskers = 1.5×IQR. Warm-ups excluded.',
         'Original complete.json wall_time_s, cross-checked against request_metrics.csv; not time to first token.')
    fig,axes=plt.subplots(1,2,figsize=(11.6,4.5));fig.subplots_adjust(bottom=.24,wspace=.38)
    for ax,data,title,ylabel,fmt in [(axes[0],[r['aggregate_generation_tokens_per_s'] for r in token_rows],
              'Observed generation throughput','Generated tokens / generation second','.1f'),
             (axes[1],[r['ollama_allocation_mib'] for r in memory],
              'Ollama-reported model allocation','Allocation (MiB)','.0f')]:
        ax.bar(x,data,color=COLORS,width=.55)
        for i,value in enumerate(data):ax.text(i,value+max(data)*.025,format(value,fmt),ha='center')
        ax.set(xticks=x,xticklabels=LABELS,ylabel=ylabel,title=title,ylim=(0,max(data)*1.18));ax.grid(axis='y',alpha=.18)
    save(fig,'06_throughput_and_allocation','Throughput uses each model’s tokenizer and variable-length outputs. Allocations are NOT independent GPU peak measurements.',
         'Throughput = sum(eval_count)/sum(eval_duration_s), 70 scored requests/model. Memory = consistent recorded size_vram / 2^20.')
    fig,ax=plt.subplots(figsize=(9.0,4.3));fig.subplots_adjust(left=.34,bottom=.25)
    for i,r in enumerate(paired):
        d=r['accuracy_difference_percentage_points'];lo=r['paired_bootstrap95_low_percentage_points'];hi=r['paired_bootstrap95_high_percentage_points']
        ax.errorbar(d,i,xerr=[[d-lo],[hi-d]],fmt='o',color='#333333',capsize=6,lw=1.8)
        ax.text(hi+1.1,i,f'{d:+.0f} pp',va='center',fontsize=9)
    ax.axvline(0,color='#999',ls='--',lw=1)
    ax.set(yticks=range(3),yticklabels=[LABELS[1]+' − '+LABELS[0],LABELS[2]+' − '+LABELS[0],LABELS[2]+' − '+LABELS[1]],
           xlabel='Paired accuracy difference (percentage points)',title='GSM8K paired question-level comparisons')
    ax.invert_yaxis();ax.set_xlim(min(-4,min(p['paired_bootstrap95_low_percentage_points'] for p in paired)-4),max(p['paired_bootstrap95_high_percentage_points'] for p in paired)+9);ax.grid(axis='x',alpha=.18)
    save(fig,'07_gsm8k_paired_differences','95% paired percentile bootstrap; 20,000 shared-ID resamples, seed 42. Descriptive pointwise intervals; no significance claims.',
         'Resample 50 matched question IDs with replacement, preserving all models for each ID; percentile endpoints 2.5/97.5%.')
    write_json(out/'figure_derivations.json',figure_info)

    # Save tables in a clean Markdown companion with explicit denominators and units.
    clean=[{'Model':r['model'],'Automatic /58':f"{r['automatic_correct']}/58 ({r['automatic_accuracy_percent']:.1f}%)",
            'GSM8K /50':f"{r['gsm8k_correct']}/50 ({r['gsm8k_accuracy_percent']:.1f}%)",
            'GSM8K 95% CI':f"{r['gsm8k_wilson95_low_percent']:.1f}–{r['gsm8k_wilson95_high_percent']:.1f}%",
            'Human C/P/I/U /12':f"{r['human_correct']}/{r['human_partly_correct']}/{r['human_incorrect']}/{r['human_uncertain']}",
            'Mean human correctness /5':f"{r['human_correctness_mean_1_to_5']:.2f}"} for r in summary_rows]
    text='# Research tables\n\nAutomatic correctness and researcher verdicts remain separate; C/P/I/U = correct/partly correct/incorrect/uncertain.\n\n'+markdown_table(clean,list(clean[0]))
    for title,records in [('Automatic categories',auto_categories),('Human-reviewed categories',human_categories),('Scored-request latency, seconds',latency),('Token counts and generation rate',token_rows),('Ollama allocation, bytes and MiB',memory),('Paired GSM8K comparisons, percentage points',paired)]:
        formatted=[{k:(f'{v:.4f}' if isinstance(v,float) else v) for k,v in row.items()} for row in records]
        text+='\n## '+title+'\n\n'+markdown_table(formatted,list(formatted[0]))
    write_md(out/'TABLES.md',text)

    # Research prose uses only actual imported outcomes and validated source observations.
    results=f'''# Results and Discussion

## Study condition and analysis scope

The evaluation compared the installed Ollama tags qwen3:1.7b, qwen3:8b and gemma4:12b on
70 fixed English-language questions each: 20 curated internal items and 50 GSM8K items.
One repetition produced 210 scored responses. All requests used the frozen condition:
8192 configured context tokens, 4096 maximum generated tokens, temperature 0, seed 42,
top_k 40, top_p 0.9, repeat_penalty 1.0, repeat_last_n 64, explicit think=false,
non-streaming responses, keep_alive=30s, and a 600-second transport timeout. The runtime
was Ollama {snapshot['ollama_version']['version']} on the recorded RTX 5060 Ti system.
The installed quantized artifacts/templates are the comparison units; parameter count
alone was not isolated experimentally. Exact model digests are in model_metadata.json.

Automatic correctness applies to 58 items/model (50 GSM8K, four reasoning and four
instruction tasks). The remaining 12 items/model received researcher correctness review
(four coding, four knowledge and four summarization). These measurement types are reported
separately. No combined accuracy over 70 items or invented /25 rubric aggregate is used.

## Collection integrity

All 210 scored requests completed with one attempt each. Request/response hashes, plan,
frozen settings, dataset/reference identities and source bindings passed offline checks.
No scored truncation, missing response or recorded infrastructure error occurred. The
three one-token warm-ups ended at their intentional length limit and were excluded from
quality and scored latency summaries. Full 8192/4096 capacity was not certified.

## Automatically scored correctness

'''+markdown_table(clean,list(clean[0]))+f'''

The automatic-subset correctness rates were 60.3%, 82.8% and 91.4%, respectively. Because
50 of the 58 automatic items are GSM8K, this pooled metric is strongly weighted toward
that dataset rather than an equal-category general-quality score (Figure 1).

GSM8K accuracy was 34/50 (68%) for Qwen3 1.7B, 45/50 (90%) for Qwen3 8B, and 47/50 (94%)
for Gemma4 12B. All 150 answers, including wrong and malformed final-answer representations,
received offline outcomes; none was excluded from its denominator. The pointwise Wilson
intervals (Figure 2) quantify nominal item-sampling uncertainty, not run-to-run variation
or uncertainty caused by benchmark contamination. They should not be generalized to all
mathematical reasoning tasks.

The paired contrasts in Figure 7 and tables/gsm8k_paired_comparisons.csv use the same 50
question IDs. They retain discordant outcomes rather than treating model samples as
independent. The following are descriptive, exploratory comparisons, with no formal
hypothesis test, multiplicity-adjusted inference, or claim of statistical significance:

'''
    for p in paired:
        results+=f"- {p['comparison_model']} minus {p['reference_model']}: {p['accuracy_difference_percentage_points']:+.0f} percentage points; paired bootstrap 95% interval {p['paired_bootstrap95_low_percentage_points']:.0f} to {p['paired_bootstrap95_high_percentage_points']:.0f} points; {p['comparison_only_correct_n']} comparison-only correct versus {p['reference_only_correct_n']} reference-only correct answers.\n"
    results+='''
The observed four-point gap between the two larger models represents only two net
questions; it should not be presented as established general superiority. The much
smaller internal automatic categories also illustrate metric sensitivity: correctness
was 1/4, 0/4 and 3/4 for reasoning, and 0/4, 3/4 and 3/4 for instruction tasks (Figure 4).
Four questions per category are insufficient for broad category-level rankings.

## Researcher correctness review

One researcher (R1) recorded the 36 human ratings using AI-assisted assessment suggestions.
No independent inter-rater agreement was measured. Existing blind IDs were retained, but
the exercise should not be described as independent multi-rater validation. The judgments
and their rationales were imported unchanged; they are not automatic correctness labels.

Fully-correct verdicts were 7/12, 9/12 and 10/12 (58.3%, 75.0% and 83.3%). Partly-correct
verdicts numbered two, three and two, while incorrect verdicts numbered three, zero and
zero. No uncertain verdict was recorded (Figure 3). The mean correctness/fidelity ratings
were 4.00, 4.75 and 4.83 on the original 1–5 scale. These ordinal-rating means are descriptive;
they are not accuracy percentages. The four other rubric dimensions were not rated and
were neither imputed nor treated as zeros.

Coding was reviewed statically by tracing the supplied examples and inspecting the
algorithm; generated code was not executed. The researcher judged 2/4 Qwen3 1.7B coding
answers fully correct and 4/4 for each larger model. All 12 answers passed the automatic
structural checker, demonstrating why parsing/signature compliance cannot establish
functional correctness. Knowledge fully-correct counts were 2/4, 2/4 and 4/4. Summarization
fully-correct counts were 3/4, 3/4 and 2/4. Thus, the highest observed GSM8K score did not
translate into the highest fully-correct summarization count under this researcher's
criteria. The counts are small and sensitive to reviewer interpretation.

## Formatting sensitivity and notable failures

There were 38 automatically incorrect outcomes, including 13 format-contract failures;
five were parser/unsupported-representation failures. These counts overlap. Overall
format compliance was 63/70, 66/70 and 68/70. Exact-answer tasks intentionally couple
format and correctness, so a format failure does not always mean invalid JSON or a
mathematical error. Strict parsing and no fallback extraction were preserved.

Examples include a fenced JSON array for Qwen3 8B I02 and fenced JSON for Gemma4 12B I03.
Both violate the required output contract even when the enclosed values appear suitable.
Gemma4 12B R01 emitted an initial candidate followed by a self-correction and a second
fenced object; the scorer did not extract a favourable final object. Researcher-identified
Qwen3 1.7B code defects included adjacent-only deduplication in C01 and returning an empty
list rather than raising ValueError for nonpositive size in C03. Its K03 answer contradicted
its own rollback statement. Source hashes and exact excerpts are retained in
 tables/notable_failures.csv; no answers or ratings were repaired.

## Latency, generation rate and memory trade-offs

'''
    perf=[]
    for i,m in enumerate(MODELS):
        l=latency[i];t=token_rows[i];mem=memory[i]
        perf.append({'Model':m,'Mean wall, s':f"{l['mean_s']:.3f}",'Median wall, s':f"{l['median_s']:.3f}",
            'P95 wall, s':f"{l['p95_s']:.3f}",'Generated tokens':t['generated_tokens_total'],
            'Generation tokens/s':f"{t['aggregate_generation_tokens_per_s']:.1f}",'Ollama MiB':f"{mem['ollama_allocation_mib']:.0f}"})
    results+=markdown_table(perf,list(perf[0]))+'''

The observed condition therefore shows a quality/latency trade-off: the larger artifacts
had higher GSM8K correctness but longer median response times and larger recorded model
allocations. This is a descriptive comparison of these runs, not a causal estimate of
model-size effects. Gemma4 generated 15,416 tokens, compared with 7,380 and 7,038, so its
longer responses also contributed to elapsed latency. It had a 30.09-second maximum
request, which remained in the distribution rather than being silently removed (Figure 5).

Aggregate generation rate is total generated tokens divided by summed Ollama eval_duration.
Different tokenizers and generated lengths limit direct hardware-efficiency interpretation
(Figure 6). The requests were warmed; warm-up loading time and residency-expiration waits
are excluded from scored latency. Non-streaming wall time is not time to first token.

All 307 residency snapshots showed at most one expected model, matching digest/context
and equal size and size_vram. Recorded transitions and the final block reached empty
residency. The approximately 3028, 7156 and 8625 MiB figures are Ollama-reported allocations,
not independent GPU peak measurements. No continuous GPU-wide peak/process telemetry was
collected, so external interference between samples or from the same client/model cannot
be ruled out retrospectively.

## Limitations and interpretation

The study used a single repetition, so it provides no estimate of between-run reliability
or seed/hardware/runtime variance. Temperature zero and a fixed seed do not establish
universal determinism. The internal sample contains only four questions/category/model;
the public GSM8K subset has 50 questions and may overlap model training data. Observed
performance must be limited to these tasks and installed quantized model/runtime conditions.

The researcher review used AI-assisted suggestions and only one rater. Anchoring,
confirmation bias, shared assessment errors and subjective treatment of omissions may
influence its outcomes. No inter-rater agreement or independent execution validation is
available. Human verdict proportions should remain separately labelled, particularly for
static code assessment. There is no completed full five-category rubric score.

C03 and I01 were exposed during the smoke test. This exposure must be disclosed; conclusions
assume no tuning, model selection by favourable attempt, prompt rewriting, or changed
scoring rules after exposure. Strict formatting is part of the prespecified task contract,
but lower scores can reflect output-style compliance as well as substantive reasoning.

Question order was shared, but model execution occurred in fixed blocks. Thermal/cache/
shared-system effects were not counterbalanced by repeated runs. Wilson and paired
bootstrap intervals describe conditional item uncertainty only; they do not incorporate
these methodological sources of uncertainty. They are pointwise and exploratory, not
familywise-adjusted significance tests.

Finally, observed prompt counts and generated lengths were far below configured maxima;
no occupied 8192-token context or sustained 4096-token output certification is claimed.
The appropriate report is a completed fixed-workload quality experiment, with separate
automatic and researcher-reviewed findings and transparent performance/memory definitions.

## Statistical references

- NIST/SEMATECH e-Handbook, Wilson confidence intervals: https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- SciPy documentation, paired-index and percentile bootstrap definitions: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html

The implementation uses NumPy for explicit resampling; SciPy was not a runtime dependency.
'''
    write_md(out/'RESULTS_AND_DISCUSSION.md',results)

    # Inventory only names/hashes of private review inputs, never duplicate the blind mapping.
    for name in manifest['source_sha256']:source(project/'evaluation'/name,'bound evaluation implementation')
    idx=config['verification']['thinking_verification']['evidence']
    for relative in idx['files']:source(project/idx['root']/relative,'preserved empirical-thinking source evidence')
    source(project/'evaluation/rubrics/manual_v2.md','original manual rubric')
    inventory_rows=[{'path':name,**info} for name,info in sorted(used.items())]
    write_csv(out/'source_inventory.csv',inventory_rows)
    write_json(out/'source_inventory.json',inventory_rows)
    provenance={'run':str(run),'analysis':str(analysis),'human_ratings':str(human_dir),
        'models':{m:{'digest':snapshot['models'][m]['digest'],'details':snapshot['models'][m]['show']['details']} for m in MODELS},
        'runtime':snapshot['ollama_version'],'request_options':config['options'],'think':config['think'],
        'system_prompt':config['system_message'],'repetitions':1,'keep_alive':config['keep_alive'],
        'timeout_seconds':config['timeout_seconds'],'scope':'fixed-workload-readiness-v1; capacity_verified=false',
        'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__}
    write_json(out/'model_metadata.json',provenance)
    captions='# Figure captions and derivations\n\n'
    for i,info in enumerate(figure_info,1):
        captions+=f'## Figure {i}: {info["name"]}\n\n{info["caption"]}\n\nDerivation: {info["derivation"]}\n\n'
    write_md(out/'FIGURE_CAPTIONS.md',captions)
    readme=f'''# NECTEC final research results package

Run: `{RUN_ID}`. Prepared entirely offline into this NEW directory.

Start with RESULTS_AND_DISCUSSION.md, TABLES.md, and figures/. All seven figures are
provided as 300-DPI PNG and editable SVG. FIGURE_CAPTIONS.md and figure_derivations.json
state each derivation. Tables retain full numeric precision in CSV/JSON; manuscript prose
uses rounded values. No original source, rating, scoring rule, response or frozen setting
was modified. No inference, GPU workload, benchmark rerun, or generated-code execution ran.

## Metric definitions and denominators

- Automatic accuracy: original answer_correct True /58 per model; 50 GSM8K +4 reasoning
  +4 instruction items. Wrong/malformed answers remain failures in the denominator.
- GSM8K: True /50, with 95% Wilson intervals. Center=(p+z²/(2n))/(1+z²/n), half-width=
  z*sqrt(p(1-p)/n+z²/(4n²))/(1+z²/n), z={Z}. These nominal binomial intervals assume an
  item-sampling interpretation and do not quantify training contamination or run variability.
- Paired comparisons: shared sorted 50 question IDs; comparison minus reference accuracy.
  Resample whole question IDs with replacement for all models together ({N_BOOT} draws,
  NumPy default_rng seed {SEED}); 2.5/97.5 percentiles, linear interpolation. Discordant
  wins/losses and question-level outcomes are exported. No hypothesis tests/significance
  stars, p-values, or broad superiority claims are supplied. Intervals are pointwise.
- Human correctness: explicit researcher verdicts correct/partly_correct/incorrect/uncertain,
  /12 per model and /4 per category. Partly correct is separate, not half credit. Only
  correctness ratings were entered: original 1–5 means are descriptive, not percentages.
  The other four rubric dimensions remain unrated. No /25 or undocumented /70 composite.
- Latency: original scored complete.json wall_time_s; 70/model; warm-ups and expiration
  waits excluded. Boxes show IQR/median/Tukey whiskers with all raw points; log axis labelled.
  Descriptive P95 tables use linear interpolation at rank (n-1)*0.95; no outliers removed.
- Generation throughput: sum(eval_count)/sum(eval_duration/1e9), per model. Tokens use each
  model's own tokenizer; output lengths differ. This is not wall-clock service throughput
  or time to first token. Prompt/generated token totals and maxima are exported.
- Memory: matching recorded size_vram bytes /1048576 = MiB, not GB and not independent
  GPU peak memory. Residency sampling cannot establish absence of every external workload.

## Figure/table mapping

'''
    for info in figure_info:readme+=f'- `{info["name"]}.png/.svg`: {info["derivation"]}\n'
    readme+='''
CSV tables: model_results, automatic_categories, human_categories, latency_seconds,
tokens_and_generation, ollama_memory_allocations, gsm8k_paired_comparisons,
gsm8k_question_outcomes, request_metrics, and notable_failures. TABLES.md is the readable
companion. statistics.json preserves all aggregates; model_metadata.json pins model digests,
options, runtime and plot-library versions. source_inventory.csv/json contains source-file
paths, roles, byte sizes and SHA-256 hashes. It inventories private review input identities
without redistributing the private blind mapping or editing those inputs.

## Review provenance and cautions

ONE researcher recorded human ratings with AI-assisted assessment suggestions, as disclosed
by the researcher. No independent inter-rater agreement was measured. Static coding review
is not executed functional correctness. The final human figures report those actual
recorded decisions without re-adjudicating them. Independent review would be additional
future evidence, not something claimed here. The small internal categories, single
repetition, fixed execution order, smoke-question exposure, format sensitivity, possible
public-data contamination and uncertified maximum capacity are discussed in the draft.

## Reproduce without modifying evidence

From the project root, with the existing plotting environment:

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/nectec-final-matplotlib \\
  venv/bin/python PATH_TO_THIS_PACKAGE/build_report.py --project /home/lailai/ollama-test
```

Default execution creates another NEW uniquely named directory under evaluation_final_report/.
An optional --output must name a new directory under that root; existing outputs are refused.
Only local CPU plotting/statistics are used. No Ollama endpoints or GPU tools are called.
Do not import the build script as an evaluation module. It runs only through main().

## Output validation

validation/verification.json records recomputed counts, hashes and source/table comparisons.
validation/preservation.json records before/after source hashes. validation/output_checks.json
records image readability/resolution and SVG/table integrity. FILES_SHA256.json inventories
all finished package files (excluding itself). A contact sheet under validation/ is a
preview only; individual figures are the publication artifacts. No review score was invented.
'''
    write_md(out/'README.md',readme)
    write_json(out/'validation/verification.json',{'all_checks_passed':all(checks.values()),'checks_n':len(checks),'checks':checks,'dataset_integrity':validation})
    after={str(p.relative_to(project)):sha(p) for name in roots for p in sorted((project/name).rglob('*')) if p.is_file()}
    require(before==after,'Preserved source artifacts changed during report generation')
    write_json(out/'validation/preservation.json',{'all_preserved_sources_unchanged':True,'files_n':len(before),'files_sha256':before})
    print('OUTPUT_DIRECTORY',out)
    print('VERIFICATION_CHECKS',len(checks),'PRESERVED_FILES',len(before))
    print('RESULTS',json.dumps(summary_rows))
    print('PAIRED_COMPARISONS',json.dumps(paired))
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=Path('/home/lailai/ollama-test'))
    p.add_argument('--output',type=Path)
    args=p.parse_args();out=build(args.project,args.output)
    Path('/tmp/nectec-final-report-output.txt').write_text(str(out))


if __name__=='__main__':main()
