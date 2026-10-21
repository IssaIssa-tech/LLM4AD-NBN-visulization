# Module Name: EoH
# Last Revision: 2025/2/16
# This file is part of the LLM4AD project (https://github.com/Optima-CityU/llm4ad).
#
# Reference:
#   - Fei Liu, Tong Xialiang, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu, and Qingfu Zhang.
#       "Evolution of Heuristics: Towards Efficient Automatic Algorithm Design Using Large Language Model."
#       In Forty-first International Conference on Machine Learning (ICML). 2024.
#
# ------------------------------- Copyright --------------------------------
# Copyright (c) 2025 Optima Group.
#
# Permission is granted to use the LLM4AD platform for research purposes.
# All publications, software, or other works that utilize this platform
# or any part of its codebase must acknowledge the use of "LLM4AD" and
# cite the following reference:
#
# Fei Liu, Rui Zhang, Zhuoliang Xie, Rui Sun, Kai Li, Xi Lin, Zhenkun Wang,
# Zhichao Lu, and Qingfu Zhang, "LLM4AD: A Platform for Algorithm Design
# with Large Language Model," arXiv preprint arXiv:2412.17287 (2024).
#
# For inquiries regarding commercial use or licensing, please contact
# http://www.llm4ad.com/contact.html
# --------------------------------------------------------------------------

from __future__ import annotations

import concurrent.futures
import math
import time
import traceback
from threading import Thread
from typing import Optional, Literal

from .population import Population
from .profiler import EoHProfiler
from .prompt import EoHPrompt
from .sampler import EoHSampler
from ...base import (
    Evaluation, LLM, Function, Program, TextFunctionProgramConverter, SecureEvaluator
)
from ...tools.profiler import ProfilerBase


