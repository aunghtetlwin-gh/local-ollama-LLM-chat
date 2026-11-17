"""Offline vocabulary-only tokenization; no Ollama requests or tensor evaluation.

Only the saved two-message, text-only profiles are supported. Counts are unavailable
unless a CPU vocabulary backend and all saved calibration checks succeed.
"""
import argparse
import importlib.util
import re
from pathlib import Path

from .common import BASE, DATASETS, digest, load_questions, read_json, sha256, write_new

VERSION = 'cpu-prompt-tokens-v1'
PHASE2 = BASE.parent / 'evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e'
LIMITATION = ('Exact compatible CPU tokenizer/rendering profile unavailable. No token estimates '
              'are substituted. Install/review a compatible llama-cpp-python vocabulary backend '
              'and pass saved calibration before preparing live requests.')


def render(model, messages, think):
    if type(think) is not bool or [m.get('role') for m in messages] != ['system', 'user']:
        raise ValueError('Only explicit boolean thinking and system/user text profiles supported')
    if any(set(m) != {'role', 'content'} or not isinstance(m['content'], str) for m in messages):
        raise ValueError('Text-only messages required')
    system, user = [m['content'] for m in messages]
    # Literal special-token spellings in input would change parsing semantics.
    if any(x in system + user for x in ('<|', '<bos>', '<turn|>')):
        raise ValueError('Special-token injection is outside this rendering profile')
    if model.startswith('qwen3:'):
        prefix = (f'<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}'
                  + (' /think' if think else ' /no_think')
                  + '<|im_end|>\n<|im_start|>assistant\n')
        return prefix + ('' if think else '<think>\n\n</think>\n\n')
    if model == 'gemma4:12b':
        # Installed 12B resolves to the large no-think profile. BOS is supplied by
        # the tokenizer (Ollama strips the renderer's leading BOS in this path).
        prefix = ('<|turn>system\n' + ('<|think|>\n' if think else '') + system.strip()
                  + '<turn|>\n<|turn>user\n' + user.strip() + '<turn|>\n<|turn>model\n')
        return prefix + ('' if think else '<|channel>thought\n<channel|>')
    raise ValueError('Unsupported rendering profile')


class CpuCounter:
    """Optional llama.cpp vocabulary-only backend. Never creates a generation context."""
    def __init__(self, snapshot, phase2=PHASE2):
        self.snapshot, self.phase2 = snapshot, Path(phase2)
        self.models, self.identities, self.reasons = {}, {}, {}
        self.baseline = read_json(self.phase2 / 'metadata.json')
        self.library = None
        if importlib.util.find_spec('llama_cpp') is None:
            for model in snapshot['models']:
                self.reasons[model] = LIMITATION
            return
        try:
            import llama_cpp
            self.library = llama_cpp
            for model in snapshot['models']:
                try:
                    self._load(model)
                except Exception as error:
                    self.reasons[model] = LIMITATION + ' ' + str(error)
                    self.close_model(model)
        except Exception as error:
            for model in snapshot['models']:
                self.reasons[model] = LIMITATION + ' ' + str(error)

    def _load(self, model):
        if self.snapshot != self.baseline or self.snapshot['ollama_version'] != {'version': '0.32.15'}:
            raise ValueError('Only exact Phase 2 runtime/model metadata is supported')
        data = self.snapshot['models'][model]
        paths = re.findall(r'^FROM (/.+)$', data['show']['modelfile'], flags=re.MULTILINE)
        if not paths:
            raise ValueError('No installed GGUF path')
        path = Path(paths[0])
        # Validate installed manifest/config identity without touching model tensors.
        manifest_path = path.parent.parent / 'manifests/registry.ollama.ai/library' / model.replace(':', '/')
        if sha256(manifest_path.read_bytes()) != data['digest']:
            raise ValueError('Installed model manifest digest mismatch')
        manifest = read_json(manifest_path)
        config_path = path.parent / manifest['config']['digest'].replace(':', '-')
        if sha256(config_path.read_bytes()) != manifest['config']['digest'].split(':')[1]:
            raise ValueError('Installed config hash mismatch')
        installed = read_json(config_path)
        if model == 'gemma4:12b' and installed.get('renderer') != 'gemma4':
            raise ValueError('Unexpected Gemma renderer')
        lib = self.library
        required = ('llama_model_default_params', 'llama_model_load_from_file',
                    'llama_model_get_vocab', 'llama_tokenize', 'llama_model_free')
        if not all(hasattr(lib, name) for name in required):
            raise ValueError('Incompatible vocabulary-only API')
        params = lib.llama_model_default_params()
        params.vocab_only, params.n_gpu_layers, params.use_mmap = True, 0, True
        handle = lib.llama_model_load_from_file(str(path).encode(), params)
        if not handle:
            raise ValueError('Vocabulary load failed')
        self.models[model] = handle
        calibration = []
        for case in 'ABC':
            attempt = self.phase2 / (model.replace(':', '_') + '-' + case)
            req, raw = read_json(attempt / 'request.json'), read_json(attempt / 'response.json')
            observed = len(self._tokens(model, render(model, req['messages'], req['think'])))
            if observed != raw['prompt_eval_count']:
                raise ValueError('Renderer/tokenizer calibration mismatch; exact counts unavailable')
            calibration.append({'case': case, 'count': observed,
                                'request_sha256': sha256((attempt / 'request.json').read_bytes()),
                                'response_sha256': sha256((attempt / 'response.json').read_bytes())})
        native = Path(lib.llama_cpp._lib._name)
        binding = Path(lib.llama_cpp.__file__)
        implementation_hashes = {str(p): sha256(p.read_bytes()) for p in (native, binding)}
        self.identities[model] = {'implementation_sha256': implementation_hashes, 'version': VERSION, 'status': 'calibrated_cpu',
            'tokenizer': 'llama-cpp-python', 'tokenizer_version': lib.__version__,
            'binding_sha256': sha256(Path(lib.__file__).read_bytes()),
            'model_digest': data['digest'], 'metadata_sha256': digest(data),
            'rendering': 'pinned-0.32.15-two-message-text-profile; saved A/B/C calibrated',
            'calibration': calibration, 'cpu_only': True, 'vocab_only': True}

    def _tokens(self, model, text):
        import ctypes
        data = text.encode('utf-8')
        lib = self.library
        vocab = lib.llama_model_get_vocab(self.models[model])
        size = len(data) + 64
        output = (ctypes.c_int32 * size)()
        count = lib.llama_tokenize(vocab, data, len(data), output, size, True, True)
        if count < 0:
            raise ValueError('Tokenizer buffer insufficient')
        return list(output[:count])

    def measure(self, model, messages, think=False):
        if model not in self.identities:
            raise ValueError(self.reasons.get(model, LIMITATION))
        text = render(model, messages, think)
        ids = self._tokens(model, text)
        return {'identity': self.identities[model], 'rendered': text,
                'rendered_sha256': sha256(text.encode()), 'token_ids': ids, 'count': len(ids),
                'messages_sha256': digest(messages), 'think': think}

    def close_model(self, model):
        handle = self.models.pop(model, None)
        if handle is not None:
            self.library.llama_model_free(handle)

    def close(self):
        for model in list(self.models):
            self.close_model(model)


