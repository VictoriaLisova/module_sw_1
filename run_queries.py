import requests
import csv
import json
from datetime import datetime, timezone


URL = "https://query.wikidata.org/sparql"

HEADERS = {"User-Agent": "mkr1/1.0"}


def run_query(query_file, output_file):
    with open(query_file, "r", encoding="utf-8") as f:
        query = f.read()

    response = requests.get(URL, params={"query": query, "format": "json"}, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    variables = data["head"]["vars"]
    rows = data["results"]["bindings"]

    with open(output_file,"w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=variables)
        writer.writeheader()
        for row in rows:
            writer.writerow({variable: row.get(variable, {}).get("value", "") for variable in variables})


def main():
    run_query("q1.rq", "q1.csv")
    run_query("q2.rq", "q2.csv")
    run_query("q3.rq", "q3.csv")

    meta = {"retrieved_at": datetime.now(timezone.utc).isoformat()}
    with open("meta.json","w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()