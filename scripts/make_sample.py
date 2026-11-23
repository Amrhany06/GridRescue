"""Deterministic contiguous development slice, not a representative random sample.

Read the first 100,000 actual observations per development year. The boundary
truncates time coverage; label incompleteness includes this extraction artifact.
Never reads 2022. Originals are not moved or modified.
"""
import csv
import json
from itertools import islice
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'data/sample'
    out.mkdir(parents=True,exist_ok=True)
    log=[]
    for year in range(2018,2022):
        name=f'eaglei_outages_{year}.csv'
        source=ROOT/'data/raw'/name
        if not source.exists():
            source=ROOT/name
        target=out/name
        with source.open(newline='',encoding='utf-8-sig') as src,target.open('w',newline='',encoding='utf-8') as dst:
            reader=csv.reader(src); writer=csv.writer(dst)
            writer.writerow(next(reader)); n=0
            for row in islice(reader,100000):
                writer.writerow(row); n+=1
        log.append({'year':year,'source':str(source.relative_to(ROOT)),'sample':str(target.relative_to(ROOT)),'rows':n,'method':'first 100000 source observations; contiguous prefix; not population representative'})
    (ROOT/'reports/sample_manifest.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
    print(json.dumps(log,indent=2))


if __name__=='__main__':
    main()
