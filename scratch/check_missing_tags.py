import re

with open('frontend/src/pages/client/UniversalWorkflowRunner.jsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Find all JSX tags <PascalCase ...>
jsx_tags = set(re.findall(r'<([A-Z][a-zA-Z0-9]+)', code))

# Find imports from lucide-react
lucide_match = re.search(r'import \{([^}]+)\} from [\'"]lucide-react[\'"]', code)
lucide_imports = set(re.findall(r'([A-Za-z0-9]+)', lucide_match.group(1))) if lucide_match else set()

# Find all other imports
other_imports = set(re.findall(r'import\s+([A-Za-z0-9]+)', code))
named_other_imports = set(re.findall(r'import\s+\{([^}]+)\}', code))
for block in named_other_imports:
    for item in re.findall(r'([A-Za-z0-9]+)', block):
        other_imports.add(item)

# Find component definitions
defined_components = set(re.findall(r'function ([A-Z][a-zA-Z0-9]+)', code))
defined_consts = set(re.findall(r'const ([A-Z][a-zA-Z0-9]+)\s*=', code))

all_known = lucide_imports | other_imports | defined_components | defined_consts | {'React', 'Fragment'}

for tag in sorted(list(jsx_tags)):
    if tag not in all_known:
        print(f'MISSING TAG: {tag}')
print('Done scanning JSX tags!')
