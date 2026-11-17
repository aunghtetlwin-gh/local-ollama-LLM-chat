"""Score saved runs and export blinded manual-review forms; never calls Ollama."""
import argparse
import csv
from pathlib import Path

from .common import DATASETS, digest, read_json, read_jsonl, sha256, write_new
from .scoring import score


def csv_safe(value):
    value = '' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value


def write_csv(path, fields, rows):
    with path.open('x',newline='',encoding='utf-8') as file:
        writer = csv.DictWriter(file,fieldnames=fields);writer.writeheader()
        for row in rows: writer.writerow({k:csv_safe(row.get(k)) for k in fields})


def analyze(run, output):
    run = Path(run); output = Path(output)
    manifest = read_json(run/'manifest.json'); plan = read_json(run/'plan.json')
    if digest(plan) != manifest['plan_sha256']: raise ValueError('Plan checksum mismatch')
    if digest(manifest['config']) != manifest['config_sha256']: raise ValueError('Configuration checksum mismatch')
    references = {}
    ref_hashes = {}
    for suite in manifest['suites']:
        directory = DATASETS[suite]; dataset = read_json(directory/'manifest.json')
        if dataset != manifest['dataset_manifests'][suite]: raise ValueError('Dataset provenance changed')
        path = directory/'references.jsonl'
        if sha256(path.read_bytes()) != dataset['references_sha256']: raise ValueError('References changed')
        ref_hashes[suite] = dataset['references_sha256']
        references.update({r['id']:r for r in read_jsonl(path)})
    scores=[];review=[];mapping=[]
    for item in plan:
        attempts = sorted((run/'requests'/item['request_id']).glob('attempt-*'))
        completed = [p for p in attempts if (p/'complete.json').exists()]
        status='missing';text='';response_hash=None;attempt_name=None;wall=None
        if completed:
            attempt = completed[-1]; attempt_name=attempt.name
            completion = read_json(attempt/'complete.json')
            if completion['request_sha256'] != digest(item): raise ValueError('Saved request identity changed')
            if sha256((attempt/'request.json').read_bytes()) != completion['request_file_sha256']:
                raise ValueError('Saved request changed')
            status=completion['status'];wall=completion.get('wall_time_s')
            if completion.get('response_sha256'):
                response_hash=sha256((attempt/'response.json').read_bytes())
                if response_hash != completion['response_sha256']: raise ValueError('Saved response changed')
                raw=read_json(attempt/'response.json')
                message=raw.get('message',{}) if isinstance(raw,dict) else {}
                text=message.get('content','') if isinstance(message,dict) else ''
            elif (attempt/'response.json').exists():
                raise ValueError('Unexpected response without completion checksum')
        elif attempts: status='interrupted'
        result=score(text,references[item['question_id']],status)
        scores.append({'request_id':item['request_id'],'model':item['model'],
            'question_id':item['question_id'],'repetition':item['repetition'],
            'attempt':attempt_name,'attempt_count':len(attempts),'response_sha256':response_hash,
            'wall_time_s':wall,**result})
        if references[item['question_id']]['kind'] != 'numeric':
            blind_id=digest({'request':item['request_id'],'run':manifest['created_at']})[:20]
            reference=references[item['question_id']]
            review.append({'blind_id':blind_id,'question_id':item['question_id'],
                'repetition':item['repetition'],'prompt':item['payload']['messages'][-1]['content'],
                'response':text if isinstance(text,str) else '', 'status':result['status'],
                'criteria':' | '.join(reference['acceptance_criteria']),
                'review_examples':reference.get('review_examples',[]),
                'reviewer_id':'','correctness':'','instruction_following':'','relevance':'',
                'completeness':'','conciseness':'','rationale':''})
            mapping.append({'blind_id':blind_id,'request_id':item['request_id'],'model':item['model']})
    # Validate/read everything before creating a fresh output directory.
    output.mkdir(parents=True,exist_ok=False)
    write_new(output/'scores.json',scores)
    fields=['request_id','model','question_id','repetition','attempt','attempt_count','status',
            'answer_correct','format_compliant','static_checks_pass','runtime_correctness',
            'manual_review_required','details','response_sha256','wall_time_s']
    write_csv(output/'scores.csv',fields,scores)
    review.sort(key=lambda row:row['blind_id'])
    write_csv(output/'manual_review.csv',['blind_id','question_id','repetition','prompt','response','status',
              'criteria','review_examples','reviewer_id','correctness','instruction_following','relevance',
              'completeness','conciseness','rationale'],review)
    write_new(output/'private_blind_mapping.json',mapping)
    (output/'private_blind_mapping.json').chmod(0o600)
    write_new(output/'analysis_manifest.json',{'input_manifest_sha256':sha256((run/'manifest.json').read_bytes()),
        'plan_sha256':manifest['plan_sha256'],'reference_hashes':ref_hashes,
        'evaluator_hashes':{p.name:sha256(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('scoring.py')]},
        'rubric_sha256':sha256((Path(__file__).parent/'rubrics/manual_v2.md').read_bytes()),
        'note':'No generated code executed. No automatic semantic score for knowledge, summaries, or coding.'})
    return scores


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    try: print('Scored',len(analyze(args.run_dir,args.output_dir)),'planned requests offline')
    except (ValueError,KeyError,OSError) as error: parser.exit(1,f'Scoring stopped: {error}\n')


if __name__=='__main__': main()
