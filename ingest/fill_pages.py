"""Write the page numbers found by pages.py into the chunk shards.

    WORK_NAME=work_v2 uv run --package rag-ingest python ingest/fill_pages.py data/eurlex/pages.json

Run before the load stage, so the database gets the pages with the chunks.
Each shard file is rewritten under a temporary name and renamed when complete.
"""

import gzip
import json
import sys
from pathlib import Path

import work


def main() -> None:
    pages = json.loads(Path(sys.argv[1]).read_text())
    placed = 0
    total = 0
    for shard in work.shards():
        path = work.chunks_path(shard)
        tmp = path.with_suffix(".tmp")
        with gzip.open(path, "rt", encoding="utf-8") as src, gzip.open(tmp, "wt", encoding="utf-8") as dst:
            for line in src:
                chunk = json.loads(line)
                found = pages.get(chunk["doc_id"], [])
                if chunk["index"] < len(found) and found[chunk["index"]][0] > 0:
                    chunk["page_start"], chunk["page_end"] = found[chunk["index"]]
                    placed += 1
                total += 1
                dst.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        tmp.rename(path)
    print(f"{placed:,} of {total:,} chunks have a page ({placed / total:.1%})")


if __name__ == "__main__":
    main()
