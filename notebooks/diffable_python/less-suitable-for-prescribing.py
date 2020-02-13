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

# +
# housekeeping

import os
from glob import glob
from itertools import count
import requests
from bs4 import BeautifulSoup
from ebmdatalab import bq
import pandas as pd

# +
# get mapping from AMP to BNF code

df = bq.cached_read("select id, bnf_code from dmd.amp", csv_path="../bq-cache/amps.csv")
amp_id_to_bnf_code = dict(df.itertuples(index=False))

# +
# scrape the data and store HTML in ../data/drugs and ../data/medicinal-forms

SCRAPE = False  # change to `SCRAPE = True` to re-scrape the data

if SCRAPE:
    os.makedirs("../data/drugs", exist_ok=True)
    os.makedirs("../data/medicinal-forms", exist_ok=True)

    for page in count(1):
        url = f"https://bnf.nice.org.uk/search?q=%22less%20suitable%20for%20prescribing%20drug%22&page={page}"
        rsp = requests.get(url)
        results = rsp.json()
        hits = results["hits"]["hits"]
        for hit in hits:
            drug = hit["_source"]["document"]["link"].split("/")[-1].split(".")[0]

            rsp = requests.get(f"http://bnf.nice.org.uk/drug/{drug}.html")
            with open(f"../data/drugs/{drug}.html", "w") as f:
                f.write(rsp.text)

            rsp = requests.get(f"https://bnf.nice.org.uk/medicinal-forms/{drug}.html")
            with open(f"../data/medicinal-forms/{drug}.html", "w") as f:
                f.write(rsp.text)

        if not hits:
            break

# +
# extract drug LSFP advice from drugs pages

rows = []

for path in glob("../data/drugs/*.html"):
    drug_name = path.split("/")[-1].split(".")[0]
    with open(path) as f1:
        doc = BeautifulSoup(f1.read(), "html.parser")

    section = doc.find(id="lessSuitableForPrescribings")
    rows.append([drug_name, "\n".join(p.text.strip() for p in section.find_all("p"))])

drugs_and_advice = pd.DataFrame(rows, columns=["drug", "lsfp_advice"])
# -

with pd.option_context("display.max_colwidth", -1):
    display(drugs_and_advice.head())

# +
# extract AMPs from medicinal-forms pages, and match against BNF codes

rows = []

for path in glob("../data/medicinal-forms/*.html"):
    drug_name = path.split("/")[-1].split(".")[0]
    with open(path) as f1:
        doc = BeautifulSoup(f1.read(), "html.parser")

    for div in doc.find_all("div", class_="medicinalProduct"):
        title_spans = div.find("h4", class_="productTitle").find_all("span")
        amp_descr = f"{title_spans[0].text.strip()} ({title_spans[1].text.strip()})"
        id = int(div.find("tbody").find("tr")["id"])
        bnf_code = amp_id_to_bnf_code.get(id)
        rows.append([drug_name, id, bnf_code, amp_descr])

medicinal_forms = pd.DataFrame(
    rows, columns=["drug", "amp_id", "bnf_code", "amp_descr"]
)
# -

with pd.option_context("display.max_colwidth", -1):
    display(medicinal_forms.head())

# +
# pull out distinct BNF codes for LSFP drugs

bnf_codes = sorted(set(medicinal_forms["bnf_code"].dropna()))
# -

len(bnf_codes)

# +
# do measure calculation for items prescribed per 1000 patients
#
# (see https://openprescribing.net/docs/querying-the-raw-data-yourself/)

joined_bnf_codes = ", ".join("'{}'".format(bnf_code) for bnf_code in bnf_codes)

sql = f"""
WITH practice_numerator AS (
    SELECT
        CAST(month AS DATE) AS month,
        practice_id,
        SUM(items) AS numerator
    FROM public_draft.prescribing
    WHERE bnf_code IN ({joined_bnf_codes})
    GROUP BY month, practice_id
),

practice_denominator AS (
    SELECT
        CAST(month AS DATE) AS month,
        practice_id,
        total / 1000.0 AS denominator
    FROM public_draft.list_size
),

month_practice AS (
    SELECT
        m.month,
        p.id AS practice_id
    FROM public_draft.practice AS p
    CROSS JOIN (
        SELECT DISTINCT month FROM practice_numerator
        UNION DISTINCT
        SELECT DISTINCT month FROM practice_denominator
        ORDER BY month
    ) AS m
    WHERE p.setting = 4
),

practice_combined AS (
    SELECT
        mp.month,
        mp.practice_id,
        COALESCE(n.numerator, 0) AS numerator,
        COALESCE(d.denominator, 0) AS denominator
    FROM month_practice AS mp
    LEFT JOIN practice_numerator AS n
        ON mp.month = n.month AND mp.practice_id = n.practice_id
    LEFT JOIN practice_denominator AS d
        ON mp.month = d.month AND mp.practice_id = d.practice_id
),

practice_combined_with_ratio AS (
    SELECT
        month,
        practice_id,
        numerator,
        denominator,
        CASE
            WHEN numerator = 0 AND denominator = 0 THEN 0
            WHEN denominator = 0 THEN NULL
            ELSE numerator / denominator
        END AS ratio
    FROM practice_combined
)

SELECT
    *,
    PERCENT_RANK() OVER (PARTITION BY month ORDER BY ratio) AS percentile
FROM practice_combined_with_ratio
ORDER BY month DESC, percentile DESC
"""

df = bq.cached_read(sql, csv_path="../bq-cache/prescribing.csv")
# -

df.head(20)


