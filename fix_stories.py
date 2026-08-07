import yaml

with open('backlog/stories.yaml', 'r') as f:
    data = yaml.safe_load(f)

for s in data['stories']:
    if s['id'].startswith('S0-'):
        s['status'] = 'done'

with open('backlog/stories.yaml', 'w') as f:
    yaml.dump(data, f, sort_keys=False)
