# Bounded-program feedback repair case study

Prior-work review: M2-R changed a structural prompt package and returned 0/5 valid (four invalid geometry, one unpacking exception). Code-checked M2 allowed one error-informed repair after an eight-second precheck; all five repaired candidates failed before full evaluation. Those results remain negative evidence and are not repeated here.

The new case study repairs exactly two newly generated 100-round bounded programs. Each receives its complete failed source and exact evaluation/source-inspection feedback; the historical parent/node and original call ID remain linked in the manifest. The feedback is researcher-assisted, not autonomous diagnosis. One repair request per source, no retries, manual patches or replacement candidates. Model/settings and twenty-second evaluator remain fixed. No initial candidate is regenerated or reevaluated.

Report pre/post status, actual geometry, score and work-limit compliance. Review code diffs for unrequested changes. A successful repair measures delivery/feasibility only and is not a demonstrated improvement over a valid incumbent. These two selected failures cannot estimate population repair success or compare NBN regions. Preserve both failures even if repairs succeed; invalid outcomes get no invented score. Registration precedes all calls. No official-verifier equivalence is claimed.
