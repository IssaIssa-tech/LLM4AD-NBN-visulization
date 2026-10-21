from __future__ import annotations

import copy
from typing import List, Dict

from ...base import *


class EoHPrompt:
    @classmethod
    def create_instruct_prompt(cls, prompt: str) -> List[Dict]:
        content = [
            {'role': 'system', 'message': cls.get_system_prompt()},
            {'role': 'user', 'message': prompt}
        ]
        return content

    @classmethod
    def get_system_prompt(cls) -> str:
        return ''

    @classmethod
    def get_prompt_i1(cls, task_prompt: str, template_function: Function):
        # template
        temp_func = copy.deepcopy(template_function)
        temp_func.body = ''
        # create prompt content
        prompt_content = f'''{task_prompt}
1. First, describe your new algorithm and main steps in one sentence. The description must be inside within boxed {{}}. 
2. Next, implement the following Python function:
{str(temp_func)}
Do not give additional explanations.'''
        return prompt_content

    @classmethod
    def get_prompt_e1(cls, task_prompt: str, indivs: List[Function], template_function: Function):
        for indi in indivs:
            assert hasattr(indi, 'algorithm')
        # template
        temp_func = copy.deepcopy(template_function)
        temp_func.body = ''
        # create prompt content for all individuals
        indivs_prompt = ''
        for i, indi in enumerate(indivs):
            indivs_prompt += f'No. {i + 1} algorithm and the corresponding code are:\n{indi.algorithm}\n{indi.to_code_without_docstring()}'
        # create prmpt content
        prompt_content = f'''{task_prompt}
I have {len(indivs)} existing algorithms with their codes as follows:
{indivs_prompt}
Please help me create a new algorithm that has a totally different form from the given ones. 
1. First, describe your new algorithm and main steps in one sentence. The description must be inside within boxed {{}}.
2. Next, implement the following Python function:
{str(temp_func)}
Do not give additional explanations.'''
        return prompt_content

    @classmethod
    def get_prompt_e2(cls, task_prompt: str, indivs: List[Function], template_function: Function):
        for indi in indivs:
            assert hasattr(indi, 'algorithm')

        # template
        temp_func = copy.deepcopy(template_function)
        temp_func.body = ''
        # create prompt content for all individuals
        indivs_prompt = ''
        for i, indi in enumerate(indivs):
            indivs_prompt += f'No. {i + 1} algorithm and the corresponding code are:\n{indi.algorithm}\n{indi.to_code_without_docstring()}'
        # create prmpt content
        prompt_content = f'''{task_prompt}
I have {len(indivs)} existing algorithms with their codes as follows:
{indivs_prompt}
Please help me create a new algorithm that has a totally different form from the given ones but can be motivated from them.
1. Firstly, identify the common backbone idea in the provided algorithms. 
2. Secondly, based on the backbone idea describe your new algorithm in one sentence. The description must be inside within boxed {{}}.
3. Thirdly, implement the following Python function:
{str(temp_func)}
Do not give additional explanations.'''
        return prompt_content

    @classmethod
    def get_prompt_m1(cls, task_prompt: str, indi: Function, template_function: Function):
        assert hasattr(indi, 'algorithm')
        # template
        temp_func = copy.deepcopy(template_function)
        temp_func.body = ''

        # create prmpt content
        prompt_content = f'''{task_prompt}
I have one algorithm with its code as follows. Algorithm description:
{indi.algorithm}
Code:
{indi.to_code_without_docstring()}
Please assist me in creating a new algorithm that has a different form but can be a modified version of the algorithm provided.
1. First, describe your new algorithm and main steps in one sentence. The description must be inside within boxed {{}}.
2. Next, implement the following Python function:
{str(temp_func)}
Do not give additional explanations.'''
        return prompt_content

    @classmethod
    def get_prompt_m2(cls, task_prompt: str, indi: Function, template_function: Function):
        assert hasattr(indi, 'algorithm')
        # template
        temp_func = copy.deepcopy(template_function)
        temp_func.body = ''
        # create prmpt content
        prompt_content = f'''{task_prompt}
I have one algorithm with its code as follows. Algorithm description:
{indi.algorithm}
Code:
{indi.to_code_without_docstring()}
Please identify the main algorithm parameters and assist me in creating a new algorithm that has a different parameter settings of the score function provided.
1. First, describe your new algorithm and main steps in one sentence. The description must be inside within boxed {{}}.
2. Next, implement the following Python function:
{str(temp_func)}
Do not give additional explanations.'''
        return prompt_content

    @classmethod
    def get_prompt_m3(
        cls,
        task_prompt: str,
        indi: Function,
        template_function: Function,
        ref: dict | None = None,
    ):
        """局部改进算子 m3（链爬行）。

        ref = 锚点的最近更高分解（父节点），可选。参考框架由环境变量 CLIMB_M3_MODE 选择：
          - 'target'（v3 原文，链爬行实验记录.md §2.3）：分数=目标、代码=目标参考
            （"链的下一站"，可朝它靠近），要求"语义上比参考更靠近基准"；
          - 'negative'（v5，默认）：分数=目标标杆（要超过）、代码=【反面例子】
            （不同思路，不要模仿，在基准思路内打赢它）；
          - 'none'（v4 风格）：不给 ref 代码/分数，纯局部改进（目标分=基准分）。
        默认 negative = v5 语义（运行中进程不受文件改动影响；新进程无 env 时行为不变）。
        """
        import os

        mode = os.environ.get("CLIMB_M3_MODE", "negative")
        assert hasattr(indi, "algorithm")
        temp_func = copy.deepcopy(template_function)
        temp_func.body = ""
        base_score = getattr(indi, "score", None)
        base_score_txt = (
            f"{base_score:.6f}" if isinstance(base_score, (int, float)) else "unknown"
        )
        has_ref = bool(ref and str(ref.get("code", "") or "").strip())
        if has_ref:
            parent_code = str(ref.get("code", "") or "").strip()
            parent_score = float(ref.get("score", 0.0))
        if has_ref and mode == "target":
            target_txt = f"score at least {parent_score:.6f}"
            ref_block = (
                "The nearest improved solution (the closest KNOWN solution that "
                "scores higher than the baseline; it is the next step of the "
                "improvement chain) has score "
                f"{parent_score:.6f} and is semantically very close to the baseline. "
                "Its implementation is:\n"
                f"{parent_code}\n\n"
                "Use it as the TARGET to approach: your improved baseline should "
                "stay semantically closer to the baseline than this reference is "
                "(i.e. stay between the baseline and the reference), while "
                "reaching its score.\n"
            )
        elif has_ref and mode == "negative":
            target_txt = f"score strictly higher than {parent_score:.6f}"
            ref_block = (
                "A higher-scoring solution exists near the baseline "
                f"(score {parent_score:.6f}); it proves the baseline has room to "
                "improve. Its implementation is:\n"
                f"{parent_code}\n\n"
                "Note: that higher-scoring solution uses a DIFFERENT algorithmic "
                "idea. Do NOT imitate its implementation. Your task is to improve "
                "the BASELINE within its own idea, and to beat that solution's "
                "score by being better, not by becoming it.\n"
            )
        else:  # has_ref and mode == "none", or no ref at all
            target_txt = f"score strictly higher than {base_score_txt}"
            ref_block = ""
        prompt_content = f'''{task_prompt}
I have a working baseline algorithm. The baseline is the algorithm you must improve; keep its algorithmic idea and structure.
Baseline algorithm score: {base_score_txt}
Baseline algorithm code:
{indi.to_code_without_docstring()}
{ref_block}Your task: create an improved version of the BASELINE algorithm by a SMALL LOCAL modification.
1. Keep the same algorithmic idea and structure as the baseline: change at most a few parameters, placement rules, or loop details. The result must still be recognizably the same algorithm family, just better.
2. Requirement: {target_txt}.
3. Do NOT switch to a completely different method family.
4. Evaluation time budget is about 15 seconds: heavy iterative optimizers (large scipy.optimize budgets, long loops) will TIME OUT and be scored as invalid. Prefer lightweight, constructive computations.
5. First, describe your new algorithm and main steps in one sentence. The description must be inside within boxed {{}}.
6. Next, implement the following Python function:
{str(temp_func)}
Do not give additional explanations.'''
        return prompt_content
