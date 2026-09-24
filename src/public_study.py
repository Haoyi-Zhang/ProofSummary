"""Check the six retained public-source finite summary quotients."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from frontier_checker import check
from frontier_oracle import enumerate_frontier
from frontier_producer import produce
from public_cases import public_cases


def run(out: Path) -> dict:
    if out.exists(): raise ValueError("output directory must not exist")
    for d in ("inputs", "certificates", "details"): (out/d).mkdir(parents=True, exist_ok=False)
    fields=["id","source","expected_safe","status","cost","frontier","oracle_status","agreement"]
    rows=[]
    with (out/"raw.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for p,source,expected_safe in public_cases():
            cert,stats=produce(p); checked=check(p,cert); oracle=enumerate_frontier(p)
            observed_safe=checked["status"]=="safe_bounded"
            agreement=(observed_safe==expected_safe and checked["status"]==oracle["status"] and checked["initial_frontier"]==oracle["frontier"])
            row={"id":p["id"],"source":source,"expected_safe":str(expected_safe).lower(),"status":checked["status"],
                 "cost":"" if checked["upper"] is None else checked["upper"],"frontier":json.dumps(checked["initial_frontier"],separators=(",",":")),
                 "oracle_status":oracle["status"],"agreement":"yes" if agreement else "NO"}
            rows.append(row); w.writerow(row)
            (out/"inputs"/(p["id"]+".json")).write_text(json.dumps(p,sort_keys=True)+"\n")
            (out/"certificates"/(p["id"]+".json")).write_text(json.dumps(cert,separators=(",",":"))+"\n")
            (out/"details"/(p["id"]+".json")).write_text(json.dumps({"checker":checked,"oracle":oracle,"producer_statistics":stats,"source":source,"expected_safe":expected_safe},sort_keys=True)+"\n")
    summary={"cases":len(rows),"agreement":sum(r["agreement"]=="yes" for r in rows),"safe":sum(r["status"]=="safe_bounded" for r in rows),"unsafe":sum(r["status"]=="optimal_bounded" for r in rows)}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    return summary

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    try: s=run(a.out)
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({"status":"failed","reason":str(e)})); return 1
    print(json.dumps(s,sort_keys=True)); return 0 if s["agreement"]==s["cases"] else 1
if __name__=="__main__": raise SystemExit(main())
