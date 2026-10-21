"""ctypes adapter for the OFEC portable C ABI; process-local persistent networks."""
from __future__ import annotations
import atexit
import ctypes as ct
import hashlib
import os
import threading
from collections import OrderedDict
from pathlib import Path
import numpy as np

_LOCK = threading.RLock()
_NETWORKS = OrderedDict()
_LIB = None

def library_path():
    configured = os.getenv("OFEC_NBN_PORTABLE_LIBRARY", "").strip()
    if configured:
        return Path(configured)
    root = Path(__file__).resolve().parents[2] / "ofec"
    name = "nbn_portable.dll" if os.name == "nt" else "libnbn_portable.so"
    return root / "utility/hnsw/hnsw_general/portable" / name

def library():
    global _LIB
    with _LOCK:
        if _LIB is None:
            lib = ct.CDLL(str(library_path()))
            h, i, d = ct.c_uint64, ct.c_int, ct.c_double
            ip, dp = ct.POINTER(i), ct.POINTER(d)
            signatures = {
                "nbn_create": [i,i,i,d,ct.POINTER(h)],
                "nbn_destroy": [h], "nbn_size": [h,ip],
                "nbn_add": [h,dp,dp,i,ip],
                "nbn_add_ids": [h,dp,dp,i,ip],
                "nbn_update": [h,ip,dp,dp,i],
                "nbn_set_fitness": [h,dp,i],
                "nbn_get": [h,ip,dp,i],
            }
            for name, args in signatures.items():
                getattr(lib,name).argtypes=args
                getattr(lib,name).restype=i
            lib.nbn_last_error.argtypes=[]
            lib.nbn_last_error.restype=ct.c_char_p
            _LIB=lib
        return _LIB

def check(code):
    if code != 0:
        raise RuntimeError(library().nbn_last_error().decode("utf-8",errors="replace"))

def ptr(array):
    return array.ctypes.data_as(ct.POINTER(ct.c_double))

def clear_networks():
    with _LOCK:
        if _LIB is not None:
            for state in _NETWORKS.values():
                _LIB.nbn_destroy(state["handle"])
        _NETWORKS.clear()

atexit.register(clear_networks)

def compute(key, embeddings, fitness):
    """Deduplicate native nodes; preserve one displayed row per source sample."""
    x=np.ascontiguousarray(embeddings,dtype=np.float64)
    f=np.ascontiguousarray(fitness,dtype=np.float64)
    if x.ndim != 2 or f.shape != (x.shape[0],) or not x.shape[1]:
        raise ValueError("invalid encoding/fitness shape")
    if not np.isfinite(x).all() or not np.isfinite(f).all():
        raise ValueError("encoding and fitness must be finite")
    if len(x) and np.any(np.max(np.abs(x),axis=1)==0):
        raise ValueError("zero encoding has undefined cosine distance")
    method=os.getenv("OFEC_NBN_METHOD","static").strip().lower()
    if method not in ("static","hierarchy"):
        raise ValueError("OFEC_NBN_METHOD must be static or hierarchy")
    threads=int(os.getenv("OFEC_NBN_THREADS","4"))
    seed=float(os.getenv("OFEC_NBN_SEED","0.5"))
    cache_key=(str(Path(key).resolve()),method,threads,seed,x.shape[1])
    hashes=[hashlib.sha256(row.tobytes()).digest() for row in x]
    with _LOCK:
        lib=library()
        state=_NETWORKS.get(cache_key)
        rebuilt=False
        changed_count=sum(a!=b for a,b in zip(hashes,state["hashes"])) if state else 0
        # An edited/removed row can split or merge an alias group. Rebuild from
        # sample order rather than mutate a shared node on behalf of one alias.
        if state and (len(x)<len(state["hashes"]) or hashes[:len(state["hashes"])]!=state["hashes"]):
            check(lib.nbn_destroy(state["handle"]))
            del _NETWORKS[cache_key]; state=None; rebuilt=True
        reused=state is not None
        old_count=len(state["hashes"]) if state else 0
        if state is None:
            handle=ct.c_uint64()
            check(lib.nbn_create(0 if method=="static" else 1,x.shape[1],threads,seed,ct.byref(handle)))
            state={"handle":handle,"hashes":[],"sample_ids":np.empty(0,dtype=np.int32),
                   "unique_fitness":np.empty(0)}
            _NETWORKS[cache_key]=state
        old_unique=len(state["unique_fitness"])
        try:
            sample_ids=state["sample_ids"].copy()
            if len(x)>old_count:
                xx=np.ascontiguousarray(x[old_count:])
                ff=np.ascontiguousarray(f[old_count:])
                ids=np.empty(len(xx),dtype=np.int32)
                check(lib.nbn_add_ids(state["handle"],ptr(xx),ptr(ff),len(xx),
                                     ids.ctypes.data_as(ct.POINTER(ct.c_int))))
                sample_ids=np.concatenate((sample_ids,ids))
            count=ct.c_int()
            check(lib.nbn_size(state["handle"],ct.byref(count)))
            unique_count=count.value
            first=np.full(unique_count,len(x),dtype=np.int32)
            if len(x): np.minimum.at(first,sample_ids,np.arange(len(x),dtype=np.int32))
            if np.any(first==len(x)): raise RuntimeError("unmapped native NBN node")
            unique_fitness=np.ascontiguousarray(f[first])
            # Only the first sample owning an encoding controls its native
            # fitness. An appended duplicate never silently overwrites it.
            if old_unique and not np.array_equal(unique_fitness[:old_unique],state["unique_fitness"]):
                check(lib.nbn_set_fitness(state["handle"],ptr(unique_fitness),unique_count))
            up=np.empty(unique_count,dtype=np.int32)
            ud=np.empty(unique_count,dtype=np.float64)
            check(lib.nbn_get(state["handle"],up.ctypes.data_as(ct.POINTER(ct.c_int)),ptr(ud),unique_count))
            # Translate native IDs into displayed sample indices. Duplicate
            # roots stay self roots; no synthetic duplicate edges are invented.
            native_parent=up[sample_ids]
            p=np.arange(len(x),dtype=np.int32)
            d=np.zeros(len(x),dtype=np.float64)
            linked=native_parent>=0
            p[linked]=first[native_parent[linked]]
            d[linked]=ud[sample_ids[linked]]
            state["hashes"]=hashes
            state["sample_ids"]=sample_ids
            state["unique_fitness"]=unique_fitness.copy()
        except BaseException:
            lib.nbn_destroy(state["handle"])
            del _NETWORKS[cache_key]
            raise
        _NETWORKS.move_to_end(cache_key)
        while len(_NETWORKS)>8:
            _,evicted=_NETWORKS.popitem(last=False)
            check(lib.nbn_destroy(evicted["handle"]))
        return p,d,{"nbnMode":"hnsw_"+method,"nbnBackend":"libnbn_portable",
            "nbnLibrary":str(library_path()),"nbnHandleReused":reused,
            "nbnAppendedCount":unique_count-old_unique,
            "nbnUpdatedCount":changed_count,
            "nbnRebuilt":rebuilt,"nbnThreads":threads,
            "nbnDeduplicated":True,"nbnUniqueNodeCount":unique_count,
            "nbnDuplicateSampleCount":len(x)-unique_count,
            "_sampleNodeIds":sample_ids.tolist(),
            "_representativeIndices":first[sample_ids].tolist(),
            "_effectiveFitness":unique_fitness[sample_ids].tolist()}