def installed_identity(model, snapshot):
    """Read-only manifest/config identity; no model tensor loading."""
    data = snapshot['models'][model]
    paths = re.findall(r'^FROM (/.+)$', data['show'].get('modelfile', ''), flags=re.MULTILINE)
    result = {'identity_source': 'saved-phase2-metadata', 'installed_manifest_verified': False,
              'rendering_method': 'Gemma4 built-in renderer/BOS profile' if model == 'gemma4:12b'
                                  else 'Qwen3 pinned two-message template profile'}
    if not paths:
        return result
    root = Path(paths[0]).parent.parent
    path = root / 'manifests/registry.ollama.ai/library' / model.replace(':', '/')
    try:
        result['installed_manifest_sha256'] = sha256(path.read_bytes())
        result['installed_manifest_verified'] = result['installed_manifest_sha256'] == data['digest']
        manifest = read_json(path)
        config_path = root / 'blobs' / manifest['config']['digest'].replace(':', '-')
        result['installed_config_sha256'] = sha256(config_path.read_bytes())
        result['installed_renderer'] = read_json(config_path).get('renderer', 'template/native; calibration required')
    except (OSError, ValueError, KeyError) as error:
        result['identity_limitation'] = str(error)
    return result


def census(config, snapshot, counter):
    rows = []
    for model in config['models']:
        for suite in DATASETS:
            for q in load_questions(suite):
                messages = [{'role': 'system', 'content': config['system_message']},
                            {'role': 'user', 'content': q['prompt']}]
                row = {'model': model, 'model_digest': snapshot['models'][model]['digest'],
                       'metadata_sha256': digest(snapshot['models'][model]), 'suite': suite,
                       'id': q['id'], 'prompt_sha256': q['prompt_sha256'],
                       'messages_sha256': digest(messages), 'think': False,
                       **installed_identity(model, snapshot)}
                try:
                    result = counter.measure(model, messages, False)
                    row.update(status='calibrated_cpu', count=result['count'],
                               rendered_sha256=result['rendered_sha256'], tokenizer=result['identity'])
                except (ValueError, OSError) as error:
                    row.update(status='unavailable', count=None, tokenizer_version=None,
                               rendering_method=None, limitation=str(error))
                rows.append(row)
    observed = {}
    for model in config['models']:
        observed[model] = {case: read_json(PHASE2 / (model.replace(':', '_') + '-' + case) / 'response.json')['prompt_eval_count']
                           for case in 'ABC'}
    return {'version': VERSION, 'saved_development_counts_not_dataset_counts': observed, 'config_sha256': digest(config), 'snapshot_sha256': digest(snapshot),
            'rows': rows, 'exact_counts_available': all(r['count'] is not None for r in rows),
            'no_inference': True, 'cpu_only': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE / 'configs/quality_v2.draft.json')
    parser.add_argument('--metadata', type=Path, default=PHASE2 / 'metadata.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    snapshot = read_json(args.metadata)
    counter = CpuCounter(snapshot)
    try:
        write_new(args.output, census(read_json(args.config), snapshot, counter))
    finally:
        counter.close()
    print(args.output)


if __name__ == '__main__':
    main()
