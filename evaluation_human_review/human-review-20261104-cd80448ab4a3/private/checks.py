"""Offline checks. Synthetic decisions below apply only to temporary fake responses."""
import csv
from collections import Counter
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review_import',ROOT/'private/import_ratings.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))


def write_rows(path, rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=review.FIELDS);w.writeheader();w.writerows(rows)


class ReviewChecks(unittest.TestCase):
    def setUp(self):
        for name in ('socket.create_connection','socket.socket.connect','subprocess.run'):
            p=patch(name,side_effect=AssertionError('No network or GPU work in review checks'))
            p.start();self.addCleanup(p.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.expected={'test-blind':{'question_id':'K01','category':'knowledge'}}
        self.row=dict.fromkeys(review.FIELDS,'')
        self.row.update(blind_id='test-blind',question_id='K01',category='knowledge',
                        reviewer_id='OFFLINE_FIXTURE',human_verdict='uncertain',
                        rationale='SYNTHETIC FIXTURE ONLY; no real response was reviewed')
        self.ratings=self.root/'ratings.csv'

    def validate(self, rows):
        write_rows(self.ratings,rows)
        return review.validate_rows(self.ratings,self.expected)

    def test_real_packet_has_exactly_36_preserved_blind_responses(self):
        manifest=review.load(ROOT/'private/manifest.json')
        records=[json.loads(line) for line in (ROOT/'reviewer/responses.jsonl').read_text().splitlines()]
        self.assertEqual(len(records),36)
        self.assertEqual(Counter(r['category'] for r in records),{'coding':12,'knowledge':12,'summarization':12})
        self.assertTrue(all(n==3 for n in Counter(r['question_id'] for r in records).values()))
        for record in records:
            self.assertEqual(record['response'],review.load(manifest['responses'][record['blind_id']]['raw_response_file'])['message']['content'])
        rendered=(ROOT/'reviewer/booklet.html').read_text()
        recovered=[html.unescape(s) for s in re.findall(r'<pre class="response">(.*?)</pre>',rendered,re.S)]
        self.assertEqual(recovered,[r['response'] for r in records])
        self.assertNotIn('<script',rendered.lower())
        for path in (ROOT/'reviewer').iterdir():
            self.assertIsNone(re.search(r'qwen|gemma|ollama|alibaba|openai|chatgpt|google',path.read_text(),re.I))
        for filename,checksum in manifest['source_files_sha256'].items():self.assertEqual(review.sha(filename),checksum)
        for relative,checksum in manifest['packet_files_sha256'].items():self.assertEqual(review.sha(ROOT/relative),checksum)

    def test_real_template_remains_blank_and_cannot_be_imported(self):
        with (ROOT/'reviewer/ratings_template.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),36)
        self.assertTrue(all(not r[k] for r in rows for k in review.FIELDS if k not in ('blind_id','question_id','category')))
        expected=review.load(ROOT/'private/manifest.json')['responses']
        with self.assertRaisesRegex(ValueError,'Reviewer ID missing'):
            review.validate_rows(ROOT/'reviewer/ratings_template.csv',expected)

    def test_uncertainty_preserves_missing_ratings(self):
        result=self.validate([self.row])
        self.assertIsNone(result[0]['correctness'])
        metrics=review.review_summary(result)
        self.assertEqual(metrics['human_uncertain'],1)
        self.assertEqual(metrics['correctness_n'],0)
        self.assertIsNone(metrics['correctness_mean_1_to_5'])
        self.assertIsNone(metrics['human_fully_correct_fraction_decided_only'])

    def test_valid_decided_fixture_keeps_explicit_verdict_separate_from_rating(self):
        self.row.update(human_verdict='correct',**dict.fromkeys(review.DIMENSIONS,'4'))
        result=self.validate([self.row])
        self.assertEqual(result[0]['correctness'],4)
        self.assertEqual(review.review_summary(result)['human_correct'],1)

    def test_minimal_review_does_not_invent_optional_dimension_ratings(self):
        self.row.update(human_verdict='partly_correct',correctness='3')
        result=self.validate([self.row])
        metrics=review.review_summary(result)
        self.assertEqual(metrics['correctness_n'],1)
        self.assertEqual(metrics['instruction_following_n'],0)
        self.assertIsNone(metrics['instruction_following_mean_1_to_5'])

    def test_bad_ranges_and_blank_decided_ratings_rejected(self):
        self.row['human_verdict']='incorrect'
        for value in ('','0','6','4.5','NaN','=1+1'):
            with self.subTest(value=value):
                self.row.update(dict.fromkeys(review.DIMENSIONS,'3'));self.row['correctness']=value
                with self.assertRaises(ValueError):self.validate([self.row])

    def test_duplicate_missing_unknown_and_changed_ids_rejected(self):
        with self.assertRaises(ValueError):self.validate([])
        with self.assertRaises(ValueError):self.validate([self.row,self.row])
        for key,value in (('blind_id','unknown'),('question_id','K02'),('category','coding')):
            row=dict(self.row);row[key]=value
            with self.assertRaises(ValueError):self.validate([row])

    def test_missing_decision_reviewer_rationale_rejected(self):
        for key in ('human_verdict','reviewer_id','rationale'):
            row=dict(self.row);row[key]=''
            with self.assertRaises(ValueError):self.validate([row])

    def fake_package(self):
        package=self.root/'packet';(package/'private').mkdir(parents=True);(package/'reviewer').mkdir()
        records=[];expected={};sources={};scores=[];categories={};ratings=[]
        for m in range(3):
            model='SYNTHETIC_MODEL_'+str(m)
            for i in range(12):
                category=('coding','knowledge','summarization')[i//4]
                qid=('C','K','S')[i//4]+str(i%4+1);bid=f'test-blind-{m}-{i}'
                response='OFFLINE FIXTURE RESPONSE; no model inference or real judgement'
                raw=self.root/f'raw-{m}-{i}.json';dump(raw,{'message':{'content':response}});sources[str(raw)]=review.sha(raw)
                expected[bid]={'question_id':qid,'category':category,'model':model,'request_id':f'fake-{m}-{i}',
                               'raw_response_file':str(raw),'response_text_sha256':hashlib.sha256(response.encode()).hexdigest()}
                records.append({'blind_id':bid,'response':response})
                row=dict(self.row);row.update(blind_id=bid,question_id=qid,category=category);ratings.append(row)
                scores.append({'model':model,'question_id':qid,'answer_correct':None})
            for prefix,n,category in (('R',4,'reasoning'),('I',4,'instruction'),('G',50,'gsm8k')):
                for i in range(n):
                    qid=prefix+str(i);categories[qid]=category
                    scores.append({'model':model,'question_id':qid,'answer_correct':True})
        score_file=self.root/'scores.json';dump(score_file,scores);sources[str(score_file)]=review.sha(score_file)
        packet=package/'reviewer/responses.jsonl';packet.write_text(''.join(json.dumps(r)+'\n' for r in records))
        manifest={'version':'human-review-packet-v1','responses':expected,'scores_json':str(score_file),
                  'source_files_sha256':sources,'packet_files_sha256':{'reviewer/responses.jsonl':review.sha(packet)},'categories':categories}
        dump(package/'private/manifest.json',manifest)
        write_rows(self.ratings,ratings)
        return package,score_file

    def test_import_synthetic_fixture_to_new_private_output_only(self):
        package,source=self.fake_package();before=source.read_bytes()
        output=package/'private/results/fixture'
        review.import_ratings(package,self.ratings,output)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual((output/'completed_ratings.csv').read_bytes(),self.ratings.read_bytes())
        with (output/'model_metrics.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r['human_uncertain']=='12' and r['automatic_n']=='58' for r in rows))
        self.assertTrue(all('combined_accuracy' not in r for r in rows))
        with self.assertRaises(FileExistsError):review.import_ratings(package,self.ratings,output)

    def test_source_and_packet_tampering_rejected_before_output(self):
        package,source=self.fake_package();original=source.read_bytes()
        output=package/'private/results/rejected'
        source.write_text('[]')
        with self.assertRaisesRegex(ValueError,'source missing/changed'):review.import_ratings(package,self.ratings,output)
        self.assertFalse(output.exists());source.write_bytes(original)
        (package/'reviewer/responses.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'Packet file missing/changed'):review.import_ratings(package,self.ratings,output)
        self.assertFalse(output.exists())

    def test_model_labelled_results_cannot_be_written_to_reviewer_folder(self):
        package,_=self.fake_package()
        with self.assertRaisesRegex(ValueError,'private/results'):
            review.import_ratings(package,self.ratings,package/'reviewer/results')
        self.assertFalse((package/'reviewer/results').exists())


if __name__=='__main__':unittest.main(verbosity=2)
