import os, re
for root, dirs, files in os.walk('backlog'):
    for file in files:
        if file.endswith('.md') and file != 'README.md' and file != 'COVERAGE_AUDIT.md' and file != '00_phase0_data_foundation.md' and file != '01_slice_1a_foundation.md':
            with open(os.path.join(root, file)) as f:
                content = f.read()
            parts = re.split(r'^(#+\s+(?:⏳ \[TODO\]|🟢 \[DONE\])?\s*S\d+.*?)$', content, flags=re.MULTILINE)
            for i in range(1, len(parts), 2):
                header = parts[i].strip()
                body = parts[i+1]
                if '**As a**' not in body:
                    print(f"{file} | {header}")