class EoH:
    def __init__(self,
                 llm: LLM,
                 evaluation: Evaluation,
                 profiler: ProfilerBase = None,
                 max_generations: Optional[int] = 10,
                 max_sample_nums: Optional[int] = 100,
                 pop_size: Optional[int] = 5,
                 selection_num=2,
                 use_e2_operator: bool = True,
                 use_m1_operator: bool = True,
                 use_m2_operator: bool = True,
                 use_m3_operator: bool = False,
                 num_samplers: int = 1,
                 num_evaluators: int = 1,
                 operator_preference: str = "balanced",
                 operator_weights: dict = None,
                 *,
                 resume_mode: bool = False,
                 debug_mode: bool = False,
                 multi_thread_or_process_eval: Literal['thread', 'process'] = 'thread',
                 evaluation_executor=None,
                 **kwargs):
        """Evolutionary of Heuristics.
        Args:
            llm             : an instance of 'llm4ad.base.LLM', which provides the way to query LLM.
            evaluation      : an instance of 'llm4ad.base.Evaluator', which defines the way to calculate the score of a generated function.
            profiler        : an instance of 'llm4ad.method.eoh.EoHProfiler'. If you do not want to use it, you can pass a 'None'.
            max_generations : terminate after evolving 'max_generations' generations or reach 'max_sample_nums',
                              pass 'None' to disable this termination condition.
            max_sample_nums : terminate after evaluating max_sample_nums functions (no matter the function is valid or not) or reach 'max_generations',
                              pass 'None' to disable this termination condition.
            pop_size        : population size, if set to 'None', EoH will automatically adjust this parameter.
            selection_num   : number of selected individuals while crossover.
            use_e2_operator : if use e2 operator.
            use_m1_operator : if use m1 operator.
            use_m2_operator : if use m2 operator.
            resume_mode     : in resume_mode, randsample will not evaluate the template_program, and will skip the init process. TODO: More detailed usage.
            debug_mode      : if set to True, we will print detailed information.
            multi_thread_or_process_eval: use 'concurrent.futures.ThreadPoolExecutor' or 'concurrent.futures.ProcessPoolExecutor' for the usage of
                multi-core CPU while evaluation. Please note that both settings can leverage multi-core CPU. As a result on my personal computer (Mac OS, Intel chip),
                setting this parameter to 'process' will faster than 'thread'. However, I do not sure if this happens on all platform so I set the default to 'thread'.
                Please note that there is one case that cannot utilize multi-core CPU: if you set 'safe_evaluate' argument in 'evaluator' to 'False',
                and you set this argument to 'thread'.
            **kwargs                    : some args pass to 'llm4ad.base.SecureEvaluator'. Such as 'fork_proc'.
        """
        self._template_program_str = evaluation.template_program
        self._task_description_str = evaluation.task_description
        self._max_generations = max_generations
        self._max_sample_nums = max_sample_nums
        self._pop_size = pop_size
        self._selection_num = selection_num
        self._use_e2_operator = use_e2_operator
        self._use_m1_operator = use_m1_operator
        self._use_m2_operator = use_m2_operator
        self._use_m3_operator = use_m3_operator

        # samplers and evaluators
        self._num_samplers = num_samplers
        self._num_evaluators = num_evaluators
        self._operator_preference = operator_preference
        self._operator_weights = operator_weights or {}
        self._resume_mode = resume_mode
        self._debug_mode = debug_mode
        llm.debug_mode = debug_mode
        self._multi_thread_or_process_eval = multi_thread_or_process_eval

        # function to be evolved
        self._function_to_evolve: Function = TextFunctionProgramConverter.text_to_function(self._template_program_str)
        self._function_to_evolve_name: str = self._function_to_evolve.name
        self._template_program: Program = TextFunctionProgramConverter.text_to_program(self._template_program_str)

        # adjust population size
        self._adjust_pop_size()

        # population, sampler, and evaluator
        self._population = Population(pop_size=self._pop_size)
        self._sampler = EoHSampler(llm, self._template_program_str)
        self._evaluator = SecureEvaluator(evaluation, debug_mode=debug_mode, **kwargs)
        self._profiler = profiler

        # statistics
        self._tot_sample_nums = 0

        # reset _initial_sample_nums_max
        self._initial_sample_nums_max = min(
            self._max_sample_nums,
            2 * self._pop_size
        )

        # multi-thread executor for evaluation
        if evaluation_executor is not None:
            self._evaluation_executor = evaluation_executor
        else:
            assert multi_thread_or_process_eval in ['thread', 'process']
            if multi_thread_or_process_eval == 'thread':
                self._evaluation_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=num_evaluators
                )
            else:
                self._evaluation_executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=num_evaluators
                )

        # pass parameters to profiler
        if profiler is not None:
            self._profiler.record_parameters(llm, evaluation, self)  # ZL: necessary

    def _adjust_pop_size(self):
        # adjust population size
        if self._max_sample_nums >= 10000:
            if self._pop_size is None:
                self._pop_size = 40
            elif abs(self._pop_size - 40) > 20:
                print(f'Warning: population size {self._pop_size} '
                      f'is not suitable, please reset it to 40.')
        elif self._max_sample_nums >= 1000:
            if self._pop_size is None:
                self._pop_size = 20
            elif abs(self._pop_size - 20) > 10:
                print(f'Warning: population size {self._pop_size} '
                      f'is not suitable, please reset it to 20.')
        elif self._max_sample_nums >= 200:
            if self._pop_size is None:
                self._pop_size = 10
            elif abs(self._pop_size - 10) > 5:
                print(f'Warning: population size {self._pop_size} '
                      f'is not suitable, please reset it to 10.')
        else:
            if self._pop_size is None:
                self._pop_size = 5
            elif abs(self._pop_size - 5) > 5:
                print(f'Warning: population size {self._pop_size} '
                      f'is not suitable, please reset it to 5.')

    def _sample_evaluate_register(self, prompt, operator: str = "", parents: list = None):
        """Perform following steps:
        1. Sample an algorithm using the given prompt.
        2. Evaluate it by submitting to the process/thread pool, and get the results.
        3. Add the function to the population and register it to the profiler.
        """
        # NOTE: _tot_sample_nums is incremented *after* the LLM call succeeds.
        # If the LLM call raises (timeout, network error, API refusal, etc.) the
        # exception propagates to the caller (_iteratively_use_eoh_operator /
        # _iteratively_init_population) which catches it and retries.  Counting
        # those failed attempts here would silently burn the entire
        # max_sample_nums budget on API errors without producing a single
        # recorded sample, causing EoH to terminate far earlier than expected.
        sample_start = time.time()
        thought, func = self._sampler.get_thought_and_function(prompt)
        sample_time = time.time() - sample_start
        self._tot_sample_nums += 1
        if thought is None or func is None:
            self._register_failed_sample(
                sample_time=sample_time,
                reason="LLM response could not be parsed into a valid function.",
                operator=f"{operator}_parse_failed",
                parents=parents,
            )
            return
        # convert to Program instance
        program = TextFunctionProgramConverter.function_to_program(func, self._template_program)
        if program is None:
            self._register_failed_sample(
                sample_time=sample_time,
                reason="Generated function could not be converted into an executable program.",
                operator=f"{operator}_program_failed",
                parents=parents,
            )
            return
        # evaluate
        score, eval_time = self._evaluation_executor.submit(
            self._evaluator.evaluate_program_record_time,
            program
        ).result()
        # register to profiler
        func.score = score
        func.evaluate_time = eval_time
        func.algorithm = thought
        func.sample_time = sample_time
        func.operator = operator
        func.parents = parents or []
        if self._profiler is not None:
            self._profiler.register_function(func, program=str(program))
            if isinstance(self._profiler, EoHProfiler):
                self._profiler.register_population(self._population)

        # register to the population
        self._population.register_function(func)

    def _register_failed_sample(
            self,
            *,
            sample_time: float,
            reason: str,
            operator: str,
            parents: list = None,
    ) -> None:
        placeholder = Function(
            name=self._function_to_evolve.name,
            args=self._function_to_evolve.args,
            body=f'    raise RuntimeError("{reason}")',
            return_type=self._function_to_evolve.return_type,
            docstring=self._function_to_evolve.docstring,
        )
        placeholder.score = None
        placeholder.evaluate_time = 0.0
        placeholder.sample_time = sample_time
        placeholder.operator = operator
        placeholder.parents = parents or []
        placeholder.algorithm = f"{{{reason}}}"
        if self._profiler is not None:
            self._profiler.register_function(placeholder, program="")
            if isinstance(self._profiler, EoHProfiler):
                self._profiler.register_population(self._population)

    def register_seed_function(
            self,
            function: str | Function,
            *,
            algorithm: str = "{Fallback seed function.}",
            operator: str = "seed",
            sample_time: float | None = 0.0,
    ) -> bool:
        """Evaluate and register a deterministic seed function before normal sampling.

        A single feasible seed is enough for EoH to start iterating, because the
        selection step can repeatedly sample that individual when the population
        is still small.
        """
        self._tot_sample_nums += 1
        program = TextFunctionProgramConverter.function_to_program(function, self._template_program)
        if program is None:
            return False
        func = TextFunctionProgramConverter.text_to_function(str(program))
        if func is None:
            return False

        score, eval_time = self._evaluation_executor.submit(
            self._evaluator.evaluate_program_record_time,
            program
        ).result()
        func.score = score
        func.evaluate_time = eval_time
        func.algorithm = algorithm
        func.sample_time = sample_time
        func.operator = operator

        if self._profiler is not None:
            self._profiler.register_function(func, program=str(program))
            if isinstance(self._profiler, EoHProfiler):
                self._profiler.register_population(self._population)

        self._population.register_function(func)
        return func.score is not None and not math.isinf(func.score)

    def register_prescored_seed_function(
            self,
            function: str | Function,
            *,
            score: float,
            algorithm: str = "{Historical seed function reused without re-evaluation.}",
            operator: str = "seed",
            sample_time: float | None = 0.0,
            evaluate_time: float | None = 0.0,
    ) -> bool:
        """Register a deterministic historical seed using an existing trusted score.

        This avoids re-evaluating a selected historical candidate when the
        platform already has its score and only needs to bootstrap the
        population for the current run.
        """
        self._tot_sample_nums += 1
        if score is None or not math.isfinite(float(score)):
            return False
        program = TextFunctionProgramConverter.function_to_program(function, self._template_program)
        if program is None:
            return False
        func = TextFunctionProgramConverter.text_to_function(str(program))
        if func is None:
            return False

        func.score = float(score)
        func.evaluate_time = 0.0 if evaluate_time is None else float(evaluate_time)
        func.algorithm = algorithm
        func.sample_time = 0.0 if sample_time is None else float(sample_time)
        func.operator = operator

        if self._profiler is not None:
            self._profiler.register_function(func, program=str(program))
            if isinstance(self._profiler, EoHProfiler):
                self._profiler.register_population(self._population)

        self._population.register_function(func)
        return True

    def _continue_loop(self) -> bool:
        if self._max_generations is None and self._max_sample_nums is None:
            return True
        elif self._max_generations is not None and self._max_sample_nums is None:
            return self._population.generation < self._max_generations
        elif self._max_generations is None and self._max_sample_nums is not None:
            return self._tot_sample_nums < self._max_sample_nums
        else:
            return (self._population.generation < self._max_generations
                    and self._tot_sample_nums < self._max_sample_nums)

    def _iteratively_use_eoh_operator(self):
        import random
        consecutive_errors = 0
        max_consecutive_errors = max(20, self._max_sample_nums)
        while self._continue_loop():
            try:
                
                # Determine probabilities based on operator_weights if provided, else fallback to operator_preference
                if getattr(self, "_operator_weights", {}):
                    weights = self._operator_weights
                    w_e1 = float(weights.get("e1", 1.0))
                    w_e2 = float(weights.get("e2", 1.0)) if self._use_e2_operator else 0.0
                    w_m1 = float(weights.get("m1", 1.0)) if self._use_m1_operator else 0.0
                    w_m2 = float(weights.get("m2", 1.0)) if self._use_m2_operator else 0.0
                    w_m3 = float(weights.get("m3", 0.0)) if getattr(self, "_use_m3_operator", False) else 0.0
                    total_w = w_e1 + w_e2 + w_m1 + w_m2 + w_m3
                    if total_w <= 0:
                        op = "e1"
                    else:
                        r = random.uniform(0, total_w)
                        if r < w_e1:
                            op = "e1"
                        elif r < w_e1 + w_e2:
                            op = "e2"
                        elif r < w_e1 + w_e2 + w_m1:
                            op = "m1"
                        elif r < w_e1 + w_e2 + w_m1 + w_m2:
                            op = "m2"
                        else:
                            op = "m3"
                else:
                    pref = getattr(self, "_operator_preference", "balanced")
                    if pref == "crossover_heavy":
                        cross_prob = 0.8
                    elif pref == "mutation_heavy":
                        cross_prob = 0.2
                    elif pref == "crossover_only":
                        cross_prob = 1.0
                    elif pref == "mutation_only":
                        cross_prob = 0.0
                    else:
                        cross_prob = 0.5
                    
                    has_mutation = self._use_m1_operator or self._use_m2_operator
                    has_crossover = True  # e1 is always available
                    
                    if not has_mutation:
                        cross_prob = 1.0
                    if not has_crossover:
                        cross_prob = 0.0
                    
                    # Select operator type
                    if random.random() < cross_prob:
                        # Choose crossover
                        if self._use_e2_operator and random.random() < 0.5:
                            op = "e2"
                        else:
                            op = "e1"
                    else:
                        # Choose mutation
                        mut_ops = []
                        if self._use_m1_operator:
                            mut_ops.append("m1")
                        if self._use_m2_operator:
                            mut_ops.append("m2")
                        if mut_ops:
                            op = random.choice(mut_ops)
                        else:
                            op = "e1"  # fallback

                if op == "e1":
                    indivs = [self._population.selection() for _ in range(self._selection_num)]
                    prompt = EoHPrompt.get_prompt_e1(self._task_description_str, indivs, self._function_to_evolve)
                    if self._debug_mode:
                        print(f'E1 Prompt: {prompt}')
                    self._sample_evaluate_register(prompt, operator="e1", parents=[str(indiv) for indiv in indivs])
                    
                elif op == "e2":
                    indivs = [self._population.selection() for _ in range(self._selection_num)]
                    prompt = EoHPrompt.get_prompt_e2(self._task_description_str, indivs, self._function_to_evolve)
                    if self._debug_mode:
                        print(f'E2 Prompt: {prompt}')
                    self._sample_evaluate_register(prompt, operator="e2", parents=[str(indiv) for indiv in indivs])

                elif op == "m1":
                    indiv = self._population.selection()
                    prompt = EoHPrompt.get_prompt_m1(self._task_description_str, indiv, self._function_to_evolve)
                    if self._debug_mode:
                        print(f'M1 Prompt: {prompt}')
                    self._sample_evaluate_register(prompt, operator="m1", parents=[str(indiv)])

                elif op == "m2":
                    indiv = self._population.selection()
                    prompt = EoHPrompt.get_prompt_m2(self._task_description_str, indiv, self._function_to_evolve)
                    if self._debug_mode:
                        print(f'M2 Prompt: {prompt}')
                    self._sample_evaluate_register(prompt, operator="m2", parents=[str(indiv)])

                elif op == "m3":
                    indiv = self._population.selection()
                    prompt = EoHPrompt.get_prompt_m3(
                        self._task_description_str,
                        indiv,
                        self._function_to_evolve,
                        ref=getattr(self, "_vp_m3_ref", None),
                    )
                    if self._debug_mode:
                        print(f'M3 Prompt: {prompt}')
                    self._sample_evaluate_register(prompt, operator="m3", parents=[str(indiv)])

                # Any _sample_evaluate_register call above completed without raising,
                # so reset the consecutive-error counter.
                consecutive_errors = 0

            except KeyboardInterrupt:
                break
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print(
                        f'Terminating EoH search: {consecutive_errors} consecutive LLM/API errors '
                        f'(timeout, network, or parsing). Last error: {e}')
                    break
                if self._debug_mode:
                    traceback.print_exc()
                    exit()
                continue

        # shutdown evaluation_executor
        try:
            self._evaluation_executor.shutdown(cancel_futures=True)
        except:
            pass

    def _iteratively_init_population(self):
        """Let a thread repeat {sample -> evaluate -> register to population}
        to initialize a population.
        """
        consecutive_errors = 0
        max_consecutive_errors = max(20, self._initial_sample_nums_max)
        while self._population.generation == 0:
            try:
                # get a new func using i1
                prompt = EoHPrompt.get_prompt_i1(self._task_description_str, self._function_to_evolve)
                self._sample_evaluate_register(prompt, operator="i1", parents=[])
                consecutive_errors = 0
                if self._tot_sample_nums >= self._initial_sample_nums_max:
                    # print(f'Warning: Initialization not accomplished in {self._initial_sample_nums_max} samples !!!')
                    print(
                        f'Note: During initialization, EoH gets {len(self._population) + len(self._population._next_gen_pop)} algorithms '
                        f'after {self._initial_sample_nums_max} trails.')
                    break
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print(
                        f'Terminating initialization: {consecutive_errors} consecutive LLM/API errors.')
                    break
                if self._debug_mode:
                    traceback.print_exc()
                    exit()
                continue

    def _multi_threaded_sampling(self, fn: callable, *args, **kwargs):
        """Execute `fn` using multithreading.
        In EoH, `fn` can be `self._iteratively_init_population` or `self._iteratively_use_eoh_operator`.
        """
        # threads for sampling
        sampler_threads = [
            Thread(target=fn, args=args, kwargs=kwargs)
            for _ in range(self._num_samplers)
        ]
        for t in sampler_threads:
            t.start()
        for t in sampler_threads:
            t.join()

    def run(self):
        if not self._resume_mode:
            # do initialization
            self._multi_threaded_sampling(self._iteratively_init_population)
            self._population.survival()
            feasible_population = [
                func for func in self._population
                if func.score is not None and not math.isinf(func.score)
            ]
            # terminate searching if
            if not feasible_population:
                print(
                    f'The search is terminated since EoH unable to obtain any feasible algorithm during initialization. '
                    f'Please increase the `initial_sample_nums_max` argument (currently {self._initial_sample_nums_max}). '
                    f'Please also check your evaluation implementation and LLM implementation.')
                return

        # evolutionary search
        self._multi_threaded_sampling(self._iteratively_use_eoh_operator)

        # finish
        if self._profiler is not None:
            self._profiler.finish()

        self._sampler.llm.close()
