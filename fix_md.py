import glob
import re

files = glob.glob("backlog/mvp/*.md")

for fp in files:
    with open(fp, "r") as f:
        content = f.read()

    # 1. Clean up broken descriptions:
    # Pattern: \n### Description\n(.*?)\n\*\*so that\*\*
    # We want to put "**so that**" back with its line.
    # Actually it's easier to just strip them out if we can match them.
    # But wait! I can just checkout the files from the commit before `b052224`!
    pass
