# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: all
#     notebook_metadata_filter: all,-language_info
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.3.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# First we must find all the products in the BNF that are denoted as "less suitable for prescribing". We will use the NICE commissioned BNF found at https://bnf.nice.org.uk/ This is available to anyone working in the NHS 
#
# We could manually search but that would take awhile as _less suitable for prescribing_ returns 82 results. First let us download relevant results for _"less suitable for prescribing drug"_ to isolate specific drugs as opposed to general information

from itertools import count
import requests
for page in count(1):
    url = "https://bnf.nice.org.uk/search?q=%22less%20suitable%20for%20prescribing%20drug%22&page=" + str(page)
    rsp = requests.get(url)
    results = rsp.json()
    hits = results["hits"]["hits"]
    for hit in hits:
        print(hit["_source"])
    if not hits:
        break

import pandas as pd
import json
pd.json_normalize(hit)

df= pd.json_normalize(hit)
df

df2= pd.json_normalize(hits)
df2

df3 = pd.json_normalize(hit["_source"])
df3


