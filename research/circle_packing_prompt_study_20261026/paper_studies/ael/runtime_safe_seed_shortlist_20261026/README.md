# Runtime-safe AEL seed shortlist

**Subsequent diagnostic, 2026-10-31:** All thirty listed sources have now been checked under a registered 20-second condition: 22 valid positive-score outputs and 8 timeouts. See the [complete parent-eligibility results](../../../ael_parent_eligibility_20261031/AEL_PARENT_ELIGIBILITY_RESULTS.md). Current graph identities were explicitly reconciled with the frozen HNSW graph. The text below records the original static-selection stage; it is not a claim that all thirty passed runtime evaluation.

This is a static-screened shortlist from historical Circle Packing code. It is not a runtime result. Every listed program must still pass the current 20-second isolated evaluator before becoming an AEL parent.

- Historical records scanned: 14,000
- Static-filter eligible records: 355
- Shortlisted unique programs: 30

| Rank | Sample | Historical score | NBN branch | Loops | Max nesting | Largest literal range | Code file |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 9180 | 2.533806569785 | 13793 | 3 | 2 | 0 | `candidate_code/shortlist_01_sample_09180.py` |
| 2 | 7918 | 2.393526620287 | 9707 | 4 | 2 | 100 | `candidate_code/shortlist_02_sample_07918.py` |
| 3 | 3221 | 2.145813181925 | 12991 | 7 | 2 | 20 | `candidate_code/shortlist_03_sample_03221.py` |
| 4 | 11156 | 2.373092227528 | 13793 | 4 | 2 | 0 | `candidate_code/shortlist_04_sample_11156.py` |
| 5 | 13793 | 2.341167275807 | 9707 | 6 | 2 | 0 | `candidate_code/shortlist_05_sample_13793.py` |
| 6 | 11877 | 2.302135525781 | 13793 | 6 | 2 | 0 | `candidate_code/shortlist_06_sample_11877.py` |
| 7 | 11307 | 2.291184725760 | 13793 | 7 | 2 | 0 | `candidate_code/shortlist_07_sample_11307.py` |
| 8 | 3904 | 2.272533126025 | 13793 | 8 | 2 | 50 | `candidate_code/shortlist_08_sample_03904.py` |
| 9 | 11062 | 2.264217946579 | 13793 | 2 | 1 | 0 | `candidate_code/shortlist_09_sample_11062.py` |
| 10 | 9227 | 2.259051616562 | 13793 | 5 | 2 | 0 | `candidate_code/shortlist_10_sample_09227.py` |
| 11 | 6613 | 2.230961723746 | 13793 | 4 | 2 | 0 | `candidate_code/shortlist_11_sample_06613.py` |
| 12 | 2581 | 2.196828643810 | 13793 | 3 | 2 | 150 | `candidate_code/shortlist_12_sample_02581.py` |
| 13 | 12796 | 2.192313854844 | 13793 | 4 | 2 | 0 | `candidate_code/shortlist_13_sample_12796.py` |
| 14 | 12849 | 2.139297480167 | 13793 | 8 | 2 | 100 | `candidate_code/shortlist_14_sample_12849.py` |
| 15 | 12852 | 2.109107549241 | 13793 | 6 | 2 | 0 | `candidate_code/shortlist_15_sample_12852.py` |
| 16 | 7510 | 1.972145151721 | 9707 | 6 | 2 | 100 | `candidate_code/shortlist_16_sample_07510.py` |
| 17 | 1300 | 1.920019738041 | 13793 | 3 | 2 | 50 | `candidate_code/shortlist_17_sample_01300.py` |
| 18 | 2058 | 1.899140148187 | 13793 | 4 | 2 | 0 | `candidate_code/shortlist_18_sample_02058.py` |
| 19 | 2226 | 1.883842147957 | 12991 | 5 | 2 | 0 | `candidate_code/shortlist_19_sample_02226.py` |
| 20 | 12801 | 1.882583245573 | 13793 | 4 | 2 | 0 | `candidate_code/shortlist_20_sample_12801.py` |
| 21 | 1042 | 1.874027597792 | 13793 | 3 | 2 | 0 | `candidate_code/shortlist_21_sample_01042.py` |
| 22 | 3445 | 1.860415364520 | 13793 | 2 | 2 | 100 | `candidate_code/shortlist_22_sample_03445.py` |
| 23 | 1755 | 1.848034448764 | 13793 | 5 | 2 | 10 | `candidate_code/shortlist_23_sample_01755.py` |
| 24 | 860 | 1.837936441396 | 13793 | 2 | 2 | 0 | `candidate_code/shortlist_24_sample_00860.py` |
| 25 | 7692 | 1.836158318113 | 13793 | 4 | 2 | 0 | `candidate_code/shortlist_25_sample_07692.py` |
| 26 | 679 | 1.830491642113 | 13793 | 2 | 2 | 0 | `candidate_code/shortlist_26_sample_00679.py` |
| 27 | 929 | 1.830491642113 | 13793 | 2 | 2 | 0 | `candidate_code/shortlist_27_sample_00929.py` |
| 28 | 947 | 1.830491642113 | 13793 | 2 | 2 | 0 | `candidate_code/shortlist_28_sample_00947.py` |
| 29 | 1258 | 1.830491642113 | 13793 | 2 | 2 | 0 | `candidate_code/shortlist_29_sample_01258.py` |
| 30 | 1368 | 1.826902161546 | 13793 | 3 | 2 | 0 | `candidate_code/shortlist_30_sample_01368.py` |

Static rejections by reason: `{"contains_while": 380, "disallowed_import": 133, "forbidden_name": 3, "literal_range_gt_500": 10, "loop_nesting_gt_2": 6973}`.
