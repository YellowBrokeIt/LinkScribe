"""One retained no-model guard counterexample; original candidate stays unchanged."""
import ast
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'initial-protection.py'
data=SOURCE.read_bytes()
assert hashlib.sha256(data).hexdigest()=='62db501bd49fe55f31e55c029cedf0c8ea1a158461086653e0e3e231071c2c97'
tree=ast.parse(data)
names={'canonical','digest','reserved_present','restore_segments'}
selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
scope={'json':json,'hashlib':hashlib,'unicodedata':unicodedata,'copy':copy,'Counter':Counter,'PATTERN':re.compile(r'<x(?:0|[1-9][0-9]{0,3})/>')}
exec(compile(selected,str(SOURCE),'exec'),scope)
original=[{'start':0.0,'end':2.0,'text':'Dana arrived.'}]
masked=[{'start':0.0,'end':2.0,'text':'<x0/> arrived.'}]
markers=[{'marker':'<x0/>','segment_index':0,'start':0,'end':4,'source_text':'Dana'}]
bundle={'source_segments':original,'source_segments_sha256':scope['digest'](original),'masked_segments':masked,'markers':markers}
bundle['protection_binding_sha256']=scope['digest']({'source_segments_sha256':bundle['source_segments_sha256'],'masked_segments':masked,'markers':markers})
candidate=[{'start':0.0,'end':2.0,'text':'Η <x0/> έφτασε. </x0>'}]
restored,audit=scope['restore_segments'](bundle,candidate)
assert restored[0]['text']=='Η Dana έφτασε. </x0>'
assert scope['reserved_present']('</x0>') is False
record={'schema_version':1,'observed_at':datetime.now(timezone.utc).isoformat(),'candidate_protection_sha256':hashlib.sha256(data).hexdigest(),'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Exact four pure guard functions compiled from frozen candidate; independent synthetic source and plausible translated prose. No source normalizer, model, native runtime, full wrapper or post-restoration production guard invoked.','source':original,'candidate_response':candidate,'restoration_guard_accepted':True,'restored_result':restored,'source_closing_namespace_detected':False,'finding':'A valid expected self-closing marker plus an extra closing tag passes exact-marker counting, and the closing namespace escapes residual/source collision detection.','recommended_narrow_correction':'Treat closing x-tag namespace forms as reserved in source and in post-marker residue; reject instead of repairing. Preserve the initial candidate and add the exact source/output controls.','new_model_calls':0}
p=HERE/'initial-residual-closing-tag-probe.json'
with p.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'restoration_guard_accepted':True}))
